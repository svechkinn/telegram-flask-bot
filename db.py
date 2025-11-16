import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, username, first_name):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (user_id, username, first_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()

def get_users():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()
    conn.close()
    return [(u["user_id"],