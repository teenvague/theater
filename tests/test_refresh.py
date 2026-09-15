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
