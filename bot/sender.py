from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

async def send_message(user_id: int, text: str, parse_mode: str = None, reply_markup=None):
    try:
        await bot.send_message(user_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        return True
    except Exception as e:
        print(f"Ошибка отправки сообщения {user_id}: {e}")
        return False

async def send_photo(user_id: int, photo_url: str, caption: str, parse_mode: str = None, reply_markup=None):
    try:
        await bot.send_photo(user_id, photo_url, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        return True
    except Exception as e:
        print(f"Ошибка отправки фото {user_id}: {e}")
        return False

async def send_preview(user_id, article, content_type):
    title = article['title']
    url = article['url']
    
    # Выбираем эмодзи в зависимости от типа контента
    if content_type == 'news':
        emoji = "📰"
    elif content_type == 'blogs':
        emoji = "✍️"
    elif content_type in ('top_publications', 'fresh_publications'):
        emoji = "⭐"
    else:
        emoji = "📌"
    
    # Заголовок заглавными буквами
    header = f"{emoji} {title.upper()}"
    
    if content_type == 'news':
        # Для новостей: полный текст
        text_content = article['full_text']
        if not text_content or text_content == "Не удалось извлечь текст.":
            text_content = article['preview_text']
        
        # Создаём подпись
        caption = f"{header}\n\n{text_content}\n\nЧитать на Sports.ru: {url}"
        
        # Обрезаем, если длиннее 1024 символов
        if len(caption) > 1024:
            caption = caption[:1000] + "\n\n(полный текст – по ссылке ниже)\n\nЧитать на Sports.ru: " + url
        
        if article['cover_image']:
            return await send_photo(user_id, article['cover_image'], caption, parse_mode=None)
        else:
            return await send_message(user_id, caption, parse_mode=None)
    
    else:
        # Для публикаций: анонс (первые 300 символов)
        preview = article['preview_text']
        if not preview or len(preview.strip()) == 0:
            preview = article['full_text'][:300] if article['full_text'] else "Материал"
        
        # Создаём подпись
        caption = f"{header}\n\n{preview}...\n\nЧитать на Sports.ru: {url}"
        
        # Обрезаем, если длиннее 1024 символов
        if len(caption) > 1024:
            caption = caption[:1000] + "\n\n(полный текст – по ссылке ниже)\n\nЧитать на Sports.ru: " + url
        
        # Отправляем фото с подписью
        if article['cover_image']:
            await send_photo(user_id, article['cover_image'], caption, parse_mode=None)
        else:
            await send_message(user_id, caption, parse_mode=None)
        
        # Отправляем отдельное сообщение с кнопкой
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Читать полностью", callback_data=f"full_{article['url']}")]
        ])
        return await send_message(user_id, "🔘 Подробнее", parse_mode=None, reply_markup=keyboard)