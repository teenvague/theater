"""Cherry Lane adapter. Markup trimmed from the live site, 2026-09-15."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from adapters.cherry_lane import show_urls, parse_show, collect  # noqa: E402

SITEMAP = """<urlset>
<url><loc>https://cherrylanetheatre.org/</loc></url>
<url><loc>https://cherrylanetheatre.org/shows</loc></url>
<url><loc>https://cherrylanetheatre.org/shows/school-pictures</loc></url>
<url><loc>https://www.cherrylanetheatre.org/shows/school-pictures</loc></url>
<url><loc>https://cherrylanetheatre.org/shows/moonlight</loc></url>
</urlset>"""

SHOW = """
<h1>School Pictures</h1>
<p>October—November, 2026</p>
<img src="https://cdn.sanity.io/images/x/school-pictures.jpg?w=620">
<div class="heading-md">Oct 7</div>
<div class="heading-md">Oct 28</div>
<div class="heading-md">Nov 8</div>
"""

PAST = """
<h1>Moonlight</h1>
<p>January—February, 2024</p>
<div class="heading-md">Jan 5</div>
<div class="heading-md">Feb 2</div>
"""

TURN_OF_YEAR = """
<h1>Winter Piece</h1>
<p>December, 2026—January, 2027</p>
<div class="heading-md">Dec 20</div>
<div class="heading-md">Jan 9</div>
"""

VENUE = {'id': 'cherry-lane-theatre', 'name': 'Cherry Lane Theatre', 'neighborhood': 'West Village'}


class TestDiscovery(unittest.TestCase):
    def test_collapses_the_www_duplicate_and_drops_the_index(self):
        self.assertEqual(show_urls(SITEMAP), [
            'https://cherrylanetheatre.org/shows/school-pictures',
            'https://cherrylanetheatre.org/shows/moonlight',
        ])


class TestParse(unittest.TestCase):
    def test_takes_the_run_from_first_and_last_performance(self):
        record = parse_show(SHOW)
        self.assertEqual(record['title'], 'School Pictures')
        self.assertEqual(record['startDate'], '2026-10-07')
        self.assertEqual(record['closingDate'], '2026-11-08')
        self.assertEqual(record['performances'], 3)

    def test_takes_the_production_image(self):
        self.assertTrue(parse_show(SHOW)['image'].startswith('https://cdn.sanity.io/'))

    def test_rolls_the_year_when_months_go_backwards(self):
        record = parse_show(TURN_OF_YEAR)
        self.assertEqual(record['startDate'], '2026-12-20')
        self.assertEqual(record['closingDate'], '2027-01-09')

    def test_returns_nothing_without_dates(self):
        self.assertIsNone(parse_show('<h1>Untitled</h1><p>Coming soon</p>'))


class TestCollect(unittest.TestCase):
    def test_drops_shows_that_have_already_closed(self):
        pages = {'https://cherrylanetheatre.org/sitemap.xml': SITEMAP,
                 'https://cherrylanetheatre.org/shows/school-pictures': SHOW,
                 'https://cherrylanetheatre.org/shows/moonlight': PAST}
        rows = collect({'id': 'cherry-lane-theatre'}, VENUE,
                       get=lambda url: pages[url], today=date(2026, 9, 15))
        self.assertEqual([r['title'] for r in rows], ['School Pictures'])
        self.assertEqual(rows[0]['engagements'][0]['closingDate'], '2026-11-08')


if __name__ == '__main__':
    unittest.main()


class TestResilience(unittest.TestCase):
    def test_one_broken_page_does_not_lose_the_venue(self):
        pages = {'https://cherrylanetheatre.org/sitemap.xml': SITEMAP,
                 'https://cherrylanetheatre.org/shows/school-pictures': SHOW}

        def get(url):
            if url not in pages:
                raise ValueError('HTTP Error 500: Internal Server Error')
            return pages[url]

        rows = collect({'id': 'cherry-lane-theatre'}, VENUE, get=get, today=date(2026, 9, 15))
        self.assertEqual([r['title'] for r in rows], ['School Pictures'])

    def test_an_unreachable_sitemap_still_fails_the_source(self):
        def get(url):
            raise ValueError('HTTP Error 500')
        with self.assertRaises(ValueError):
            collect({'id': 'cherry-lane-theatre'}, VENUE, get=get, today=date(2026, 9, 15))


RUNNING = """
<h1>Shifters</h1>
<p>July—September, 2026</p>
<div class="heading-md">Sep 15</div>
<div class="heading-md">Sep 20</div>
"""


class TestAlreadyRunning(unittest.TestCase):
    def test_a_running_show_starts_when_the_range_says_not_at_its_next_performance(self):
        # Only upcoming performances are listed, so the list alone would make a
        # show that opened in July look like it starts in September.
        record = parse_show(RUNNING)
        self.assertEqual(record['startDate'], '2026-07-01')
        self.assertEqual(record['closingDate'], '2026-09-20')

    def test_a_future_show_keeps_its_exact_first_performance(self):
        record = parse_show(SHOW)
        self.assertEqual(record['startDate'], '2026-10-07')
