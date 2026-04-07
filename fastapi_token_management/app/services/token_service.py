import asyncio
import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.admin import System, Domain
from app.models.rbac import User
from app.data_processing.polars_engine import tokenize_dataframe, detokenize_dataframe, batch_insert_to_db
from app.schemas.token import TokenizeRequest, DeTokenizeRequest

import time
from app.services.audit_service import create_audit_log

async def tokenize_data_service(admin_session: AsyncSession, token_session: AsyncSession, req: TokenizeRequest, current_user: User):
    """
    Xử lý Tokenize số lượng lớn kèm Audit Log. 
    Sử dụng admin_session cho metadata và audit, token_session cho token storage.
    """
    start_time = time.time()
    status_str = "success"
    detail = None
    version_str = None
    
    try:
        # 1. Tìm thông tin Domain theo System Name
        stmt = select(Domain).join(System).where(
            System.name == req.system_name,
            Domain.name == req.domain_name
        )
        result = await admin_session.execute(stmt)
        domain = result.scalars().first()
        
        if not domain:
            status_str = "fail"
            detail = f"Không tìm thấy Domain '{req.domain_name}'"
            raise HTTPException(status_code=404, detail=detail)

        version_str = domain.version

        # 2. Xử lý qua Polars
        data_column = "data"
        df = pl.DataFrame({data_column: req.data})
        df_tokenized = tokenize_dataframe(
            df, 
            req.system_name, 
            req.domain_name, 
            version=domain.version, 
            data_column=data_column
        )

        # Trích xuất mapping Token cho người dùng
        results_mapping = { 
            row[data_column]: row["token"] 
            for row in df_tokenized.select([data_column, "token"]).to_dicts() 
        }

        # --- IDEMPOTENCY: Kiểm tra xem Token đã tồn tại trong DB chưa ---
        from app.models.dynamic_token import create_dynamic_token_model
        DynamicTokenModel = create_dynamic_token_model(schema_name=req.system_name, table_name=req.domain_name)
        
        all_tokens = list(results_mapping.values())
        stmt_check = select(DynamicTokenModel.token).where(DynamicTokenModel.token.in_(all_tokens))
        result_check = await token_session.execute(stmt_check)
        existing_tokens = set(result_check.scalars().all())

        df_new = df_tokenized.filter(~pl.col("token").is_in(list(existing_tokens)))

        # 3. Ghi vào database (Batch Insert)
        if not df_new.is_empty():
            df_for_db = df_new.drop(data_column)
            # Truyền token_session.bind (engine) cho batch insert
            from app.core.database import token_engine
            await asyncio.to_thread(batch_insert_to_db, df_for_db, schema_name=req.system_name, table_name=req.domain_name, engine=token_engine)
        
        return {
            "message": "Tokenization completed successfully", 
            "count": df_tokenized.shape[0],
            "results": results_mapping
        }
    except Exception as e:
        if status_str == "success": # Nếu chưa set fail ở trên
            status_str = "fail"
            detail = str(e)
        raise e
    finally:
        # Ghi Audit Log vào Admin Database
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
            detail=detail
        )

async def detokenize_data_service(admin_session: AsyncSession, token_session: AsyncSession, req: DeTokenizeRequest, current_user: User):
    """
    Xử lý De-tokenize kèm Audit Log.
    Sử dụng admin_session cho metadata/audit, token_session cho token storage lookup.
    """
    start_time = time.time()
    status_str = "success"
    detail = None
    version_str = None
    
    try:
        # 1. Kiểm tra Domain tồn tại
        stmt = select(Domain).join(System).where(
            System.name == req.system_name,
            Domain.name == req.domain_name
        )
        result = await admin_session.execute(stmt)
        domain = result.scalars().first()
        
        if not domain:
            status_str = "fail"
            detail = "Domain or System not found"
            raise HTTPException(status_code=404, detail=detail)

        version_str = domain.version

        # 2. Lấy metadata của bảng động để query
        from app.models.dynamic_token import create_dynamic_token_model
        DynamicTokenModel = create_dynamic_token_model(schema_name=req.system_name, table_name=req.domain_name)
        
        stmt_data = select(DynamicTokenModel).where(DynamicTokenModel.token.in_(req.tokens))
        result_data = await token_session.execute(stmt_data)
        db_results = result_data.scalars().all()
        
        if not db_results:
            return {t: None for t in req.tokens}

        records = [
            {
                "token": r.token,
                "encrypt_dek_data": r.encrypt_dek_data,
                "kek": r.kek
            } 
            for r in db_results
        ]
        df_enc = pl.DataFrame(records)
        
        df_result = detokenize_dataframe(df_enc)
        
        decrypted_list = df_result["decrypted_data"].to_list()
        results_mapping = dict(zip(df_result["token"].to_list(), decrypted_list))
        
        return {t: results_mapping.get(t) for t in req.tokens}
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
            detail=detail
        )
