import asyncio
from sqlalchemy import select, or_
from sqlalchemy.orm import aliased
from app.models.rbac import User, Role, Permission, Group

UserAlias = aliased(User)
stmt = (
    select(Permission)
    .join(Permission.roles)
    .outerjoin(Role.users)
    .outerjoin(Role.groups)
    .outerjoin(Group.users.of_type(UserAlias))
    .where(
        or_(
            User.id == '123e4567-e89b-12d3-a456-426614174000',
            UserAlias.id == '123e4567-e89b-12d3-a456-426614174000'
        ),
        Permission.resource.in_(['sys:dom', '*', 'sys:*']),
        Permission.action.in_(['write', '*'])
    )
)
print(stmt)
