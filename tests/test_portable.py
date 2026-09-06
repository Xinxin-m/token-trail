import json, tempfile, unittest
from pathlib import Path
from token_trail.collector import connect, scan, parse_file
from token_trail.analysis import Ledger
from token_trail.coaching import playbook, markdown
from token_trail.setup import initialize, install_skill
from token_trail.instructions import audit

class PortableSources(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.db=connect(self.root/'ledger.sqlite')
    def tearDown(self):self.db.close();self.temp.cleanup()
    def write(self,path,rows):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(''.join(json.dumps(r)+'\n' for r in rows));return path
    def usage(self,**overrides):
        return dict(schema='token-trail.usage.v1',provider='custom',session_id='root',request_id='response1',timestamp=1700000000,
                    origin='human',title='Fictional task',usage=dict(fresh=100,cache_read=900,cache_write=20,output=40,reasoning=10))|overrides
    def test_arbitrary_provider_accounting_and_lineage(self):
        self.write(self.root/'events.jsonl',[self.usage(),self.usage(),self.usage(session_id='child',request_id='response2',parent_id='custom:root',origin='agent')])
        r=scan(self.db,config={'sources':[{'adapter':'usage-jsonl','path':str(self.root)}]})
        s=Ledger(self.db).summary();self.assertFalse(r['errors']);self.assertEqual(s['totals']['total'],2120)
        self.assertEqual(s['coverage']['linked_children'],1);self.assertEqual(len(s['roots']),1)
        self.assertEqual(sum(r.get('custom',0) for r in s['visuals']['histogram']),2)
        self.assertEqual(s['all_providers'],['custom']);self.assertEqual(s['totals']['input'],2040)
    def test_invalid_counter_not_silently_zero(self):
        rows=[self.usage(usage={'fresh':-1,'cache_read':0,'cache_write':0,'output':1}),self.usage(usage={'fresh':2,'output':1})]
        b=parse_file(self.write(self.root/'bad.jsonl',rows),'usage-jsonl')['bundles'][0]
        self.assertFalse(b['requests']);self.assertEqual(len(b['session']['warnings']),2)
    def test_conflicting_duplicate_and_partial_line(self):
        p=self.write(self.root/'dup.jsonl',[self.usage(),self.usage(usage=dict(fresh=5,cache_read=0,cache_write=0,output=2))])
        with p.open('a') as f:f.write('{"schema":')
        b=parse_file(p,'usage-jsonl')['bundles'][0]
        self.assertEqual(len(b['requests']),1);self.assertIn('Conflicting duplicate',b['session']['warnings'][0])
    def test_kimi_step_snapshots_child_and_missing_usage(self):
        def wire(typ,d,t=1700000000):return {'timestamp':t,'message':{'type':typ,'payload':d}}
        usage=dict(input_other=10,input_cache_read=90,input_cache_creation=5,output=8)
        rows=[{'type':'metadata','protocol_version':'1.0'},wire('TurnBegin',{'user_input':'Fictional research'}),wire('StepBegin',{'n':1}),
              wire('StatusUpdate',{'token_usage':usage}),wire('StatusUpdate',{'token_usage':usage},1700000001),
              wire('StatusUpdate',{'context_tokens':105}),wire('CompactionEnd',{}),
              wire('SubagentEvent',{'agent_id':'child','event':{'type':'StatusUpdate','payload':{'message_id':'child-response','token_usage':usage}}})]
        p=self.write(self.root/'kimi/session-id/wire.jsonl',rows)
        scan(self.db,config={'sources':[{'adapter':'kimi','path':str(p.parent.parent)}]})
        s=Ledger(self.db).summary();self.assertEqual(s['totals']['total'],226);self.assertEqual(s['coverage']['linked_children'],1)
        self.assertEqual(s['totals']['requests'],2);self.assertEqual(s['coverage']['human_roots'],0)
        b=parse_file(p,'kimi')['bundles'];self.assertEqual(b[0]['session']['compactions'],1)
    def test_unsupported_kimi_format_reports_gap(self):
        p=self.write(self.root/'k/wire.jsonl',[{'timestamp':1700000000,'message':{'type':'StatusUpdate','payload':{'token_usage':{'inputOther':10,'output':1}}}}])
        b=parse_file(p,'kimi')['bundles'][0]
        self.assertFalse(b['requests']);self.assertIn('Unsupported Kimi usage fields',b['session']['warnings'][0])
    def test_demo_does_not_discover_personal_sources(self):
        from token_trail.adapters import sources
        self.assertEqual(sources({'demo':True,'sources':[{'adapter':'kimi','path':'~/.kimi/sessions'}]}),[])
    def test_absent_optional_sources_not_failure(self):
        result=scan(self.db,config={'sources':[{'adapter':'claude','path':str(self.root/'absent')}]})
        self.assertFalse(result['errors']);self.assertEqual(result['files'],0)
    def test_handoff_is_evidence_based_and_non_mutating(self):
        self.write(self.root/'events.jsonl',[self.usage()]);scan(self.db,config={'sources':[{'adapter':'usage-jsonl','path':str(self.root)}]})
        s=Ledger(self.db).summary();p=playbook(s)
        self.assertEqual(len(p['actions']),6);self.assertIn('88.2%',p['actions'][-1]['evidence'])
        body=markdown(s,'skill');self.assertTrue(body.startswith('---\nname:'));self.assertIn('not an automatic configuration change',body)
    def test_init_and_skill_refuse_existing_targets(self):
        dest=self.root/'config.json';cfg={'db':str(self.root/'new.sqlite'),'sources':[]}
        initialize(cfg,dest);self.assertEqual(json.loads(dest.read_text())['sources'],[])
        with self.assertRaises(FileExistsError):initialize(cfg,dest)
        skill=self.root/'skill';install_skill(path=skill)
        self.assertTrue((skill/'scripts/trail.py').is_file());self.assertTrue((skill/'references/providers.md').is_file())
        with self.assertRaises(ValueError):install_skill(path=skill)
    def test_instruction_inventory_resolves_alias_once(self):
        path=self.root/'SKILL.md';path.write_text('## One\nText')
        r=audit([str(path),str(path)]);self.assertEqual(len(r['files']),1);self.assertEqual(len(r['files'][0]['aliases']),2)

if __name__=='__main__':unittest.main()
