from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from db.database import save_settings, load_settings
from parser.extractor import extract_article_data
from bot.sender import send_message

# Список всех видов спорта
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

def register_handlers(dp: Dispatcher):
    user_selections = {}

    @dp.message(Command("settings"))
    async def cmd_settings(message: types.Message):
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

    @dp.callback_query(lambda c: c.data.startswith("sport_") and c.data != "sport_done")
    async def select_sport(callback: types.CallbackQuery):
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

    @dp.callback_query(lambda c: c.data.startswith("content_") and c.data != "content_done")
    async def select_content(callback: types.CallbackQuery):
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
            f"Новости будут приходить каждые 30 минут."
        )
        await callback.answer()
        
        if user_id in user_selections:
            del user_selections[user_id]

    @dp.callback_query(lambda c: c.data == "cancel")
    async def process_cancel(callback: types.CallbackQuery):
        user_id = callback.from_user.id
        await callback.message.edit_text(
            "❌ **Настройка отменена.**\n\n"
            "Вы можете начать заново с помощью команды /settings"
        )
        await callback.answer()
        if user_id in user_selections:
            del user_selections[user_id]

    @dp.callback_query(lambda c: c.data.startswith("full_"))
    async def full_article_callback(callback: types.CallbackQuery):
        """Обработчик кнопки 'Читать полностью' – отправляем обычный текст без Markdown"""
        url = callback.data.replace("full_", "")
        print(f"DEBUG: Нажата кнопка с URL: {url}")
        
        article = await extract_article_data(url)
        if not article:
            await callback.answer("❌ Не удалось загрузить полный текст", show_alert=True)
            return
        
        # Формируем сообщение без Markdown
        full_text = f"{article['title']}\n\n{article['full_text']}\n\nЧитать на Sports.ru: {article['url']}"
        
        # Обрезаем, если длиннее 3500 символов
        if len(full_text) > 3500:
            full_text = full_text[:3450] + "\n\n...(текст обрезан)\n\nЧитать на Sports.ru: " + article['url']
        
        try:
            success = await send_message(callback.from_user.id, full_text, parse_mode=None)
            if success:
                await callback.answer("📖 Полный текст отправлен!")
            else:
                await callback.answer("❌ Ошибка отправки", show_alert=True)
        except Exception as e:
            print(f"Ошибка при отправке полного текста: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)