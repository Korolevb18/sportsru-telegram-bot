import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from parser.fetcher import fetch_html, parse_main_page, detect_sport_and_type
from parser.extractor import extract_article_data
from db.database import is_item_sent, mark_sent, load_settings
from bot.main import bot, dp, ALLOWED_USERS  # для отправки сообщений


async def send_news_to_user(user_id, article):
    """Отправляет новость пользователю"""
    text = f"**{article['title']}**\n\n{article['preview_text']}...\n\n[▶️ Читать полностью]({article['url']})"
    try:
        if article['cover_image']:
            await bot.send_photo(user_id, article['cover_image'], caption=text, parse_mode='Markdown')
        else:
            await bot.send_message(user_id, text, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка отправки пользователю {user_id}: {e}")


async def run_parser():
    print("Парсер запущен...")
    html = await fetch_html('https://sports.ru/')
    if not html:
        print("Не удалось загрузить главную страницу")
        return

    links = parse_main_page(html)
    print(f"Найдено ссылок: {len(links)}")

    for user_id in ALLOWED_USERS:
        user_sports, user_types = load_settings(user_id)
        print(f"Обработка пользователя {user_id}, спорт: {user_sports}, типы: {user_types}")

        for link in links:
            sport, content_type = detect_sport_and_type(link)

            # Проверяем, подходит ли новость под настройки пользователя
            if ('*' not in user_sports and sport not in user_sports) or \
                    ('*' not in user_types and content_type not in user_types):
                continue

            if is_item_sent(link, user_id):
                continue

            article = await extract_article_data(link)
            if article:
                await send_news_to_user(user_id, article)
                mark_sent(link, user_id)
                print(f"Отправлено пользователю {user_id}: {article['title']}")

    print("Парсер завершил работу")


if __name__ == "__main__":
    asyncio.run(run_parser())