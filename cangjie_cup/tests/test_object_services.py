"""Object service integration: explicit SDK log fixtures, real local native axes."""
import asyncio,importlib,re,json
from copy import deepcopy
from pathlib import Path
import pytest
from nexus.contracts import source_manifest
from nexus.repair import oracle,primitive_trace,sequence_trace,sequences,object_trace,object_values,object_expressions
from nexus.uploads import object_types,language
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_array_services import register,MODULES
from tests.test_object_drafts import prepare
from tests.test_object_contracts import raw_oracle,raw_property,raw_relation,sequence_raw,state
from tests.sdk.test_objects_sdk import declaration


def setup(root,kind):
    if kind=='sequence':
        raw,_=sequence_raw();u=UploadService(RunStore(root));d=u.prepare('state.cj',(declaration()+'public func advance(mode: Int64, state: OrderState, label: String): OrderState { state }\n').encode(),'切换状态的amount字段',actor_id='alice',request_key='one')
        args=dict(expected_version=1,function='advance',examples_json=json.dumps([dict(args=[0,state(0),'a'],expected=state(1),suite='target'),dict(args=[0,state(1),'a'],expected=state(0),suite='regression')]),consent=True,actor_id='alice');models=dict(sequence=raw)
    else:
        u,d,args=prepare(root);raw={'oracle':raw_oracle,'property':raw_property,'relation':raw_relation}[kind]()
        if kind=='relation':
            raw['relations'][0].update(precondition='object_get(left_arg0,"amount") <= object_get(right_arg0,"amount") and left_arg1 == right_arg1',assertion='object_get(left_result,"amount") <= object_get(right_result,"amount")')
        models={kind:raw}
    return register(u,d,args,models,kind)


def fake_sdk(monkeypatch,kind,*,good=False,unknown=False):
    module=importlib.import_module(MODULES[kind]);captured={};calls=[];primitive=primitive_trace.harness;sequence=sequence_trace.harness
    def observe(signature,cases,package,token,protocol,version=1):
        captured[token]=dict(signature=deepcopy(signature),cases=deepcopy(cases));return primitive(signature,cases,package,token,protocol,version)
    def paths(contract,traces,package,token):
        captured[token]=dict(contract=deepcopy(contract),traces=deepcopy(traces));return sequence(contract,traces,package,token)
    monkeypatch.setattr(primitive_trace,'harness',observe);monkeypatch.setattr(sequence_trace,'harness',paths)
    async def run(project,argv,**kwargs):
        filename={'oracle':'boundary_test.cj','property':'property_observations_test.cj','relation':'relation_observations_test.cj','sequence':'sequence_observations_test.cj'}[kind]
        program=(project/'src'/filename).read_text();prefix,nonce=re.search(r'(NEXUS_(?:ORACLE|PROPERTY|RELATION|SEQUENCE)_V4)\|([0-9a-f]{16})',program).groups();cls=re.search(r'class (\w+)',program)[1];data=captured[nonce]
        lines=['EXPLICIT SDK LOG FIXTURE - NOT ACTUAL SDK','TP: uploadedrepair, RESULT:',' TCS: '+cls+', RESULT:']
        if kind=='sequence':
            contract,traces=data['contract'],data['traces'];calls.append(deepcopy(traces));primitive_kind=contract['signature']['return_type'];types=contract['signature']['types']
            for i,trace in enumerate(traces):
                plan=sequences.reference_trace(contract,trace);before=deepcopy(trace['initial_state']);mode='COMPLETE';lines+=[' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:']
                for j,step in enumerate(plan['steps']):
                    actual=deepcopy(step['expected_state'] if good else before)
                    lines.append(' NEXUS_SEQUENCE_V4|'+nonce+'|case'+str(i)+'|step'+str(j)+'|'+primitive_kind+'|'+object_trace.encode(before,primitive_kind,types)+'|'+object_trace.encode(actual,primitive_kind,types));before=actual
                    if actual!=step['expected_state']:mode='MODEL_MISMATCH';break
                lines.append(' NEXUS_SEQUENCE_END_V4|'+nonce+'|case'+str(i)+'|'+str(j+1)+'|'+mode)
            count=len(traces)
        else:
            cases=data['cases'];sig=data['signature'];calls.append(deepcopy(cases));primitive_kind=sig['return_type']
            for i,args in enumerate(cases):
                actual=deepcopy(args[0]);amount=args[0]['fields']['amount'];actual['fields']['amount']=(amount if good else 3-amount) + args[1] if kind=='relation' else amount+args[1]+(0 if good else 1)
                lines+=[' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' '+prefix+'|'+nonce+'|case'+str(i)+'|'+primitive_kind+'|'+object_trace.encode(actual,primitive_kind,sig['types'])]
            count=len(cases)
        lines+=['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success','']
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]);assert kwargs['test_output']=='all'
        return (None,'\n'.join(lines),'TimeoutError') if unknown else (0,'\n'.join(lines),None)
    monkeypatch.setattr(module,'run_command',run);return calls


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_object_services_fail_pass_replay_and_snapshot_inputs(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind);c=apply();manifest=source_manifest(ws.subject_path(c.id));report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['public_test_state']=='PASS' and report['failures'] and engine.verify(c.id)==report
    assert asyncio.run(engine.run(c.id))==report and 1<=len(calls)<=3 and source_manifest(ws.subject_path(c.id))==manifest
    assert type(report['failures'][0]['actual_return'] if kind!='relation' else report['failures'][0]['left_actual_return']) is dict
    calls.clear();fake_sdk(monkeypatch,kind,good=True);next_candidate=apply('fixed-fixture');result=asyncio.run(engine.run(next_candidate.id));assert result['state']=='PASS' and engine.verify(next_candidate.id)==result


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
@pytest.mark.parametrize('dependency',[object_values,object_expressions,object_trace,object_types,language])
def test_object_service_binds_complete_type_and_encoder_dependencies(kind,dependency,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();assert asyncio.run(engine.run(c.id))['state']=='PASS'
    monkeypatch.setattr(dependency,'__file__',str(Path(oracle.__file__)))
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_object_service_unknown_is_not_reexecuted_or_reclassified(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind,unknown=True);c=apply();r=asyncio.run(engine.run(c.id));assert r['state']=='UNKNOWN' and not r['failures'] and len(calls)==1
    assert asyncio.run(engine.run(c.id))==r and len(calls)==1 and engine.verify(c.id)==r
