"""Park Avenue Armory adapter.

Markup trimmed from the live season and production pages, 2026-09-15.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from adapters.armory import parse_season, parse_production, collect  # noqa: E402

SEASON = """
<a href="/season-events/current-season/">Current</a>
<a href="/season-events/2026-season/the-cherry-orchard/">The Cherry Orchard</a>
<a href="/season-events/2026-season/clinamen/">Clinamen</a>
<a href="/season-events/2026-season/making-space-at-the-armory/artist-talk-simon-stone/">Talk</a>
<a href="/season-events/2026-season/recital-series/ben-bliss-christopher-allen/">Recital</a>
<a href="/season-events/past-events/">Past</a>
"""

PRODUCTION = """
<meta property="og:image" content="https://www.armoryonpark.org/media/x/cherry_orchard_hero.jpg">
<h1>The Cherry Orchard</h1>
<div class="rich-text large stack-md ace-pdp-dates a">
  <p>September 16, 2026 - September 26, 2026</p> Wade Thompson Drill Hall
</div>
"""

VENUE = {'id': 'park-avenue-armory', 'name': 'Park Avenue Armory', 'neighborhood': 'Upper East Side'}


class TestSeason(unittest.TestCase):
    def test_keeps_productions_and_drops_series_events(self):
        # Talks and recitals sit one level deeper, under a series.
        self.assertEqual(parse_season(SEASON), [
            '/season-events/2026-season/the-cherry-orchard/',
            '/season-events/2026-season/clinamen/',
        ])


class TestProduction(unittest.TestCase):
    def test_reads_the_run(self):
        record = parse_production(PRODUCTION)
        self.assertEqual(record['title'], 'The Cherry Orchard')
        self.assertEqual(record['startDate'], '2026-09-16')
        self.assertEqual(record['closingDate'], '2026-09-26')

    def test_keeps_the_hall_and_the_venue_published_image(self):
        record = parse_production(PRODUCTION)
        self.assertIn('Wade Thompson Drill Hall', record['hall'])
        self.assertTrue(record['image'].startswith('https://'))

    def test_skips_a_page_with_no_parseable_date(self):
        self.assertIsNone(parse_production('<h1>Untitled</h1>'))


class TestCollect(unittest.TestCase):
    def test_builds_schema_shaped_records(self):
        pages = {'https://www.armoryonpark.org/season-events/current-season/': SEASON}
        rows = collect({'id': 'park-avenue-armory'}, VENUE,
                       get=lambda url: pages.get(url, PRODUCTION))
        self.assertEqual(len(rows), 2)
        engagement = rows[0]['engagements'][0]
        self.assertEqual(engagement['venue'], 'Park Avenue Armory')
        self.assertEqual(engagement['startDate'], '2026-09-16')
        self.assertEqual(engagement['sourceId'], 'park-avenue-armory')


if __name__ == '__main__':
    unittest.main()
