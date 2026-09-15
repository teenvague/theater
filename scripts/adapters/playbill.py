"""Playbill listings, filtered to a curated venue registry.

Only facts are taken — title, venue, dates, type tags and the production URL.
Synopses, editorial copy and images stay on Playbill.

Two passes: a section index gives title / venue / link for every current
production; the detail page gives first preview, opening and closing dates.
Detail pages are only fetched for productions at venues in the registry, so a
run costs roughly as many requests as there are shows you actually track.
"""
from __future__ import annotations
import re
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from net import fetch as http_get

BASE = 'https://playbill.com'
SECTIONS = {'offbroadway': f'{BASE}/shows/offbroadway', 'broadway': f'{BASE}/shows/broadway'}
MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def norm(value: str) -> str:
    """Casefold and flatten punctuation so 'St. Ann's' matches 'St. Ann’s'."""
    value = unicodedata.normalize('NFKD', value or '')
    value = value.replace('’', "'").replace('‘', "'")
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def parse_index(html: str) -> list[dict]:
    """Title, venue and link for each production card in a section listing."""
    soup = BeautifulSoup(html, 'html.parser')
    best, best_count = None, 0
    for node in soup.find_all(['div', 'section', 'ul', 'ol', 'main']):
        count = sum(1 for kid in node.find_all(recursive=False)
                    if kid.find('a', href=re.compile(r'^/production/')))
        if count > best_count:
            best, best_count = node, count
    if not best:
        return []

    rows = []
    for card in best.find_all(recursive=False):
        link = card.find('a', href=re.compile(r'^/production/'))
        if not link:
            continue
        lines = [line.strip() for line in card.get_text('\n').split('\n') if line.strip()]
        lines = [l for l in lines if l not in ('View Details', 'Buy Tickets')]
        if not lines:
            continue
        # The status line is optional: a card without one puts the venue second.
        status = lines[1] if len(lines) > 2 and _is_status(lines[1]) else ''
        venue = lines[2] if status else (lines[1] if len(lines) > 1 else '')
        rows.append({'title': lines[0], 'status': status, 'venue': venue,
                     'url': urljoin(BASE, link['href'])})
    return rows


def _is_status(line: str) -> bool:
    return bool(re.search(r'\b(closes|opens|begins previews|in previews|open run)\b', line, re.I))


def parse_detail(html: str) -> dict:
    """First preview / opening / closing dates and type tags from a production page."""
    soup = BeautifulSoup(html, 'html.parser')
    dates: dict[str, str] = {}
    for item in soup.select('ul.bsp-list-promo-list li'):
        label = item.select_one('.bsp-list-promo-title')
        circle = item.select_one('.info-circular')
        if not label or not circle:
            continue
        key = norm(label.get_text())
        if key in dates:
            continue                      # responsive duplicates of the same block
        month = circle.select_one('.info-circular-pre-text')
        day = circle.select_one('.info-circular-text')
        year = circle.select_one('.info-circular-post-text')
        if not (month and day and year):
            continue
        try:
            value = datetime(int(year.get_text().strip()),
                             MONTHS[month.get_text().strip()[:3].lower()],
                             int(day.get_text().strip())).date().isoformat()
        except (KeyError, ValueError):
            continue
        dates[key] = value

    tags = [t.get_text(strip=True) for t in soup.select('.production-tags a, .production-tags span')]
    body = soup.get_text('\n')
    credits = []
    author = re.search(r'PLAYWRIGHT:\s*([^\n]+)', body, re.I)
    director = re.search(r'Directed by\s+([^\n]+)', body, re.I)
    if author:
        credits.append(author.group(1).strip().title())
    if director:
        credits.append('Directed by ' + director.group(1).strip())
    return {
        'credits': ' \u00b7 '.join(credits),
        'firstPreview': dates.get('first preview'),
        'openingDate': dates.get('opening date'),
        'closingDate': dates.get('closing date'),
        'types': [t.title() for t in tags if t],
    }


def match_venue(playbill_venue: str, registry: list[dict]) -> dict | None:
    """Map a Playbill venue string onto a curated venue by longest matching alias."""
    haystack = norm(playbill_venue)
    winner, best_len = None, 0
    for venue in registry:
        for alias in venue.get('playbill', []):
            needle = norm(alias)
            if needle and needle in haystack and len(needle) > best_len:
                winner, best_len = venue, len(needle)
    return winner


def collect(source: dict, registry: list[dict], get=http_get) -> list[dict]:
    """Productions at registry venues, in the repository's production schema."""
    seen, productions = set(), []
    for section in source.get('sections', list(SECTIONS)):
        for card in parse_index(get(SECTIONS[section])):
            venue = match_venue(card['venue'], registry)
            if not venue or card['url'] in seen:
                continue
            seen.add(card['url'])
            detail = parse_detail(get(card['url']))
            start = detail['firstPreview'] or detail['openingDate']
            if not start:
                continue          # no verifiable start date: skip rather than guess
            slug = card['url'].rstrip('/').rsplit('/', 1)[-1]
            productions.append({
                'id': f'playbill:{slug}',
                'title': card['title'],
                'credits': detail.get('credits', ''),
                'image': '',
                'types': detail['types'] or [section.replace('offbroadway', 'Off-Broadway').title()],
                'description': '',
                'runtimeMinutes': None,
                'company': venue['name'],
                'engagements': [{
                    'id': f'playbill:{slug}:{venue["id"]}',
                    'venue': venue['name'],
                    'neighborhood': venue.get('neighborhood', 'New York'),
                    'sourceId': source['id'],
                    'sourceUrl': SECTIONS[section],
                    'url': card['url'],
                    'startDate': start,
                    'openingDate': detail['openingDate'],
                    'closingDate': detail['closingDate'],
                    'status': 'scheduled',
                }],
            })
    return productions


def fetch(source):
    import json
    from pathlib import Path
    registry = json.loads((Path(__file__).resolve().parents[2] / 'data/sources.json').read_text())['sources']
    return collect(source, [v for v in registry if v.get('playbill')])
