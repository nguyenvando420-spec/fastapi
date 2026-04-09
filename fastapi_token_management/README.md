# FastAPI Token Management Platform

Hệ thống quản lý Tokenization bảo mật cao sử dụng FastAPI, PostgreSQL (Dual-DB), Polars Engine và RBAC granular.

## 🚀 Hướng dẫn cài đặt và chạy ứng dụng

### 1. Yêu cầu hệ thống
- Python 3.9+
- PostgreSQL (Đang chạy tại localhost:5432)

### 2. Thiết lập môi trường
Tạo file `.env` tại thư mục gốc (đã có mã mẫu trong dự án):
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432

# Admin User mặc định (Tự động seeding)
FIRST_SUPERUSER=admin
FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin_password_123
```

### 3. Cài đặt Dependencies (Sử dụng Poetry)
```bash
# Cài đặt toàn bộ package (nếu chưa cài)
poetry install
```

### 4. Khởi tạo Database và Seeding Admin
Chạy script để tạo database (`admin_db`, `token_db`) và tạo tài khoản admin đầu tiên:
```bash
# Mở Docker daemon/OrbStack và chạy PostgreSQL
docker compose up -d

# Tạo các Database nếu chưa có
PYTHONPATH=. poetry run python3 init_databases.py

# Chạy database migrations qua Alembic
PYTHONPATH=. poetry run alembic upgrade head

# Seed tài khoản Admin và cấu hình quyền hạn
PYTHONPATH=. poetry run python3 seed_admin.py
```

### 5. Chạy ứng dụng
Sử dụng Granian server thông qua poetry:
```bash
PYTHONPATH=. poetry run python3 app/main.py
```

💡 Mẹo: Bạn cũng có thể dùng trực tiếp script `./run.sh` để tự động khởi động database và server cùng lúc.
Server sẽ lắng nghe tại: `http://localhost:8000`

## 🛠 Cách sử dụng (Quick Start)

1. **Truy cập Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
2. **Đăng nhập**: 
   - Gọi API `POST /api/v1/auth/login` với username `admin` và password `admin_password_123`.
   - Copy `access_token` trả về.
3. **Authorize**: Bấm nút "Authorize" trên cùng bên phải Swagger và dán token vào.
4. **Tokenize**: Sử dụng endpoint `POST /api/v1/tokens/tokenize` để bắt đầu mã hóa dữ liệu.

## 🧪 Kiểm thử (Testing)
Để chạy toàn bộ bộ test case:
```bash
PYTHONPATH=. venv/bin/python -m pytest tests/
```
