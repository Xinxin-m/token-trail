import json,tempfile,unittest,zlib
from pathlib import Path
from token_trail.collector import parse_file,connect,scan,encoded,category
from token_trail.analysis import Ledger
R='11111111-1111-4111-8111-111111111111';C='22222222-2222-4222-8222-222222222222';T='2026-09-01T10:00:00Z'
def e(t,p):return dict(type=t,payload=p,timestamp=T)
def u(i=100,c=70,o=20):return dict(input_tokens=i,cached_input_tokens=c,output_tokens=o,reasoning_output_tokens=5,total_tokens=i+o)
def m(s=R,p=None):return e('session_meta',dict(id=s,timestamp=T,source='exec' if p else 'vscode',parent_thread_id=p))
def count(v):return e('event_msg',dict(type='token_count',info=dict(total_token_usage=v,last_token_usage=v)))
def record(v,rid='r1',sid=R):return e('token_usage_record',dict(thread_id=sid,response_id=rid,usage=v))
class Accounting(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def parse(self,rows,provider='codex',name=None):
  p=self.root/(name or R+'.jsonl');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(r)+'\n' for r in rows));return parse_file(p,provider)
 def ledger(self,*bundles):
  db=connect(self.root/'cache.sqlite')
  for i,d in enumerate(bundles):db.execute('insert into files values(?,?,?,?,?,?)',(str(i),0,0,1,0,zlib.compress(encoded(d).encode())))
  db.commit();self.addCleanup(db.close);return Ledger(db)
 def test_claude_cache_and_streaming_dedup(self):
  def a(o):return dict(type='assistant',timestamp=T,uuid=str(o),message=dict(id='msg1',model='test',content=[],usage=dict(input_tokens=7,cache_creation_input_tokens=30,cache_read_input_tokens=100,output_tokens=o,output_tokens_details={'thinking_tokens':3})))
  d=self.parse([a(5),a(9),a(9)],'claude');self.assertEqual(len(d['requests']),1);r=d['requests'][0];self.assertEqual((r['input'],r['total'],r['reasoning']),(137,146,3))
 def test_codex_cache_subset_and_duplicate_snapshot(self):
  d=self.parse([m(),count(u()),count(u()),count(u(220,150,40))]);self.assertEqual(sum(r['total'] for r in d['requests']),260);self.assertEqual(sum(r['fresh'] for r in d['requests']),70)
 def test_detail_and_cumulative_not_both_counted(self):
  d=self.parse([m(),record(u()),count(u()),record(u())]);self.assertEqual(len(d['requests']),1);self.assertEqual(d['requests'][0]['total'],120)
 def test_fork_with_retimestamped_ancestor_history(self):
  old=m();old['payload']['timestamp']='2026-09-01T09:00:00Z'
  d=self.parse([m(C,R),old,e('event_msg',dict(type='task_started',started_at=1788253200)),count(u(1000,700,200)),e('event_msg',dict(type='task_started',started_at=1788256800)),count(u(1100,770,220))],name=C+'.jsonl')
  self.assertEqual(d['session']['id'],'codex:'+C);self.assertEqual(d['session']['parent'],'codex:'+R);self.assertEqual(sum(r['total'] for r in d['requests']),120)
 def test_claude_subagent_path(self):
  d=self.parse([],provider='claude',name=R+'/subagents/agent-a.jsonl');self.assertEqual(d['session']['parent'],'claude:'+R);self.assertEqual(d['session']['origin'],'agent')
 def test_images_not_text_tokens(self):
  d=self.parse([m(),e('response_item',dict(type='function_call',call_id='c',name='view_image',arguments='{}')),e('response_item',dict(type='function_call_output',call_id='c',output=[{'type':'image','data':'a'*100000},{'type':'text','text':'hello'}]))]);self.assertEqual(d['tools'][0]['images'],1);self.assertEqual(d['tools'][0]['result_tokens'],2);self.assertFalse(d['tools'][0]['error'])
 def test_malformed_and_partial_tail(self):
  p=self.root/'partial.jsonl';p.write_text(json.dumps(m())+'\nBAD\n'+json.dumps(count(u()))[:-3]);d=parse_file(p,'codex');self.assertEqual(len(d['requests']),0);self.assertIn('1 malformed JSON lines skipped',d['session']['warnings'])
 def test_scan_idempotence(self):
  p=self.root/'claude';p.mkdir();self.parse([m(),count(u())],name='codex/'+R+'.jsonl');db=connect(self.root/'cache.sqlite');self.addCleanup(db.close);self.assertEqual(scan(db,p,self.root/'codex')['changed'],1);self.assertEqual(scan(db,p,self.root/'codex')['changed'],0);self.assertEqual(Ledger(db).summary()['totals']['total'],120)
 def test_rolling_window(self):
  l=self.ledger(self.parse([m(),record(u())]));ts=l.requests[0]['ts'];self.assertEqual(l.summary(hours=2,now=ts+3600)['totals']['total'],120);self.assertEqual(l.summary(hours=2,now=ts+3*3600)['totals']['total'],0)
 def test_headless_user_label_is_unresolved(self):
  meta=m();meta['payload'].update(source='exec',thread_source='user');self.assertEqual(self.parse([meta])['session']['origin'],'unresolved')
 def test_skill_label(self):self.assertEqual(category('Read','{"file_path":"/skills/demo/SKILL.md"}'),'Skills')
 def test_launch_result_establishes_cross_provider_link(self):
  a=self.parse([dict(type='user',timestamp=T,entrypoint='claude-vscode',origin={'kind':'human'},message={'content':'task'})],'claude');b=self.parse([m(C),record(u(),sid=C)],name=C+'.jsonl');b['session']['origin']='unresolved';a['links']=[dict(parent=a['session']['id'],child=b['session']['id'],ts=b['session']['start']+10)];l=self.ledger(a,b);self.assertEqual(l.sessions[b['session']['id']]['root'],a['session']['id'])
if __name__=='__main__':unittest.main()

class AdditionalAccounting(unittest.TestCase):
 setUp=Accounting.setUp
 tearDown=Accounting.tearDown
 parse=Accounting.parse
 ledger=Accounting.ledger
 def test_template_automation_not_counted_as_human(self):
  bundles=[]
  for i in range(4):
   b=self.parse([dict(type='user',timestamp=T,entrypoint='claude-vscode',message={'content':'You are an automated summarizer. '+('A long repeated deterministic prompt template. '*5)})],'claude',name=str(i)+'.jsonl');bundles.append(b)
  l=self.ledger(*bundles);self.assertTrue(all(s['origin']=='likely automation' for s in l.sessions.values()))
 def test_histogram_conserves_all_records_and_tokens(self):
  l=self.ledger(self.parse([m(),record(u()),record(u(17000),rid='r2')]));s=l.summary();self.assertEqual(sum(b['count'] for b in s['visuals']['histogram']),s['totals']['requests']);self.assertEqual(sum(b['total'] for b in s['visuals']['histogram']),s['totals']['total'])
 def test_launch_trace_hook_accepts_inherited_cross_provider_id(self):
  import os,io
  from unittest.mock import patch
  from token_trail.trace import hook
  config={'db':str(self.root/'trace.sqlite')}
  with patch.dict(os.environ,{'CODEX_THREAD_ID':R,'TOKEN_TRAIL_PARENT':''}),patch('sys.stdin',io.StringIO(json.dumps({'session_id':C}))):hook(config,'claude')
  db=connect(config['db']);value=json.loads(db.execute('select payload from trace_events').fetchone()[0]);self.assertEqual(value['parent'],'codex:'+R);self.assertEqual(value['session'],'claude:'+C);db.close()

 def test_claude_env_file_preserves_other_hooks(self):
  import os,io
  from unittest.mock import patch
  from token_trail.trace import hook
  envfile=self.root/'session.env';envfile.write_text('export EXISTING=keep\n')
  with patch.dict(os.environ,{'CLAUDE_ENV_FILE':str(envfile)}),patch('sys.stdin',io.StringIO(json.dumps({'session_id':C}))):hook({'db':str(self.root/'trace.sqlite')},'claude')
  text=envfile.read_text();self.assertTrue(text.startswith('export EXISTING=keep'));self.assertIn('TOKEN_TRAIL_CURRENT=claude:'+C,text)
 def test_repeated_image_representations_are_counted(self):
  rows=[m()]
  for n in range(2):rows.append(e('response_item',dict(type='message',id=str(n),role='user',content=[{'type':'input_image','image_url':'data:image/png;base64,AAAA'}])))
  s=self.ledger(self.parse(rows)).summary();self.assertEqual(s['observed']['images'],2);self.assertEqual(s['observed']['repeated_images'],1)
 def test_equal_totals_after_counter_reset_are_distinct(self):
  d=self.parse([m(),count(u()),count(u(200,140,40)),count(u()),count(u(200,140,40))]);self.assertEqual(sum(r['total'] for r in d['requests']),480)
