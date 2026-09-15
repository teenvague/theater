"""Production images, resolved from show pages and cached in the repo.

A venue publishes an og:image so link previews of its show look right. That is
the image this uses. Direct venue pages are preferred; the linked production listing is a fallback.

Matching is deliberately strict. A page only supplies an image if its own
heading, structured event name, or metadata title matches the production. A wrong image
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
MIN_WIDTH, MIN_HEIGHT = 250, 160


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
    # Short page slugs commonly omit a subtitle (e.g. /tix/anon/).
    prefix = slug(title.split(':', 1)[0])
    abbreviated = [url for url in urls if len(prefix) >= 4 and slug(urlparse(url).path.rstrip('/').rsplit('/',1)[-1]) == prefix]
    return list(dict.fromkeys(exact + segment_hit + loose + abbreviated))


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


def title_matches(value: str, title: str) -> bool:
    target = slug(title)
    # Match a complete title or a separated branding suffix, never a substring
    # such as Hamlet inside Hamletmachine or Hamlet: A Different Production.
    value = re.sub(r'\s*\((?:Off-Broadway|Broadway),[^)]*\)', '', value or '', flags=re.I)
    return slug(value) == target or any(
        slug(part) == target for part in re.split(r'\s+[|–—]\s+|\s+[-]\s+', value or ''))


def generic_image(url: str) -> bool:
    name = urlparse(url).path.casefold()
    return any(token in name for token in ('placeholder', 'default-social', 'og-share',
               'explore-the-theatre', 'company-logo', 'theater-company-logo', 'main-logo', '/logo/', '_logo', '/logos/'))


def page_details(html: str, title: str, page_url: str = '') -> dict:
    """Read show-specific metadata, accepting site branding and structured data."""
    soup = BeautifulSoup(html, 'html.parser')
    def meta(prop):
        tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
        return (tag.get('content') or '').strip() if tag else ''
    titles = [meta('og:title'), meta('twitter:title')]
    titles += [tag.get_text(' ', strip=True) for tag in soup.find_all('h1')]
    if soup.title:
        titles.append(soup.title.get_text(' ', strip=True))
    structured = []
    def visit(value):
        if isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, dict):
            if title_matches(value.get('name', ''), title) and value.get('image'):
                image = value['image']
                if isinstance(image, list): image = image[0] if image else ''
                if isinstance(image, dict): image = image.get('url') or image.get('contentUrl') or ''
                if isinstance(image, str): structured.append(image)
            for key in ('@graph', 'mainEntity'):
                if key in value: visit(value[key])
    for tag in soup.select('script[type="application/ld+json"]'):
        try: visit(json.loads(tag.string or tag.get_text()))
        except (ValueError, TypeError): pass
    matches = any(title_matches(value, title) for value in titles)
    candidates = structured + ([(tag.get('content') or '') for tag in soup.select('meta[property="og:image"], meta[name="twitter:image"], meta[name="twitter:image:src"]')] if matches else [])
    # An explicitly labelled production image is safer than the first <img>,
    # which is often a logo or a headshot.
    if matches:
        for tag in soup.find_all('img'):
            if title_matches(tag.get('alt', ''), title):
                candidates.append(tag.get('src') or tag.get('data-src') or '')
    if matches and urlparse(page_url).netloc.endswith('mcctheater.org'):
        # Verified MCC production header, distinct from the cast gallery.
        header = soup.select_one('main img')
        if header: candidates.append(header.get('src', ''))
    urls = [urljoin(page_url, value).replace('http://', 'https://', 1) for value in candidates if value]
    image = next((url for url in urls if url.startswith('https://') and not generic_image(url)), '')
    return {'image': image, 'images': list(dict.fromkeys(u for u in urls if u.startswith('https://') and not generic_image(u))), 'description': summary(meta('og:description')) if matches else ''}


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
    report = {'resolved': 0, 'cached': 0, 'remote': [], 'unmatched': [], 'noSite': []}

    overrides_path = ROOT / 'data/image-overrides.json'
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    for production in productions:
        pid = production['id']
        venue = production['engagements'][0]['venue']
        remembered = catalog.get(pid, {})
        current = production.get('image', '')
        if generic_image(current):
            current = production['image'] = ''
        if current.startswith('images/') and (ROOT / 'dist' / current).is_file():
            report['resolved'] += 1
            continue
        if current.startswith('images/'):
            production['image'] = ''  # repair dangling references from older publishes
        if remembered and (ROOT / 'dist' / remembered.get('file', '')).is_file():
            production['image'] = remembered['file']
            production['imageSourceUrl'] = remembered['page']
            report['resolved'] += 1
            continue
        origin = sites.get(venue)
        override = overrides.get(pid, {})
        candidates = []
        for url, page in [(override.get('image'), override.get('page')),
                          (current if current.startswith('https://') else '', production['engagements'][0]['url']),
                          (remembered.get('source'), remembered.get('page'))]:
            if url: candidates.append((url, page or '', ''))
        pages = []
        if override.get('page'): pages.append(override['page'])
        # Direct show URLs are more precise and cheaper than sitemap discovery.
        pages += [e['url'] for e in production['engagements']
                  if origin and urlparse(e['url']).netloc.removeprefix('www.') == urlparse(origin).netloc.removeprefix('www.')]
        stored = None
        tried = set()
        def save_candidates():
            nonlocal stored
            for image_url, page, description in candidates:
                if image_url in tried: continue
                tried.add(image_url)
                try: stored = cache(image_url, get_bytes)
                except Exception: stored = None
                if not stored: continue
                production['image'] = stored
                production['imageSourceUrl'] = page
                catalog[pid] = {'file': stored, 'page': page, 'source': image_url,
                                'description': description}
                report['resolved'] += 1
                report['cached'] += 1
                return True
            return False
        if save_candidates(): continue
        if origin:
            if origin not in listings:
                listings[origin] = page_urls(origin, get)
                print(f'  sitemap {origin}: {len(listings[origin])} urls', flush=True)
            pages += candidate_pages(production['title'], listings[origin])[:6]
            if not pages:
                # Some venues have no usable sitemap. Inspect their navigation
                # for exact show links rather than inventing page URLs.
                try:
                    home = BeautifulSoup(get(origin), 'html.parser')
                    links = [urljoin(origin, a['href']) for a in home.find_all('a', href=True)]
                    pages += candidate_pages(production['title'], links)[:6]
                except Exception: pass
        else:
            report['noSite'].append(venue)
        # Preserve a record of the page and original asset. These are production
        # artwork references, not generic image-search matches or venue logos.
        pages += [e['url'] for e in production['engagements']]
        visited = set()
        for page in pages:
            if page in visited: continue
            visited.add(page)
            try:
                html = get(page)
                found = page_details(html, production['title'], page)
                if urlparse(page).netloc == 'playbill.com':
                    # The listing's official/ticket link often points to a
                    # producer website rather than the venue's website.
                    soup = BeautifulSoup(html, 'html.parser')
                    for a in soup.find_all('a', href=True):
                        href = urljoin(page, a['href'])
                        if a.get_text(' ', strip=True).casefold() == 'buy tickets' and href.startswith('https://') and urlparse(href).netloc != 'playbill.com':
                            if len(pages) < 16 and href not in pages: pages.append(href)
            except Exception: continue
            if found['image']:
                candidates += [(url, page, '') for url in found.get('images', [found['image']])]
                if save_candidates(): break
        if not stored and candidates:
            # Preserve the source URL when a CDN prevents server-side caching.
            # Report it separately; this is not a verified local asset.
            image_url, page, _ = candidates[0]
            production['image'] = image_url
            production['imageSourceUrl'] = page
            report['remote'].append({'title': production['title'], 'url': image_url})
            report['resolved'] += 1
        elif not stored:
            report['unmatched'].append(f"{production['title']} ({venue})")
        print(f"  image {production['title']}: {'cached' if stored else 'remote' if candidates else 'unresolved'}", flush=True)

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
    (ROOT / 'data').mkdir(parents=True, exist_ok=True)
    (ROOT / 'data/image-health.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
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
