import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from parser.fetcher import (
    fetch_news_links, fetch_blogs_links, fetch_mainpage_banners, fetch_mainpage_fresh_links,
    detect_sport_from_url
)
from parser.extractor import extract_article_data
from db.database import is_item_sent, mark_sent, load_settings
from bot.sender import send_message, send_photo, send_preview   # <-- добавить send_message

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

# Словарь для отслеживания отправленных заголовков типов в текущем запуске
sent_headers = {}

async def send_type_header(user_id, header_text):
    """Отправляет заголовок для группы материалов, если ещё не отправляли"""
    key = f"{user_id}_{header_text}"
    if key not in sent_headers:
        await send_message(user_id, header_text, parse_mode="Markdown")
        sent_headers[key] = True

async def process_feed(user_id, items, feed_type, type_name):
    """
    Обрабатывает список материалов, отправляет их с заголовком группы.
    feed_type: 'news', 'blogs', 'top_publications', 'fresh_publications'
    type_name: отображаемое название (например, 'НОВОСТИ')
    """
    user_sports, user_types = load_settings(user_id)
    if feed_type not in user_types and '*' not in user_types:
        return 0
    sent = 0
    first_in_group = True
    for url, pub_date in items:
        sport = detect_sport_from_url(url)
        if '*' not in user_sports and sport not in user_sports:
            continue
        if is_item_sent(url, user_id):
            continue
        article = await extract_article_data(url)
        if article:
            # Отправляем заголовок группы перед первым материалом
            if first_in_group:
                await send_type_header(user_id, f"**{type_name}**")
                first_in_group = False
            success = await send_preview(user_id, article, feed_type)
            if success:
                mark_sent(url, user_id, pub_date)
                sent += 1
                print(f"    ✅ Отправлено {feed_type}: {article['title']}")
            else:
                print(f"    ⚠️ Не удалось отправить {feed_type}: {article['title']} (пользователь {user_id})")
        else:
            print(f"    ❌ Не удалось извлечь: {url}")
    return sent

async def run_parser():
    print("Парсер запущен...")
    news_items = await fetch_news_links()                     # без minutes
    blog_items = await fetch_blogs_links()                    # без minutes
    top_publications = await fetch_mainpage_banners()         # без изменений
    fresh_publications = await fetch_mainpage_fresh_links()   # без minutes

    await asyncio.sleep(0.1)
    print(f"Найдено новостей за сегодня: {len(news_items)}")
    print(f"Найдено блогов (всего на странице): {len(blog_items)}")
    print(f"Найдено топ-публикаций (баннеров): {len(top_publications)}")
    print(f"Найдено свежих публикаций (всего на главной): {len(fresh_publications)}")

    for user_id in ALLOWED_USERS:
        print(f"\nОбработка пользователя {user_id}")
        total = 0
        # Очищаем счётчик отправленных заголовков для каждого пользователя
        global sent_headers
        sent_headers = {}
        
        total += await process_feed(user_id, news_items, 'news', '📰 НОВОСТИ')
        total += await process_feed(user_id, top_publications, 'top_publications', '⭐ ТОП-ПУБЛИКАЦИИ')
        total += await process_feed(user_id, fresh_publications, 'fresh_publications', '🆕 СВЕЖИЕ ПУБЛИКАЦИИ')
        total += await process_feed(user_id, blog_items, 'blogs', '✍️ БЛОГИ')
        
        print(f"  Отправлено всего: {total}")
    print("\nПарсер завершил работу")

if __name__ == "__main__":
    asyncio.run(run_parser())