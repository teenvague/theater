"""Cherry Lane Theatre.

Playbill carries at most one Cherry Lane show at a time; the venue's own site
carries the whole season, which is the reason this adapter exists.

Show pages are discovered from the sitemap, which also lists past events, so
runs that have already closed are dropped by date rather than by guessing from
the slug. Each page prints a month-level range ("October-November, 2026") and a
list of individual performances ("Oct 7", "Nov 8") with no year on them. The
run is taken from the first and last performance; the year comes from the range.
"""
from __future__ import annotations
import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from net import fetch as http_get

BASE = 'https://cherrylanetheatre.org'
SITEMAP = f'{BASE}/sitemap.xml'
SHOW_URL = re.compile(r'<loc>\s*(https://(?:www\.)?cherrylanetheatre\.org/shows/[^<\s]+)\s*</loc>')
PERFORMANCE = re.compile(r'^([A-Z][a-z]{2}) (\d{1,2})$')
YEARS = re.compile(r'(20\d\d)')
RANGE_TEXT = re.compile(r'([A-Z][a-z]+)[^A-Za-z0-9]*(20\d\d)?\s*[-\u2013\u2014]\s*([A-Z][a-z]+)?[^A-Za-z0-9]*(20\d\d)?')
MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def show_urls(sitemap_xml: str) -> list[str]:
    seen = []
    for url in SHOW_URL.findall(sitemap_xml):
        url = url.replace('://www.', '://')
        if url not in seen and not url.rstrip('/').endswith('/shows'):
            seen.append(url)
    return seen


def _performances(soup) -> list[tuple[int, int]]:
    out = []
    for node in soup.select('.heading-md'):
        hit = PERFORMANCE.match(node.get_text(strip=True))
        if hit and hit.group(1).lower() in MONTHS:
            out.append((MONTHS[hit.group(1).lower()], int(hit.group(2))))
    return out


def _range_span(soup):
    """(month, year) the run began, from the month-level range line.

    The performance list only carries dates still to come, so a show already
    running would otherwise look like it had not started.
    """
    for node in soup.find_all(['p', 'span', 'div', 'h2', 'h3']):
        if node.find():
            continue
        text = node.get_text(' ', strip=True)
        if len(text) >= 60 or not YEARS.search(text) or not re.search(r'[-\u2013\u2014]', text):
            continue
        hit = RANGE_TEXT.search(text)
        if not hit:
            continue
        month = MONTHS.get((hit.group(1) or '')[:3].lower())
        years = [int(y) for y in YEARS.findall(text)]
        if month and years:
            return month, years[0]
    return None


def _range_years(soup) -> list[int]:
    for node in soup.find_all(['p', 'span', 'div', 'h2', 'h3']):
        if node.find():
            continue
        text = node.get_text(' ', strip=True)
        if len(text) < 60 and YEARS.search(text) and re.search(r'[-–—]', text):
            years = [int(y) for y in YEARS.findall(text)]
            if years:
                return years
    return []


def production_copy(soup):
    """Read the show's rich text, excluding navigation and newsletter copy."""
    block=soup.select_one('.freetext-richtext')
    paragraphs=[p.get_text(' ',strip=True) for p in block.find_all('p')] if block else []
    credits=[]
    description=[]
    for text in paragraphs:
        if not text:continue
        if re.match(r'^(by\b|written\b|directed\b|starring\b|developed\b|and Cherry Lane)',text,re.I):
            credits.append(text.rstrip('. '))
        else:description.append(text)
    return {'credits':' · '.join(credits),'description':' '.join(description)}

def parse_show(html: str) -> dict | None:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1')
    performances = _performances(soup)
    years = _range_years(soup)
    if not title or not performances or not years:
        return None

    span = _range_span(soup)

    # Months run forward through the season; a decrease means the new year.
    year = years[0]
    dated, previous_month = [], performances[0][0]
    for month, day in performances:
        if month < previous_month:
            year = years[-1] if len(years) > 1 else year + 1
        previous_month = month
        try:
            dated.append(date(year, month, day))
        except ValueError:
            continue
    if not dated:
        return None

    start = min(dated)
    precision = 'day'
    if span:
        range_month, range_year = span
        # A run that began before its remaining performances starts at the month
        # the range names. The day is not published, so the first is used; the
        # closing date stays exact.
        if (range_year, range_month) < (start.year, start.month):
            start = date(range_year, range_month, 1)
            precision = 'month'

    image = ''
    for tag in soup.find_all('img'):
        src = tag.get('src') or tag.get('data-src') or ''
        if src.startswith('https://cdn.sanity.io/'):
            image = src
            break

    return {
        **production_copy(soup),
        'title': title.get_text(strip=True),
        'startDate': start.isoformat(),
        'startDatePrecision': precision,
        'closingDate': max(dated).isoformat(),
        'performances': len(dated),
        'image': image,
    }


def collect(source: dict, venue: dict, get=http_get, today=None) -> list[dict]:
    from summaries import one_line
    today = today or date.today()
    productions = []
    try:
        listing = show_urls(get(SITEMAP))
    except Exception as exc:
        raise ValueError(f'sitemap unavailable: {exc}') from exc

    failures = 0
    for url in listing:
        # The sitemap lists years of past events and some of those pages error.
        # One broken page must not cost the whole venue.
        try:
            record = parse_show(get(url))
        except Exception as exc:
            failures += 1
            print(f'  cherry-lane: skipped {url} ({exc})', flush=True)
            if failures > 12:
                print('  cherry-lane: too many bad pages; stopping early', flush=True)
                break
            continue
        if not record:
            continue
        if datetime.fromisoformat(record['closingDate']).date() < today:
            continue                        # already closed; the sitemap keeps past shows
        slug = url.rstrip('/').rsplit('/', 1)[-1]
        productions.append({
            'id': f'cherry-lane:{slug}',
            'title': record['title'],
            'credits': record['credits'],
            'image': record['image'],
            'types': ['Off-Broadway'],
            'description': one_line(record['description']),
            'runtimeMinutes': None,
            'company': venue['name'],
            'engagements': [{
                'id': f'cherry-lane:{slug}:{venue["id"]}',
                'venue': venue['name'],
                'neighborhood': venue.get('neighborhood', 'West Village'),
                'sourceId': source['id'],
                'sourceUrl': f'{BASE}/shows',
                'url': url,
                'startDate': record['startDate'],
                'startDatePrecision': record['startDatePrecision'],
                'openingDate': None,
                'closingDate': record['closingDate'],
                'status': 'scheduled',
            }],
        })
    return productions


def fetch(source):
    import json
    from pathlib import Path
    registry = json.loads((Path(__file__).resolve().parents[2] / 'data/sources.json').read_text())['sources']
    venue = next(v for v in registry if v['id'] == 'cherry-lane-theatre')
    return collect(source, venue)
