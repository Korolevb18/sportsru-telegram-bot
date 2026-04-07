import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

async def fetch_html(url: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"Ошибка загрузки {url}: статус {response.status}")
                    return None
    except Exception as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None

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
    if '/blogs/' in url or '/tribuna/blogs/' in url:
        return 'blogs'
    if '/news/' in url:
        return 'news'
    return 'news'

async def fetch_news_links():
    """
    Парсит https://www.sports.ru/news/top/
    Возвращает список (url, published_at) для ВСЕХ новостей из сегодняшнего блока.
    Фильтрация по времени и дедупликация выполняются позже через sent_items.
    """
    url = 'https://www.sports.ru/news/top/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    now_msk = datetime.utcnow() + timedelta(hours=3)  # текущее время по Москве

    # Формируем сегодняшнюю дату как на сайте: "6 апреля"
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    today_str = f"{now_msk.day} {months[now_msk.month]}"

    # Находим все блоки short-news
    blocks = soup.find_all('div', class_='short-news')
    today_block = None

    # Ищем блок с сегодняшней датой (учитываем возможный пробел в конце)
    for block in blocks:
        b_tag = block.find('b')
        if b_tag:
            date_text = b_tag.get_text(strip=True)
            # Сравниваем по началу строки (на случай пробелов)
            if date_text.startswith(today_str):
                today_block = block
                break

    if not today_block:
        print("Не найден блок с сегодняшними новостями")
        return []

    items = []
    # Парсим все новости внутри сегодняшнего блока
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

        # Формируем дату публикации по Москве
        pub_date_msk = datetime(now_msk.year, now_msk.month, now_msk.day, hour, minute)
        # Если время больше текущего – значит новость вчерашняя (пропускаем, хотя по логике этого блока не должно быть)
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

        # Сохраняем в БД время в UTC
        pub_date_utc = pub_date_msk - timedelta(hours=3)
        items.append((href, pub_date_utc.isoformat()))

    return items

   

async def fetch_blogs_links():
    """
    Парсит https://www.sports.ru/tribuna/
    Возвращает список (url, published_at) для ВСЕХ постов блогов на первой странице.
    published_at используется только для информации, фильтрация по времени не применяется.
    """
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
        # Время публикации оставляем как есть (MSK), но для единообразия сохраняем в UTC
        pub_date_utc = None
        if datetime_attr:
            try:
                pub_date_msk = datetime.strptime(datetime_attr, '%Y-%m-%d %H:%M:%S')
                pub_date_utc = pub_date_msk - timedelta(hours=3)
            except:
                pass
        if not pub_date_utc:
            pub_date_utc = datetime.utcnow()  # fallback

        title_link = li.find('a', class_='h1')
        if not title_link:
            continue
        href = title_link.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.sports.ru' + href
        href = normalize_url(href)
        items.append((href, pub_date_utc.isoformat()))
    return items
    
async def fetch_mainpage_banners():
    """
    Парсит главную страницу https://www.sports.ru/
    Возвращает список (url, published_at) для трёх баннеров (supertop-1,2,3).
    Время публикации не указано, поэтому используем текущее время как published_at.
    """
    url = 'https://www.sports.ru/'
    html = await fetch_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, 'lxml')
    items = []
    now_utc = datetime.utcnow()
    
    # Ищем все ссылки с data-analytics-category, начинающимся на "supertop-"
    for i in range(1, 4):  # supertop-1, supertop-2, supertop-3
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
        # Для баннеров время не указано, ставим текущее UTC
        items.append((href, now_utc.isoformat()))
    return items

async def fetch_mainpage_fresh_links():
    """
    Парсит главную страницу https://www.sports.ru/
    Возвращает список (url, published_at) для ВСЕХ материалов из .material-list__item-text.
    """
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
        items.append((href, pub_date_utc.isoformat()))
    return items