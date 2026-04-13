import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import System, Domain
from sqlalchemy import text
from app.models.dynamic_token import create_dynamic_token_model

# override_get_db moved to conftest.py

@pytest.mark.asyncio
async def test_tokenize_bulk_api(override_get_db, db_session, token_db_session, auth_token):
    """Test POST /api/v1/tokens/tokenize"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    # 1. Setup: Tạo System và Domain
    from app.models.admin import System, Domain
    system = System(name="sys_token_test", description="system for token test")
    db_session.add(system)
    await db_session.flush()
    
    domain = Domain(name="dom_token_test", system_id=system.id, version_number=1, version="v1", status="active")
    db_session.add(domain)
    await db_session.flush()
    
    # Tạo schema và table vật lý TRÊN TOKEN DATABASE (tên bảng = domain_v{version_number})
    from sqlalchemy import text
    table_name = f"{domain.name}_v{domain.version_number}"  # e.g. "dom_token_test_v1"
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = f'CREATE TABLE IF NOT EXISTS "{system.name}"."{table_name}" (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
    await token_db_session.execute(text(table_ddl))
    await token_db_session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "system_name": "sys_token_test",
            "domain_name": "dom_token_test",
            "data": ["Secret1", "Secret2"]
        }
        response = await ac.post("/api/v1/tokens/tokenize", json=payload, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 2
        assert "Secret1" in data["results"]

@pytest.mark.asyncio
async def test_detokenize_bulk_api(override_get_db, db_session, token_db_session, auth_token):
    """Test POST /api/v1/tokens/detokenize"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    # 1. Setup giống tokenize nhưng có sẵn dữ liệu
    from app.models.admin import System, Domain
    system = System(name="sys_detok_test", description="system for detok test")
    db_session.add(system)
    await db_session.flush()
    domain = Domain(name="dom_detok_test", system_id=system.id, version_number=1, version="v1", status="active")
    db_session.add(domain)
    await db_session.flush()
    
    from sqlalchemy import text
    table_name = f"{domain.name}_v{domain.version_number}"  # e.g. "dom_detok_test_v1"
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = f'CREATE TABLE IF NOT EXISTS "{system.name}"."{table_name}" (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
    await token_db_session.execute(text(table_ddl))
    await token_db_session.commit()

    # Tokenize trước để có token
    from app.services.token_service import tokenize_data_service
    from app.schemas.token import TokenizeRequest
    from app.models.rbac import User
    
    # Tạo mock user để phục vụ audit log bên trong service
    mock_user = User(username="test_admin", email="test@admin.com", hashed_password="fake")
    db_session.add(mock_user)
    await db_session.flush()

    req = TokenizeRequest(system_name="sys_detok_test", domain_name="dom_detok_test", data=["Hello"])
    # Truyền cả 2 session cho service
    res = await tokenize_data_service(db_session, token_db_session, req, mock_user)
    token = list(res["results"].values())[0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "system_name": "sys_detok_test",
            "domain_name": "dom_detok_test",
            "tokens": [token]
        }
        response = await ac.post("/api/v1/tokens/detokenize", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["results"][token] == "Hello"


@pytest.mark.asyncio
async def test_tokenize_forbidden_no_permission(override_get_db, db_session, token_db_session):
    """Test: User không có permission → 403 Forbidden khi tokenize"""
    from app.models.rbac import User
    from app.core.security import create_access_token, get_password_hash
    import uuid

    # Tạo user không có bất kỳ role/permission nào
    username = f"noperm_{uuid.uuid4().hex[:8]}"
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()

    token_jwt = create_access_token(data={"sub": username})
    headers = {"Authorization": f"Bearer {token_jwt}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "system_name": "any_system",
            "domain_name": "any_domain",
            "data": ["SensitiveData"],
        }
        response = await ac.post("/api/v1/tokens/tokenize", json=payload, headers=headers)

        # User không có quyền → phải trả về 403
        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tokenize_allowed_via_group(override_get_db, db_session, token_db_session):
    """Test: User có permission QUA GROUP (không direct) → 201 Created khi tokenize"""
    from app.models.rbac import User, Role, Permission, Group
    from app.core.security import create_access_token, get_password_hash
    from app.models.admin import System, Domain
    import uuid

    uid = uuid.uuid4().hex[:8]

    # 1. Setup System + Domain trong admin DB
    system = System(name=f"sys_grp_{uid}", description="group permission test")
    db_session.add(system)
    await db_session.flush()

    domain = Domain(name=f"dom_grp_{uid}", system_id=system.id, version_number=1, version="v1", status="active")
    db_session.add(domain)
    await db_session.flush()

    # Tạo schema + table vật lý trên token DB (tên bảng = domain_v{version_number})
    table_name = f"{domain.name}_v{domain.version_number}"  # e.g. "dom_grp_xxx_v1"
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = (
        f'CREATE TABLE IF NOT EXISTS "{system.name}"."{table_name}" '
        f'(id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, '
        f'encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
    )
    await token_db_session.execute(text(table_ddl))
    await token_db_session.commit()

    # 2. Tạo Permission cho resource cụ thể
    resource = f"{system.name}:{domain.name}"
    perm = Permission(resource=resource, action="write")
    db_session.add(perm)

    # 3. Tạo Role gán Permission này
    role = Role(name=f"role_grp_{uid}", permissions=[perm])
    db_session.add(role)

    # 4. Tạo Group gán Role này
    group = Group(name=f"grp_{uid}", roles=[role])
    db_session.add(group)

    # 5. Tạo User KHÔNG có direct role — chỉ thuộc Group
    username = f"grpuser_{uid}"
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("password123"),
        groups=[group],  # quyền chỉ đến từ group
    )
    db_session.add(user)
    await db_session.commit()

    token_jwt = create_access_token(data={"sub": username})
    headers = {"Authorization": f"Bearer {token_jwt}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "system_name": system.name,
            "domain_name": domain.name,
            "data": ["GroupSecret"],
        }
        response = await ac.post("/api/v1/tokens/tokenize", json=payload, headers=headers)

        # User có quyền qua Group → phải pass
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["count"] == 1
        assert "GroupSecret" in data["results"]
