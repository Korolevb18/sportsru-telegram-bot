import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(str(Path(__file__).parent.parent))

from db.database import save_settings, load_settings, is_user_allowed
from parser.extractor import extract_article_data
from bot.sender import send_message, get_url_from_callback

logger = logging.getLogger(__name__)

SPORTS = [
    ("football", "⚽ Футбол"),
    ("hockey", "🏒 Хоккей"),
    ("basketball", "🏀 Баскетбол"),
    ("tennis", "🎾 Теннис"),
    ("biathlon", "🎯 Биатлон"),
    ("figure_skating", "⛸ Фигурное катание"),
    ("boxing_mma", "🥊 Бокс/MMA"),
    ("autosport", "🏎 Автоспорт"),
    ("other", "📰 Прочее"),
]

CONTENT_TYPES = [
    ("news", "📰 Новости"),
    ("longreads", "📖 Материалы"),
    ("blogs", "✍️ Блоги"),
    ("top_publications", "⭐ Топ-публикации"),
    ("fresh_publications", "🆕 Свежие публикации")
]

# Глобальный словарь для хранения промежуточных выборов в процессе настройки
user_selections = {}


async def cmd_settings(message: types.Message):
    """Обработчик команды /settings (глобальный, используется также из main)."""
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    user_id = message.from_user.id
    saved_sports, saved_types = load_settings(user_id)
    user_selections[user_id] = {
        "sports": saved_sports if saved_sports != ["*"] else [],
        "content_types": saved_types if saved_types != ["*"] else []
    }

    keyboard = []
    for key, name in SPORTS:
        display_name = f"✅ {name}" if key in user_selections[user_id]["sports"] else name
        keyboard.append([InlineKeyboardButton(text=display_name, callback_data=f"sport_{key}")])
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="sport_done")])

    await message.answer(
        "🎯 Выберите виды спорта (можно несколько):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


def register_handlers(dp: Dispatcher):
    # Регистрируем команду /settings
    dp.message.register(cmd_settings, Command("settings"))

    # Вспомогательная проверка доступа для callback
    async def check_callback_access(callback: types.CallbackQuery) -> bool:
        if not is_user_allowed(callback.from_user.id):
            await callback.answer("⛔ Доступ запрещён.", show_alert=True)
            return False
        return True

    # ---------- Выбор видов спорта ----------
    @dp.callback_query(lambda c: c.data.startswith("sport_") and c.data != "sport_done")
    async def select_sport(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        user_id = callback.from_user.id
        sport_key = callback.data.replace("sport_", "")

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        if sport_key in user_selections[user_id]["sports"]:
            user_selections[user_id]["sports"].remove(sport_key)
        else:
            user_selections[user_id]["sports"].append(sport_key)

        keyboard = []
        for key, name in SPORTS:
            display_name = f"✅ {name}" if key in user_selections[user_id]["sports"] else name
            keyboard.append([InlineKeyboardButton(text=display_name, callback_data=f"sport_{key}")])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="sport_done")])

        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "sport_done")
    async def sport_done(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        user_id = callback.from_user.id
        selected_sports = user_selections.get(user_id, {}).get("sports", [])

        if not selected_sports:
            await callback.answer("❌ Выберите хотя бы один вид спорта!", show_alert=True)
            return

        keyboard = []
        for key, name in CONTENT_TYPES:
            display_name = f"✅ {name}" if key in user_selections[user_id]["content_types"] else name
            keyboard.append([InlineKeyboardButton(text=display_name, callback_data=f"content_{key}")])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="content_done")])

        await callback.message.edit_text(
            "📝 Выберите типы контента (можно несколько):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()

    # ---------- Выбор типов контента ----------
    @dp.callback_query(lambda c: c.data.startswith("content_") and c.data != "content_done")
    async def select_content(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        user_id = callback.from_user.id
        content_key = callback.data.replace("content_", "")

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        if content_key in user_selections[user_id]["content_types"]:
            user_selections[user_id]["content_types"].remove(content_key)
        else:
            user_selections[user_id]["content_types"].append(content_key)

        keyboard = []
        for key, name in CONTENT_TYPES:
            display_name = f"✅ {name}" if key in user_selections[user_id]["content_types"] else name
            keyboard.append([InlineKeyboardButton(text=display_name, callback_data=f"content_{key}")])
        keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="content_done")])

        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "content_done")
    async def content_done(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        user_id = callback.from_user.id
        selected_sports = user_selections.get(user_id, {}).get("sports", [])
        selected_types = user_selections.get(user_id, {}).get("content_types", [])

        if not selected_types:
            await callback.answer("❌ Выберите хотя бы один тип контента!", show_alert=True)
            return

        save_settings(user_id, selected_sports, selected_types)

        sport_names = [next((name for key, name in SPORTS if key == s), s) for s in selected_sports]
        type_names = [next((name for key, name in CONTENT_TYPES if key == t), t) for t in selected_types]

        await callback.message.edit_text(
            f"✅ **Настройки сохранены!**\n\n"
            f"**Виды спорта:** {', '.join(sport_names)}\n"
            f"**Типы контента:** {', '.join(type_names)}\n\n"
            f"Новости будут приходить каждые 60 минут."
        )
        await callback.answer()
        if user_id in user_selections:
            del user_selections[user_id]

    @dp.callback_query(lambda c: c.data == "cancel")
    async def process_cancel(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        user_id = callback.from_user.id
        await callback.message.edit_text("❌ **Настройка отменена.**")
        await callback.answer()
        if user_id in user_selections:
            del user_selections[user_id]

    # ---------- Читать полностью (разбивка) ----------
    @dp.callback_query(lambda c: c.data.startswith("full_"))
    async def full_article_callback(callback: types.CallbackQuery):
        if not await check_callback_access(callback):
            return
        url = get_url_from_callback(callback.data)
        if not url:
            await callback.answer("❌ Ссылка устарела", show_alert=True)
            return
        article = await extract_article_data(url)
        if not article:
            await callback.answer("❌ Не удалось загрузить полный текст", show_alert=True)
            return

        full_text = article['full_text']
        title = article['title']
        original_url = article['url']

        MAX_LEN = 4000
        chunks = []
        remaining = full_text
        first_chunk = f"**{title}**\n\n{remaining[:MAX_LEN - len(title) - 4]}"
        chunks.append(first_chunk)
        remaining = remaining[MAX_LEN - len(title) - 4:]

        while remaining:
            if len(remaining) <= MAX_LEN:
                chunks.append(remaining)
                break
            split_at = remaining.rfind('\n\n', 0, MAX_LEN)
            if split_at == -1:
                split_at = remaining.rfind('\n', 0, MAX_LEN)
            if split_at == -1:
                split_at = remaining.rfind(' ', 0, MAX_LEN)
            if split_at == -1 or split_at == 0:
                split_at = MAX_LEN
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip()

        total = len(chunks)
        sent_ok = 0
        for i, chunk in enumerate(chunks, 1):
            prefix = f"[{i}/{total}]\n\n" if total > 1 else ""
            suffix = f"\n\nЧитать на Sports.ru: {original_url}" if i == total else ""
            message_text = prefix + chunk + suffix
            success = await send_message(callback.from_user.id, message_text, parse_mode="Markdown")
            if success:
                sent_ok += 1
                await asyncio.sleep(0.25)   # защита от флуда
            else:
                logger.warning(f"Не удалось отправить часть {i}/{total} пользователю {callback.from_user.id}")

        await callback.answer(f"📖 Отправлено {sent_ok} из {total} част.")