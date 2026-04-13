import asyncio
import re
import polars as pl
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from fastapi import HTTPException
from app.models.admin import System, Domain, DOMAIN_STATUS_ACTIVE, DOMAIN_STATUS_ROTATED, DOMAIN_STATUS_DEPRECATED
from app.models.rbac import User
from app.data_processing.polars_engine import tokenize_dataframe, detokenize_dataframe, batch_insert_to_db
from app.schemas.token import TokenizeRequest, DeTokenizeRequest, TokenDomainStats

import time
from app.services.audit_service import create_audit_log


def _make_table_name(domain_name: str, version_number: int) -> str:
    """
    Tạo tên bảng an toàn từ domain name và version number.
    Ví dụ: domain='customers', version_number=2 → 'customers_v2'
    """
    return f"{domain_name}_v{version_number}"


def _make_table_name_from_version_str(domain_name: str, version: str) -> str:
    """
    Backward compat: tạo tên bảng từ version string.
    Ví dụ: domain='customers', version='v1' → 'customers_v1'
    """
    safe_version = re.sub(r'[^a-zA-Z0-9]', '_', version)
    return f"{domain_name}_{safe_version}"


async def _get_active_domain(
    admin_session: AsyncSession,
    system_name: str,
    domain_name: str,
) -> Domain:
    """
    Lấy Domain version active mới nhất cho tokenize.
    Chỉ version có status='active' mới được dùng để tokenize mới.
    """
    stmt = (
        select(Domain)
        .join(System)
        .where(
            System.name == system_name,
            System.is_active == True,
            Domain.name == domain_name,
            Domain.is_active == True,
            Domain.status == DOMAIN_STATUS_ACTIVE,
        )
        .order_by(desc(Domain.version_number))
        .limit(1)
    )
    result = await admin_session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_detokenizable_domains(
    admin_session: AsyncSession,
    system_name: str,
    domain_name: str,
) -> List[Domain]:
    """
    Lấy tất cả version có thể detokenize (status: active hoặc rotated).
    Version deprecated sẽ bị bỏ qua.
    Tham khảo HashiCorp Vault: rotated key vẫn decrypt được dữ liệu cũ.
    """
    stmt = (
        select(Domain)
        .join(System)
        .where(
            System.name == system_name,
            System.is_active == True,
            Domain.name == domain_name,
            Domain.is_active == True,
            Domain.status.in_([DOMAIN_STATUS_ACTIVE, DOMAIN_STATUS_ROTATED]),
        )
        .order_by(desc(Domain.version_number))
    )
    result = await admin_session.execute(stmt)
    return result.scalars().all()


async def tokenize_data_service(
    admin_session: AsyncSession,
    token_session: AsyncSession,
    req: TokenizeRequest,
    current_user: User,
):
    """
    Xử lý Tokenize hàng loạt kèm Audit Log.
    Luôn dùng version active mới nhất (tham khảo Vault: encrypt luôn dùng latest key).
    """
    start_time = time.time()
    status_str = "success"
    detail = None
    version_str = None

    try:
        # 1. Lấy Domain version active mới nhất
        domain = await _get_active_domain(admin_session, req.system_name, req.domain_name)

        if not domain:
            status_str = "fail"
            detail = f"Không tìm thấy Domain '{req.domain_name}' (active) trong System '{req.system_name}'."
            raise HTTPException(status_code=404, detail=detail)

        version_str = domain.version

        # 2. Xử lý qua Polars Engine
        data_column = "data"
        df = pl.DataFrame({data_column: req.data})
        df_tokenized = tokenize_dataframe(
            df, req.system_name, req.domain_name, version=domain.version, data_column=data_column
        )

        results_mapping = {
            row[data_column]: row["token"]
            for row in df_tokenized.select([data_column, "token"]).to_dicts()
        }

        # 3. Idempotency: bỏ qua token đã tồn tại trong DB
        from app.models.dynamic_token import create_dynamic_token_model
        token_table_name = _make_table_name(domain.name, domain.version_number)
        DynamicTokenModel = create_dynamic_token_model(
            schema_name=req.system_name, table_name=token_table_name
        )

        all_tokens = list(results_mapping.values())
        stmt_check = select(DynamicTokenModel.token).where(DynamicTokenModel.token.in_(all_tokens))
        result_check = await token_session.execute(stmt_check)
        existing_tokens = set(result_check.scalars().all())

        df_new = df_tokenized.filter(~pl.col("token").is_in(list(existing_tokens)))

        # 4. Ghi vào DB (Batch Insert)
        if not df_new.is_empty():
            df_for_db = df_new.drop(data_column)
            await asyncio.to_thread(
                batch_insert_to_db,
                df_for_db,
                schema_name=req.system_name,
                table_name=token_table_name,
                engine=token_session.bind,
            )

        return {
            "message": "Tokenization completed successfully",
            "count": df_tokenized.shape[0],
            "results": results_mapping,
        }

    except Exception as e:
        if status_str == "success":
            status_str = "fail"
            detail = str(e)
        raise e

    finally:
        duration = time.time() - start_time
        await create_audit_log(
            session=admin_session,
            request_type="tokenize",
            system=req.system_name,
            domain=req.domain_name,
            user=current_user.username,
            version=version_str,
            duration=duration,
            total_token=len(req.data),
            auth_status="allowed",
            status=status_str,
            detail=detail,
        )


async def detokenize_data_service(
    admin_session: AsyncSession,
    token_session: AsyncSession,
    req: DeTokenizeRequest,
    current_user: User,
):
    """
    Xử lý De-tokenize hàng loạt kèm Audit Log.
    Tìm kiếm trên TẤT CẢ version có thể detokenize (active + rotated).
    Tham khảo HashiCorp Vault: rotated key vẫn decrypt được dữ liệu cũ.
    """
    start_time = time.time()
    status_str = "success"
    detail = None
    version_str = None

    try:
        # 1. Lấy tất cả domain version có thể detokenize
        domains = await _get_detokenizable_domains(admin_session, req.system_name, req.domain_name)

        if not domains:
            status_str = "fail"
            detail = f"Không tìm thấy Domain '{req.domain_name}' trong System '{req.system_name}'."
            raise HTTPException(status_code=404, detail=detail)

        version_str = domains[0].version  # Latest version for audit

        # 2. Tìm token trên tất cả các version (từ mới nhất trước)
        from app.models.dynamic_token import create_dynamic_token_model
        remaining_tokens = set(req.tokens)
        all_db_results = []

        for domain in domains:
            if not remaining_tokens:
                break  # Đã tìm hết

            token_table_name = _make_table_name(domain.name, domain.version_number)
            DynamicTokenModel = create_dynamic_token_model(
                schema_name=req.system_name, table_name=token_table_name
            )

            stmt_data = select(DynamicTokenModel).where(
                DynamicTokenModel.token.in_(list(remaining_tokens))
            )
            result_data = await token_session.execute(stmt_data)
            db_results = result_data.scalars().all()

            if db_results:
                all_db_results.extend(db_results)
                found_in_version = {r.token for r in db_results}
                remaining_tokens -= found_in_version

        # 3. Xác định tokens không tìm thấy
        missing_tokens = [t for t in req.tokens if t in remaining_tokens]

        if not all_db_results:
            return {"results": {t: None for t in req.tokens}, "missing_tokens": missing_tokens}

        # 4. Giải mã
        records = [
            {"token": r.token, "encrypt_dek_data": r.encrypt_dek_data, "kek": r.kek}
            for r in all_db_results
        ]
        df_enc = pl.DataFrame(records)
        df_result = detokenize_dataframe(df_enc)

        results_mapping = dict(zip(df_result["token"].to_list(), df_result["decrypted_data"].to_list()))
        # Bổ sung None cho tokens không tìm thấy
        full_result = {t: results_mapping.get(t) for t in req.tokens}

        return {"results": full_result, "missing_tokens": missing_tokens}

    except Exception as e:
        if status_str == "success":
            status_str = "fail"
            detail = str(e)
        raise e

    finally:
        duration = time.time() - start_time
        await create_audit_log(
            session=admin_session,
            request_type="detokenize",
            system=req.system_name,
            domain=req.domain_name,
            user=current_user.username,
            version=version_str,
            duration=duration,
            total_token=len(req.tokens),
            auth_status="allowed",
            status=status_str,
            detail=detail,
        )


async def get_token_stats(
    admin_session: AsyncSession,
    token_session: AsyncSession,
    system_name: Optional[str] = None,
) -> List[TokenDomainStats]:
    """
    Thống kê số lượng token trong từng domain/version.
    Query trực tiếp từ token_session vào các bảng động.
    """
    # Lấy danh sách active domains (tất cả version)
    stmt = select(Domain).join(System).where(Domain.is_active == True, System.is_active == True)
    if system_name:
        stmt = stmt.where(System.name == system_name)

    result = await admin_session.execute(stmt)
    domains = result.scalars().all()

    stats = []
    for domain in domains:
        system_result = await admin_session.execute(
            select(System).where(System.id == domain.system_id)
        )
        sys = system_result.scalar_one_or_none()
        if not sys:
            continue

        table_name = _make_table_name(domain.name, domain.version_number)
        try:
            from app.models.dynamic_token import create_dynamic_token_model
            DynamicModel = create_dynamic_token_model(
                schema_name=sys.name, table_name=table_name
            )
            count_result = await token_session.execute(
                select(func.count(DynamicModel.id))
            )
            count = count_result.scalar_one()
        except Exception:
            count = 0

        stats.append(
            TokenDomainStats(
                system=sys.name,
                domain=domain.name,
                version=domain.version,
                token_count=count,
            )
        )

    return stats
