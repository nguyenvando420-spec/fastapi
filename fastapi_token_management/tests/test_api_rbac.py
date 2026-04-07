import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
import uuid

@pytest.mark.asyncio
async def test_rbac_user_management_api(override_get_db, auth_token):
    """Test RBAC User creation and Role assignment via API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a User (Admin only now)
        username = f"api_user_{uuid.uuid4().hex[:8]}"
        user_payload = {
            "username": username,
            "email": f"{username}@test.com",
            "password": "securepassword123"
        }
        response = await ac.post("/api/v1/rbac/users", json=user_payload, headers=headers)
        assert response.status_code == 201
        user_data = response.json()
        user_id = user_data["id"]

        # 2. Create a Role
        role_name = f"api_role_{uuid.uuid4().hex[:8]}"
        role_payload = {"name": role_name, "description": "Role created via API"}
        response = await ac.post("/api/v1/rbac/roles", json=role_payload, headers=headers)
        assert response.status_code == 201
        role_id = response.json()["id"]

        # 3. Assign Role to User
        assign_payload = {"role_id": role_id}
        response = await ac.post(f"/api/v1/rbac/users/{user_id}/roles", json=assign_payload, headers=headers)
        assert response.status_code == 200
        assert "assigned" in response.json()["message"]

@pytest.mark.asyncio
async def test_rbac_permission_management_api(override_get_db, auth_token):
    """Test RBAC Permission creation and Role-Permission assignment via API"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a Permission
        perm_payload = {"resource": "test:resource", "action": "read"}
        response = await ac.post("/api/v1/rbac/permissions", json=perm_payload, headers=headers)
        assert response.status_code == 201
        perm_id = response.json()["id"]

        # 2. Create a Role
        role_name = f"perm_role_{uuid.uuid4().hex[:8]}"
        role_payload = {"name": role_name}
        response = await ac.post("/api/v1/rbac/roles", json=role_payload, headers=headers)
        assert response.status_code == 201
        role_id = response.json()["id"]

        # 3. Assign Permission to Role
        assign_payload = {"permission_id": perm_id}
        response = await ac.post(f"/api/v1/rbac/roles/{role_id}/permissions", json=assign_payload, headers=headers)
        assert response.status_code == 200
        assert "assigned" in response.json()["message"]

@pytest.mark.asyncio
async def test_rbac_unauthorized_access(override_get_db):
    """Test RBAC APIs without token (Should fail)"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Try to create a role without token
        response = await ac.post("/api/v1/rbac/roles", json={"name": "fail_role"})
        # Should be 401 Unauthorized
        assert response.status_code == 401
