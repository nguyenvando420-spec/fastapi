***Prompt 1***: Lên cấu trúc kiến trúc (Architecture & Setup)

Hãy đóng vai trò là một Software Architect và Senior Python Developer.

Tôi đang bắt đầu một dự án mới với yêu cầu nghiệp vụ tổng quan như sau: 
- Hệ thống quản lý token, với đầu vào là domain, system, data, output là token tương ứng với data. 
- Mỗi system là một schema trong database, mỗi domain và version token là một table trong schema, table sẽ lưu token và encrypt (DEK + data) và KEK, từ KEK và DEK có thể decrypt (DEK + data) để lấy data và DEK. KEK được lưu trong database. Token tôi lấy key từ api và kết hợp với data và mã hoá hmac để tạo token. 
- Tôi muốn sử dụng polars để xử lý data và insert vào database, cũng như để detokenize. 
- Tôi muốn quản lý permision, user, role, group cho system và domain. User có thể có nhiều role, role có thể có nhiều permission, group có thể có nhiều user, group có thể có nhiều role. 
- Tôi muốn quản lý connection pool cho database.
- Quản lý admin tạo schema - system, tạo table - domain, mỗi table đều lưu trữ các cột giống nhau.

Tech Stack bắt buộc:

Backend: FastAPI và granian, alembic, polars

Database: PostgreSQL với SQLAlchemy ORM

Nhiệm vụ của bạn:

Đề xuất một cấu trúc thư mục (folder structure) tối ưu, dễ mở rộng (scalable) cho toàn bộ dự án. Giải thích ngắn gọn lý do chọn cấu trúc đó.

Cung cấp các lệnh terminal (CLI) cần thiết để khởi tạo dự án và cài đặt các thư viện trên.

Xin đừng viết code logic vội. Trả về cho tôi cấu trúc file dưới dạng cây (tree format).

***Prompt 2***: Bắt tay vào Code tính năng cụ thể (Sau khi đã có kiến trúc)

Hãy đóng vai trò là một Senior Backend Developer. Chúng ta đang làm việc trên dự án Token Management System sử dụng stack: FastAPI, granian, alembic, PostgreSQL với SQLAlchemy ORM.

Tôi cần bạn viết code cho tính năng: Tạo API endpoint để tạo tokenize, với đầu vào domain (là type email, số điện thoại, ...), data (là email, số điện thoại, ...), system, data có thể là email, số điện thoại, ...; có giới hạn độ dài data; đầu ra trả về data maping với token tương ứng

Đây là các yêu cầu nghiệp vụ chi tiết:

Yêu cầu 1: Tôi có một key được lấy từ api với đầu vào domain, system, data để tạo token với key bằng Hmac

Yêu cầu 2: Lưu token vào database với thông tin domain, system, token

Yêu cầu 3: Kiểm tra token có tồn tại trong database không, những data chưa có token thì lưu lại trên database, những data đã có token thì không lưu lại token trên database

Ràng buộc mã nguồn (Constraints):

Code phải tuân thủ nguyên tắc SOLID và Clean Code.

Tách biệt logic UI và Business Logic (tạo custom hooks nếu cần).

Xử lý lỗi (Error handling) đầy đủ.

Quan trọng: Trước khi bạn viết bất kỳ dòng code nào, hãy đọc kỹ yêu cầu nghiệp vụ ở trên. Nếu bạn thấy có điểm nào thiếu sót về mặt logic, có rủi ro về bảo mật (edge cases), hoặc cần làm rõ, hãy đặt ra cho tôi tối đa 3 câu hỏi. Nếu mọi thứ đã hoàn hảo, hãy bắt đầu viết code.

***Prompt 3***: Bắt tay vào Code tính năng cụ thể (Sau khi đã có kiến trúc)

Hãy đóng vai trò là một Senior Backend Developer. Chúng ta đang làm việc trên dự án Token Management System sử dụng stack: FastAPI, granian, alembic, PostgreSQL với SQLAlchemy ORM.

Tôi cần bạn viết code cho tính năng: Tạo API endpoint để tạo de-tokenize, với đầu vào token có giới hạn độ dài danh sách token; đầu ra trả về data maping với token tương ứng

Đây là các yêu cầu nghiệp vụ chi tiết:

Yêu cầu 1: lấy dữ liệu token và data từ database để trả lại cho client

Ràng buộc mã nguồn (Constraints):

Code phải tuân thủ nguyên tắc SOLID và Clean Code.

Tách biệt logic UI và Business Logic (tạo custom hooks nếu cần).

Xử lý lỗi (Error handling) đầy đủ.

Thực hiện viết test cases và test luôn

Quan trọng: Trước khi bạn viết bất kỳ dòng code nào, hãy đọc kỹ yêu cầu nghiệp vụ ở trên. Nếu bạn thấy có điểm nào thiếu sót về mặt logic, có rủi ro về bảo mật (edge cases), hoặc cần làm rõ, hãy đặt ra cho tôi tối đa 3 câu hỏi. Nếu mọi thứ đã hoàn hảo, hãy bắt đầu viết code.