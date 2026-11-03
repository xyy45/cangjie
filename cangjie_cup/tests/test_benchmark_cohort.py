"""Plan-bound report tests use explicit synthetic rows, never live AI."""
import json
from pathlib import Path

import pytest

from nexus.benchmark.corpus import build_corpus,load_corpus,encoded
from nexus.benchmark.runner import plan_runs,BUDGET
from nexus.benchmark.cohort import build_batch_report
from tests.test_benchmark_report import row


def batch(tmp_path):
    corpus_root=tmp_path/'data';build_corpus(corpus_root,count=30);corpus=load_corpus(corpus_root)
    root=tmp_path/'batch';root.mkdir()
    plan=plan_runs(corpus,['business_001','business_030'],['direct','mcp','cegis'],max_model_requests=18,origin='FIXTURE')
    (root/'plan.json').write_bytes(encoded(plan))
    return corpus_root,corpus,root,plan


def test_missing_whole_task_stays_in_plan_denominator(tmp_path,monkeypatch):
    corpus_root,corpus,root,plan=batch(tmp_path)
    verified={}
    for mode in ('direct','mcp','cegis'):
        r=row('business_001',mode,True,'FIXTURE');r.update(corpus_hash=corpus['corpus_hash'],result_hash=mode,implementation_hash=plan['implementation_hash'],run_state='COMPLETE',plan_hash=plan['plan_hash'])
        p=root/('business_001-'+mode);p.mkdir();(p/'result.json').write_text('{}');verified[p.resolve()]=r
        (p/'STARTED.json').write_bytes(encoded({k:r[k] for k in ('corpus_hash','task_id','mode','origin','budget','plan_hash','implementation_hash')}))
    monkeypatch.setattr('nexus.benchmark.cohort.verify_run',lambda c,p:verified[Path(p).resolve()])
    report=build_batch_report(corpus_root,root,tmp_path/'report')
    assert report['comparison_state']=='FIXTURE_ONLY' and report['plan_hash']==plan['plan_hash']
    assert report['cohort_kind']=='DECLARED_PLAN' and report['planned_runs']==6
    for m in report['modes']:
        assert m['tasks']==2 and m['verified_repairs']==1 and m['verified_repair_rate']==0.5
        assert m['missing_runs']==1 and m['estimated_cost'] is None and m['model_requests'] is None
    assert len(report['tasks'])==6
    assert {t['run_state'] for t in report['tasks']}=={'COMPLETE','MISSING'}


def test_inflight_request_preserved_with_unknown_usage_and_no_replay(tmp_path):
    from nexus.store import RunStore
    corpus_root,corpus,root,plan=batch(tmp_path)
    p=root/'business_001-direct';p.mkdir()
    (p/'STARTED.json').write_bytes(encoded(dict(corpus_hash=corpus['corpus_hash'],task_id='business_001',mode='direct',origin='FIXTURE',budget=BUDGET,plan_hash=plan['plan_hash'],implementation_hash=plan['implementation_hash'])))
    store=RunStore(p/'runtime');task=store.create_task('b_0','fixture',['src/a.cj'])
    req='records/call.request.json';(store.root/req).write_text('{"model":"fixture"}')
    store.append_record(task.id,'model_call',dict(id='call',task_id=task.id,origin='TEST',model_id='fixture',request_ref=req,status='STARTED'))
    report=build_batch_report(corpus_root,root,tmp_path/'report')
    interrupted=next(r for r in report['tasks'] if r['task_id']=='business_001' and r['mode']=='direct')
    assert interrupted['run_state']=='UNFINISHED' and interrupted['model_requests']==1
    assert interrupted['usage_state']=='UNKNOWN' and interrupted['verified_repair'] is False
    assert interrupted['prompt_tokens'] is None
    assert len(store.records(task.id,'model_call'))==1
    assert not (root/'business_001-mcp').exists()


def test_plan_and_started_binding_and_symlinks_are_rejected(tmp_path):
    corpus_root,corpus,root,plan=batch(tmp_path)
    changed={**plan,'max_model_requests':19};(root/'plan.json').write_bytes(encoded(changed))
    with pytest.raises(ValueError,match='计划'):build_batch_report(corpus_root,root,tmp_path/'bad')
    (root/'plan.json').write_bytes(encoded(plan));outside=tmp_path/'outside';outside.mkdir()
    (root/'business_001-direct').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='链接'):build_batch_report(corpus_root,root,tmp_path/'bad2')
    (root/'business_001-direct').unlink();p=root/'business_001-direct';p.mkdir()
    (p/'STARTED.json').write_bytes(encoded(dict(corpus_hash='f'*64,task_id='business_001',mode='direct',origin='FIXTURE',budget=BUDGET)))
    with pytest.raises(ValueError,match='绑定'):build_batch_report(corpus_root,root,tmp_path/'bad3')


def test_cli_stops_after_exception_and_preserves_declared_plan(tmp_path,monkeypatch,capsys):
    import nexus.benchmark.__main__ as cli
    corpus_root,corpus,_,_=batch(tmp_path);output=tmp_path/'cli';calls=[]
    async def interrupted(*args,**kwargs):
        calls.append(args[2]);raise OSError('fixture failure, do not persist arbitrary exception text')
    monkeypatch.setattr(cli,'run_case',interrupted)
    monkeypatch.setattr('sys.argv',['benchmark','--corpus',str(corpus_root),'run','--tasks','business_001,business_030','--modes','direct,mcp,cegis','--max-model-requests','18','--output',str(output)])
    with pytest.raises(SystemExit) as exc:cli.main()
    assert exc.value.code==1 and calls==['direct']
    assert (output/'plan.json').exists()
    stopped=json.loads((output/'STOPPED.json').read_text())
    assert stopped['error_type']=='OSError' and 'exception text' not in json.dumps(stopped)
    assert json.loads(capsys.readouterr().out)['batch_state']=='STOPPED'


def test_reduced_rehashed_plan_cannot_relabel_started_runs(tmp_path):
    corpus_root,corpus,root,plan=batch(tmp_path)
    p=root/'business_001-direct';p.mkdir()
    (p/'STARTED.json').write_bytes(encoded(dict(corpus_hash=corpus['corpus_hash'],task_id='business_001',mode='direct',origin='FIXTURE',budget=BUDGET,plan_hash=plan['plan_hash'],implementation_hash=plan['implementation_hash'])))
    reduced=plan_runs(corpus,['business_001'],['direct','mcp','cegis'],max_model_requests=9,origin='FIXTURE')
    (root/'plan.json').write_bytes(encoded(reduced))
    with pytest.raises(ValueError,match='绑定'):build_batch_report(corpus_root,root,tmp_path/'report')


def test_complete_results_also_validate_original_started_marker(tmp_path,monkeypatch):
    corpus_root,corpus,root,plan=batch(tmp_path)
    reduced=plan_runs(corpus,['business_001'],['direct','mcp','cegis'],max_model_requests=9,origin='FIXTURE')
    (root/'plan.json').write_bytes(encoded(reduced));rows={}
    for mode in ('direct','mcp','cegis'):
        p=root/('business_001-'+mode);p.mkdir();(p/'result.json').write_text('{}')
        (p/'STARTED.json').write_bytes(encoded(dict(corpus_hash=corpus['corpus_hash'],task_id='business_001',mode=mode,origin='FIXTURE',budget=BUDGET,plan_hash=plan['plan_hash'],implementation_hash=plan['implementation_hash'])))
        r=row('business_001',mode,True,'FIXTURE');r.update(corpus_hash=corpus['corpus_hash'],plan_hash=reduced['plan_hash'],result_hash=mode);rows[p.resolve()]=r
    monkeypatch.setattr('nexus.benchmark.cohort.verify_run',lambda c,p:rows[Path(p).resolve()])
    with pytest.raises(ValueError,match='绑定'):build_batch_report(corpus_root,root,tmp_path/'report')


def test_linked_records_root_is_rejected_for_incomplete_evidence(tmp_path):
    from nexus.store import RunStore
    corpus_root,corpus,root,plan=batch(tmp_path)
    p=root/'business_001-direct';p.mkdir()
    (p/'STARTED.json').write_bytes(encoded(dict(corpus_hash=corpus['corpus_hash'],task_id='business_001',mode='direct',origin='FIXTURE',budget=BUDGET,plan_hash=plan['plan_hash'],implementation_hash=plan['implementation_hash'])))
    store=RunStore(p/'runtime');outside=tmp_path/'external';(store.root/'records').rename(outside);(outside/'unrelated.txt').write_text('local fixture')
    (store.root/'records').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='链接'):build_batch_report(corpus_root,root,tmp_path/'report')


def test_linked_runtime_rejected_before_opening_any_database(tmp_path):
    from nexus.benchmark.runner import material_hash,verify_run
    from nexus.benchmark.quality import toolchain_identity
    from nexus.contracts import digest
    corpus_root,corpus,root,plan=batch(tmp_path);p=root/'business_001-direct';p.mkdir();case=corpus['tasks'][0]
    started=dict(corpus_hash=corpus['corpus_hash'],task_id=case['id'],mode='direct',origin='FIXTURE',budget=BUDGET,plan_hash=plan['plan_hash'],implementation_hash=plan['implementation_hash'])
    result={**started,'public_material_hash':material_hash(case),'toolchain':toolchain_identity(),'record_manifest':{}}
    result['result_hash']=digest(result);(p/'result.json').write_bytes(encoded(result));(p/'STARTED.json').write_bytes(encoded(started))
    outside=tmp_path/'external';outside.mkdir();(outside/'sentinel').write_text('unchanged');(p/'runtime').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ValueError,match='链接'):verify_run(corpus_root,p)
    assert [f.name for f in outside.iterdir()]==['sentinel']


@pytest.mark.parametrize('status,holdout,independent',[
    ('BLOCKED','NOT_RUN','NOT_ENABLED'),('REVIEW_PENDING','UNKNOWN','NOT_ENABLED'),
    ('REVIEW_PENDING','PASS','UNKNOWN'),('IN_DOUBT','PASS','NOT_ENABLED'),
])
def test_cli_stops_on_unknown_validation_before_next_paid_slot(tmp_path,monkeypatch,capsys,status,holdout,independent):
    import nexus.benchmark.__main__ as cli
    corpus_root,corpus,_,_=batch(tmp_path);calls=[];output=tmp_path/'cli-unknown'
    async def unfinished(corpus,case,mode,*args,**kwargs):
        calls.append((case['id'],mode))
        return dict(task_id=case['id'],mode=mode,verified_repair=False,task_status=status,holdout_state=holdout,
                    independent_search_state=independent,build_state='PASS',public_state='PASS')
    monkeypatch.setattr(cli,'run_case',unfinished)
    monkeypatch.setattr('sys.argv',['benchmark','--corpus',str(corpus_root),'run','--tasks','business_001,business_030','--modes','direct,mcp,cegis','--max-model-requests','18','--output',str(output)])
    with pytest.raises(SystemExit):cli.main()
    assert len(calls)==1
    assert json.loads(capsys.readouterr().out)['batch_state'] in ('IN_DOUBT','STOPPED')
    assert len(json.loads((output/'plan.json').read_bytes())['runs'])==6


def test_last_unresolved_result_is_not_complete_or_live_comparable(tmp_path,monkeypatch):
    corpus_root,corpus,root,plan=batch(tmp_path)
    # Only local, explicitly synthetic result bindings are used, no model invocation.
    plan=plan_runs(corpus,['business_001','business_030'],['direct','mcp','cegis'],max_model_requests=18)
    (root/'plan.json').write_bytes(encoded(plan));verified={}
    for i,slot in enumerate(plan['runs']):
        r=row(slot['task_id'],slot['mode'],i<5);r.update(corpus_hash=corpus['corpus_hash'],implementation_hash=plan['implementation_hash'],
            result_hash=str(i),plan_hash=plan['plan_hash'],family=next(t['family'] for t in corpus['tasks'] if t['id']==slot['task_id']),
            variant=next(t['variant'] for t in corpus['tasks'] if t['id']==slot['task_id']),task_status='IN_DOUBT' if i==5 else 'REVIEW_PENDING')
        p=root/(slot['task_id']+'-'+slot['mode']);p.mkdir();(p/'result.json').write_text('{}');verified[p.resolve()]=r
        (p/'STARTED.json').write_bytes(encoded({k:r[k] for k in ('corpus_hash','task_id','mode','origin','budget','plan_hash','implementation_hash')}))
    monkeypatch.setattr('nexus.benchmark.cohort.verify_run',lambda c,p:verified[Path(p).resolve()])
    report=build_batch_report(corpus_root,root,tmp_path/'report')
    assert report['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    assert report['completion_state']=='INCOMPLETE'
    assert report['tasks'][-1]['run_state']=='UNFINISHED' and report['tasks'][-1]['task_status']=='IN_DOUBT'
    assert report['planned_runs']==len(report['tasks'])==6
