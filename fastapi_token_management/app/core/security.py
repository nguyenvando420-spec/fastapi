"""
security.py — Toàn bộ mật mã học và JWT của hệ thống

Chuẩn JWT RFC 7519 với claims:
  - sub: username
  - exp: thời hạn
  - iat: thời điểm phát hành
  - jti: JWT ID duy nhất (để hỗ trợ blacklist/logout)
  - type: "access" | "refresh" (để tránh dùng lẫn)
"""
import hmac
import hashlib
import uuid
import re
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from typing import Tuple, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

# Khởi tạo bcrypt context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ─────────────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> list[str]:
    """
    Kiểm tra độ mạnh mật khẩu — trả về danh sách lỗi (rỗng = hợp lệ).
    Tiêu chuẩn: tối thiểu 8 ký tự, có chữ hoa, chữ thường, số.
    """
    errors = []
    if len(password) < 8:
        errors.append("Mật khẩu phải có ít nhất 8 ký tự.")
    if not re.search(r'[A-Z]', password):
        errors.append("Mật khẩu phải có ít nhất 1 chữ hoa.")
    if not re.search(r'[a-z]', password):
        errors.append("Mật khẩu phải có ít nhất 1 chữ thường.")
    if not re.search(r'[0-9]', password):
        errors.append("Mật khẩu phải có ít nhất 1 chữ số.")
    return errors


# ── JWT Tokens ────────────────────────────────────────────────────────────────

def _build_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    """
    Builder nội bộ cho cả access và refresh token.
    Tự động bổ sung: exp, iat, jti, type, iss.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "exp": now + expires_delta,
        "iat": now,
        "jti": str(uuid.uuid4()),   # JWT ID — dùng để logout/blacklist
        "type": token_type,
        "iss": settings.PROJECT_NAME,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Tạo Access Token ngắn hạn (mặc định 60 phút hoặc theo config)."""
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _build_token(data, delta, token_type="access")


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Tạo Refresh Token dài hạn (mặc định 7 ngày hoặc theo config).
    Refresh token phải được lưu phía client an toàn (HttpOnly cookie).
    """
    delta = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _build_token(data, delta, token_type="refresh")


def decode_token(token: str) -> Optional[dict]:
    """
    Giải mã và xác thực JWT.
    Trả về payload dict hoặc None nếu token không hợp lệ / hết hạn.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ── Key Management ───────────────────────────────────────────────────────────

def get_mac_key_from_api(system: str, domain: str) -> bytes:
    """
    Mock gọi KMS/Vault để lấy MAC Secret Key theo system và domain.
    Trong production: gọi httpx đến HashiCorp Vault hoặc AWS KMS.
    """
    return b"super_secret_mac_key_mockup_from_api"


def generate_hmac_token(data: str, mac_key: bytes) -> str:
    """Tạo token HMAC-SHA256 — deterministic, có thể xác minh lại."""
    h = hmac.new(mac_key, data.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()


def generate_kek() -> str:
    """Tạo Key Encryption Key (Fernet) — lưu trong DB cùng với record."""
    return Fernet.generate_key().decode('utf-8')


def generate_dek() -> bytes:
    """Tạo Data Encryption Key — dùng một lần cho mỗi bản ghi."""
    return Fernet.generate_key()


def encrypt_payload(data: str, kek_str: str) -> str:
    """
    Mã hoá (DEK + Data) bằng KEK.
    Payload = DEK || Data, sau đó mã hoá toàn bộ bằng Fernet(KEK).
    """
    dek = generate_dek()
    payload = f"{dek.decode('utf-8')}||{data}"
    f_kek = Fernet(kek_str.encode('utf-8'))
    return f_kek.encrypt(payload.encode('utf-8')).decode('utf-8')


def decrypt_payload(encrypted_payload: str, kek_str: str) -> Tuple[str, str]:
    """
    Giải mã payload, trả về (dek_str, original_data).
    """
    f_kek = Fernet(kek_str.encode('utf-8'))
    decrypted_str = f_kek.decrypt(encrypted_payload.encode('utf-8')).decode('utf-8')
    parts = decrypted_str.split('||', 1)
    if len(parts) != 2:
        raise ValueError("Payload giải mã sai định dạng (thiếu dấu ||).")
    return parts[0], parts[1]
