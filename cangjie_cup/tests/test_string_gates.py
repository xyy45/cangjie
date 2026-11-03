"""String controller/approval boundaries over explicit transport/SDK fixtures."""
import asyncio,json
import pytest
from nexus.contracts import CheckResult
from nexus.llm.provider import ProviderUnavailable
from nexus.repair.cegis_loop import RepairLoop
from nexus.execution.delivery import DeliveryService
from nexus.web.app import create_app
from tests.test_string_services import setup,fake_sdk
from tests.test_repair_loop import Client
from tests.test_web import Loop,authorize,OPERATOR_KEY


def test_actual_generation_context_describes_bounded_string_grammar(tmp_path):
    store,ws,task,_,_=setup(tmp_path,'oracle');contexts=[]
    class Stop:
        async def propose(self,context):contexts.append(context);raise ProviderUnavailable('EXPLICIT STOP BEFORE ANY MODEL REQUEST')
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Stop(),client_factory=Client).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    constraints=contexts[0]['upload_constraints']
    assert 'String' in constraints['types'] and constraints['string_max_utf8_bytes']==256
    assert '.size' in constraints['allowed'] and '.toRuneArray().size' in constraints['allowed']
    assert 'verification/oracle.json' not in contexts[0]['files']


def public_build(store,task,c):
    public=next(r for r in store.records(task.id,'check') if r['subject_id']==c.id and r['kind']=='test')
    result=CheckResult.model_validate({**public,'id':'fixture-build-'+c.id,'kind':'build','counts':{},'case_results':{},'suite_results':{},'argv':['cjpm','build'],
        'log_ref':'records/'+c.id+'.build.log','report_ref':'records/'+c.id+'.build.json','diagnostics':'EXPLICIT BUILD FIXTURE\ncjpm build success\n'})
    (store.root/result.log_ref).write_text(result.diagnostics);(store.root/result.report_ref).write_text(result.model_dump_json());store.append_record(task.id,'check',result.model_dump())


@pytest.mark.parametrize('kind',['oracle','property','relation'])
@pytest.mark.parametrize('state',['FAIL','UNKNOWN'])
def test_string_failure_or_unknown_cannot_be_user_approved(kind,state,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,unknown=state=='UNKNOWN');c=apply();public_build(store,task,c)
    report=asyncio.run(engine.run(c.id));assert report['state']==state
    store.update_task(task.id,status='REVIEW_PENDING');store.append_record(task.id,'event',dict(selected_candidate_id=c.id))
    delivery=DeliveryService(store)
    with pytest.raises(ValueError,match='验证尚未通过'):delivery.check_set_hash(c.id)
    app=create_app(store,Loop(),delivery,operator_key=OPERATOR_KEY);app.testing=True;app.config['RUN_TASKS']=False;client=app.test_client();authorize(client)
    with client.session_transaction() as s:s['actor_id']='alice';token=s['csrf']
    response=client.post('/api/candidates/'+c.id+'/accept',json=dict(check_set_hash='a'*64,task_revision=store.get_task(task.id).revision),headers={'Origin':'http://localhost','X-CSRF-Token':token})
    assert response.status_code==400 and response.json['code']=='CHECKS_NOT_PASS'
    assert not store.records(task.id,'acceptance') and not list((store.root/'exports').glob('*.zip'))
