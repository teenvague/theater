import sys,unittest
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from adapters.cherry_lane import parse_show,collect
from summaries import from_page

# Minimal fixtures retain the live site's rich-text structure and credit formats.
CASES=[('School Pictures','school-pictures',
 'Faith hates reading, Jane has lost her flashcards and Javier sees no point in studying because of climate change.',
 '<p>Written and performed by Milo Cramer (Cute Activist, Minor Character) and directed by longtime collaborator Morgan Green.</p>',
 ['Milo Cramer','Morgan Green']),
 ('Two Girls','two-girls','Two Girls revisits a viral video through verbatim dialogue.',
 '<p>By Eliya Smith</p><p>Developed with The Goat Exchange</p><p>and Cherry Lane Theatre</p><p>Directed by Chloe Claudel and Mitchell Polonsky</p><p>Starring Chloe Claudel and Juliana Sass</p>',
 ['Eliya Smith','Chloe Claudel','Mitchell Polonsky','Juliana Sass'])]

class CherryLaneCopyTests(unittest.TestCase):
 def test_metadata_survives_parsing_collection_and_summary_enrichment(self):
  for title,slug,description,credits,names in CASES:
   with self.subTest(title=title):
    markup=f'<h1><span>{title}</span></h1><p>October—November, 2026</p><div class="freetext-richtext heading-sm"><p>{description}</p><p></p>{credits}</div><div class="heading-md">Oct 7</div><div class="heading-md">Nov 8</div><footer><p>Sign up for our newsletter</p></footer>'
    record=parse_show(markup)
    self.assertEqual(record['description'],description)
    for name in names:self.assertIn(name,record['credits'])
    venue={'id':'cherry-lane-theatre','name':'Cherry Lane Theatre'}
    url='https://cherrylanetheatre.org/shows/'+slug
    rows=collect(venue,venue,get=lambda u:f'<loc>{url}</loc>' if u.endswith('sitemap.xml') else markup,today=date(2026,9,15))
    self.assertEqual(rows[0]['description'],description)
    self.assertEqual(rows[0]['credits'],record['credits'])
    self.assertEqual(from_page(markup,title,venue['name']),description)
