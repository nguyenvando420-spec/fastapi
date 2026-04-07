import pytest
from app.core.security import (
    generate_hmac_token,
    generate_kek,
    encrypt_payload,
    decrypt_payload,
    get_password_hash,
    verify_password,
    create_access_token,
    get_mac_key_from_api
)
from jose import jwt
from app.core.config import settings

def test_generate_hmac_token():
    mac_key = b"test_mac_key"
    data = "hello world"
    
    token1 = generate_hmac_token(data, mac_key)
    token2 = generate_hmac_token(data, mac_key)
    
    # Deterministic test
    assert token1 == token2 
    # SHA256 hex digest results in 64 characters
    assert len(token1) == 64 

def test_envelope_encryption_pipeline():
    """Test mã hoá bao thư từ đầu cuối"""
    original_data = "my_secret_transaction_data_001"
    
    kek = generate_kek()
    
    # Mã hoá
    encrypted_payload = encrypt_payload(original_data, kek)
    
    assert encrypted_payload != original_data
    assert isinstance(encrypted_payload, str)
    
    # Giải mã
    dek_str, decrypted_data = decrypt_payload(encrypted_payload, kek)
    
    assert decrypted_data == original_data
    assert len(dek_str) > 0

def test_decrypt_invalid_kek():
    """Đảm bảo không thể phân giải KEK sai"""
    data = "test_data_leak"
    kek1 = generate_kek()
    kek2 = generate_kek() # Sai khoá
    
    encrypted = encrypt_payload(data, kek1)
    
    with pytest.raises(Exception):
        decrypt_payload(encrypted, kek2)

def test_verify_password_and_hash():
    password = "test_pwd"
    hashed_pw = get_password_hash(password)
    
    assert hashed_pw != password
    assert verify_password(password, hashed_pw) is True
    assert verify_password("wrongpassword", hashed_pw) is False

def test_create_access_token():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    
    # Verify token
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "testuser"
    assert "exp" in payload

def test_get_mac_key_from_api():
    mac_key = get_mac_key_from_api("systemA", "domainB")
    assert isinstance(mac_key, bytes)
    assert len(mac_key) > 0
