import asyncio
import sys
from pathlib import Path
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(str(Path(__file__).parent.parent))

from logger_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from db.database import (
    init_db, add_user, is_user_allowed, add_allowed_user,
    use_invite_code, get_allowed_users, create_invite_code
)
from handlers import register_handlers

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("Не найден BOT_TOKEN в .env файле!")
    sys.exit(1)

# ---------- ID администраторов (можно добавить несколько) ----------
ADMIN_USER_IDS = [
    50608447,   # основной админ
    295808045, 
]

init_db()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Регистрируем обработчики (настройки и колбэки)
register_handlers(dp)

# ---------- Команда /start ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Активация по пригласительной ссылке
    if len(args) > 1:
        code = args[1].strip()
        if use_invite_code(code, user_id):
            add_allowed_user(user_id)
            await message.answer(
                "✅ Доступ активирован! Добро пожаловать!\n\n"
                "Теперь вы будете получать новости Sports.ru каждый час.\n"
                "Настройте подписки, чтобы видеть только интересное.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚙️ Настроить подписки", callback_data="goto_settings")]
                ])
            )
        else:
            await message.answer("❌ Неверный или уже использованный код приглашения.")
        return

    # Обычный старт для уже авторизованных
    if not is_user_allowed(user_id):
        await message.answer(
            "⛔ Доступ к боту ограничен.\n"
            "Попросите у администратора пригласительную ссылку."
        )
        return

    add_user(user_id)
    await message.answer(
        "👋 Привет! Я бот новостей Sports.ru.\n\n"
        "📰 Каждый час я присылаю свежие новости, блоги и топ-публикации.\n"
        "⚙️ Настройте подписки, чтобы получать только то, что вам интересно.\n\n"
        "Команды:\n"
        "/settings – настроить подписки\n"
        "/help – помощь",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Перейти к настройкам", callback_data="goto_settings")]
        ])
    )

# ---------- Обработчик кнопки "Настройки" из приветствия ----------
@dp.callback_query(lambda c: c.data == "goto_settings")
async def goto_settings_callback(callback: types.CallbackQuery):
    if not is_user_allowed(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    # Перенаправляем на команду /settings
    await callback.message.delete()
    await cmd_settings(callback.message)

# Импортируем cmd_settings из handlers (нужно будет добавить экспорт)
from handlers import cmd_settings  # см. изменения в handlers.py

# ---------- Команда /help ----------
@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "📌 **Помощь по боту Sports.ru**\n\n"
        "🔹 /start – приветствие и активация\n"
        "🔹 /settings – настройка подписок (виды спорта, типы контента)\n"
        "🔹 /help – эта справка\n\n"
        "Новости приходят автоматически каждый час.\n"
        "Вы можете в любой момент изменить подписки.",
        parse_mode="Markdown"
    )

# ---------- Команда /invite (только для админов) ----------
@dp.message(Command("invite"))
async def cmd_invite(message: Message):
    if message.from_user.id not in ADMIN_USER_IDS:
        await message.answer("⛔ Команда доступна только администратору.")
        return

    code = create_invite_code()
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"
    await message.answer(
        f"🔗 **Одноразовая ссылка для приглашения:**\n`{link}`\n\n"
        "Отправьте её другу. После активации код станет недействительным.",
        parse_mode="Markdown"
    )

# ---------- Запуск ----------
async def main():
    logger.info("Бот запущен...")
    allowed = get_allowed_users()
    logger.info(f"Разрешённые пользователи: {allowed}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())