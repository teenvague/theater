"""Parser regression tests.

The markup below is trimmed from the live Playbill pages (captured 2026-09-15):
the listing grid's card shape, and the production page's promo list, which uses
stable semantic classes rather than utility classes.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from adapters.playbill import parse_index, parse_detail, match_venue, collect  # noqa: E402

INDEX = """
<div class="grid">
  <div><a href="/production/america-who-hurt-you-off-broadway-tfana-2026">
      <figure><img></figure></a>
    <h3><a href="/production/america-who-hurt-you-off-broadway-tfana-2026">America, Who Hurt You?</a></h3>
    <p>In Previews | Opens Sep 17, 2026</p>
    <p>Theatre for a New Audience @ Polonsky Shakespeare Center</p>
    <a href="/production/america-who-hurt-you-off-broadway-tfana-2026">View Details</a>
    <a href="https://tickets.example/x">Buy Tickets</a></div>
  <div><h3><a href="/production/spelling-bee-off-broadway-new-world-stages-2025">The 25th Annual Putnam County Spelling Bee</a></h3>
    <p>Closes Oct 11, 2026</p><p>New World Stages Stage 3</p>
    <a href="/production/spelling-bee-off-broadway-new-world-stages-2025">View Details</a></div>
  <div><h3><a href="/production/some-revue-off-broadway-the-culture-club-2026">Some Revue</a></h3>
    <p>The Culture Club</p>
    <a href="/production/some-revue-off-broadway-the-culture-club-2026">View Details</a></div>
</div>
"""

DETAIL = """
<div class="production-tags"><a>Off-Broadway</a><a>Solo</a><a>Play</a></div>
<p>PLAYWRIGHT: SARAH JONES</p><p>Directed by Eric Ting</p>
<ul class="bsp-list-promo-list">
  <li><div class="bsp-list-promo-section-text"><div class="bsp-list-promo-title">Opening Date</div></div>
    <div class="info-circular"><span class="info-circular-pre-text">Sep</span>
      <span class="info-circular-text">17</span><span class="info-circular-post-text">2026</span></div></li>
  <li><div class="bsp-list-promo-title">Closing Date</div>
    <div class="info-circular"><span class="info-circular-pre-text">Oct</span>
      <span class="info-circular-text">4</span><span class="info-circular-post-text">2026</span></div></li>
  <li><div class="bsp-list-promo-title">First Preview</div>
    <div class="info-circular"><span class="info-circular-pre-text">Sep</span>
      <span class="info-circular-text">11</span><span class="info-circular-post-text">2026</span></div></li>
  <li><div class="bsp-list-promo-title">Opening Date</div>
    <div class="info-circular"><span class="info-circular-pre-text">Sep</span>
      <span class="info-circular-text">17</span><span class="info-circular-post-text">2026</span></div></li>
</ul>
"""

REGISTRY = [v for v in json.loads((ROOT / 'data/sources.json').read_text())['sources'] if v.get('playbill')]


class TestIndex(unittest.TestCase):
    def test_reads_every_card(self):
        rows = parse_index(INDEX)
        self.assertEqual(len(rows), 3)

    def test_separates_status_from_venue(self):
        first = parse_index(INDEX)[0]
        self.assertEqual(first['title'], 'America, Who Hurt You?')
        self.assertEqual(first['status'], 'In Previews | Opens Sep 17, 2026')
        self.assertEqual(first['venue'], 'Theatre for a New Audience @ Polonsky Shakespeare Center')

    def test_card_without_a_status_line_keeps_its_venue(self):
        # Some cards carry no status; the venue must not be read as one.
        third = parse_index(INDEX)[2]
        self.assertEqual(third['status'], '')
        self.assertEqual(third['venue'], 'The Culture Club')

    def test_drops_the_call_to_action_text(self):
        for row in parse_index(INDEX):
            self.assertNotIn(row['venue'], ('View Details', 'Buy Tickets'))


class TestDetail(unittest.TestCase):
    def test_reads_all_three_dates(self):
        d = parse_detail(DETAIL)
        self.assertEqual(d['firstPreview'], '2026-09-11')
        self.assertEqual(d['openingDate'], '2026-09-17')
        self.assertEqual(d['closingDate'], '2026-10-04')

    def test_ignores_the_repeated_responsive_block(self):
        self.assertEqual(parse_detail(DETAIL)['openingDate'], '2026-09-17')

    def test_takes_tags_and_credits_but_not_the_synopsis(self):
        d = parse_detail(DETAIL)
        self.assertIn('Play', d['types'])
        self.assertIn('Sarah Jones', d['credits'])
        self.assertIn('Directed by Eric Ting', d['credits'])


class TestVenueMatching(unittest.TestCase):
    def test_matches_a_sub_venue_to_its_parent(self):
        self.assertEqual(match_venue('Public Theater/Newman Theater', REGISTRY)['id'], 'the-public-theater')

    def test_survives_a_curly_apostrophe(self):
        self.assertEqual(match_venue('St. Ann’s Warehouse', REGISTRY)['id'], 'st-anns-warehouse')

    def test_declines_a_venue_outside_the_registry(self):
        self.assertIsNone(match_venue('Laura Pels Theatre', REGISTRY))


class TestCollect(unittest.TestCase):
    def test_builds_schema_shaped_records_for_registry_venues_only(self):
        pages = {'https://playbill.com/shows/offbroadway': INDEX}
        rows = collect({'id': 'playbill', 'sections': ['offbroadway']}, REGISTRY,
                       get=lambda url: pages.get(url, DETAIL))
        self.assertEqual(len(rows), 1)          # only the TFANA show is in the registry
        production = rows[0]
        self.assertEqual(production['engagements'][0]['venue'], 'Theatre for a New Audience')
        self.assertEqual(production['engagements'][0]['startDate'], '2026-09-11')
        self.assertEqual(production['engagements'][0]['sourceId'], 'playbill')
        self.assertEqual(production['image'], '')


if __name__ == '__main__':
    unittest.main()
