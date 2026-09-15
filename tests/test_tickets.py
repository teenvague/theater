import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tickets import booking_link,attach

class TicketTests(unittest.TestCase):
 def test_only_production_booking_action(self):
  html='<a href="https://playbill.com/discount">Buy Tickets</a><a href="https://venue.org/show">Buy Tickets</a>'
  self.assertEqual(booking_link(html,'https://playbill.com/production/test'),'https://venue.org/show')
 def test_unsafe_url_rejected(self):
  self.assertEqual(booking_link('<a href="javascript:alert(1)">Buy Tickets</a>','https://playbill.com/production/test'),'')
 def test_preserves_source_and_previous_booking_on_failure(self):
  e={'url':'https://playbill.com/production/test','ticketUrl':'https://venue.org/show'}
  def fail(url):raise RuntimeError('offline')
  attach([{'title':'Test','engagements':[e]}],get=fail)
  self.assertEqual(e['ticketUrl'],'https://venue.org/show')
  self.assertEqual(e['url'],'https://playbill.com/production/test')
