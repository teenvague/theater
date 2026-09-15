"""Ask the venue sites directly what they object to, and write down the answer.

Runs in the same environment as the scraper. Tries the same URL several ways so
the failure can be attributed: to the user agent, to the path, or to the address
the request comes from.
"""
from __future__ import annotations
import json
import ssl
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]

BROWSER = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
NAMED = 'NowPlayingTheater/1.0 (+https://teenvague.github.io/theater)'

TARGETS = [
    ('armory-season', 'https://www.armoryonpark.org/season-events/current-season/'),
    ('armory-robots', 'https://www.armoryonpark.org/robots.txt'),
    ('cherry-sitemap', 'https://cherrylanetheatre.org/sitemap.xml'),
    ('cherry-show', 'https://cherrylanetheatre.org/shows/school-pictures'),
    ('playwrights', 'https://www.playwrightshorizons.org/robots.txt'),
    ('playbill-control', 'https://playbill.com/shows/offbroadway'),
]

VARIANTS = {
    'browser': {'User-Agent': BROWSER, 'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9'},
    'named-bot': {'User-Agent': NAMED, 'Accept': 'text/html'},
    'browser-plus': {'User-Agent': BROWSER,
                     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                     'Accept-Language': 'en-US,en;q=0.9',
                     'Referer': 'https://www.google.com/',
                     'Upgrade-Insecure-Requests': '1',
                     'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
                     'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1'},
}

INTERESTING = ('server', 'cf-ray', 'cf-mitigated', 'x-served-by', 'retry-after', 'content-type')


def attempt(url, headers):
    try:
        with urlopen(Request(url, headers=headers), timeout=25,
                     context=ssl.create_default_context()) as response:
            body = response.read(400)
            return {'status': response.status, 'bytes': len(body),
                    'headers': {k.lower(): v for k, v in response.headers.items()
                                if k.lower() in INTERESTING}}
    except HTTPError as exc:
        return {'status': exc.code, 'error': str(exc),
                'headers': {k.lower(): v for k, v in (exc.headers or {}).items()
                            if k.lower() in INTERESTING},
                'bodyPeek': (exc.read(300) or b'').decode('utf-8', 'replace')}
    except URLError as exc:
        return {'status': None, 'error': f'{type(exc).__name__}: {exc}'}
    except Exception as exc:
        return {'status': None, 'error': f'{type(exc).__name__}: {exc}'}


def main():
    results = {}
    for name, url in TARGETS:
        results[name] = {'url': url}
        for variant, headers in VARIANTS.items():
            results[name][variant] = attempt(url, headers)
    out = ROOT / 'data/probe.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(results, indent=2)[:4000])


if __name__ == '__main__':
    main()
