"""Actual local SDK/review/export receipts; review actor is an explicit fixture."""
import asyncio,json,zipfile
from copy import deepcopy
import pytest
from nexus.contracts import CandidateProposal,file_hash
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.execution.delivery import DeliveryService
from tests.test_package_context import setup
from tests.sdk.test_package_reports_sdk import save

pytestmark=pytest.mark.sdk


def test_real_scoped_review_export_keeps_all_sdk_originals_and_tamper_stops_download(tmp_path):
    store,ws,task,value=setup(tmp_path,with_oracle=False)
    original=ws.read_file(task.baseline_id,'src/step.cj')
    c=ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/step.cj',before_hash=file_hash(original),content=original+'\n// explicit local public-only candidate')],requirement_refs=['REQ-UPLOAD']))
    async def run():
        verifier=CangjieVerifier(tmp_path,task.id);built=await verifier.build(c.id);assert built.state=='PASS',built
        tested=await verifier.test(c.id);assert tested.state=='PASS',tested
        delivery=DeliveryService(store);checked=delivery.check_set_hash(c.id)
        store.update_task(task.id,status='REVIEW_PENDING');store.append_record(task.id,'event',dict(selected_candidate_id=c.id))
        approval=delivery.accept(c.id,checked,actor_id='alice',task_revision=store.get_task(task.id).revision)
        exported=delivery.export(c.id,approval.id)
        assert exported['status']=='DELIVERED'
        delivery.acceptance(c.id,approval.id,actor_id='alice');archive=delivery.verify_archive(exported['export_id'],approval)
        with zipfile.ZipFile(archive) as package:
            names=set(package.namelist());refs=[]
            for result in (built,tested):
                proof=result.package_evidence
                refs.extend(item[k]['ref'] for item in proof['scans'] for k in ('stdout','stderr'))
                if proof['test'] is not None:
                    refs.append(proof['test']['stdout']['ref']);refs.extend(item['ref'] for item in proof['test']['reports'].values())
            assert all('evidence/native/'+ref in names for ref in refs)
            assert not any('bridge' in n or 'nexus_verify_' in n for n in names if n.startswith('project/'))
            metadata=json.loads(package.read('evidence/upload.json'))
            assert metadata['graph_hash']==value['project_index']['graph_hash']
        save(tmp_path,'immutable-delivery-originals',{p.name:p.read_bytes() for p in (tmp_path/'records').iterdir() if p.is_file()})
        save(tmp_path,'export',exported)
        from nexus.web.app import create_app
        from nexus.repair.cegis_loop import RepairLoop
        app=create_app(store,RepairLoop(store),delivery,require_operator=False);app.testing=True;web=app.test_client();web.get('/')
        with web.session_transaction() as session:session['actor_id']='alice'
        before=web.get('/api/candidates/'+c.id)
        assert before.status_code==200 and before.json['checks'][-1]['state']=='PASS'
        xml=next(iter(tested.package_evidence['test']['reports'].values()))
        (tmp_path/xml['ref']).write_bytes(b'<tampered disposable original/>')
        with pytest.raises(ValueError):delivery.acceptance(c.id,approval.id,actor_id='alice')
        after=web.get('/api/candidates/'+c.id)
        assert after.status_code==200 and after.json['checks'][-1]['state']=='UNKNOWN' and after.json['check_set_hash'] is None
    asyncio.run(run())
