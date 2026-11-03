"""Service binding over explicit SDK fixtures; native axes are real.

This file is not real SDK/model repair evidence. Separate sdk tests own that.
"""
import asyncio,json,re
from pathlib import Path
import pytest
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.repair import oracle,string_trace,values
from tests.test_string_uploads import prepare
from tests.test_string_contracts import raw_oracle,raw_property,raw_relation
from tests.test_relation_service import record_public

MODULES={'oracle':'nexus.repair.exploration','property':'nexus.repair.property_service','relation':'nexus.repair.relation_service'}
CLASSES={'oracle':'ExplorationService','property':'PropertyService','relation':'RelationService'}


def setup(root,kind,*,previous=False):
    uploads,draft,args=prepare(root);models={kind:({'oracle':raw_oracle,'property':raw_property,'relation':raw_relation}[kind]())}
    if previous:models['oracle']=raw_oracle()
    uploads.confirm(draft['id'],**args,**{('properties' if k=='property' else 'relations' if k=='relation' else k)+'_json':json.dumps(v) for k,v in models.items()})
    source=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.')
    requirements=RequirementService(store);prepared=requirements.prepare_requirement(draft['id'],uploads.profile(draft['id'])['goal'])
    spec=requirements.confirm_requirement(prepared['id'],dict(schema_version=1,expected_version=1,requirements=prepared['requirements'],allowed_paths=prepared['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def apply(suffix=''):
        c=ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+chr(10)+'// fixture '+suffix+chr(10))],requirement_refs=['REQ-UPLOAD']))
        record_public(store,ws,task,c);return c
    import importlib
    engine=getattr(importlib.import_module(MODULES[kind]),CLASSES[kind])(store)
    return store,ws,task,apply,engine


def fake_sdk(monkeypatch,kind,*,good=False,unknown=False):
    import importlib
    module=importlib.import_module(MODULES[kind]);calls=[]
    async def run(project,argv,**kwargs):
        path=project/'src'/('boundary_test.cj' if kind=='oracle' else 'property_observations_test.cj' if kind=='property' else 'relation_observations_test.cj')
        program=path.read_text();prefix,nonce=re.search(r'(NEXUS_(?:ORACLE|PROPERTY|RELATION)_V2)'+chr(92)+'|([0-9a-f]{16})',program).groups();cls=re.search(r'class ([A-Za-z_0-9]+)',program)[1]
        rows=re.findall(r'let __nexusObserved(?:Value)* = __nexusV2Bound[A-Za-z_0-9]*'+chr(92)+'(([^'+chr(10)+']*)'+chr(92)+')',program)
        args=[]
        for row in rows:
            args.append([values.decode_string_literal(v) if v.startswith('"') else v=='true' if v in ('true','false') else int(v) for v in row.split(', ')])
        calls.append(args);lines=['EXPLICIT SDK LOG FIXTURE','TP: uploaded, RESULT:',' TCS: '+cls+', RESULT:']
        for i,arg in enumerate(args):
            actual=arg[0]+(':Y' if arg[1]>0 else ':N') if good else '' if kind!='relation' else 'collision'
            lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' '+prefix+'|'+nonce+'|case'+str(i)+'|String|'+string_trace.encode(actual,'String')])
        n=len(args);lines.extend(['Summary: TOTAL: '+str(n)+' PASSED: '+str(n)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]);assert kwargs['test_output']=='all'
        return (None,chr(10).join(lines),'TimeoutError') if unknown else (0,chr(10).join(lines),None)
    monkeypatch.setattr(module,'run_command',run);return calls


def test_string_oracle3_uses_observed_typed_empty_failure_and_no_reexecution(tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,'oracle');calls=fake_sdk(monkeypatch,'oracle');c=apply();manifest=source_manifest(ws.subject_path(c.id))
    report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL' and report['public_test_state']=='PASS'
    failure=report['failures'][0];assert failure['actual_return']=='' and failure['actual']=='""' and type(failure['expected_value']) is str
    assert failure['test_id'].startswith('NexusOracleV2') and failure['source']['log_ref']
    assert report['batches'][0]['token'] and report['batches'][0]['result']['observations']
    count=len(calls);assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==count
    assert source_manifest(ws.subject_path(c.id))==manifest


@pytest.mark.parametrize('kind',['property','relation'])
def test_string_failure_score_and_observer_dependencies_are_usable(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind);c=apply();report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['failures'] and calls
    assert engine.verify(c.id)==report


@pytest.mark.parametrize('kind',['oracle','property','relation'])
@pytest.mark.parametrize('dependency',[string_trace,values])
def test_string_encoder_and_value_source_changes_invalidate_saved_reports(kind,dependency,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    changed=tmp_path/'changed'/Path(dependency.__file__).name;changed.parent.mkdir();changed.write_bytes(Path(dependency.__file__).read_bytes()+b'# changed dependency')
    monkeypatch.setattr(dependency,'__file__',str(changed))
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation'])
def test_string_public_log_changes_invalidate_all_independent_reports(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();assert asyncio.run(engine.run(c.id))['state']=='PASS'
    record=[r for r in store.records(task.id,'check') if r['subject_id']==c.id and r['kind']=='test'][-1]
    (store.root/record['log_ref']).write_text('changed public log')
    with pytest.raises(ValueError):engine.verify(c.id)


def test_string_property_requires_current_configured_oracle_before_execution(tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,'property',previous=True);calls=fake_sdk(monkeypatch,'property',good=True);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and not calls and not report['batches']


def test_string_oracle_unknown_does_not_retry_or_allow_a_later_candidate(tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,'oracle');calls=fake_sdk(monkeypatch,'oracle',unknown=True);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and len(calls)==1
    assert asyncio.run(engine.run(c.id))==report and len(calls)==1
    next_candidate=apply('later');assert asyncio.run(engine.run(next_candidate.id))['state']=='UNKNOWN' and len(calls)==1


@pytest.mark.parametrize('kind',['oracle','property','relation'])
def test_prior_started_string_report_blocks_later_candidate(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind,good=True);first=apply('first')
    table={'oracle':'exploration_runs','property':'property_runs','relation':'relation_runs'}[kind]
    with store.connect() as db:db.execute('INSERT INTO '+table+' VALUES (?,?,?,NULL,NULL)',(first.id,task.id,'STARTED'))
    second=apply('second');report=asyncio.run(engine.run(second.id))
    assert report['state']=='UNKNOWN' and not calls and not report['batches']
    assert engine.verify(second.id)==report


@pytest.mark.parametrize('field',['seed','algorithm','search_cases','shrink_cases','regression_cases','failures','inputs','token','argv'])
def test_string_oracle_report_is_reconstructed_even_with_fresh_record_hash(tmp_path,monkeypatch,field):
    store,ws,task,apply,engine=setup(tmp_path,'oracle');fake_sdk(monkeypatch,'oracle',good=True);c=apply();report=asyncio.run(engine.run(c.id))
    assert report['state']=='PASS'
    if field in ('seed','search_cases','shrink_cases','regression_cases'):report[field]+=1
    elif field=='algorithm':report[field]='other'
    elif field=='failures':report['failures']=[{}]
    elif field=='inputs':report['batches'][0]['inputs']=report['batches'][0]['inputs'][::-1]
    elif field=='token':report['batches'][0]['token']='f'*16
    else:report['batches'][0]['execution_argv']=[]
    ref,hash_=engine.write_record(report,'.exploration.json')
    with store.connect() as db:db.execute('UPDATE exploration_runs SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,hash_,c.id))
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation'])
def test_string_report_replay_has_no_execution_or_network(kind,tmp_path,monkeypatch):
    import importlib,socket
    from nexus.policy import core
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    def forbidden(*args,**kwargs):raise AssertionError('verification triggered external effect')
    monkeypatch.setattr(importlib.import_module(MODULES[kind]),'run_command',forbidden);monkeypatch.setattr(core.NativeCoreClient,'call',forbidden);monkeypatch.setattr(socket,'create_connection',forbidden)
    assert engine.verify(c.id)==report
