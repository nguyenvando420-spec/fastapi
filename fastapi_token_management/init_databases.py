import asyncio
import asyncpg
from app.core.config import settings

async def init_databases():
    # Connect to the default 'postgres' database
    conn = await asyncpg.connect(
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        database="postgres"
    )
    
    try:
        # Check and create admin_db
        exists_admin = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", "admin_db")
        if not exists_admin:
            print("Creating database: admin_db")
            await conn.execute("CREATE DATABASE admin_db")
        else:
            print("Database admin_db already exists.")

        # Check and create token_db
        exists_token = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", "token_db")
        if not exists_token:
            print("Creating database: token_db")
            await conn.execute("CREATE DATABASE token_db")
        else:
            print("Database token_db already exists.")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(init_databases())
