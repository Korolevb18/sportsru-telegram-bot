from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("test"))
async def test(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Нажми меня", callback_data="test_button")]
    ])
    await message.answer("Нажми на кнопку:", reply_markup=keyboard)

@dp.callback_query()
async def callback(callback: types.CallbackQuery):
    print(f"Получен callback: {callback.data}")
    await callback.answer("Кнопка нажата!")
    await callback.message.edit_text("✅ Кнопка сработала!")

async def main():
    print("Бот с кнопкой запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())