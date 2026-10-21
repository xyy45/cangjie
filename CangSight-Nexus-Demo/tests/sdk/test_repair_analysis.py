"""Real MCP/SDK plus fake analysis transport; not a live AI evaluation."""
import asyncio
import hashlib
import json
import zipfile
import pytest
from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.contracts import CandidateProposal,file_hash
from nexus.demo.app import create_demo_app
from nexus.demo.probes import execute_approval_probe
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.cegis_loop import RepairLoop
from nexus.requirements.service import RequirementService
from nexus.scenarios import ROOT,get_profile
from nexus.store import RunStore

pytestmark=pytest.mark.sdk


def test_analysis_bound_journey_and_approval_probe_preserve_delivery_evidence(tmp_path):
    class Transport:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def analyze(self,tool,args):
            result={'status':'success'}
            if tool=='sympas_slice':result['data']={'backward_slices':{'value':{args['filename']:[1]}}}
            if tool=='sympas_dep_graph':result['json_graphs']=[{'graph_type':'Ddg','nodes':[{'id':'v','label':'[L1]: variable'}],'edges':[]}]
            if tool=='ast_symbol_extractor':result['symbols']=[{'symbol':'value'}]
            result['untrusted_ref']='records/do-not-export.json'
            return dict(http_status=200,response=result,elapsed_ms=1,transport='TEST_ONLY')
    profile=get_profile('cross-validation');source=ROOT/profile['source'];store=RunStore(tmp_path)
    ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    requirements=RequirementService(store);draft=requirements.prepare_requirement('cross-validation','测试分析关联')
    spec=requirements.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='TEST_FIXTURE')
    task=requirements.prepare_task('cross-validation',spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    captured=[]
    class Reference:
        async def propose(self,context):
            captured.append(context)
            replacements={'src/quantity.cj':('quantity >= 0','quantity >= 1'),
                'src/fee.cj':('quantity + unitPrice','quantity * unitPrice')}
            return CandidateProposal(edits=[dict(path=p,before_hash=file_hash(context['files'][p]['content']),
                content=context['files'][p]['content'].replace(*v)) for p,v in replacements.items()],
                requirement_refs=[r.id for r in spec.requirements])
    bridge=RepairAnalysis(store,AnalysisService(tmp_path,client_factory=Transport))
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Reference(),context_enricher=bridge.enrich).run(task.id))
    assert result.status=='REVIEW_PENDING' and len(captured[0]['analysis']['files'])==2
    assert not store.records(task.id,'model_call')
    probe=asyncio.run(execute_approval_probe(store,task.id))
    assert probe['error']=='ACCEPTANCE_REQUIRED' and not probe['action_executed']
    assert store.get_task(task.id).status=='REVIEW_PENDING' and not store.records(task.id,'acceptance')
    candidate=next(e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e)
    from nexus.analysis.impact import ImpactService
    impact=ImpactService(store,bridge.service);impact.start(candidate);impact.run(candidate)
    service=DeliveryService(store);acceptance=service.accept(candidate,service.check_set_hash(candidate),actor_id='TEST_FIXTURE')
    exported=service.export(candidate,acceptance.id)
    with zipfile.ZipFile(tmp_path/exported['download_ref']) as z:
        comparison=json.loads(z.read('evidence/impact.json'))
        assert comparison['reports'][0]['candidate_id']==candidate
        report=json.loads(z.read('evidence/analysis.json'))
        assert report['contexts'][0]==captured[0]['analysis']
        assert not any('do-not-export' in n for n in z.namelist())
        event=next(e for e in store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT')
        for entry in event['evidence_files']:
            raw=z.read('evidence/native/'+entry['record_ref'])
            assert hashlib.sha256(raw).hexdigest()==entry['sha256']
    app=create_demo_app(tmp_path,provider='rule');app.config['TESTING']=True
    with app.test_client() as client:
        assert client.get(f'/api/demo/tasks/{task.id}/analysis').status_code==200
