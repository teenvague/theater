"""Production images, taken from the venue's own page and cached in the repo.

A venue publishes an og:image so link previews of its show look right. That is
the image this uses. Nothing is taken from an aggregator.

Matching is deliberately strict. A page only supplies an image if its own
og:title matches the production title once both are normalized. A wrong image
on a listing is worse than no image, and the front end already falls back to
text.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from net import fetch as http_get, fetch_bytes

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'dist/data/images.json'
STORE = ROOT / 'dist/images'
MIN_WIDTH, MIN_HEIGHT = 500, 250


def slug(value: str) -> str:
    value = (value or '').casefold().replace('&', ' and ')
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def sitemap_locations(origin: str, get=http_get) -> list[str]:
    """Sitemap URLs for a site, from robots.txt with the conventional fallback."""
    try:
        robots = get(urljoin(origin, '/robots.txt'))
    except Exception:
        robots = ''
    found = re.findall(r'(?im)^\s*sitemap:\s*(\S+)', robots)
    return found or [urljoin(origin, '/sitemap.xml')]


def page_urls(origin: str, get=http_get, depth: int = 1) -> list[str]:
    """Every page URL a site's sitemap advertises, following one level of index."""
    urls: list[str] = []
    for location in sitemap_locations(origin, get):
        try:
            xml = get(location)
        except Exception:
            continue
        locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', xml)
        if depth and '<sitemapindex' in xml:
            for nested in locs[:20]:
                try:
                    urls += re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', get(nested))
                except Exception:
                    continue
        else:
            urls += locs
    return urls


def candidate_pages(title: str, urls: list[str]) -> list[str]:
    """Pages that look like they are about this production.

    Exact slug matches on the last path segment first, then any segment, then a
    containment match for sites that suffix or prefix the slug. Ordering matters
    because only the first few are fetched, and every candidate still has to pass
    the og:title check before its image is used.
    """
    target = slug(title)
    if len(target) < 4:
        return []
    exact, segment_hit, loose = [], [], []
    for url in urls:
        segments = [slug(part) for part in urlparse(url).path.strip('/').split('/') if part]
        if not segments:
            continue
        if segments[-1] == target:
            exact.append(url)
        elif target in segments:
            segment_hit.append(url)
        elif any(target in part and len(part) < len(target) + 24 for part in segments):
            loose.append(url)
    return exact + segment_hit + loose


def summary(text: str, limit: int = 170) -> str:
    """One sentence, trimmed. A listing line, not a reproduction of the copy."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    if not text:
        return ''
    sentence = re.split(r'(?<=[.!?])\s', text)[0]
    if len(sentence) > limit:
        sentence = sentence[:limit].rsplit(' ', 1)[0].rstrip(',;:') + '\u2026'
    return sentence


def boilerplate(text: str, title: str, venue: str) -> bool:
    """True when a description is the venue's site-wide blurb, not this show's.

    Many sites set og:title per page but leave og:description as the house
    boilerplate, which otherwise reads as a synopsis of the wrong thing.
    """
    lowered = slug(text)
    if slug(venue) and slug(venue) in lowered:
        return True
    house = ('is new york', 'award winning off broadway home', 'our mission',
             'founded in', 'is a non profit', 'is a nonprofit', 'tickets and information',
             'subscribe', 'official site', 'official website')
    return any(phrase.replace(' ', '-') in lowered for phrase in house) and slug(title) not in lowered


def page_details(html: str, title: str) -> dict:
    """The venue's own og:image and og:description, if the page is this show."""
    soup = BeautifulSoup(html, 'html.parser')

    def meta(prop):
        tag = soup.find('meta', attrs={'property': prop})
        return (tag.get('content') or '').strip() if tag else ''

    page_title = meta('og:title') or (soup.find('h1').get_text(strip=True) if soup.find('h1') else '')
    if slug(page_title) != slug(title):
        return {'image': '', 'description': ''}
    image = meta('og:image')
    return {
        'image': image if image.startswith('https://') else '',
        'description': summary(meta('og:description')),
    }


def image_from_page(html: str, title: str) -> str:
    return page_details(html, title)['image']


def cache(url: str, get_bytes=fetch_bytes) -> str | None:
    """Download once, keep as JPEG, return the path the site should reference."""
    from PIL import Image

    name = 'images/' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.jpg'
    destination = ROOT / 'dist' / name
    if destination.exists():
        return name
    raw = get_bytes(url)
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
            return None
        image = image.convert('RGB')
        image.thumbnail((1200, 1200))
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, 'JPEG', quality=88, optimize=True)
    return name


def attach(productions: list[dict], registry: list[dict], get=http_get, get_bytes=fetch_bytes) -> dict:
    """Fill in missing images from each venue's own site. Returns a report."""
    catalog = json.loads(CATALOG.read_text()) if CATALOG.exists() else {}
    sites = {v['name']: v['site'] for v in registry if v.get('site')}
    listings: dict[str, list[str]] = {}
    report = {'resolved': 0, 'cached': 0, 'unmatched': [], 'noSite': []}

    for production in productions:
        if production.get('image'):
            continue
        venue = production['engagements'][0]['venue']
        remembered = catalog.get(production['id'])
        if remembered:
            production['image'] = remembered['file']
            production['imageSourceUrl'] = remembered['page']
            if remembered.get('description') and not production.get('description'):
                production['description'] = remembered['description']
            report['resolved'] += 1
            continue
        origin = sites.get(venue)
        if not origin:
            report['noSite'].append(venue)
            continue
        if origin not in listings:
            listings[origin] = page_urls(origin, get)
            print(f'  sitemap {origin}: {len(listings[origin])} urls', flush=True)
        image_url = page = description = ''
        for url in candidate_pages(production['title'], listings[origin])[:4]:
            try:
                found = page_details(get(url), production['title'])
            except Exception:
                continue
            if found['image'] or found['description']:
                image_url, description, page = found['image'], found['description'], url
                break
        if description and not production.get('description'):
            if not boilerplate(description, production['title'], venue):
                production['description'] = description
            else:
                description = ''
        if not image_url:
            report['unmatched'].append(f"{production['title']} ({venue})")
            continue
        try:
            stored = cache(image_url, get_bytes)
        except Exception:
            stored = None
        if not stored:
            report['unmatched'].append(f"{production['title']} ({venue}) - image rejected")
            continue
        production['image'] = stored
        production['imageSourceUrl'] = page
        catalog[production['id']] = {'file': stored, 'page': page, 'source': image_url,
                                     'description': description}
        report['resolved'] += 1
        report['cached'] += 1

    # Any description shared by two productions at one venue is the house blurb.
    by_venue: dict[tuple, list] = {}
    for production in productions:
        text = production.get('description')
        if text:
            key = (production['engagements'][0]['venue'], text)
            by_venue.setdefault(key, []).append(production)
    for (_, _text), shared in by_venue.items():
        if len(shared) > 1:
            for production in shared:
                production['description'] = ''
                entry = catalog.get(production['id'])
                if entry:
                    entry['description'] = ''

    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n')
    return report


def prune(productions: list[dict]) -> dict:
    """Delete cached images nothing references any more.

    This stops the repository growing. It does not shrink it: every file ever
    committed stays in git history until that history is rewritten.
    """
    referenced = {p['image'] for p in productions if (p.get('image') or '').startswith('images/')}
    removed = []
    if STORE.exists():
        for file in sorted(STORE.iterdir()):
            if file.is_file() and f'images/{file.name}' not in referenced:
                file.unlink()
                removed.append(file.name)

    catalog = json.loads(CATALOG.read_text()) if CATALOG.exists() else {}
    kept = {key: value for key, value in catalog.items() if value.get('file') in referenced}
    if kept != catalog:
        CATALOG.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + '\n')
    return {'removed': len(removed), 'kept': len(referenced)}
