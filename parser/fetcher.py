import aiohttp
from bs4 import BeautifulSoup
import re
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Кэш HTML-страниц (на один запуск)
_html_cache = {}

# Глобальная сессия aiohttp для переиспользования
_session = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0'})
    return _session

async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()

async def fetch_html(url: str, use_cache: bool = True, max_retries: int = 2) -> str | None:
    """
    Загружает HTML с повторными попытками при временных ошибках (500, 502, 503, 504 и т.п.).
    """
    if use_cache and url in _html_cache:
        logger.debug(f"Использован кэш для {url}")
        return _html_cache[url]

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            session = await get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    if use_cache:
                        _html_cache[url] = html
                    return html
                elif response.status in (500, 502, 503, 504):
                    # временная ошибка сервера – можно повторить
                    last_error = f"статус {response.status}"
                    logger.warning(f"Попытка {attempt+1}/{max_retries+1} для {url}: {last_error}")
                else:
                    logger.error(f"Ошибка загрузки {url}: статус {response.status}")
                    return None
        except Exception as e:
            last_error = str(e)
            logger.error(f"Ошибка при запросе {url}: {e}")
            # при сетевых ошибках тоже пробуем повторить
        if attempt < max_retries:
            await asyncio.sleep(2.0)  # пауза перед повтором

    logger.error(f"Не удалось загрузить {url} после {max_retries+1} попыток: {last_error}")
    return None

def clear_html_cache():
    global _html_cache
    _html_cache.clear()

def normalize_url(url: str) -> str:
    url = url.split('#')[0]
    url = url.split('?')[0]
    return url

def detect_sport_from_url(url: str) -> str:
    if '/football/' in url: return 'football'
    if '/hockey/' in url: return 'hockey'
    if '/basketball/' in url: return 'basketball'
    if '/tennis/' in url: return 'tennis'
    if '/biathlon/' in url: return 'biathlon'
    if '/figure_skating/' in url: return 'figure_skating'
    if '/boxing/' in url or '/mma/' in url: return 'boxing_mma'
    if '/autosport/' in url or '/formula1/' in url: return 'autosport'
    return 'other'

def detect_content_type(url: str) -> str:
    if '/blogs/' in url or '/tribuna/blogs/' in url or '/post/' in url:
        return 'blogs'
    if '/news/' in url:
        return 'news'
    return 'news'

def is_competition_url(url: str) -> bool:
    patterns = ['/picker/', '/special/', 'm.sports.ru/picker', 'sports.ru/special', 'specials.sports.ru']
    url_lower = url.lower()
    return any(p in url_lower for p in patterns)

async def fetch_news_links():
    url = 'https://www.sports.ru/news/top/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    now_msk = datetime.utcnow() + timedelta(hours=3)

    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    today_str = f"{now_msk.day} {months[now_msk.month]}"

    blocks = soup.find_all('div', class_='short-news')
    today_block = None
    for block in blocks:
        b_tag = block.find('b')
        if b_tag:
            date_text = b_tag.get_text(strip=True)
            if date_text.startswith(today_str):
                today_block = block
                break

    if not today_block:
        logger.warning("Не найден блок с сегодняшними новостями")
        return []

    items = []
    for p in today_block.find_all('p'):
        time_span = p.find('span', class_='time')
        if not time_span:
            continue
        time_str = time_span.get_text(strip=True)
        if ':' not in time_str:
            continue
        hour_str, minute_str = time_str.split(':')
        try:
            hour = int(hour_str)
            minute = int(minute_str)
        except:
            continue

        pub_date_msk = datetime(now_msk.year, now_msk.month, now_msk.day, hour, minute)
        if pub_date_msk > now_msk:
            continue

        link = p.find('a', class_='short-text')
        if not link:
            continue
        href = link.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.sports.ru' + href
        href = normalize_url(href)

        if is_competition_url(href):
            continue

        pub_date_utc = pub_date_msk - timedelta(hours=3)
        items.append((href, pub_date_utc.isoformat()))
    return items

async def fetch_blogs_links():
    url = 'https://www.sports.ru/tribuna/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    items = []

    for li in soup.find_all('li', class_='blog-feed__item'):
        time_tag = li.find('time', class_='time-block time-block_top')
        if not time_tag:
            continue
        datetime_attr = time_tag.get('datetime')
        pub_date_utc = None
        if datetime_attr:
            try:
                pub_date_msk = datetime.strptime(datetime_attr, '%Y-%m-%d %H:%M:%S')
                pub_date_utc = pub_date_msk - timedelta(hours=3)
            except:
                pass
        if not pub_date_utc:
            pub_date_utc = datetime.utcnow()

        title_link = li.find('a', class_='h1')
        if not title_link:
            continue
        href = title_link.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.sports.ru' + href
        href = normalize_url(href)

        if is_competition_url(href):
            continue

        items.append((href, pub_date_utc.isoformat()))
    return items

async def fetch_mainpage_banners():
    url = 'https://www.sports.ru/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    items = []
    now_utc = datetime.utcnow()

    for i in range(1, 4):
        selector = f'a[data-analytics-category="supertop-{i}"]'
        link = soup.select_one(selector)
        if not link:
            continue
        href = link.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.sports.ru' + href
        href = normalize_url(href)

        if is_competition_url(href):
            continue

        items.append((href, now_utc.isoformat()))
    return items

async def fetch_mainpage_fresh_links():
    url = 'https://www.sports.ru/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    items = []

    for block in soup.find_all('div', class_='material-list__item-text'):
        time_tag = block.find('time', class_='time-block')
        pub_date_utc = None
        if time_tag and time_tag.get('datetime'):
            try:
                pub_date_msk = datetime.strptime(time_tag['datetime'], '%Y-%m-%d %H:%M:%S')
                pub_date_utc = pub_date_msk - timedelta(hours=3)
            except:
                pass
        if not pub_date_utc:
            pub_date_utc = datetime.utcnow()

        title_link = block.find('a', class_='material-list__title-link')
        if not title_link:
            continue
        href = title_link.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.sports.ru' + href
        href = normalize_url(href)

        if is_competition_url(href):
            continue

        items.append((href, pub_date_utc.isoformat()))
    return items