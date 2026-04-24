from bs4 import BeautifulSoup
from parser.fetcher import fetch_html
import re
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

def extract_video_urls(soup, base_url: str) -> list:
    video_links = set()

    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        if not src:
            continue
        if src.startswith('/'):
            src = urljoin(base_url, src)
        if 'youtube.com/embed/' in src or 'youtu.be/' in src or 'youtube.com/watch' in src:
            video_links.add(src)
        elif 'video.sports.ru' in src:
            video_links.add(src)

    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if 'video.sports.ru/video/' in full_url or 'youtube.com/watch' in full_url or 'youtu.be/' in full_url:
            video_links.add(full_url)

    og_video = soup.find('meta', property='og:video')
    if og_video and og_video.get('content'):
        content = og_video['content']
        if content.startswith('/'):
            content = urljoin(base_url, content)
        video_links.add(content)

    return list(video_links)[:3]


def extract_image_urls(soup, base_url: str, cover_image: str = None) -> list:
    images = []
    seen = set()

    def add_image(url):
        if not url:
            return
        full_url = urljoin(base_url, url)
        # Игнорируем служебные и мелкие изображения, включая photobooth
        if any(x in full_url.lower() for x in ['pixel', '1x1', 'blank', 'icon', 'logo', 'fill/32/', 'fill/64/',
                                                  'photobooth.cdn.sports.ru']):
            return
        if 'pictures.cdn.sports.ru' in full_url and ('fill/32' in full_url or 'fill/64' in full_url):
            return
        if full_url not in seen:
            seen.add(full_url)
            images.append(full_url)

    if cover_image:
        add_image(cover_image)

    content_div = (
        soup.find('div', class_='structured-body-wrapper') or
        soup.find('div', class_='news-item__text') or
        soup.find('div', class_='article__content') or
        soup.find('div', class_='content') or
        soup.find('div', class_='post-content') or
        soup.find('article') or
        soup.find('div', class_='text') or
        soup.find('div', class_='entry-content') or
        soup.find('div', class_='blog-post__content') or
        soup.find('div', class_='material-content')
    )

    if content_div:
        for img in content_div.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original')
            add_image(src)

    return images[:10]


def clean_photo_credits(text: str) -> str:
    patterns = ['Фото:', 'Photo:', 'Иллюстрация:', 'Illustration:', 'Источник:', 'Source:']
    cut_pos = -1
    for pat in patterns:
        pos = text.rfind(pat)
        if pos > cut_pos:
            cut_pos = pos
    if cut_pos > 0 and cut_pos > len(text) * 0.8:
        text = text[:cut_pos].strip()
    text = re.sub(r'\n\s*\n+$', '', text)
    return text.strip()


async def extract_article_data(url: str):
    html = await fetch_html(url)
    if not html:
        logger.warning(f"Не удалось загрузить HTML для {url}")
        return None
    soup = BeautifulSoup(html, 'lxml')

    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else "Без заголовка"

    cover_image = None
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        cover_image = og_image['content']

    content_div = (
        soup.find('div', class_='structured-body-wrapper') or
        soup.find('div', class_='news-item__text') or
        soup.find('div', class_='article__content') or
        soup.find('div', class_='content') or
        soup.find('div', class_='post-content') or
        soup.find('article') or
        soup.find('div', class_='text') or
        soup.find('div', class_='entry-content') or
        soup.find('div', class_='blog-post__content') or
        soup.find('div', class_='material-content')
    )

    full_text = ""
    preview_text = ""

    if content_div:
        for unwanted in content_div.find_all(['script', 'style', 'aside', 'div'],
                                             class_=['banner', 'ad', 'share', 'comments', 'recommendations']):
            unwanted.decompose()
        paragraphs = content_div.find_all('p')
        if paragraphs:
            processed_paragraphs = []
            for p in paragraphs:
                p_text = p.get_text(strip=False)
                p_text = re.sub(r'[\[\]]', '', p_text)
                if p_text:
                    processed_paragraphs.append(p_text)
            full_text = '\n\n'.join(processed_paragraphs)
            preview_text = full_text[:300]
        else:
            full_text = content_div.get_text(strip=False)
            full_text = re.sub(r'[\[\]]', '', full_text)
            preview_text = full_text[:300]
    else:
        meta_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            full_text = meta_desc['content']
            preview_text = full_text[:300]

    if not full_text:
        full_text = "Не удалось извлечь текст."
        preview_text = full_text

    full_text = re.sub(r'[\[\]]', '', full_text)
    preview_text = re.sub(r'[\[\]]', '', preview_text)

    full_text = clean_photo_credits(full_text)

    video_urls = extract_video_urls(soup, url)
    all_images = extract_image_urls(soup, url, cover_image)

    if title == "Без заголовка" and full_text == "Не удалось извлечь текст.":
        logger.warning(f"Пропущена страница без контента: {url}")
        return None

    return {
        'title': title,
        'full_text': full_text,
        'preview_text': preview_text,
        'cover_image': cover_image,
        'url': url,
        'video_urls': video_urls,
        'all_images': all_images,
    }