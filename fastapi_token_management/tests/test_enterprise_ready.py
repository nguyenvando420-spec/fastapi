import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings
from app.models.rbac import User, RevokedToken
from app.core.security import create_access_token, create_refresh_token
from sqlalchemy import select
import uuid

@pytest.mark.asyncio
async def test_auth_me(auth_token):
    """Test GET /auth/me returns current user info"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = await ac.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "username" in data
        assert "is_active" in data
        assert data["is_active"] is True

@pytest.mark.asyncio
async def test_refresh_token_flow(db_session):
    """Test the full access/refresh token rotation flow"""
    # 1. Create a user
    username = f"test_refresh_{uuid.uuid4().hex[:6]}"
    user = User(username=username, email=f"{username}@example.com", hashed_password="hashed", is_active=True)
    db_session.add(user)
    await db_session.commit()

    # 2. Issue refresh token
    refresh_token = create_refresh_token(data={"sub": username})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 3. Request new access token
        response = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # 4. Use new access token
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_resp = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == username

@pytest.mark.asyncio
async def test_logout_blacklist(auth_token, db_session):
    """Test that logout blacklists the token"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # 1. Verify token works
        resp = await ac.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        
        # 2. Logout
        logout_resp = await ac.post("/api/v1/auth/logout", headers=headers)
        assert logout_resp.status_code == 204
        
        # 3. Verify token is now blacklisted
        resp_after = await ac.get("/api/v1/auth/me", headers=headers)
        assert resp_after.status_code == 401
        assert "vô hiệu hóa" in resp_after.json()["detail"].lower() or "hết hạn" in resp_after.json()["detail"].lower()

@pytest.mark.asyncio
async def test_admin_system_regex_validation(auth_token):
    """Test that invalid system names are rejected by Pydantic and Service guard"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Invalid: starting with number
        resp1 = await ac.post("/api/v1/admin/systems", headers=headers, json={"name": "123system"})
        assert resp1.status_code == 422
        
        # Invalid: uppercase
        resp2 = await ac.post("/api/v1/admin/systems", headers=headers, json={"name": "System_Name"})
        assert resp2.status_code == 422
        
        # Valid
        resp3 = await ac.post("/api/v1/admin/systems", headers=headers, json={"name": "valid_system_123"})
        assert resp3.status_code == 201

@pytest.mark.asyncio
async def test_audit_stats_endpoint(auth_token):
    """Test that audit stats endpoint returns expected structure"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Trigger some action
        await ac.get("/api/v1/auth/me", headers=headers)
        
        # Check stats
        resp = await ac.get("/api/v1/audit/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_requests" in data
        assert "by_type" in data
        assert "top_users" in data

@pytest.mark.asyncio
async def test_token_batch_limit(auth_token):
    """Test that tokenize request size is limited"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Excessive data ( > 1000 )
        large_data = ["data"] * 1001
        resp = await ac.post("/api/v1/tokens/tokenize", headers=headers, json={
            "system_name": "sys",
            "domain_name": "dom",
            "data": large_data
        })
        assert resp.status_code == 422
        assert "Tối đa 1000 items" in resp.text

@pytest.mark.asyncio
async def test_detokenize_missing_tokens(auth_token, db_session):
    """Test that detokenize reports missing tokens correctly"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Create a system and domain first
        sys_resp = await ac.post("/api/v1/admin/systems", headers=headers, json={"name": "test_missing_sys"})
        assert sys_resp.status_code == 201
        sys_id = sys_resp.json()["id"]
        
        dom_resp = await ac.post("/api/v1/admin/domains", headers=headers, json={
            "name": "test_missing_dom",
            "system_id": sys_id
        })
        assert dom_resp.status_code == 201
        
        # Detokenize with random non-existent token
        non_existent_token = "non_existent_token_123"
        resp = await ac.post("/api/v1/tokens/detokenize", headers=headers, json={
            "system_name": "test_missing_sys",
            "domain_name": "test_missing_dom",
            "tokens": [non_existent_token]
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert non_existent_token in data["missing_tokens"]
        assert data["results"][non_existent_token] is None
