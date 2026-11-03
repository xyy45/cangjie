import pytest

from nexus.benchmark.corpus import build_corpus,load_corpus
from nexus.benchmark.runner import plan_runs,usage_metrics


def test_same_budget_three_modes_and_no_implicit_bulk_live_run(tmp_path):
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data')
    plan=plan_runs(corpus,['business_001'],['direct','mcp','cegis'],max_model_requests=9)
    assert len(plan['runs'])==3 and plan['max_model_requests']==9
    assert all(r['budget']==dict(max_rounds=3,timeout_seconds=480,max_output_tokens=6000,temperature=0.2) for r in plan['runs'])
    with pytest.raises(ValueError):plan_runs(corpus,[],['direct'],max_model_requests=99)
    with pytest.raises(ValueError):plan_runs(corpus,['business_001'],['mcp','cegis'],max_model_requests=5)
    with pytest.raises(ValueError):plan_runs(corpus,['unknown'],['direct'],max_model_requests=3)
    with pytest.raises(ValueError):plan_runs(corpus,['business_001'],['direct','direct'],max_model_requests=6)


def test_missing_usage_is_unknown_and_in_doubt_is_not_zero_cost():
    assert usage_metrics([])['prompt_tokens'] is None
    rows=[dict(id='a',status='STARTED',usage={}),dict(id='a-result',status='SUCCEEDED',usage={'prompt_tokens':10,'completion_tokens':5,'total_tokens':15})]
    assert usage_metrics(rows)==dict(model_requests=1,prompt_tokens=10,completion_tokens=5,total_tokens=15,usage_state='KNOWN')
    assert usage_metrics(rows+[dict(id='b',status='STARTED',usage={})])['usage_state']=='UNKNOWN'
    rows[-1]['usage']['prompt_tokens']=True
    assert usage_metrics(rows)['usage_state']=='UNKNOWN'


def test_cegis_candidate_before_exploration_is_reportable_not_success(tmp_path):
    from nexus.benchmark.runner import prepare,grade_summary
    from nexus.store import RunStore
    from nexus.execution.workspace import WorkspaceStore
    from nexus.contracts import CandidateProposal,file_hash
    build_corpus(tmp_path/'data',count=30);case=load_corpus(tmp_path/'data')['tasks'][0]
    store=RunStore(tmp_path/'run');task=prepare(store,case,'cegis')
    source=WorkspaceStore(store.root).verify_baseline(task.baseline_id)
    proposal=CandidateProposal(edits=[dict(path=p,before_hash=file_hash((source/p).read_text()),content=raw.decode()) for p,raw in case['reference'].items()],requirement_refs=['REQ-UPLOAD'])
    WorkspaceStore(store.root).apply_candidate(task,proposal)
    result=grade_summary(store,task.id,case,'cegis',None)
    assert result['independent_search_state']=='NOT_RUN' and not result['verified_repair']
