import unittest,tempfile,json,datetime as dt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from news_atlas import price_lens as p
from news_atlas.snapshots import validate_price_focus
class PriceLensTests(unittest.TestCase):
 def test_full_sessions_and_mean(self):
  bars=[{'date':d,'close':c} for d,c in [('2026-10-30',100),('2026-11-02',110),('2026-11-03',120),('2026-11-04',130),('2026-11-05',140)]]
  rows=[{'id':'pre','published_at':'2026-10-30T13:29:00Z'},{'id':'open','published_at':'2026-10-30T13:30:00Z'},{'id':'weekend','published_at':'2026-11-01T12:00:00Z'},{'id':'dst','published_at':'2026-11-02T14:29:00Z'},{'id':'unknown','published_at':None}]
  out=p.measurements(rows,bars)
  self.assertEqual(out['pre']['baseline_date'],'2026-10-30')
  self.assertAlmostEqual(out['pre']['returns']['3'],.2)
  for key in ['open','weekend','dst']:self.assertEqual(out[key]['baseline_date'],'2026-11-02')
  self.assertIsNone(out['pre']['returns']['5']);self.assertIsNone(out['unknown']['returns']['1'])
 def test_cache_and_cutoff(self):
  with tempfile.TemporaryDirectory() as folder:
   store=SimpleNamespace(path=Path(folder)/'news.db');body={'ticker':'AAPL','articles':[{'id':'a','published_at':'2026-10-29T12:00:00Z'}]}
   raw={'status':'OK','adjusted':True,'results':[{'t':1793318400000,'o':99,'h':102,'l':98,'c':100}]}
   with patch.object(p,'fetch',return_value=json.dumps(raw).encode()) as fetch:
    result=p.load(store,body,'secret',now=dt.datetime(2026,11,3,12,tzinfo=dt.timezone.utc))
    other=p.load(store,body,'',now=dt.datetime(2026,11,3,12,tzinfo=dt.timezone.utc))
    self.assertEqual(result['as_of'],'2026-11-02');self.assertTrue(other['cached']);self.assertEqual(fetch.call_count,1)
    self.assertEqual(result['bars'][0]['open'],99);self.assertEqual(result['bars'][0]['high'],102)
    self.assertNotIn('secret',json.dumps(result));self.assertNotIn('secret',fetch.call_args.args[0])
   with self.assertRaises(ValueError):p.load(store,{**body,'ticker':''},'')
   with self.assertRaises(ValueError):p.load(store,{**body,'ticker':'MSFT'},'')
   with patch.object(p,'fetch',return_value=b'[]'):
    with self.assertRaises(p.SourceError):p.load(store,{**body,'ticker':'MSFT'},'secret')
 def test_snapshot_whitelist(self):
  value={'mix':.7,'horizon':3,'ticker':'AAPL','observations':{'a':{'published_at':None,'returns':{'1':.1},'secret':'no'}},'massive_key':'no'}
  clean=validate_price_focus(value,{'a'})
  self.assertEqual(clean['mix'],.7);self.assertNotIn('no',json.dumps(clean))
  with self.assertRaises(ValueError):validate_price_focus(value,{'b'})
  value['mix']=float('nan')
  with self.assertRaises(ValueError):validate_price_focus(value,{'a'})

 def test_ohlc_snapshot(self):
  bar={'date':'2026-10-30','open':99,'high':102,'low':98,'close':100}
  clean=validate_price_focus({'bars':[bar]},set())
  self.assertEqual(clean['bars'],[bar])
  with self.assertRaises(ValueError):validate_price_focus({'bars':[{**bar,'low':101}]},set())
  with self.assertRaises(ValueError):validate_price_focus({'bars':[bar,bar]},set())
  self.assertEqual(validate_price_focus({'bars':[{ 'date':bar['date'],'close':100}]},set())['bars'][0]['open'],None)
