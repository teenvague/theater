"""Park Avenue Armory season listings.

Playbill does not carry the Armory: it presents rather than running an
Off-Broadway house, so it needs its own adapter.

Season pages are three segments deep (/season-events/<year>-season/<slug>/).
Talks, lectures and recitals sit a level deeper under a series, so depth alone
separates the productions from the ancillary programming.
"""
from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from net import fetch as http_get

BASE = 'https://www.armoryonpark.org'
SEASON = f'{BASE}/season-events/current-season/'
PRODUCTION_PATH = re.compile(r'^/season-events/\d{4}-season/[^/]+/$')
RANGE = re.compile(
    r'([A-Z][a-z]+ \d{1,2}, \d{4})\s*[-–—]\s*([A-Z][a-z]+ \d{1,2}, \d{4})')
SINGLE = re.compile(r'([A-Z][a-z]+ \d{1,2}, \d{4})')


def _date(value: str) -> str:
    return datetime.strptime(value.strip(), '%B %d, %Y').date().isoformat()


def parse_season(html: str) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    paths = []
    for link in soup.find_all('a', href=True):
        href = link['href'].split('?')[0]
        if PRODUCTION_PATH.match(href) and href not in paths:
            paths.append(href)
    return paths


def parse_production(html: str) -> dict | None:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.find('h1')
    dates = soup.select_one('.ace-pdp-dates')
    if not title or not dates:
        return None

    text = dates.get_text(' ', strip=True)
    span = RANGE.search(text)
    if span:
        start, closing = _date(span.group(1)), _date(span.group(2))
    else:
        one = SINGLE.search(text)
        if not one:
            return None                    # no parseable date: skip rather than guess
        start = closing = _date(one.group(1))

    def meta(prop):
        tag = soup.find('meta', attrs={'property': prop})
        return (tag.get('content') or '').strip() if tag else ''

    # The hall is printed after the dates in the same block.
    hall = RANGE.sub('', text).strip(' -–—')
    return {
        'title': title.get_text(strip=True),
        'startDate': start,
        'closingDate': closing,
        'hall': hall,
        'image': meta('og:image'),
    }


def collect(source: dict, venue: dict, get=http_get) -> list[dict]:
    productions = []
    for path in parse_season(get(SEASON)):
        url = urljoin(BASE, path)
        record = parse_production(get(url))
        if not record:
            continue
        slug = path.rstrip('/').rsplit('/', 1)[-1]
        productions.append({
            'id': f'armory:{slug}',
            'title': record['title'],
            'credits': '',
            'image': record['image'],
            'types': ['Performance'],
            'description': '',
            'runtimeMinutes': None,
            'company': venue['name'],
            'engagements': [{
                'id': f'armory:{slug}:{venue["id"]}',
                'venue': venue['name'],
                'neighborhood': venue.get('neighborhood', 'Upper East Side'),
                'sourceId': source['id'],
                'sourceUrl': SEASON,
                'url': url,
                'startDate': record['startDate'],
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
    venue = next(v for v in registry if v['id'] == 'park-avenue-armory')
    return collect(source, venue)
