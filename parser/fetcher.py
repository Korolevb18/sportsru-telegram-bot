import aiohttp
import asyncio
from bs4 import BeautifulSoup


async def fetch_html(url: str) -> str | None:
    """Загружает HTML страницы по URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"Ошибка загрузки {url}: статус {response.status}")
                    return None
    except Exception as e:
        print(f"Ошибка при запросе {url}: {e}")
        return None


def parse_main_page(html: str):
    """Парсит главную страницу sports.ru, возвращает список ссылок на материалы"""
    soup = BeautifulSoup(html, 'lxml')
    links = []

    # Ищем все ссылки на материалы (упрощённый вариант — все ссылки с /news/, /articles/, /blog/)
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(prefix in href for prefix in ['/news/', '/articles/', '/blog/', '/tribuna/']):
            if href.startswith('/'):
                href = 'https://sports.ru' + href
            links.append(href)

    # Убираем дубликаты
    return list(set(links))


def detect_sport_and_type(url: str):
    """Определяет вид спорта и тип контента по URL"""
    sport = 'other'
    content_type = 'news'

    if '/football/' in url:
        sport = 'football'
    elif '/hockey/' in url:
        sport = 'hockey'
    elif '/basketball/' in url:
        sport = 'basketball'
    elif '/tennis/' in url:
        sport = 'tennis'
    elif '/biathlon/' in url:
        sport = 'biathlon'
    elif '/figure_skating/' in url:
        sport = 'figure_skating'
    elif '/boxing/' in url or '/mma/' in url:
        sport = 'boxing_mma'
    elif '/autosport/' in url or '/formula1/' in url:
        sport = 'autosport'

    if '/articles/' in url:
        content_type = 'longreads'
    elif '/blog/' in url or '/tribuna/' in url:
        content_type = 'blogs'

    return sport, content_type