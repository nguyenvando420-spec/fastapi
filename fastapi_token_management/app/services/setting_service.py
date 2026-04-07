from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.setting import SystemSetting
from typing import Optional

async def get_setting(session: AsyncSession, key: str, default: str = None) -> str:
    """
    Lấy giá trị cấu hình từ database. Nếu chưa có, trả về default.
    """
    stmt = select(SystemSetting).where(SystemSetting.key == key)
    result = await session.execute(stmt)
    setting = result.scalars().first()
    return setting.value if setting else default

async def set_setting(session: AsyncSession, key: str, value: str, description: str = None):
    """
    Cập nhật hoặc tạo mới cấu hình.
    """
    stmt = select(SystemSetting).where(SystemSetting.key == key)
    result = await session.execute(stmt)
    setting = result.scalars().first()
    
    if setting:
        setting.value = value
        if description:
            setting.description = description
    else:
        setting = SystemSetting(key=key, value=value, description=description)
        session.add(setting)
    
    await session.commit()
    return setting
