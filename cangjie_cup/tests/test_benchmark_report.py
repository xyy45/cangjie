from copy import deepcopy

import pytest

from nexus.benchmark.runner import BUDGET
from nexus.benchmark.report import summarize,markdown


def row(task,mode,success,origin='LIVE'):
    return dict(task_id=task,family='quantity',variant=1,mode=mode,origin=origin,implementation_hash='a'*64,corpus_hash='a'*64,budget=dict(BUDGET),
        model_ids=['same-model'],verified_repair=success,build_state='PASS',public_state='PASS',holdout_state='PASS' if success else 'UNKNOWN',
        duration_ms=100,repair_duration_ms=80,model_requests=1,prompt_tokens=10,completion_tokens=5,total_tokens=15,usage_state='KNOWN')


def test_unknowns_stay_in_denominator_and_all_modes_same_task_cohort():
    rows=[row(t,m,t=='a') for t in ('a','b') for m in ('direct','mcp','cegis')]
    report=summarize(rows)
    assert report['comparison_state']=='LIVE_COMPARABLE'
    assert all(m['tasks']==2 and m['verified_repairs']==1 and m['verified_repair_rate']==0.5 and m['unknown_holdout']==1 for m in report['modes'])
    assert report['families'][0]['tasks']==6 and report['families'][0]['verified_repairs']==3
    assert all(m['estimated_cost'] is None for m in report['modes'])
    assert summarize(rows[:-1])['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    with pytest.raises(ValueError):summarize(rows+[rows[0]])


def test_fixture_mixed_models_budgets_and_missing_usage_cannot_claim_fair_live_result():
    rows=[row('a',m,True,'FIXTURE') for m in ('direct','mcp','cegis')]
    assert summarize(rows)['comparison_state']=='FIXTURE_ONLY'
    rows[0]['origin']='LIVE'
    assert summarize(rows)['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    rows=[row('a',m,True) for m in ('direct','mcp','cegis')]
    rows[1]['model_ids']=['another-model']
    assert summarize(rows)['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    rows[1]['model_ids']=['same-model'];rows[1]['budget']['max_rounds']=9
    assert summarize(rows)['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    rows[1]['budget']=dict(BUDGET);rows[1]['usage_state']='UNKNOWN';rows[1]['prompt_tokens']=None
    report=summarize(rows,prices={'input_per_million':'1','output_per_million':'2','currency':'CNY'})
    assert report['modes'][1]['estimated_cost'] is None
    assert report['modes'][0]['estimated_cost']=='0.000020'
    assert 'UNKNOWN' in markdown(report) and '私有验收' in markdown(report)
    with pytest.raises(ValueError):summarize(rows,prices={'input_per_million':'NaN','output_per_million':'2','currency':'CNY'})
