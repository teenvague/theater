"""Reference adapter for an explicitly configured normalized JSON endpoint.
Venue HTML adapters should implement the same fetch(source) contract.
"""
import json
from urllib.request import Request, urlopen

def fetch(source):
    if not source['url'].startswith('https://'):
        raise ValueError('Feed must use HTTPS')
    request = Request(source['url'], headers={'User-Agent': 'NowPlayingTheater/1.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError('Feed exceeds 5 MB')
    data = json.loads(raw)
    return data['productions']
