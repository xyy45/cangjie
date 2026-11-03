"""Focused regressions for the one whole-stage review; execution is explicit fixtures."""
import asyncio,json,re
import pytest
from nexus.contracts import CandidateProposal,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.repair import oracle,primitive_trace,sequence_trace
from tests.test_primitive_trace import TOKEN,signature as numeric_signature,log as primitive_log
from tests.test_sequence_trace import contract as numeric_sequence,trajectory,log as sequence_log
from tests.test_string_trace import sig,fixture,model,sequence_fixture
from tests.test_string_services import fake_sdk
from tests.test_string_uploads import prepare
from tests.test_relation_service import record_public


@pytest.mark.parametrize('kind',['single-v1','relation-v1','single-v2','relation-v2','oracle-v2','sequence-v1','sequence-v2'])
@pytest.mark.parametrize('prefix',primitive_trace.OBSERVATION_PREFIXES)
@pytest.mark.parametrize('position',['before-suite','after-observations'])
def test_reserved_protocol_with_embedded_suite_header_is_never_ignored(kind,prefix,position):
    if kind=='sequence-v1':text=sequence_log();run=lambda value:sequence_trace.interpret(numeric_sequence(),[trajectory()],TOKEN,value,0,None)
    elif kind=='sequence-v2':
        contract,trace=model();text=sequence_fixture();run=lambda value:sequence_trace.interpret(contract,[trace],TOKEN,value,0,None)
    elif kind.endswith('v1'):
        protocol=kind.split('-')[0];text=primitive_log(protocol);run=lambda value:primitive_trace.read(numeric_signature(),[[1],[2]],TOKEN,protocol,value,0,None)
    else:
        protocol=kind.split('-')[0];text=fixture(protocol,['s:61']);run=lambda value:primitive_trace.read(sig(),[['a']],TOKEN,protocol,value,0,None,version=2)
    assert run(text)['state']=='PASS'
    injected=prefix+'wrong|case0|VALUE_LIMIT TCS: injected,'+chr(10)
    if position=='before-suite':
        marker=next(line for line in text.splitlines(True) if 'TCS:' in line);changed=text.replace(marker,injected+marker,1)
    else:changed=text.replace('Summary:',injected+'Summary:',1)
    result=run(changed)
    assert result['state']=='UNKNOWN' and not result['observations'] and not result.get('failures')


def test_oracle3_invalid_unsampled_shrink_model_is_rejected_before_sdk(tmp_path,monkeypatch):
    from nexus.repair.exploration import ExplorationService
    from nexus.repair import exploration
    uploads,draft,args=prepare(tmp_path)
    expression='('+json.dumps('x'*256)+' + "!") if qty == 50 else code + (":Y" if qty > 0 else ":N")'
    raw=dict(version=3,function='ticket',domains=dict(code=dict(values=['']),qty=dict(min=0,max=100,points=[])),expression=expression,seed=7,max_cases=16,excluded_inputs=[])
    args['examples_json']=json.dumps([dict(args=['',0],expected=':N',suite='target'),dict(args=['',1],expected=':Y',suite='regression')])
    confirmed=uploads.confirm(draft['id'],**args,oracle_json=json.dumps(raw));contract=confirmed['oracle_contract']
    assert ['',50] not in oracle.generate_inputs(contract) and ['',50] in oracle.shrink_inputs(contract,['',100])
    source=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.');req=RequirementService(store);d=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice');task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj');c=ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']));record_public(store,ws,task,c)
    calls=fake_sdk(monkeypatch,'oracle',good=True);underlying=exploration.run_command
    async def one_failure(*arguments,**kwargs):
        code,log,problem=await underlying(*arguments,**kwargs)
        for i,args in enumerate(calls[-1]):
            if args==['',100]:log=re.sub(r'(NEXUS_ORACLE_V2\|[0-9a-f]{16}\|case'+str(i)+r'\|String\|)s:[0-9a-f]*',r'\g<1>s:626164',log)
        return code,log,problem
    monkeypatch.setattr(exploration,'run_command',one_failure);engine=ExplorationService(store);report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and len(calls)==1 and len(report['batches'])==1
    assert report['shrink_cases']==0 and '256' in report['reason'] and report['failures'][0]['args']==['',100]
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==1
    with store.connect() as db:assert db.execute('SELECT state FROM exploration_runs WHERE candidate_id=?',(c.id,)).fetchone()[0]=='UNKNOWN'
