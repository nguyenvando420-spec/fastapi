import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import AdminSessionLocal
from app.models.rbac import User, Role, Permission
from app.core.security import get_password_hash
from app.core.config import settings

async def seed_admin():
    async with AdminSessionLocal() as session:
        # 1. Get or Create Superuser Role
        role_stmt = select(Role).options(selectinload(Role.permissions)).where(Role.name == "superuser")
        role = (await session.execute(role_stmt)).scalar_one_or_none()
        if not role:
            print("Creating superuser role...")
            role = Role(name="superuser", description="Full system access")
            session.add(role)
            await session.flush()
            # Re-fetch with permissions if just created
            role_stmt = select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id)
            role = (await session.execute(role_stmt)).scalar_one()

        # 2. Get or Create Admin User (with is_superuser=True)
        user_stmt = select(User).options(selectinload(User.roles)).where(User.username == settings.FIRST_SUPERUSER)
        user = (await session.execute(user_stmt)).scalar_one_or_none()
        if not user:
            print(f"Creating admin user: {settings.FIRST_SUPERUSER}")
            user = User(
                username=settings.FIRST_SUPERUSER,
                email=settings.FIRST_SUPERUSER_EMAIL,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_active=True,
                is_superuser=True,  # Superuser bypass mọi permission check
                auth_source="local",
                display_name="System Administrator"
            )
            session.add(user)
            await session.flush()
            # Re-fetch with roles if just created
            user_stmt = select(User).options(selectinload(User.roles)).where(User.id == user.id)
            user = (await session.execute(user_stmt)).scalar_one()
        else:
            # Đảm bảo admin luôn là superuser
            if not user.is_superuser:
                user.is_superuser = True
                print(f"Updated '{user.username}' to is_superuser=True")
            
        if role not in user.roles:
            print(f"Assigning 'superuser' role to user '{user.username}'")
            user.roles.append(role)
        
        # 3. Handle Permissions (bao gồm cả admin:* permissions cho quản trị)
        permissions_to_create = [
            ("*", "*", "Full access to all resources and actions"),
            ("admin:users", "create", "Create new users"),
            ("admin:users", "read", "View user list and details"),
            ("admin:users", "write", "Modify user roles, groups, and status"),
            ("admin:roles", "create", "Create new roles"),
            ("admin:roles", "read", "View role list"),
            ("admin:roles", "write", "Modify role permissions"),
            ("admin:groups", "create", "Create new groups"),
            ("admin:groups", "read", "View group list"),
            ("admin:groups", "write", "Modify group members and roles"),
            ("admin:permissions", "create", "Create new permissions"),
            ("admin:permissions", "read", "View permission list"),
        ]
        
        for res, act, desc in permissions_to_create:
            perm_stmt = select(Permission).where(
                (Permission.resource == res) & (Permission.action == act)
            )
            perm = (await session.execute(perm_stmt)).scalar_one_or_none()
            if not perm:
                print(f"Creating permission {res}:{act}")
                perm = Permission(resource=res, action=act, description=desc)
                session.add(perm)
                await session.flush()
            
            if perm not in role.permissions:
                print(f"Assigning permission {res}:{act} to role 'superuser'")
                role.permissions.append(perm)

        await session.commit()
        print("Seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_admin())
