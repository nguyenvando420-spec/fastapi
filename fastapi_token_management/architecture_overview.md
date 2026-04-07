# Tài liệu Kiến trúc Hệ thống Token Management

Tài liệu này tóm tắt các bước xây dựng dự án và giải thích chi tiết từng thành phần trong kiến trúc của hệ thống Tokenization hiệu năng cao dùng FastAPI, PostgreSQL và Polars.

---

## 1. Tóm tắt các bước xây dựng dự án

Quá trình phát triển được thực hiện theo 5 giai đoạn chính:

1.  **Thiết kế Kiến trúc (Design Phase)**:
    *   Xác định mô hình dữ liệu động (Dynamic Schema/Tables) cho từng phân vùng dữ liệu (Systems/Domains).
    *   Thiết kế hệ thống phân quyền RBAC (Role-Based Access Control) để kiểm soát quyền truy cập Token.
    *   Lựa chọn công cụ hiệu năng: **Polars** để xử lý dữ liệu bulk và **ADBC** để ghi dữ liệu tốc độ cao vào Postgres.

2.  **Xây dựng Nền tảng (Core Phase)**:
    *   Thiết lập Security: Tích hợp JWT, BCrypt cho Password và **Envelope Encryption** (Fernet) để bảo mật token.
    *   Cấu hình Database: Sử dụng `SQLAlchemy (asyncpg)` cho các luồng xử lý bất đồng bộ.

3.  **Triển khai Logic Nghiệp vụ (Business Logic Phase)**:
    *   Xây dựng **Admin Service**: Tự động tạo Schema và Table vật lý trên Postgres khi khai báo System/Domain.
    *   Xây dựng **Token Service**: Xử lý Tokenize (mã hóa dữ liệu theo lô) và De-tokenize (giải mã).
    *   Xây dựng **RBAC Service**: Quản lý User, Role và Permission.

4.  **Phát triển API & Web Server (API Phase)**:
    *   Sử dụng FastAPI để cung cấp các Endpoint RESTful.
    *   Tích hợp Pydantic v2 để validate dữ liệu đầu vào.

5.  **Kiểm thử & Tối ưu (Testing & Optimization Phase)**:
    *   Xây dựng bộ Test Suite (21 test cases) bao phủ toàn bộ tính năng.
    *   Tối ưu hóa Event Loop và Connection Pool để đảm bảo hệ thống chạy ổn định trên macOS/Python 3.9.

---

## 2. Giải thích chi tiết từng phần của dự án

Hệ thống được tổ chức theo cấu trúc thư mục chuẩn FastAPI:

### 2.1. Thư mục `app/core` (Hạt nhân)
*   **`security.py`**: Chứa "trái tim" bảo mật. Sử dụng **Envelope Encryption**: Mỗi mẩu tin được mã hóa bằng một khóa DEK riêng, sau đó DEK lại được bảo vệ bởi khóa KEK. Điều này đảm bảo nếu lộ 1 bản ghi, các bản ghi khác vẫn an toàn.
*   **`database.py`**: Quản lý kết nối Database. Sử dụng `asyncpg` để đạt hiệu suất I/O cao nhất.
*   **`config.py`**: Quản lý cấu hình qua biến môi trường (.env).

### 2.2. Thư mục `app/models` (Dữ liệu)
*   **`admin.py`**: Định nghĩa System (Phân vùng) và Domain (Bảng dữ liệu). Đây là metadata để hệ thống biết cần tạo bảng ở đâu.
*   **`rbac.py`**: Định nghĩa mối quan hệ N-N giữa User, Role, Group và Permission.
*   **`dynamic_token.py`**: Chứa **Model Factory**. Đây là kỹ thuật đặc biệt để tạo ra các class SQLAlchemy tại thời điểm thực thi (runtime) dựa trên tên bảng mà người dùng khai báo.

### 2.3. Thư mục `app/data_processing` (Cỗ máy xử lý)
*   **`polars_engine.py`**: Sử dụng thư viện **Polars** (viết bằng Rust) để xử lý dữ liệu cực nhanh.
    *   `tokenize_dataframe`: Mã hóa hàng loạt dữ liệu trên RAM.
    *   `batch_insert_to_db`: Sử dụng **ADBC (Arrow Database Connectivity)** để tải dữ liệu vào Postgres nhanh gấp nhiều lần so với các hàm `insert` thông thường.

### 2.4. Thư mục `app/services` (Nghiệp vụ)
*   **`token_service.py`**: Điều phối luồng Tokenize. Nó nhận dữ liệu từ API, gọi Polars Engine để xử lý, và lưu vào các bảng động.
*   **`admin_service.py`**: Chịu trách nhiệm thực thi các lệnh DDL (Data Definition Language) như `CREATE SCHEMA` và `CREATE TABLE` trên Postgres một cách tự động.

### 2.5. Thư mục `app/api` (Giao tiếp)
*   **`v1/auth.py`**: Đăng ký và Đăng nhập.
*   **`v1/admin.py`**: Quản trị hệ thống (Tạo System/Domain).
*   **`v1/token.py`**: Endpoint cho người dùng cuối để Tokenize dữ liệu.

### 2.6. Thư mục `tests` (Bảo chứng chất lượng)
*   **`conftest.py`**: Cấu hình môi trường giả lập. Nó tự động tạo database sạch (`token_db_test`) trước khi chạy test và dọn dẹp sau khi xong.

### 2.7. Web Server
*   **Granian**: Hệ thống vận hành trên **Granian** - một HTTP server thế hệ mới viết bằng Rust, hỗ trợ cả ASGI/RSGI với hiệu năng vượt trội so với Uvicorn truyền thống.

---

## 3. Tại sao kiến trúc này mạnh mẽ?
1.  **Tính linh động**: Bạn có thể tạo thêm hàng ngàn Domain (bảng) mới thông qua API mà không cần sửa code hay khởi động lại server.
2.  **Hiệu năng**: Việc tách biệt luồng Query (SQLAlchemy) và luồng Bulk Insert (Polars/ADBC) giúp hệ thống xử lý được hàng triệu bản ghi mà không bị treo.
3.  **Bảo mật**: Tuân thủ các tiêu chuẩn mã hóa hiện đại nhất cho hệ thống Tokenization.
