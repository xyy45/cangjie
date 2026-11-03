"""Array reconstruction and side-effect gates, over explicit SDK fixtures."""
import asyncio,json,re
from copy import deepcopy
import pytest
from nexus.repair import oracle
from nexus.uploads.service import UploadService
from nexus.store import RunStore
from tests.test_array_services import setup,register,fake_sdk

TABLES={'oracle':'exploration_runs','property':'property_runs','relation':'relation_runs','sequence':'sequence_runs'}


def replace_report(store,engine,candidate,kind,report):
    ref,identity=engine.write_record(report,'.tampered.json')
    with store.connect() as db:db.execute('UPDATE '+TABLES[kind]+' SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,identity,candidate.id))


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_batch_count_bool_cannot_equal_integer_with_fresh_record_hash(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    report=deepcopy(report);assert report['batches'][0]['result']['counts']['failed']==0;report['batches'][0]['result']['counts']['failed']=False
    replace_report(store,engine,c,kind,report)
    with pytest.raises(ValueError):engine.verify(c.id)


def test_oracle4_nested_bool_cannot_replace_int64_return_with_fresh_hash(tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,'oracle',array_return=True);fake_sdk(monkeypatch,'oracle',good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    report=deepcopy(report);item=next(o for o in report['batches'][0]['result']['observations'] if o['actual_return']==[1]);item['actual_return']=[True]
    replace_report(store,engine,c,'oracle',report)
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
@pytest.mark.parametrize('field',['schema_version','seed','algorithm'])
def test_array_report_metadata_is_reconstructed_with_fresh_record_hash(kind,field,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    report=deepcopy(report);report[field]='forged' if field=='algorithm' else 999
    replace_report(store,engine,c,kind,report)
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_zero_regression_count_is_not_boolean_false(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    field={'oracle':'regression_cases','property':'regression_cases','relation':'regression_pairs','sequence':'regression_traces'}[kind]
    report=deepcopy(report);assert report[field]==0;report[field]=False;replace_report(store,engine,c,kind,report)
    with pytest.raises(ValueError):engine.verify(c.id)


def test_oracle4_invalid_unsampled_shrink_model_is_rejected_before_sdk(tmp_path,monkeypatch):
    import nexus.repair.exploration as exploration
    expression='array_append(['+','.join('0' for _ in range(16))+'], 0) if qty == 50 else []'
    raw=dict(version=4,function='keep',domains=dict(items=dict(values=[[]]),qty=dict(min=0,max=100,points=[])),expression=expression,seed=7,max_cases=16,excluded_inputs=[])
    uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare('keep.cj',b'public func keep(items: Array<Int64>, qty: Int64): Array<Int64> { [] }\n','返回空数组',actor_id='alice',request_key='k')
    args=dict(expected_version=1,function='keep',examples_json=json.dumps([dict(args=[[],0],expected=[],suite='target'),dict(args=[[],1],expected=[],suite='regression')]),consent=True,actor_id='alice')
    sig=next(f for f in draft['functions'] if f['name']=='keep');contract=oracle.validate_contract(raw,sig,[])
    assert [[],50] not in oracle.generate_inputs(contract) and [[],50] in oracle.shrink_inputs(contract,[[],100])
    store,ws,task,apply,engine=register(uploads,draft,args,dict(oracle=raw),'oracle');calls=fake_sdk(monkeypatch,'oracle',good=True);underlying=exploration.run_command
    async def one_failure(*arguments,**kwargs):
        code,log,problem=await underlying(*arguments,**kwargs)
        for i,values in enumerate(calls[-1]):
            if values==[[],100]:log=re.sub(r'(NEXUS_ORACLE_V3\|[0-9a-f]{16}\|case'+str(i)+r'\|Array<Int64>\|)a:0:',r'\g<1>a:1:1',log)
        return code,log,problem
    monkeypatch.setattr(exploration,'run_command',one_failure);c=apply();report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and len(calls)==1 and len(report['batches'])==1 and report['shrink_cases']==0
    assert '16' in report['reason'] and report['failures'][0]['args']==[[],100]
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==1
    assert len([e for e in store.records(task.id,'event') if e['type']=='EXPLORATION_BATCH_STARTED'])==1
