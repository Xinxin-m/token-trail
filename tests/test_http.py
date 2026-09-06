import json,tempfile,threading,unittest,zlib
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from token_trail.server import State,handler
from token_trail.collector import connect,encoded
from token_trail.analysis import Ledger

class LocalHTTP(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.dbpath=Path(self.temp.name)/'ledger.sqlite';db=connect(self.dbpath)
  for i in ['a','b']:
   s=dict(id='claude:'+i,native_id=i,provider='claude',title='Private title '+i,cwd='/private/example',start=1,end=2,parent='',lineage='',origin='human',source='test',topic='Private topic',compactions=0,human_turns=1,warnings=[])
   r=dict(id=i,session=s['id'],ts=2,model='test',input=100,cache_read=70,cache_write=20,fresh=10,output=20,reasoning=5,total=120,purpose='Conversation',epoch=0,kind='response')
   b=dict(session=s,requests=[r],tools=[],items=[],links=[]);db.execute('insert into files values(?,?,?,?,?,?)',(i,0,0,1,0,zlib.compress(encoded(b).encode())))
  db.commit();self.state=State({'db':str(self.dbpath)});self.state.ledger=Ledger(db);db.close();self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.state));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def get(self,path,headers=None):return urlopen(Request(self.url+path,headers=headers or {}))
 def post(self,body,origin=True):
  h={'Content-Type':'application/json','X-Token-Trail':'local'}
  if origin:h['Origin']=self.url
  return urlopen(Request(self.url+'/api/link',data=json.dumps(body).encode(),headers=h))
 def test_share_allowlist_excludes_private_labels(self):
  with self.get('/api/share?hours=all') as r:body=r.read().decode();data=json.loads(body)
  self.assertEqual(data['totals']['total'],240);self.assertNotIn('Private',body);self.assertNotIn('claude:a',body);self.assertNotIn('/private',body)
 def test_cross_origin_and_bad_host_blocked(self):
  with self.assertRaises(HTTPError) as e:self.post({'child':'claude:b','parent':'claude:a'},False)
  self.assertEqual(e.exception.code,403)
  with self.assertRaises(HTTPError) as e:self.get('/api/status',{'Host':'attacker.example'})
  self.assertEqual(e.exception.code,403)
 def test_link_persists_and_cycle_rejected(self):
  with self.post({'child':'claude:b','parent':'claude:a'}) as r:self.assertTrue(json.load(r)['ok'])
  db=connect(self.dbpath);self.state.ledger=Ledger(db);db.close()
  self.assertEqual(self.state.ledger.sessions['claude:b']['root'],'claude:a')
  with self.assertRaises(HTTPError) as e:self.post({'child':'claude:a','parent':'claude:b'})
  self.assertEqual(e.exception.code,400)
 def test_traversal_not_served(self):
  with self.assertRaises(HTTPError) as e:self.get('/%2e%2e/collector.py')
  self.assertEqual(e.exception.code,404)
