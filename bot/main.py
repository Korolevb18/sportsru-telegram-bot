import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from db.database import init_db, add_user
from handlers import register_handlers  # <-- вот так

BOT_TOKEN = "8608448787:AAEVb5cT2icc5oUvTY6uj_VYM3fkKvNzKGg"

# Загружаем список разрешённых пользователей
ALLOWED_USERS = set()
allowed_file = Path(__file__).parent.parent / ".allowed_users.txt"
if allowed_file.exists():
    with open(allowed_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    ALLOWED_USERS.add(int(line))
                except ValueError:
                    print(f"Неверный ID в файле: {line}")
else:
    print("Предупреждение: файл .allowed_users.txt не найден. Бот никому не ответит.")

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

async def check_access(message: Message):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Вы не в списке разрешённых пользователей.")
        return False
    return True

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрируем обработчики из handlers.py
register_handlers(dp)

init_db()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not await check_access(message):
        return
    user_id = message.from_user.id
    add_user(user_id)
    await message.answer(
        "👋 Привет! Я бот новостей Sports.ru.\n\n"
        "Используйте /settings для настройки подписок.\n"
        "Новости будут приходить каждые 30 минут."
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not await check_access(message):
        return
    await message.answer(
        "📌 **Команды бота:**\n"
        "/start — приветствие\n"
        "/settings — настройка подписок\n"
        "/help — эта справка\n\n"
        "Новости будут приходить автоматически.",
        parse_mode="Markdown"
    )

async def main():
    print("Бот запущен...")
    print(f"Разрешённые пользователи: {ALLOWED_USERS}")
    await dp.start_polling(bot)
    
print("===== ТЕСТ: БОТ ЗАПУСКАЕТСЯ =====")

if __name__ == "__main__":
    asyncio.run(main())