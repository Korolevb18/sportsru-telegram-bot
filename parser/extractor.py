from bs4 import BeautifulSoup
from parser.fetcher import fetch_html
import re

async def extract_article_data(url: str):
    """Извлекает заголовок, полный текст, превью и обложку из страницы новости/блога"""
    html = await fetch_html(url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'lxml')

    # Заголовок
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else "Без заголовка"

    # Обложка
    cover_image = None
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        cover_image = og_image['content']

    # Текст – ищем контейнер
    content_div = (
        soup.find('div', class_='structured-body-wrapper') or
        soup.find('div', class_='news-item__text') or
        soup.find('div', class_='article__content') or
        soup.find('div', class_='content') or
        soup.find('div', class_='post-content') or
        soup.find('article') or
        soup.find('div', class_='text') or
        soup.find('div', class_='entry-content')
    )

    full_text = ""
    preview_text = ""

    if content_div:
        # Удаляем мусор
        for unwanted in content_div.find_all(['script', 'style', 'aside', 'div'], 
                                             class_=['banner', 'ad', 'share', 'comments', 'recommendations']):
            unwanted.decompose()
        
        # Находим все параграфы
        paragraphs = content_div.find_all('p')
        if paragraphs:
            processed_paragraphs = []
            for p in paragraphs:
                # Получаем текст, НЕ удаляем пробелы по краям
                p_text = p.get_text(strip=False)
                # Только удаляем квадратные скобки
                p_text = re.sub(r'[\[\]]', '', p_text)
                # Не делаем strip() – сохраняем пробелы в начале/конце
                if p_text:
                    processed_paragraphs.append(p_text)
            # Объединяем с двумя переносами строки
            full_text = '\n\n'.join(processed_paragraphs)
            # preview – первые 300 символов полного текста
            preview_text = full_text[:300]
        else:
            full_text = content_div.get_text(strip=False)
            full_text = re.sub(r'[\[\]]', '', full_text)
            preview_text = full_text[:300]
        
    else:
        # Fallback
        meta_desc = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            full_text = meta_desc['content']
            preview_text = full_text[:300]

    if not full_text:
        full_text = "Не удалось извлечь текст."
        preview_text = full_text

    # Финальная очистка от скобок
    full_text = re.sub(r'[\[\]]', '', full_text)
    preview_text = re.sub(r'[\[\]]', '', preview_text)

    return {
        'title': title,
        'full_text': full_text,
        'preview_text': preview_text,
        'cover_image': cover_image,
        'url': url
    }