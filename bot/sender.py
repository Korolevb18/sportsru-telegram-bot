# bot/sender.py
import asyncio
import hashlib
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))
from db.database import save_callback_id, get_url_by_callback_id

logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)


def _make_short_id(url: str, prefix: str) -> str:
    hash_obj = hashlib.md5(url.encode())
    short = hash_obj.hexdigest()[:8]
    callback_data = f"{prefix}_{short}"
    save_callback_id(callback_data, url)
    return callback_data


def get_url_from_callback(callback_data: str) -> str | None:
    return get_url_by_callback_id(callback_data)


async def send_message(user_id: int, text: str, parse_mode: str = None, reply_markup=None):
    try:
        await bot.send_message(user_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения {user_id}: {e}")
        return False


async def send_photo(user_id: int, photo_url: str, caption: str, parse_mode: str = None, reply_markup=None):
    try:
        await bot.send_photo(user_id, photo_url, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки фото {user_id}: {e}")
        return False


async def send_media_group(user_id: int, media: list, caption: str = None):
    try:
        input_media = []
        for i, img_url in enumerate(media):
            if i == 0 and caption:
                input_media.append(InputMediaPhoto(media=img_url, caption=caption))
            else:
                input_media.append(InputMediaPhoto(media=img_url))
        await bot.send_media_group(user_id, media=input_media)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки альбома {user_id}: {e}")
        return False


def _truncate_caption(base_text: str, max_len: int, url: str) -> str:
    footer = f"\n\nЧитать на Sports.ru: {url}"
    available = max_len - len(footer)
    if available <= 0:
        return footer.strip()
    if len(base_text) <= available:
        return base_text + footer
    truncated = base_text[:available]
    if ' ' in truncated:
        truncated = truncated[:truncated.rfind(' ')]
    return truncated + footer


async def send_preview(user_id, article, content_type):
    title = article['title']
    url = article['url']
    all_images = article.get('all_images', [])
    video_urls = article.get('video_urls', [])

    # Эмодзи и префикс
    if content_type == 'news':
        emoji = "📰"
        prefix = ""
    elif content_type == 'blogs':
        emoji = "✍️"
        prefix = ""
    elif content_type == 'top_publications':
        emoji = "⭐"
        prefix = "⭐ ТОП-ПУБЛИКАЦИЯ ⭐\n🏆 "
    elif content_type == 'fresh_publications':
        emoji = "🆕"
        prefix = ""
    else:
        emoji = "📌"
        prefix = ""

    header = f"{emoji} {prefix}{title.upper()}"

    # Кнопки
    keyboard_rows = []
    action_buttons = []

    if content_type != 'news':
        short_full = _make_short_id(url, "full")
        action_buttons.append(InlineKeyboardButton(text="📖 Читать полностью", callback_data=short_full))

    for idx, video_url in enumerate(video_urls, 1):
        label = f"🎬 Видео {idx}" if len(video_urls) > 1 else "🎬 Смотреть видео"
        action_buttons.append(InlineKeyboardButton(text=label, url=video_url))

    if action_buttons:
        keyboard_rows.append(action_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None

    # Текст
    if content_type == 'news':
        text_content = article['full_text']
        if not text_content or text_content == "Не удалось извлечь текст.":
            text_content = article['preview_text']
        base_caption = f"{header}\n\n{text_content}"
    else:
        preview = article['preview_text']
        if not preview or len(preview.strip()) == 0:
            preview = article['full_text'][:300] if article['full_text'] else "Материал"
        base_caption = f"{header}\n\n{preview}..."

    max_caption_len = 1024
    full_caption = _truncate_caption(base_caption, max_caption_len, url)

    # Отправка
    if len(all_images) > 1:
        success_album = await send_media_group(user_id, all_images, caption=None)
        if success_album:
            await asyncio.sleep(1.5)  # увеличенная начальная пауза
            msg_success = await send_message(user_id, full_caption, parse_mode=None, reply_markup=reply_markup)
            # Повторные попытки с экспоненциальной задержкой
            for attempt in range(2):  # ещё 2 попытки (всего 3)
                if msg_success:
                    break
                delay = 2.0 * (attempt + 1)  # 2 сек, потом 4 сек
                logger.warning(f"Повторная попытка отправить текст после альбома для {url} через {delay}с")
                await asyncio.sleep(delay)
                msg_success = await send_message(user_id, full_caption, parse_mode=None, reply_markup=reply_markup)
            if not msg_success:
                logger.error(f"Окончательно не удалось отправить текст после альбома для {url}")
            return success_album and msg_success
        else:
            return False
    elif len(all_images) == 1:
        return await send_photo(user_id, all_images[0], full_caption, parse_mode=None, reply_markup=reply_markup)
    else:
        return await send_message(user_id, full_caption, parse_mode=None, reply_markup=reply_markup)