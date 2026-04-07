import pytest
import polars as pl
from unittest.mock import patch
from app.data_processing.polars_engine import (
    tokenize_dataframe, 
    detokenize_dataframe, 
    batch_insert_to_db
)

def test_tokenize_and_detokenize_dataframe():
    """Test full flow mã hoá toàn bộ Dataframe qua 3 cột DB"""
    # 1. Dữ liệu thô ban đầu (Raw Data)
    raw_data = {"id": [1, 2, 3], "data": ["info1", "info2", "info3"]}
    df_raw = pl.DataFrame(raw_data)
    
    # 2. Đầu ra sau khi Tokenize
    df_tokenized = tokenize_dataframe(df_raw, system="sys", domain="dom", version="v1", data_column="data")
    
    # Đảm bảo vẫn giữ cột id gốc và mọc thêm 3 cột schema mới
    assert "token" in df_tokenized.columns
    assert "encrypt_dek_data" in df_tokenized.columns
    assert "kek" in df_tokenized.columns
    assert df_tokenized.shape[0] == 3 # Số records không đổi
    
    # Đảm bảo data đã khác biệt giữa các row và có format version:token
    tokens = df_tokenized["token"].to_list()
    assert len(set(tokens)) == 3
    assert tokens[0].startswith("v1:")
    
    # 3. Phục vụ việc Detokenize (Đọc từ Database lên)
    # df_tokenized chính tả mockup table lấy về
    df_detokenized = detokenize_dataframe(df_tokenized, encrypt_column="encrypt_dek_data", kek_column="kek")
    
    assert "decrypted_data" in df_detokenized.columns
    
    # Đối chiếu dữ liệu ban đầu 
    decrypted_list = df_detokenized["decrypted_data"].to_list()
    assert decrypted_list == ["info1", "info2", "info3"]

def test_tokenize_with_null_data():
    """Trường hợp data bị rỗng thì không sinh ra token rác"""
    raw_data = {"id": [1], "data": [None]}
    df_raw = pl.DataFrame(raw_data)
    
    df_tokenized = tokenize_dataframe(df_raw, system="sys", domain="dom", version="v1", data_column="data")
    
    assert df_tokenized["token"][0] is None
    assert df_tokenized["encrypt_dek_data"][0] is None
    assert df_tokenized["kek"][0] is None

def test_detokenize_invalid_data():
    """Trường hợp data gửi vào bị rác hoặc giải mã thất bại"""
    raw_data = {"id": [1, 2], "encrypt_dek_data": ["invalid_data", None], "kek": ["invalid_kek", None]}
    df_raw = pl.DataFrame(raw_data)
    
    df_detokenized = detokenize_dataframe(df_raw, "encrypt_dek_data", "kek")
    
    # 1 invalid payload and 1 None
    assert df_detokenized["decrypted_data"][0] is None
    assert df_detokenized["decrypted_data"][1] is None

@patch("app.data_processing.polars_engine.pl.DataFrame.write_database")
def test_batch_insert_to_db_mocked(mock_write_db):
    """Test parse logic sync connection URI (Token DB) và engine options"""
    df = pl.DataFrame({"data": [1, 2, 3]})
    
    # Không truyền engine, mặc định dùng settings.SQLALCHEMY_TOKEN_DATABASE_URI
    batch_insert_to_db(df, schema_name="mock_schema", table_name="mock_table")
    
    mock_write_db.assert_called_once()
    called_args = mock_write_db.call_args.kwargs
    
    assert called_args["table_name"] == "mock_schema.mock_table"
    assert "token_db" in called_args["connection"]
    assert "+asyncpg" not in called_args["connection"]
    assert called_args["engine"] == "adbc"
    assert called_args["if_table_exists"] == "append"
