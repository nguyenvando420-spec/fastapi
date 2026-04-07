import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from typing import Tuple, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Khởi tạo mô hình Hash bằng thuật toán BCrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Tạo JWT Token để verify sessions cho các API"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_mac_key_from_api(system: str, domain: str) -> bytes:
    """
    Mock gọi API bên thứ 3 để lấy MAC Secret Key.
    Trong thực tế hàm này sẽ dùng httpx gọi sang KMS hoặc Vault.
    """
    # Dùng string cố định mockup cho demo
    return b"super_secret_mac_key_mockup_from_api"

def generate_hmac_token(data: str, mac_key: bytes) -> str:
    """Tạo token duy nhất cho chuỗi data bằng thuật toán HMAC-SHA256"""
    h = hmac.new(mac_key, data.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()

def generate_kek() -> str:
    """Tạo Key Encryption Key (Sẽ được lưu dưới Database)"""
    return Fernet.generate_key().decode('utf-8')

def generate_dek() -> bytes:
    """Tạo Data Encryption Key (Dùng một lần cho mỗi bản ghi)"""
    return Fernet.generate_key()

def encrypt_payload(data: str, kek_str: str) -> Tuple[str, str]:
    """
    Mã hoá (DEK + Data) sử dụng KEK.
    (Giả định yêu cầu bài toán: gom payload = DEK || data, 
    sau đó mã hoá nguyên khối bằng KEK)
    
    Trả về chuỗi payload đã mã hoá (encrypt_dek_data).
    """
    dek = generate_dek()
    
    # Nối DEK và Data thành string payload (Tách bằng dấu phân tách ||)
    payload = f"{dek.decode('utf-8')}||{data}"
    
    # Khởi tạo thuật toán bằng KEK
    f_kek = Fernet(kek_str.encode('utf-8'))
    
    # Mã hóa payload
    encrypted_payload_bytes = f_kek.encrypt(payload.encode('utf-8'))
    
    return encrypted_payload_bytes.decode('utf-8')

def decrypt_payload(encrypted_payload: str, kek_str: str) -> Tuple[str, str]:
    """
    Giải mã payload chứa encrypt(DEK + Data) bằng KEK.
    Trả về bộ (Mã DEK, Data gốc ban đầu).
    """
    f_kek = Fernet(kek_str.encode('utf-8'))
    
    decrypted_str = f_kek.decrypt(encrypted_payload.encode('utf-8')).decode('utf-8')
    
    parts = decrypted_str.split('||', 1)
    if len(parts) != 2:
        raise ValueError("Lỗi: Payload giải mã sai định dạng (thiếu dấu ||)")
        
    return parts[0], parts[1]
