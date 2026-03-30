from bs4 import BeautifulSoup
from parser.fetcher import fetch_html


async def extract_article_data(url: str):
    """Извлекает заголовок, текст, обложку и фото из статьи"""
    html = await fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'lxml')

    # Заголовок (пробуем разные варианты)
    title = soup.find('h1')
    if title:
        title = title.get_text(strip=True)
    else:
        title = "Без заголовка"

    # Текст статьи
    content_div = soup.find('article') or soup.find('div', class_='content') or soup.find('div',
                                                                                          class_='article__content')
    if content_div:
        paragraphs = content_div.find_all('p')
        full_text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs])
        preview_text = paragraphs[0].get_text(strip=True)[:300] if paragraphs else full_text[:300]
    else:
        full_text = "Не удалось извлечь текст"
        preview_text = full_text[:300]

    # Обложка
    cover_image = None
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        cover_image = og_image['content']

    # Все фото внутри статьи
    images = []
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src')
        if src and src.startswith('http') and not src.endswith('.svg'):
            images.append(src)

    return {
        'title': title,
        'full_text': full_text,
        'preview_text': preview_text,
        'cover_image': cover_image,
        'images': images[:5],  # не более 5 фото
        'url': url
    }