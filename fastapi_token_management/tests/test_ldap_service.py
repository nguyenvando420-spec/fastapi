import pytest
from unittest.mock import MagicMock, patch
from app.services.ldap_service import authenticate_ldap, sync_ldap_user_to_local, sync_ldap_groups
from app.models.rbac import User, Group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

@pytest.mark.asyncio
async def test_ldap_authenticate_mock():
    """Test LDAP authentication logic with a mocked ldap3 connection"""
    
    # Mock the return value of _ldap_authenticate_sync
    mock_user_info = {
        "dn": "uid=testuser,dc=example,dc=com",
        "username": "testuser",
        "email": "testuser@example.com",
        "display_name": "Test User",
        "groups": ["cn=devs,ou=groups,dc=example,dc=com"]
    }
    
    with patch("app.services.ldap_service.run_in_threadpool") as mock_run:
        mock_run.return_value = mock_user_info
        
        result = await authenticate_ldap("testuser", "password123")
        
        assert result == mock_user_info
        mock_run.assert_called_once()

@pytest.mark.asyncio
async def test_sync_ldap_user_to_local(db_session: AsyncSession):
    """Test syncing an LDAP user to the local database"""
    ldap_info = {
        "username": "ldap_sync_user",
        "email": "ldap@sync.com",
        "dn": "uid=ldap_sync_user,dc=example,dc=com",
        "display_name": "LDAP Sync User"
    }
    
    user = await sync_ldap_user_to_local(db_session, ldap_info)
    
    assert user.username == "ldap_sync_user"
    assert user.auth_source == "ldap"
    assert user.display_name == "LDAP Sync User"
    
    # Verify in DB
    stmt = select(User).where(User.username == "ldap_sync_user")
    db_user = (await db_session.execute(stmt)).scalar_one()
    assert db_user.auth_source == "ldap"

@pytest.mark.asyncio
async def test_sync_ldap_groups(db_session: AsyncSession):
    """Test syncing LDAP groups to RBAC groups"""
    from sqlalchemy.orm import selectinload
    
    # Setup a user
    user = User(
        username="group_sync_user",
        email="groupsync@test.com",
        hashed_password="...",
        auth_source="ldap"
    )
    db_session.add(user)
    await db_session.commit()
    
    # Fetch with groups pre-loaded
    stmt = select(User).options(selectinload(User.groups)).where(User.username == "group_sync_user")
    user = (await db_session.execute(stmt)).scalar_one()
    
    ldap_groups = ["cn=Developers,ou=groups,dc=example,dc=com", "cn=Admins,ou=groups,dc=example,dc=com"]
    
    # Mock settings to ensure LDAP_SYNC_GROUPS is True
    with patch("app.services.ldap_service.settings") as mock_settings:
        mock_settings.LDAP_SYNC_GROUPS = True
        
        await sync_ldap_groups(db_session, user, ldap_groups)
        
        # Refresh user to see groups
        stmt = select(User).where(User.id == user.id)
        result = await db_session.execute(stmt)
        updated_user = result.unique().scalar_one()
        
        group_names = [g.name for g in updated_user.groups]
        assert "Developers" in group_names
        assert "Admins" in group_names
        
        # Verify groups are marked as synced
        stmt = select(Group).where(Group.name == "Developers")
        dev_group = (await db_session.execute(stmt)).scalar_one()
        assert dev_group.is_ldap_synced is True
        assert dev_group.ldap_dn == "cn=Developers,ou=groups,dc=example,dc=com"
