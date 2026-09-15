"""Image resolution and cache pruning."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import images  # noqa: E402

SITEMAP = """<urlset>
<url><loc>https://venue.example/shows/degenerates</loc></url>
<url><loc>https://venue.example/shows/some-other-play</loc></url>
</urlset>"""

PAGE = """<meta property="og:title" content="Degenerates">
<meta property="og:image" content="https://cdn.example/degen.jpg">"""

WRONG_PAGE = """<meta property="og:title" content="Some Other Play">
<meta property="og:image" content="https://cdn.example/other.jpg">"""


class TestMatching(unittest.TestCase):
    def test_finds_the_page_whose_slug_is_the_title(self):
        urls = ['https://venue.example/shows/degenerates', 'https://venue.example/about']
        self.assertEqual(images.candidate_pages('Degenerates', urls), [urls[0]])

    def test_slug_handles_punctuation_and_ampersands(self):
        self.assertEqual(images.slug('America, Who Hurt You?'), 'america-who-hurt-you')
        self.assertEqual(images.slug('Sound & Fury'), 'sound-and-fury')

    def test_takes_the_image_when_the_page_is_the_right_show(self):
        self.assertEqual(images.image_from_page(PAGE, 'Degenerates'), 'https://cdn.example/degen.jpg')

    def test_refuses_an_image_from_a_page_about_something_else(self):
        # A wrong image is worse than no image.
        self.assertEqual(images.image_from_page(WRONG_PAGE, 'Degenerates'), '')

    def test_falls_back_to_the_conventional_sitemap_path(self):
        self.assertEqual(images.sitemap_locations('https://venue.example', get=lambda u: ''),
                         ['https://venue.example/sitemap.xml'])

    def test_reads_sitemap_from_robots(self):
        robots = 'User-agent: *\nSitemap: https://venue.example/custom.xml\n'
        self.assertEqual(images.sitemap_locations('https://venue.example', get=lambda u: robots),
                         ['https://venue.example/custom.xml'])


class TestPrune(unittest.TestCase):
    def setUp(self):
        self.store = ROOT / 'dist/images'
        self.store.mkdir(parents=True, exist_ok=True)
        self.keep = self.store / 'keepme0000000000.jpg'
        self.drop = self.store / 'dropme0000000000.jpg'
        self.keep.write_bytes(b'x')
        self.drop.write_bytes(b'x')

    def tearDown(self):
        for f in (self.keep, self.drop):
            if f.exists():
                f.unlink()

    def test_removes_files_nothing_references(self):
        report = images.prune([{'id': 'a', 'image': 'images/keepme0000000000.jpg'}])
        self.assertTrue(self.keep.exists())
        self.assertFalse(self.drop.exists())
        self.assertEqual(report['kept'], 1)


if __name__ == '__main__':
    unittest.main()


class TestSummary(unittest.TestCase):
    def test_takes_the_first_sentence_only(self):
        self.assertEqual(images.summary('One thing happens. Then another.'), 'One thing happens.')

    def test_truncates_a_long_single_sentence_on_a_word(self):
        long = 'A ' + 'word ' * 80
        out = images.summary(long)
        self.assertLessEqual(len(out), 171)
        self.assertTrue(out.endswith('…'))

    def test_empty_in_empty_out(self):
        self.assertEqual(images.summary(''), '')
