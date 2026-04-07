# Hướng dẫn Viết Prompt "Hoàn hảo" cho Dự án này

Nếu bạn muốn yêu cầu một AI (như Antigravity) triển khai dự án này từ đầu một cách nhanh nhất và chính xác nhất, hãy sử dụng cấu trúc Prompt dưới đây. Nó bao gồm tất cả các "bài học xương máu" (Python 3.9, Bcrypt 3.1.7, Granian, Async Loop) mà chúng ta đã cùng nhau giải quyết.

---

## 🚀 Mẫu Prompt Tổng thể (Master Prompt)

**Tiêu đề: Xây dựng Hệ thống Tokenization Hiệu năng cao với FastAPI và Polars**

**1. Mục tiêu dự án:**
Hãy xây dựng một hệ thống Token Management cho phép:
- Quản lý đa hệ thống (Systems) và đa bảng dữ liệu (Domains).
- Tự động tạo Schema và Table vật lý trên Postgres khi khai báo Domain mới thông qua API.
- Thực hiện Tokenize và De-tokenize dữ liệu theo lô (Bulk) với hiệu suất cực cao.
- Kiểm soát truy cập bằng hệ thống RBAC (User, Role, Permission).

**2. Công nghệ yêu cầu (Must-have Stack):**
- **Ngôn ngữ**: Python 3.9 (Đảm bảo code tương thích hoàn toàn, không dùng toán từ `|` cho Union type).
- **Web Server**: FastAPI, chạy trên **Granian** (ASGI interface).
- **Dữ liệu**: PostgreSQL + SQLAlchemy (Async Session).
- **Xử lý Batch**: **Polars** phối hợp với **ADBC-driver-postgresql** để ghi dữ liệu thần tốc vào DB.
- **Bảo mật**:
    - Password hashing: Passlib + **Bcrypt==3.1.7** (để tránh lỗi 72-byte trên macOS/Python 3.9).
    - Data Encryption: **Envelope Encryption** (Mỗi record dùng 1 DEK, DEK bị mã hóa bởi KEK).
    - Auth: JWT (PyJWT).

**3. Yêu cầu Kiến trúc chi tiết:**
- **Dynamic Models**: Viết Model Factory để sinh class SQLAlchemy động dựa trên `schema_name` và `table_name`.
- **Concurrency**: Tất cả các thao tác Database đồng bộ (như Polars `write_database`) phải được bọc trong `asyncio.to_thread` để không làm treo Event Loop của FastAPI.
- **Bulk Insert**: Sử dụng phương thức `COPY` của ADBC thay vì lặp từng bản ghi.
- **Docker**: Cung cấp `docker-compose.yml` chạy Postgres 14 (để tránh lỗi phân quyền schema public của v15+).

**4. Yêu cầu Kiểm thử (Quality Assurance):**
- Xây dựng bộ test suite dùng `pytest` và `pytest-asyncio`.
- Cấu hình `conftest.py` sao cho:
    - Sử dụng một Event Loop duy nhất cho toàn bộ session test.
    - Test database là `token_db_test`.
    - Engine sử dụng `NullPool` và chế độ `create_savepoint` để hỗ trợ commit/rollback trong code service.

**5. Cấu trúc thư mục:**
- `app/core`: Security, Database config.
- `app/models`: RBAC, Admin, Dynamic Models.
- `app/services`: Tokenization logic, DDL logic.
- `app/api`: Routers (Auth, Admin, Tokens).
- `tests`: Bộ test bao phủ 100% logic chính.

---

## 📌 Tại sao Prompt này hiệu quả?
1.  **Chỉ định phiên bản cụ thể**: Việc nhắc đến `Postgres 14` và `Bcrypt 3.1.7` giúp AI tránh được những lỗi môi trường cực kỳ khó chịu ngay từ đầu.
2.  **Xác định rõ ràng Engine**: Việc yêu cầu `Polars + ADBC` giúp AI không đi vào lối mòn dùng `pandas` hay `insert slow`.
3.  **Xử lý Concurrency**: Nhắc nhở về `asyncio.to_thread` giúp code không bị lỗi `InterfaceError` khi chạy thực tế.
4.  **Cấu hình Test chi tiết**: Đây là phần khó nhất trong FastAPI async; việc định hướng `conftest.py` giúp bộ test chạy ổn định 100% ngay lần đầu.
