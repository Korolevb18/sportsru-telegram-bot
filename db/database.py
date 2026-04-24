import sqlite3
import json
import secrets
import string
from pathlib import Path
from datetime import datetime, timedelta

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS callback_cache (
                callback_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Новые таблицы для авторизации
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                user_id INTEGER PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invite_codes (
                code TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_by INTEGER,
                used_at TIMESTAMP
            )
        """)
        conn.commit()

    # Миграция: перенос существующего пользователя из .allowed_users.txt
    migrate_allowed_users_from_file()

def migrate_allowed_users_from_file():
    allowed_file = Path(__file__).parent.parent / ".allowed_users.txt"
    if not allowed_file.exists():
        return
    with open(allowed_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    user_id = int(line)
                    add_allowed_user(user_id)
                except ValueError:
                    pass
    # Переименовываем файл, чтобы не мигрировать повторно
    allowed_file.rename(allowed_file.with_suffix(".txt.bak"))

# ---------- Пользователи (общие) ----------
def add_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

# ---------- Разрешённые пользователи ----------
def is_user_allowed(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM allowed_users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def add_allowed_user(user_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        # Также добавляем в users для совместимости
        add_user(user_id)

def get_allowed_users() -> list[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM allowed_users")
        return [row[0] for row in cursor.fetchall()]

# ---------- Настройки пользователя ----------
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

# ---------- Отправленные элементы ----------
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

# ---------- Callback кэш ----------
def save_callback_id(callback_id: str, url: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO callback_cache (callback_id, url, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                       (callback_id, url))
        conn.commit()

def get_url_by_callback_id(callback_id: str) -> str | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM callback_cache WHERE callback_id = ?", (callback_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def clean_old_callbacks(days=7):
    with get_connection() as conn:
        conn.execute("DELETE FROM callback_cache WHERE created_at < datetime('now', '-' || ? || ' days')", (days,))
        conn.commit()

# ---------- Коды приглашения ----------
def generate_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_invite_code() -> str:
    """Создаёт новый неиспользованный код и возвращает его."""
    code = generate_invite_code()
    with get_connection() as conn:
        cursor = conn.cursor()
        while True:
            cursor.execute("SELECT 1 FROM invite_codes WHERE code = ? AND used_by IS NULL", (code,))
            if cursor.fetchone() is None:
                break
            code = generate_invite_code()
        cursor.execute("INSERT INTO invite_codes (code) VALUES (?)", (code,))
        conn.commit()
    return code

def use_invite_code(code: str, user_id: int) -> bool:
    """Активирует код для пользователя. Возвращает True, если код действителен."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE invite_codes
            SET used_by = ?, used_at = CURRENT_TIMESTAMP
            WHERE code = ? AND used_by IS NULL
        """, (user_id, code))
        conn.commit()
        return cursor.rowcount > 0