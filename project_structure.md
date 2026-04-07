# Cấu trúc dự án FastAPI Token Management

```text
fastapi_token_management/
├── alembic/                    # Quản lý database migrations
├── alembic.ini                 # Cấu hình alembic
├── app/                        # Mã nguồn chính của ứng dụng
│   ├── __init__.py
│   ├── main.py                 # Entry point của FastAPI application
│   ├── core/                   # Cấu hình cốt lõi & Singletons
│   │   ├── config.py           # Quản lý env variables (Pydantic BaseSettings)
│   │   ├── database.py         # Cấu hình SQLAlchemy, Engine & Connection Pool 
│   │   ├── security.py         # Tiện ích mã hoá (HMAC, JWT, Encryption/Decryption KEK/DEK)
│   │   └── exceptions.py       # Xử lý Global Errors/Exceptions
│   ├── api/                    # Application Programming Interface (Controllers layer)
│   │   ├── dependencies.py     # Setup FastAPI Depends: get_db_session, get_current_user...
│   │   └── v1/                 # API Version 1
│   │       ├── admin.py        # API cho Admin (tạo schema system, tạo table domain)
│   │       ├── auth.py         # API Đăng nhập, cấp xác thực
│   │       ├── rbac.py         # API Quản lý User, Role, Group, Permission
│   │       └── token.py        # API Tokenize & Detokenize
│   ├── models/                 # SQLAlchemy ORM Models (Data layer)
│   │   ├── base.py             # Declarative Base
│   │   ├── rbac.py             # Chứa 5 bảng: User, Role, Permission, Group và các m-n mapping tables
│   │   ├── admin.py            # Chứa các bảng dictionary tracking các System (Schema) và Domain (Table)
│   │   └── dynamic_token.py    # Function/Class để dynamically generate SQLAlchemy class cho từng bảng token
│   ├── schemas/                # Pydantic Models (Data Transfer Objects - Input/Output validation)
│   │   ├── admin.py
│   │   ├── rbac.py
│   │   └── token.py
│   ├── services/               # Business Logic layer (Tách biệt khỏi API và Database)
│   │   ├── admin_service.py    # Logic DDL (Create schema, create table dynamially)
│   │   ├── rbac_service.py     # Logic kiểm tra quyền, gán quyền
│   │   └── token_service.py    # Logic gọi Key API, kết hợp data, tính HMAC
│   └── data_processing/        # Xử lý Data Pipeline nội bộ
│       └── polars_engine.py    # Chứa logic Polars: mapping data, batch insert DB, detokenize lô lớn
├── tests/                      # Unit/Integration Tests (Pytest)
│   ├── conftest.py             # Fixtures setup DB test
├── README.md                   # Tài liệu dự án
└── .env                        # Biến môi trường
```
