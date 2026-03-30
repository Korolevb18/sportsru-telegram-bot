from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from db.database import save_settings, load_settings

# Список всех видов спорта
SPORTS = {
    "football": "⚽ Футбол",
    "hockey": "🏒 Хоккей",
    "basketball": "🏀 Баскетбол",
    "tennis": "🎾 Теннис",
    "biathlon": "🎯 Биатлон",
    "figure_skating": "⛸ Фигурное катание",
    "boxing_mma": "🥊 Бокс/MMA",
    "autosport": "🏎 Автоспорт",
    "other": "📰 Прочее"
}

# Список типов контента
CONTENT_TYPES = {
    "news": "📰 Новости",
    "longreads": "📖 Материалы",
    "blogs": "✍️ Блоги"
}

# Временное хранилище для выбора пользователя (в реальном проекте лучше использовать FSM)
user_selections = {}


def get_sports_keyboard(selected_sports=None):
    """Создаёт клавиатуру с выбором видов спорта"""
    if selected_sports is None:
        selected_sports = []

    keyboard = []
    row = []
    for i, (key, name) in enumerate(SPORTS.items(), 1):
        # Если спорт уже выбран, добавляем галочку
        display_name = f"✅ {name}" if key in selected_sports else name
        row.append(InlineKeyboardButton(text=display_name, callback_data=f"sport_{key}"))

        # Каждые 2 кнопки — новая строка
        if i % 2 == 0:
            keyboard.append(row)
            row = []

    # Добавляем последнюю строку, если осталась
    if row:
        keyboard.append(row)

    # Добавляем кнопки управления
    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="sport_done"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_content_keyboard(selected_types=None):
    """Создаёт клавиатуру с выбором типов контента"""
    if selected_types is None:
        selected_types = []

    keyboard = []
    for key, name in CONTENT_TYPES.items():
        display_name = f"✅ {name}" if key in selected_types else name
        keyboard.append([InlineKeyboardButton(text=display_name, callback_data=f"content_{key}")])

    keyboard.append([
        InlineKeyboardButton(text="✅ Готово", callback_data="content_done"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def register_handlers(dp: Dispatcher):
    """Регистрирует все обработчики"""

    @dp.message(Command("settings"))
    async def cmd_settings(message: types.Message):
        """Настройка подписок"""
        user_id = message.from_user.id

        # Загружаем текущие настройки
        sports, content_types = load_settings(user_id)

        # Сохраняем в временное хранилище
        user_selections[user_id] = {
            "sports": sports if sports != ["*"] else [],
            "content_types": content_types if content_types != ["*"] else []
        }

        await message.answer(
            "🎯 **Настройка подписок**\n\n"
            "Выберите виды спорта, которые вас интересуют:\n"
            "(можно выбрать несколько)",
            reply_markup=get_sports_keyboard(user_selections[user_id]["sports"]),
            parse_mode="Markdown"
        )

    @dp.callback_query(lambda c: c.data.startswith("sport_"))
    async def process_sport_selection(callback: types.CallbackQuery):
        user_id = callback.from_user.id

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        sport_key = callback.data.replace("sport_", "")

        if sport_key in user_selections[user_id]["sports"]:
            user_selections[user_id]["sports"].remove(sport_key)
        else:
            user_selections[user_id]["sports"].append(sport_key)

        await callback.message.edit_reply_markup(
            reply_markup=get_sports_keyboard(user_selections[user_id]["sports"])
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "sport_done")
    async def process_sport_done(callback: types.CallbackQuery):
        user_id = callback.from_user.id

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        selected_sports = user_selections[user_id]["sports"]

        if not selected_sports:
            await callback.answer("❌ Выберите хотя бы один вид спорта!", show_alert=True)
            return

        await callback.message.edit_text(
            "📝 **Выберите типы контента:**\n\n"
            "Что вы хотите получать?",
            reply_markup=get_content_keyboard(user_selections[user_id]["content_types"]),
            parse_mode="Markdown"
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("content_"))
    async def process_content_selection(callback: types.CallbackQuery):
        user_id = callback.from_user.id

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        content_key = callback.data.replace("content_", "")

        if content_key in user_selections[user_id]["content_types"]:
            user_selections[user_id]["content_types"].remove(content_key)
        else:
            user_selections[user_id]["content_types"].append(content_key)

        await callback.message.edit_reply_markup(
            reply_markup=get_content_keyboard(user_selections[user_id]["content_types"])
        )
        await callback.answer()

    @dp.callback_query(lambda c: c.data == "content_done")
    async def process_content_done(callback: types.CallbackQuery):
        user_id = callback.from_user.id

        if user_id not in user_selections:
            user_selections[user_id] = {"sports": [], "content_types": []}

        selected_types = user_selections[user_id]["content_types"]

        if not selected_types:
            await callback.answer("❌ Выберите хотя бы один тип контента!", show_alert=True)
            return

        # Сохраняем настройки в БД
        save_settings(user_id, user_selections[user_id]["sports"], user_selections[user_id]["content_types"])

        # Формируем сообщение с подтверждением
        sports_text = ", ".join([SPORTS[s] for s in user_selections[user_id]["sports"]])
        types_text = ", ".join([CONTENT_TYPES[t] for t in user_selections[user_id]["content_types"]])

        await callback.message.edit_text(
            f"✅ **Настройки сохранены!**\n\n"
            f"**Виды спорта:** {sports_text}\n"
            f"**Типы контента:** {types_text}\n\n"
            f"Новости будут приходить каждые 30 минут.",
            parse_mode="Markdown"
        )
        await callback.answer()

        # Очищаем временные данные
        if user_id in user_selections:
            del user_selections[user_id]

    @dp.callback_query(lambda c: c.data == "cancel")
    async def process_cancel(callback: types.CallbackQuery):
        user_id = callback.from_user.id

        await callback.message.edit_text(
            "❌ **Настройка отменена.**\n\n"
            "Вы можете начать заново с помощью команды /settings",
            parse_mode="Markdown"
        )
        await callback.answer()

        # Очищаем временные данные
        if user_id in user_selections:
            del user_selections[user_id]