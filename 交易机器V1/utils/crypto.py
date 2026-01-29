# utils/crypto.py
from cryptography.fernet import Fernet
import sqlite3
import os
from pathlib import Path

KEY_DB = "config/secrets.db"

def init_key_db():
    Path("config").mkdir(exist_ok=True)
    conn = sqlite3.connect(KEY_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY,
            key BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_or_create_fernet_key() -> bytes:
    init_key_db()
    conn = sqlite3.connect(KEY_DB)
    c = conn.cursor()
    c.execute("SELECT key FROM keys WHERE id = 1")
    row = c.fetchone()
    if row:
        key = row[0]
    else:
        key = Fernet.generate_key()
        c.execute("INSERT INTO keys (id, key) VALUES (1, ?)", (key,))
        conn.commit()
    conn.close()
    return key

def encrypt_data(data: str) -> bytes:
    f = Fernet(get_or_create_fernet_key())
    return f.encrypt(data.encode())

def decrypt_data(encrypted: bytes) -> str:
    f = Fernet(get_or_create_fernet_key())
    return f.decrypt(encrypted).decode()

# 使用示例（不在代码中硬编码）
# encrypted = encrypt_data("your_api_secret")
# decrypted = decrypt_data(encrypted)
