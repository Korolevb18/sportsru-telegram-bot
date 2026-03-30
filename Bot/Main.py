import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Загружаем токен из файла .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создаём объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот новостей Sports.ru.\n\n"
        "Скоро здесь будут настройки подписок и новости.\n"
        "А пока проверяем, что бот работает."
    )

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📌 Команды бота:\n"
        "/start — приветствие и начало работы\n"
        "/help — эта справка\n\n"
        "В следующих версиях появится /settings для настройки подписок."
    )

# Запуск бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())