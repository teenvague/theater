import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import artwork_sources as sources
import images

PAGE = 'https://www.todaytix.com/nyc/shows/123-brand-new-play'
ASSET = 'https://cdn.example.com/brand-new-play.jpg'

def markup(venue='Test Theatre', start='2026-09-01', end='2026-10-15', title='Brand New Play'):
    event = {'@type':'TheaterEvent', 'name': title+', '+venue,
             'performer':{'name':title}, 'location':{'name':venue},
             'startDate':start, 'endDate':end, 'image':ASSET}
    return '<script type="application/ld+json">'+json.dumps([event])+'</script>'

def production():
    return {'id':'new-play-123','title':'Brand New Play','image':'','engagements':[
        {'id':'run','venue':'Test Theatre','startDate':'2026-09-01','closingDate':'2026-10-15',
         'url':'https://venue.example.com/brand-new-play'}]}

CATALOG = '<a href="/nyc/shows/123-brand-new-play"><img alt="Brand New Play" src="/poster.jpg"></a>'

class MatchingTests(unittest.TestCase):
    def test_title_venue_and_overlapping_run(self):
        result = sources.matching_artwork(markup(),production(),[],PAGE)
        self.assertEqual(result['image'], ASSET)
    def test_rejects_other_venue(self):
        self.assertIsNone(sources.matching_artwork(markup(venue='Another Theatre'), production(), [], PAGE))
    def test_rejects_previous_revival(self):
        self.assertIsNone(sources.matching_artwork(markup(start='2025-09-01',end='2025-10-15'),production(),[],PAGE))
    def test_rejects_similar_title(self):
        self.assertIsNone(sources.matching_artwork(markup(title='Brand New Play Part Two'),production(),[],PAGE))
    def test_html_entities_in_venue(self):
        p=production();p['engagements'][0]['venue']='St. Ann’s Warehouse'
        self.assertIsNotNone(sources.matching_artwork(markup(venue='St. Ann&apos;s Warehouse'),p,[],PAGE))
    def test_bad_metadata_is_not_a_match(self):
        self.assertIsNone(sources.matching_artwork('<script type="application/ld+json">oops</script>',production(),[],PAGE))
    def test_fetches_catalog_and_detail_once(self):
        calls=[]
        def get(url):
            calls.append(url)
            return CATALOG if url in sources.INDEXES else markup()
        resolver=sources.TicketArtwork(get,[])
        self.assertIsNotNone(resolver.find(production()))
        self.assertIsNotNone(resolver.find(production()))
        self.assertEqual(calls.count(PAGE),1)
        self.assertEqual(calls.count(sources.INDEXES[0]),1)
    def test_source_failure_is_reported(self):
        def get(url):raise RuntimeError('unavailable')
        resolver=sources.TicketArtwork(get,[])
        self.assertIsNone(resolver.find(production()))
        self.assertEqual(len(resolver.errors),len(sources.INDEXES))

class FreshImportTests(unittest.TestCase):
    def test_new_play_gets_image_without_manual_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            # Deliberately no image-overrides.json and no image catalog.
            p=production()
            def get(url):
                if url in sources.INDEXES:return CATALOG
                if url == PAGE:return markup()
                return ''
            image=Image.new('RGB',(400,300),'navy');buffer=io.BytesIO();image.save(buffer,format='JPEG')
            with patch.object(images,'ROOT',root),patch.object(images,'CATALOG',root/'dist/data/images.json'):
                result=images.attach([p],[],get=get,get_bytes=lambda url:buffer.getvalue())
            self.assertEqual(result['withImage'],1)
            self.assertTrue((root/'dist'/p['image']).is_file())
            catalog=json.loads((root/'dist/data/images.json').read_text())
            self.assertEqual(catalog[p['id']]['method'],'todaytix-title-venue-dates')
            self.assertEqual(catalog[p['id']]['page'],PAGE)
            self.assertFalse((root/'data/image-overrides.json').exists())
