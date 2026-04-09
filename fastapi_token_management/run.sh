#!/bin/bash

echo "🚀 Bắt đầu khởi động PostgreSQL database qua Docker Compose..."
docker compose up -d

echo "⏳ Đang đợi database khởi động (5 giây)..."
sleep 5

# Sửa lỗi macOS xcode-select: Failed to locate 'python' bằng cách loại bỏ đường dẫn /usr/local/bin/python
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "📦 Đang cài đặt/kiểm tra thư viện bằng Poetry..."
poetry install

echo "🛠 Đang khởi tạo Database (nếu chưa có)..."
PYTHONPATH=. poetry run python3 init_databases.py

echo "🔄 Đang chạy Alembic Database Migrations..."
PYTHONPATH=. poetry run alembic upgrade head

echo "🌱 Đang chạy Database Seeder (nếu cần)..."
PYTHONPATH=. poetry run python3 seed_admin.py

echo "🚀 Đang khởi động FastAPI Server..."
PYTHONPATH=. poetry run python3 app/main.py
