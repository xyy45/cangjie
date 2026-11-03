"""Explicit SDK sequence fixtures, not compilation or model quality evidence."""
import asyncio,json,importlib
from pathlib import Path
import pytest
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.repair import values,string_trace,sequences,sequence_trace
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_string_contracts import sequence_raw
from tests.test_relation_service import record_public


def setup(tmp_path):
    raw,_=sequence_raw()
    source=b'public func appendState(op: Int64, current: String, label: String): String {\nif (op == 1) { return "" }\nreturn current + label\n}\n'
    uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare('state.cj',source,'bounded append/reset',actor_id='alice',request_key='s')
    examples=[dict(args=[0,'','a'],expected='a',suite='target'),dict(args=[1,'a','a'],expected='',suite='regression')]
    uploads.confirm(draft['id'],expected_version=1,function='appendState',examples_json=json.dumps(examples),sequences_json=json.dumps(raw),consent=True,actor_id='alice')
    source=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);d=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice');task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    c=ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// explicit fixture\n')],requirement_refs=['REQ-UPLOAD']))
    record_public(store,ws,task,c)
    engine=importlib.import_module('nexus.repair.sequence_service').SequenceService(store)
    return store,ws,c,engine


def sdk(monkeypatch,good=True):
    module=importlib.import_module('nexus.repair.sequence_service');plans={};original=sequence_trace.harness;calls=[]
    def capture(contract,traces,package,token):plans[token]=(contract,traces);return original(contract,traces,package,token)
    monkeypatch.setattr(sequence_trace,'harness',capture)
    async def run(project,argv,**kwargs):
        calls.append(project);token=next(reversed(plans));contract,traces=plans[token];rows=['EXPLICIT SDK LOG FIXTURE','TP: uploaded, RESULT:',' TCS: NexusSequencesV2'+token+', RESULT:']
        for i,trace in enumerate(traces):
            plan=sequences.reference_trace(contract,trace);before=trace['initial_state'];mode='COMPLETE';rows+=[' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:']
            for j,step in enumerate(plan['steps']):
                actual=step['expected_state'] if good else before
                rows.append(' NEXUS_SEQUENCE_V2|'+token+'|case'+str(i)+'|step'+str(j)+'|String|'+string_trace.encode(before,'String')+'|'+string_trace.encode(actual,'String'));before=actual
                if actual!=step['expected_state']:mode='MODEL_MISMATCH';break
            rows.append(' NEXUS_SEQUENCE_END_V2|'+token+'|case'+str(i)+'|'+str(j+1)+'|'+mode)
        n=len(traces);rows+=['Summary: TOTAL: '+str(n)+' PASSED: '+str(n)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success','']
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]);assert kwargs['test_output']=='all'
        return 0,chr(10).join(rows),None
    monkeypatch.setattr(module,'run_command',run);return calls


@pytest.mark.parametrize('dependency',[values,string_trace])
def test_string_sequence_codec_dependency_invalidates_report(tmp_path,monkeypatch,dependency):
    store,ws,c,engine=setup(tmp_path);sdk(monkeypatch);report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    alternative=Path(dependency.__file__).with_name('oracle.py');monkeypatch.setattr(dependency,'__file__',str(alternative))
    with pytest.raises(ValueError):engine.verify(c.id)


def test_string_sequence_actual_empty_and_state_prefix_remain_typed(tmp_path,monkeypatch):
    store,ws,c,engine=setup(tmp_path);sdk(monkeypatch,False);manifest=source_manifest(ws.subject_path(c.id));report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['failures']
    step=report['failures'][0]['steps'][-1];assert type(step['before_state']) is str and type(step['actual_return']) is str and step['source']['log_ref']
    assert engine.verify(c.id)==report and source_manifest(ws.subject_path(c.id))==manifest
