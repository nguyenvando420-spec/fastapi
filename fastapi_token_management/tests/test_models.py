import pytest
from app.models.rbac import User, Role, Group, Permission, user_role, role_permission, group_user, group_role
from app.models.admin import System, Domain
from app.models.dynamic_token import create_dynamic_token_model

@pytest.mark.asyncio
async def test_create_system_and_domain(db_session):
    """Test chức năng tạo System và Domain của Admin Dictionary"""
    # Create System
    system = System(name="banking_schema", description="System for core banking")
    db_session.add(system)
    await db_session.flush() # Flush đẩy ID về mà không cần tắt giao dịch transaction
    
    # Create Domain liên kết với System
    domain = Domain(name="card_tokens", system_id=system.id, version="v1.0")
    db_session.add(domain)
    await db_session.flush()
    
    assert domain.id is not None
    assert system.name == "banking_schema"
    # Kiểm tra back_populates
    assert domain.system.name == "banking_schema"


@pytest.mark.asyncio
async def test_rbac_user_and_roles(db_session):
    """Test chức năng gán Role cho User (N-N relationship)"""
    new_role = Role(name="admin_role", description="Quản trị viên hệ thống")
    new_user = User(username="admin_user", email="admin@local.com", hashed_password="hashed_pass")
    
    # Gán Role cho User
    new_user.roles.append(new_role)
    
    db_session.add(new_role)
    db_session.add(new_user)
    await db_session.flush()
    
    assert new_user.id is not None
    assert len(new_user.roles) == 1
    assert new_user.roles[0].name == "admin_role"


@pytest.mark.asyncio
async def test_dynamic_token_model_factory():
    """Test chức năng sinh Class SQLAlchemy động không cần Query DB"""
    table_name = "card_tokens_v1"
    schema_name = "banking_schema"
    
    # Sinh runtime class
    DynamicTokenModel = create_dynamic_token_model(schema_name=schema_name, table_name=table_name)
    
    # Kiểm tra metadata config sqlalchemy
    assert DynamicTokenModel.__tablename__ == table_name
    assert DynamicTokenModel.__table_args__['schema'] == schema_name
    
    # Đảm bảo class được tạo độc lập trong memory python
    instance = DynamicTokenModel(
        token="token_string_abc123",
        encrypt_dek_data="crypted_data",
        kek="key_enc_key"
    )
    
    assert instance.token == "token_string_abc123"

@pytest.mark.asyncio
async def test_admin_cascade_delete(db_session):
    """Test delete System sẽ tự động xóa các Domain liên quan (cascade)"""
    system = System(name="del_sys", description="System to be deleted")
    db_session.add(system)
    await db_session.flush()
    
    domain = Domain(name="del_dom", system_id=system.id)
    db_session.add(domain)
    await db_session.commit() # Commit để thực sự ghi xuống database
    
    # Refresh để chắc chắn nó tồn tại
    from sqlalchemy import select
    res = await db_session.execute(select(Domain).where(Domain.name == "del_dom"))
    assert res.scalar_one_or_none() is not None
    
    # Xóa System
    await db_session.delete(system)
    await db_session.commit()
    
    # Kiểm tra Domain bị xóa theo
    res = await db_session.execute(select(Domain).where(Domain.name == "del_dom"))
    assert res.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_rbac_full_relations(db_session):
    """Test relationship N-N phức tạp: User -> Group -> Role -> Permission"""
    user = User(username="test_rbac", email="rbac@test.com", hashed_password="pass")
    group = Group(name="test_group")
    role = Role(name="test_role")
    permission = Permission(resource="admin:*", action="*")
    
    # Thiết lập quan hệ
    user.groups.append(group)
    group.roles.append(role)
    role.permissions.append(permission)
    
    db_session.add_all([user, group, role, permission])
    await db_session.flush()
    
    # Kiểm tra truy xuất ngược qua các cấp
    assert user.groups[0].name == "test_group"
    assert user.groups[0].roles[0].name == "test_role"
    assert user.groups[0].roles[0].permissions[0].resource == "admin:*"
    
@pytest.mark.asyncio
async def test_basemodel_timestamps(db_session):
    """Đảm bảo created_at và updated_at tự sinh tự động"""
    system = System(name="time_test")
    db_session.add(system)
    await db_session.flush()
    
    assert system.created_at is not None
    assert system.updated_at is not None
    assert system.id is not None
