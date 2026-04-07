import polars as pl
from app.core.config import settings
from app.core.security import (
    get_mac_key_from_api,
    generate_hmac_token,
    generate_kek,
    encrypt_payload,
    decrypt_payload
)

def _process_tokenization(data_series: pl.Series, mac_key: bytes, version: str) -> pl.Series:
    """Hàm helper chạy Python loop nội bộ (an toàn và chuẩn chỉ cho mọi phiên bản Polars)"""
    results = []
    for val in data_series:
        if val is None:
            results.append({"token": None, "encrypt_dek_data": None, "kek": None})
            continue
            
        # Format token: {version}:{token_hmac}
        token_hmac = generate_hmac_token(val, mac_key)
        token = f"{version}:{token_hmac}"
        
        kek = generate_kek()
        encrypt_dek_data = encrypt_payload(val, kek)
        
        results.append({
            "token": token,
            "encrypt_dek_data": encrypt_dek_data,
            "kek": kek
        })
    return pl.Series("crypto_info", results)

def tokenize_dataframe(df: pl.DataFrame, system: str, domain: str, version: str, data_column: str = "data") -> pl.DataFrame:
    """
    Nhận Dataframe chứa dữ liệu gốc, ánh xạ token/key, biến đổi thành schema sẵn sàng insert DB.
    """
    # 1. Gọi API lấy khóa MAC 
    mac_key = get_mac_key_from_api(system, domain)
    
    # 2. Xử lý đồng loạt (Vectorize loop fallback bằng helper)
    struct_series = _process_tokenization(df[data_column], mac_key, version)
    
    # 3. Chèn Cột Struct vào data frame rồi giải nén thành 3 cột rời
    res_df = df.with_columns(struct_series).unnest("crypto_info")
    return res_df

def batch_insert_to_db(df: pl.DataFrame, schema_name: str, table_name: str, engine=None):
    """
    Sử dụng interface write_database của Polars qua engine ADBC (C/C++).
    Nếu engine được truyền vào (sqlalchemy engine), ta trích xuất URI.
    """
    if engine:
        # Lấy URI từ engine hiện tại, đảm bảo lấy cả username/password đầy đủ
        url = engine.url
        sync_uri = f"postgresql://{url.username}:{url.password}@{url.host}:{url.port}/{url.database}"
    else:
        # Mặc định dùng Token DB
        sync_uri = settings.SQLALCHEMY_TOKEN_DATABASE_URI.replace("+asyncpg", "")
    
    df.write_database(
        table_name=f"{schema_name}.{table_name}",
        connection=sync_uri,
        if_table_exists="append",
        engine="adbc"
    )

def _process_detokenization(encrypt_series: pl.Series, kek_series: pl.Series) -> pl.Series:
    """Helper xử lý giải mã bulk data"""
    results = []
    for enc, kek in zip(encrypt_series, kek_series):
        if not enc or not kek:
            results.append(None)
            continue
        try:
            _, original_data = decrypt_payload(enc, kek)
            results.append(original_data)
        except Exception:
            results.append(None) # Safe fallback
    return pl.Series("decrypted_data", results)

def detokenize_dataframe(df: pl.DataFrame, encrypt_column: str = "encrypt_dek_data", kek_column: str = "kek") -> pl.DataFrame:
    """
    Detokenize: truyền Dataframe được select từ Postgres chứa Encrypt Data & KEK.
    Trả ra cột Decrypted Data nguyên thuỷ.
    """
    decrypted_series = _process_detokenization(df[encrypt_column], df[kek_column])
    return df.with_columns(decrypted_series)
