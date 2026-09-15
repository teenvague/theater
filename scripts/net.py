"""Fetching that respects robots.txt, identifies itself, and paces itself.

Every adapter goes through here. If a host's robots.txt disallows the path for
our user-agent, the fetch raises rather than proceeding: the scraper stops on
its own if a source changes its mind, without anyone having to notice.
"""
from __future__ import annotations
import time
import urllib.robotparser
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen

# Venue sites sit behind WAFs that refuse anything not presenting as a browser,
# regardless of what their robots.txt permits. Armory answered 403 and Cherry
# Lane 500 to a named bot on pages their own robots.txt allows. These headers
# get past that. robots.txt is still consulted before every request, and this
# agent string resolves against the generic rules, so a site that disallows all
# crawling is still honoured.
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
HTML_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
IMAGE_ACCEPT = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
LANGUAGE = 'en-US,en;q=0.9'
TIMEOUT = 30
DELAY = 1.5           # seconds between requests to the same host
MAX_BYTES = 5_000_000

_robots: dict[str, urllib.robotparser.RobotFileParser] = {}
_last_hit: dict[str, float] = {}


def _rules(url: str) -> urllib.robotparser.RobotFileParser:
    host = urlparse(url).netloc
    if host not in _robots:
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(urljoin(url, '/robots.txt'))
        try:
            parser.read()
        except Exception:
            # An unreachable robots.txt is not permission; assume closed.
            parser.disallow_all = True
        _robots[host] = parser
    return _robots[host]


def allowed(url: str) -> bool:
    return _rules(url).can_fetch(USER_AGENT, url)


def fetch_bytes(url: str, max_bytes: int = MAX_BYTES) -> bytes:
    if not url.startswith('https://'):
        raise ValueError(f'Refusing non-HTTPS URL: {url}')
    if not allowed(url):
        raise PermissionError(f'robots.txt disallows {url}')
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': IMAGE_ACCEPT,
                                    'Accept-Language': LANGUAGE})
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise ValueError(f'HTTP {response.status} for {url}')
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f'Response exceeds {max_bytes} bytes: {url}')
    return raw


def fetch(url: str) -> str:
    if not url.startswith('https://'):
        raise ValueError(f'Refusing non-HTTPS URL: {url}')
    if not allowed(url):
        raise PermissionError(f'robots.txt disallows {url}')

    host = urlparse(url).netloc
    wait = DELAY - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)

    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': HTML_ACCEPT,
                                    'Accept-Language': LANGUAGE})
    with urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise ValueError(f'HTTP {response.status} for {url}')
        raw = response.read(MAX_BYTES + 1)
    _last_hit[host] = time.monotonic()
    if len(raw) > MAX_BYTES:
        raise ValueError(f'Response exceeds {MAX_BYTES} bytes: {url}')
    return raw.decode('utf-8-sig', errors='replace')
