import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh
class RefreshTests(unittest.TestCase):
 def setUp(self):
  self.rows=json.loads((refresh.ROOT/'dist/data/shows.json').read_text())['productions']
 def test_duplicate_and_transfer(self):
  p=copy.deepcopy(self.rows[0]);q=copy.deepcopy(p);q['engagements'][0]['id']='new-run'
  self.assertEqual(len(refresh.merge([p,p,q])[0]['engagements']),2)
 def test_invalid_date(self):
  rows=copy.deepcopy(self.rows);rows[0]['engagements'][0]['closingDate']='2020-01-01'
  with self.assertRaises(ValueError):refresh.validate(rows)
 def test_failure_preserves_feed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); config=root/'sources.json';output=root/'shows.json'
   config.write_text(json.dumps({'sources':[{'id':'test','enabled':True,'adapter':'json_feed','url':'https://example.com'}]}));output.write_text(json.dumps({'productions':self.rows}));before=output.read_bytes()
   with patch.object(refresh,'ROOT',root),patch('adapters.json_feed.fetch',side_effect=RuntimeError('offline')):
    self.assertEqual(refresh.refresh(config,output),1)
   self.assertEqual(output.read_bytes(),before)
if __name__=='__main__':unittest.main()

class AliasTests(unittest.TestCase):
 def test_same_run_sources_combine_without_losing_credits(self):
  def record(pid,eid,start,source,seen,**extra):
   return {'id':pid,'title':'Shifters','credits':'Benedict Lombe' if source=='playbill' else '', 'image':'https://example.com/show.jpg' if source!='playbill' else '', 'engagements':[{'id':eid,'startDate':start,'sourceId':source,'lastSeen':seen,**extra}]}
  a=record('playbill:shifters-off-broadway-cherry-lane-theatre-2026','playbill:shifters-off-broadway-cherry-lane-theatre-2026:cherry-lane-theatre','2026-07-06','playbill','2026-09-14')
  b=record('cherry-lane:shifters','cherry-lane:shifters:cherry-lane-theatre','2026-07-01','cherry-lane-theatre','2026-09-15',startDatePrecision='month')
  merged=refresh.merge([a,b])
  self.assertEqual(len(merged),1)
  self.assertEqual(len(merged[0]['engagements']),1)
  self.assertEqual(merged[0]['engagements'][0]['startDate'],'2026-07-06')
  self.assertEqual(merged[0]['credits'],'Benedict Lombe')
  self.assertTrue(merged[0]['image'])
  self.assertEqual(refresh.merge(merged),merged)
 def test_new_metadata_replaces_old(self):
  self.assertEqual(refresh.merge([{'id':'x','title':'Old','engagements':[]},{'id':'x','title':'Corrected','engagements':[]}])[0]['title'],'Corrected')
