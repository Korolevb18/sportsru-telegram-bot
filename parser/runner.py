# runner.py
import asyncio
import sys
from pathlib import Path
import logging

sys.path.append(str(Path(__file__).parent.parent))

from logger_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

from db.database import (
    init_db, clean_old_sent_items, clean_old_callbacks,
    get_allowed_users, is_item_sent, mark_sent, load_settings
)
from parser.fetcher import (
    fetch_news_links,
    fetch_blogs_links,
    fetch_mainpage_banners,
    fetch_mainpage_fresh_links,
    detect_sport_from_url,
    clear_html_cache,
    close_session,
)
from parser.extractor import extract_article_data
from bot.sender import send_message, send_preview

async def send_type_header(user_id, header_text, sent_headers_dict):
    """Отправляет заголовок группы, если ещё не отправлен в рамках текущего пользователя."""
    key = f"{user_id}_{header_text}"
    if key not in sent_headers_dict:
        await send_message(user_id, header_text, parse_mode="Markdown")
        sent_headers_dict[key] = True

async def run_parser():
    logger.info("Парсер запущен...")
    init_db()
    clean_old_sent_items(days=7)
    clean_old_callbacks(days=7)

    # 1. Получаем все ссылки из разных источников
    news_items = await fetch_news_links()
    blog_items = await fetch_blogs_links()
    top_publications = await fetch_mainpage_banners()
    fresh_publications = await fetch_mainpage_fresh_links()

    # 2. Объединяем все ссылки с определением типа контента
    all_items = {}  # url -> (pub_date, content_type)

    def add_items(items_list, content_type):
        for url, pub_date in items_list:
            if url in all_items:
                existing_date, existing_type = all_items[url]
                # Приоритет top_publications: если новый тип top_publications, а существующий — нет, оставляем top_publications
                if content_type == 'top_publications' and existing_type != 'top_publications':
                    all_items[url] = (pub_date, 'top_publications')
                # Иначе обновляем дату (более ранняя), тип не меняем
                elif pub_date < existing_date:
                    all_items[url] = (pub_date, existing_type)
            else:
                all_items[url] = (pub_date, content_type)

    add_items(news_items, 'news')
    add_items(blog_items, 'blogs')
    add_items(top_publications, 'top_publications')
    add_items(fresh_publications, 'fresh_publications')

    # Диагностический вывод ВСЕХ топ-публикаций после дедупликации
    top_urls = [url for url, (_, ctype) in all_items.items() if ctype == 'top_publications']
    logger.info(f"Топ-публикации после дедупликации: {len(top_urls)} шт.")
    for turl in top_urls:
        logger.info(f"  TOP URL: {turl}")

    logger.info(f"Всего уникальных URL после дедупликации: {len(all_items)}")
    logger.info(f"  - Новости: {len(news_items)}")
    logger.info(f"  - Блоги: {len(blog_items)}")
    logger.info(f"  - Топ-публикации: {len(top_publications)}")
    logger.info(f"  - Свежие публикации: {len(fresh_publications)}")

    # 3. Обрабатываем каждого пользователя
    ALLOWED_USERS = get_allowed_users()
    if not ALLOWED_USERS:
        logger.warning("Нет разрешённых пользователей!")

    for user_id in ALLOWED_USERS:
        logger.info(f"Обработка пользователя {user_id}")
        user_sports, user_types = load_settings(user_id)
        logger.info(f"  Настройки: sports={user_sports}, types={user_types}")

        # Группируем по типу контента для отправки заголовков
        items_by_type = {
            'news': [],
            'blogs': [],
            'top_publications': [],
            'fresh_publications': []
        }

        for url, (pub_date, content_type) in all_items.items():
            # Проверка подписки на тип контента
            if content_type not in user_types and '*' not in user_types:
                continue
            # Проверка вида спорта
            sport = detect_sport_from_url(url)
            if '*' not in user_sports and sport not in user_sports:
                continue
            # Проверка, не отправлялось ли ранее (теперь для всех типов)
            if content_type == 'top_publications':
                if is_item_sent(url, user_id):
                    logger.info(f"Топ-публикация уже отправлена ранее: {url} (спорт={sport})")
                    continue
                else:
                    logger.info(f"Топ-публикация будет обработана: {url} (спорт={sport})")
            else:
                if is_item_sent(url, user_id):
                    continue
            items_by_type[content_type].append((url, pub_date))

        total_sent = 0
        sent_headers = {}

        type_order = [
            ('news', '📰📰📰 НОВОСТИ 📰📰📰'),
            ('top_publications', '⭐⭐⭐ ТОП-ПУБЛИКАЦИИ ⭐⭐⭐'),
            ('fresh_publications', '🆕🆕🆕 СВЕЖИЕ ПУБЛИКАЦИИ 🆕🆕🆕'),
            ('blogs', '✍️✍️✍️ БЛОГИ ✍️✍️✍️')
        ]

        for content_type, header in type_order:
            items = items_by_type[content_type]
            if not items:
                continue

            await send_type_header(user_id, f"**{header}**", sent_headers)
            sent_count = 0

            for idx, (url, pub_date) in enumerate(items, 1):
                logger.debug(f"Извлекаем данные: {url}")
                article = await extract_article_data(url)
                if article:
                    success = await send_preview(user_id, article, content_type)
                    if success:
                        mark_sent(url, user_id, pub_date)
                        sent_count += 1
                        logger.info(f"Отправлено {content_type}: {article['title']} (пользователь {user_id})")
                        await asyncio.sleep(0.7)
                        if sent_count % 20 == 0:
                            await asyncio.sleep(2.0)
                    else:
                        logger.warning(f"Не удалось отправить {content_type}: {article['title']} (пользователь {user_id})")
                else:
                    logger.error(f"Не удалось извлечь данные из {url}")

            total_sent += sent_count
            logger.info(f"Отправлено в группе '{header}': {sent_count}")

        logger.info(f"Всего отправлено пользователю {user_id}: {total_sent}")

    # Очищаем кэш HTML и закрываем сессию aiohttp
    clear_html_cache()
    await close_session()
    logger.info("Парсер завершил работу")

if __name__ == "__main__":
    asyncio.run(run_parser())