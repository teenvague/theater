"""Hand-maintained entries, for venues no scheduled job can reach.

Park Avenue Armory is the case this exists for: its robots.txt permits
crawling, but Cloudflare bot management answers 403 to any client that is not
a real browser, so the season pages are unreadable from CI at any hour.

Entries live in data/manual.json in the same shape every adapter emits, and are
validated on the same terms. Nothing here is inferred; it is typed in.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / 'data/manual.json'


def load(path: Path = FILE) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get('productions', [])


def fetch(source):
    return load()
