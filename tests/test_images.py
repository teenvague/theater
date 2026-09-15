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


class TestBoilerplate(unittest.TestCase):
    def test_rejects_the_house_blurb(self):
        self.assertTrue(images.boilerplate(
            "Irish Repertory Theatre is New York City's award-winning Off-Broadway home for Irish drama.",
            'The Hairy Ape', 'Irish Rep'))

    def test_keeps_a_real_synopsis(self):
        self.assertFalse(images.boilerplate(
            "Else Went's new play offers a telescopic, darkly funny view of one insular community.",
            'Degenerates', 'Playwrights Horizons'))

    def test_rejects_anything_naming_the_venue(self):
        self.assertTrue(images.boilerplate('A season at Playwrights Horizons.', 'Fish', 'Playwrights Horizons'))


class TestValidateAcceptsCachedPaths(unittest.TestCase):
    """The image pass writes repo-relative paths; the next run reads them back."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('refresh', ROOT / 'scripts/refresh.py')
        self.refresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.refresh)

    def production(self, image):
        return [{'id': 'x', 'title': 'X', 'credits': '', 'image': image, 'types': ['Play'],
                 'engagements': [{'id': 'x:1', 'venue': 'V', 'neighborhood': 'N', 'sourceId': 's',
                                  'sourceUrl': 'https://e.example', 'url': 'https://e.example/x',
                                  'startDate': '2026-09-01', 'status': 'scheduled'}]}]

    def test_accepts_a_cached_path(self):
        self.refresh.validate(self.production('images/abc123.jpg'))

    def test_accepts_a_remote_url_and_an_empty_value(self):
        self.refresh.validate(self.production('https://cdn.example/a.jpg'))
        self.refresh.validate(self.production(''))

    def test_rejects_a_bare_relative_path(self):
        with self.assertRaises(ValueError):
            self.refresh.validate(self.production('some/other/path.jpg'))

    def test_rejects_traversal(self):
        with self.assertRaises(ValueError):
            self.refresh.validate(self.production('images/../../etc/passwd'))
