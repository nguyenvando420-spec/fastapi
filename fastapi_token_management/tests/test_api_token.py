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
    
    domain = Domain(name="dom_token_test", system_id=system.id, version="v1")
    db_session.add(domain)
    await db_session.flush()
    
    # Tạo schema và table vật lý TRÊN TOKEN DATABASE
    from sqlalchemy import text
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = f'CREATE TABLE IF NOT EXISTS "{system.name}"."{domain.name}" (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
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
    domain = Domain(name="dom_detok_test", system_id=system.id, version="v1")
    db_session.add(domain)
    await db_session.flush()
    
    from sqlalchemy import text
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = f'CREATE TABLE IF NOT EXISTS "{system.name}"."{domain.name}" (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
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
