import sqlite3
import os

# Путь к базе
DB_PATH = "/data/users.db"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_user(user_id: int, username: str, first_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user_id, username, first_name)
    )
    conn.commit()
    conn.close()

def get_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()
    conn.close()