import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                sports TEXT DEFAULT '["*"]',
                content_types TEXT DEFAULT '["*"]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_items (
                item_id TEXT,
                user_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                PRIMARY KEY (item_id, user_id)
            )
        """)
        conn.commit()

def add_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

def save_settings(user_id: int, sports: list, content_types: list):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_settings (user_id, sports, content_types, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, json.dumps(sports), json.dumps(content_types)))
        conn.commit()

def load_settings(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sports, content_types FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0]), json.loads(row[1])
        return ["*"], ["*"]

def is_item_sent(item_id: str, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sent_items WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        return cursor.fetchone() is not None

def mark_sent(item_id: str, user_id: int, published_at: str = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO sent_items (item_id, user_id, published_at) VALUES (?, ?, ?)",
                       (item_id, user_id, published_at))
        conn.commit()

def clean_old_sent_items(days=7):
    with get_connection() as conn:
        conn.execute("DELETE FROM sent_items WHERE sent_at < datetime('now', '-' || ? || ' days')", (days,))
        conn.commit()