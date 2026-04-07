import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession

# override_get_db moved to conftest.py

@pytest.mark.asyncio
async def test_create_system_api(override_get_db, auth_token):
    """Test POST /api/v1/admin/systems"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "api_test_system", 
            "description": "System created via API test"
        }
        response = await ac.post("/api/v1/admin/systems", json=payload, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api_test_system"
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_create_domain_api(override_get_db, db_session, auth_token):
    """Test POST /api/v1/admin/domains"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    # 1. Setup: Tạo 1 system cha trước vì domain cần FK system_id
    from app.models.admin import System
    system = System(name="api_sys_parent", description="parent for domain")
    db_session.add(system)
    await db_session.flush()
    
    # Tạo schema vật lý để Domain có chỗ trú ngụ
    from sqlalchemy import text
    await db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    await db_session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "api_test_domain",
            "version": "v1.1",
            "system_id": str(system.id),
            "description": "Domain created via API test"
        }
        response = await ac.post("/api/v1/admin/domains", json=payload, headers=headers)
        
        # In case of failure, check detail
        if response.status_code != 201:
            print(f"Error detail: {response.json()}")
            
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api_test_domain"
        assert data["version"] == "v1.1"
        assert data["system_id"] == str(system.id)

@pytest.mark.asyncio
async def test_health_check_api():
    """Test endpoint GET / (health check)"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "online"
