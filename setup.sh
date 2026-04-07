#!/bin/bash

echo "Đang khởi tạo dự án fastapi_token_management..."

# Tạo thư mục gốc dự án
mkdir -p fastapi_token_management
cd fastapi_token_management

# Tạo các thư mục con
mkdir -p app/core app/api/v1 app/models app/schemas app/services app/data_processing tests alembic

# Tạo các file cốt lõi
touch app/__init__.py app/main.py
touch app/core/__init__.py app/core/config.py app/core/database.py app/core/security.py app/core/exceptions.py

# Tạo các file API (Controllers)
touch app/api/__init__.py app/api/dependencies.py 
touch app/api/v1/__init__.py app/api/v1/admin.py app/api/v1/auth.py app/api/v1/rbac.py app/api/v1/token.py

# Tạo các file Database Models
touch app/models/__init__.py app/models/base.py app/models/rbac.py app/models/admin.py app/models/dynamic_token.py

# Tạo các file Pydantic Schemas
touch app/schemas/__init__.py app/schemas/admin.py app/schemas/rbac.py app/schemas/token.py

# Tạo các file Business Logic Services
touch app/services/__init__.py app/services/admin_service.py app/services/rbac_service.py app/services/token_service.py

# Tạo các file Data Processing cho Polars
touch app/data_processing/__init__.py app/data_processing/polars_engine.py

# Tạo các file phụ trợ
touch .env README.md alembic.ini
touch tests/conftest.py

echo "✅ Đã tạo xong cấu trúc thư mục và file trắng cho dự án!"
echo ""
echo "👉 HƯỚNG DẪN TIẾP THEO:"
echo "1. Cd vào thư mục: cd fastapi_token_management"
echo "2. Tạo môi trường ảo: python3 -m venv venv"
echo "3. Kích hoạt môi trường: source venv/bin/activate"
echo "4. Cài đặt thư viện: pip install fastapi pydantic pydantic-settings granian sqlalchemy alembic asyncpg psycopg2-binary polars adbc-driver-postgresql pyarrow cryptography passlib python-jose httpx pytest pytest-asyncio"
echo "5. Khởi tạo alembic: alembic init alembic (Lưu ý: Bạn có thể bỏ qua nếu đã copy file alembic.ini tự tạo)"
