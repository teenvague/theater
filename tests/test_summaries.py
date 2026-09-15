import json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import summaries
PAGE='<meta property="og:title" content="New Play | Test Theatre"><meta property="og:description" content="Two estranged sisters reunite to sell their childhood home. Their plans unravel over dinner.">'
class SummaryTests(unittest.TestCase):
 def test_synopsis_preferred_to_billing(self):
  page=PAGE+'<b>SYNOPSIS:</b><p>Dr. Jones returns home to discover a family secret.</p>'
  self.assertEqual(summaries.from_page(page,'New Play','Test Theatre'),'Dr. Jones returns home to discover a family secret.')
 def test_billing_is_not_a_summary(self):
  self.assertEqual(summaries.one_line('Presented by La Femme Theatre Productions'),'')
 def test_markdown_removed(self):
  self.assertEqual(summaries.one_line('*Two sisters* return home to uncover a secret.'),'Two sisters return home to uncover a secret.')
 def test_first_sentence(self):
  self.assertEqual(summaries.from_page(PAGE,'New Play','Test Theatre'),'Two estranged sisters reunite to sell their childhood home.')
 def test_complete_sentence_preserved_for_responsive_layout(self):
  sentence='A family '+('discovers ' * 80)+'a secret.'
  self.assertEqual(summaries.one_line(sentence),sentence)
 def test_skip_marketing(self):
  s=summaries.one_line('Buy tickets for this incredible new show today. Two sisters return home and uncover a long-hidden secret.')
  self.assertEqual(s,'Two sisters return home and uncover a long-hidden secret.')
 def test_wrong_show_rejected(self):
  self.assertEqual(summaries.from_page(PAGE,'Different Play','Test Theatre'),'')
 def test_independent_of_existing_image(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(summaries,'ROOT',Path(folder)):
   p={'id':'new','title':'New Play','image':'images/already-cached.jpg','engagements':[{'venue':'Test Theatre','url':'https://venue.example/new'}]}
   report=summaries.attach([p],[],get=lambda u:PAGE)
   self.assertEqual(report['updated'],1);self.assertTrue(p['description']);self.assertEqual(p['descriptionSourceUrl'],'https://venue.example/new')
 def test_cached_summary_skips_fetch(self):
  now=datetime(2026,9,15,tzinfo=timezone.utc)
  with tempfile.TemporaryDirectory() as folder,patch.object(summaries,'ROOT',Path(folder)):
   p={'description':'Two sisters return home to uncover a secret.','descriptionUpdatedAt':now.isoformat(),'descriptionSourceUrl':'https://venue.example/new'}
   report=summaries.attach([p],[],get=lambda u:self.fail('should not fetch'),now=now+timedelta(days=1))
   self.assertEqual(report['withDescription'],1)
 def test_failure_keeps_last_good_summary(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(summaries,'ROOT',Path(folder)):
   old='Two sisters return home to uncover a secret.'
   p={'id':'new','title':'New Play','description':old,'engagements':[{'venue':'Test Theatre','url':'https://venue.example/new'}]}
   def fail(u):raise RuntimeError('offline')
   summaries.attach([p],[],get=fail)
   self.assertEqual(p['description'],old)
