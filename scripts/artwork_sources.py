"""Automatic artwork discovery in the public NYC TodayTix catalog.

No per-production URLs or image overrides are required. A catalog card only
suggests a detail page: title, venue and overlapping engagement dates must be
confirmed in that page's structured metadata before its artwork is accepted.
"""
from __future__ import annotations
import html
import json
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

INDEXES = (
    'https://www.todaytix.com/nyc/category/off-broadway-shows',
    'https://www.todaytix.com/nyc/category/plays',
    'https://www.todaytix.com/nyc/category/all-shows',
)


def normalize(value):
    value = unicodedata.normalize('NFKD', html.unescape(value or '')).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', value.replace('&', ' and ')).strip()


def objects(value):
    if isinstance(value, list):
        for item in value:
            yield from objects(item)
    elif isinstance(value, dict):
        yield value
        if '@graph' in value:
            yield from objects(value['@graph'])


def metadata(soup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from objects(json.loads(script.string or script.get_text()))
        except (TypeError, ValueError):
            continue


def image_url(value, page):
    if isinstance(value, list):
        value = value[0] if value else ''
    if isinstance(value, dict):
        value = value.get('url') or value.get('contentUrl') or ''
    if not isinstance(value, str):
        return ''
    url = urljoin(page, value) if value else ''
    return url if urlparse(url).scheme == 'https' else ''


def matching_artwork(markup, production, registry, page):
    nodes = list(metadata(BeautifulSoup(markup, 'html.parser')))
    title = normalize(production['title'])
    products = [n for n in nodes if n.get('@type') == 'Product' and normalize(n.get('name')) == title]
    events = [n for n in nodes if n.get('@type') in ('TheaterEvent', 'Event')]
    for event in events:
        location = event.get('location')
        if not isinstance(location, dict):
            continue
        performer = event.get('performer')
        performer_name = performer.get('name') if isinstance(performer, dict) else ''
        event_name = normalize(event.get('name'))
        venue_name = normalize(location.get('name'))
        if normalize(performer_name) != title and event_name not in (title, title + ' ' + venue_name):
            continue
        try:
            start = date.fromisoformat(event['startDate'][:10])
            end = date.fromisoformat(event['endDate'][:10])
            if end < start:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        for engagement in production['engagements']:
            venue = next((v for v in registry if v.get('name') == engagement['venue']), {})
            aliases = [engagement['venue'], *venue.get('playbill', []), *venue.get('imageAliases', [])]
            # Accept exact names or a named substage, not an arbitrary substring.
            if not any(venue_name == normalize(a) or venue_name.startswith(normalize(a) + ' ') for a in aliases if normalize(a)):
                continue
            first = date.fromisoformat(engagement['startDate'])
            last = date.fromisoformat(engagement['closingDate']) if engagement.get('closingDate') else date.max
            if first > end or start > last:
                continue
            for value in [event.get('image'), *[p.get('image') for p in products]]:
                url = image_url(value, page)
                if url:
                    return {'image': url, 'page': page, 'method': 'todaytix-title-venue-dates'}
    return None


class TicketArtwork:
    """One catalog fetch per index per refresh, only matched details are read."""
    def __init__(self, get, registry):
        self.get = get
        self.registry = registry
        self.cards = {}
        self.loaded = set()
        self.details = {}
        self.errors = []

    def load(self, index):
        if index in self.loaded:
            return
        self.loaded.add(index)
        try:
            soup = BeautifulSoup(self.get(index), 'html.parser')
            for anchor in soup.find_all('a', href=True):
                page = urljoin(index, anchor['href'])
                parsed = urlparse(page)
                if parsed.scheme != 'https' or parsed.netloc != 'www.todaytix.com' or not parsed.path.startswith('/nyc/shows/'):
                    continue
                picture = anchor.find('img', alt=True)
                # Title-only links and image alt text are stable across CSS changes.
                label = picture['alt'] if picture else anchor.get_text(' ', strip=True)
                if label:
                    self.cards.setdefault(normalize(label), set()).add(page)
        except Exception as exc:
            self.errors.append({'page': index, 'error': str(exc)})

    def find(self, production):
        visited = set()
        for index in INDEXES:
            self.load(index)
            for page in sorted(self.cards.get(normalize(production['title']), set())):
                if page in visited:
                    continue
                visited.add(page)
                if page not in self.details:
                    try:
                        self.details[page] = self.get(page)
                    except Exception as exc:
                        self.details[page] = ''
                        self.errors.append({'page': page, 'error': str(exc)})
                result = matching_artwork(self.details[page], production, self.registry, page)
                if result:
                    return result
        return None
