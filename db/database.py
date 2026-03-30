import sqlite3
import json
from pathlib import Path

# Путь к файлу базы данных
DB_PATH = Path(__file__).parent.parent / "data" / "bot.db"


def get_connection():
    """Возвращает соединение с БД"""
    # Создаём папку data, если её нет
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Создаёт таблицы при первом запуске"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица настроек пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                sports TEXT DEFAULT '["*"]',
                content_types TEXT DEFAULT '["*"]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Таблица отправленных новостей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_items (
                item_id TEXT,
                user_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (item_id, user_id)
            )
        """)

        conn.commit()


def add_user(user_id: int):
    """Добавляет нового пользователя, если его ещё нет"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()


def save_settings(user_id: int, sports: list, content_types: list):
    """Сохраняет или обновляет настройки пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_settings (user_id, sports, content_types, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, json.dumps(sports), json.dumps(content_types)))
        conn.commit()


def load_settings(user_id: int):
    """Загружает настройки пользователя. Если настроек нет — возвращает значения по умолчанию (всё)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT sports, content_types FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0]), json.loads(row[1])
        return ["*"], ["*"]  # По умолчанию — все виды спорта и все типы контента


def is_item_sent(item_id: str, user_id: int) -> bool:
    """Проверяет, отправляли ли мы эту новость пользователю"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sent_items WHERE item_id = ? AND user_id = ?", (item_id, user_id))
        return cursor.fetchone() is not None


def mark_sent(item_id: str, user_id: int):
    """Отмечает новость как отправленную для пользователя"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO sent_items (item_id, user_id) VALUES (?, ?)", (item_id, user_id))
        conn.commit()