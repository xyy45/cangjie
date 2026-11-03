"""Real pinned compiler/test execution; no model or remote analysis requests."""
import asyncio

import pytest

from nexus.benchmark.corpus import build_corpus,load_corpus
from nexus.benchmark.quality import validate_quality,verify_quality
from nexus.benchmark.runner import run_case,verify_run

pytestmark=pytest.mark.sdk


def test_real_sdk_baseline_defects_and_reference_fixes_are_independently_graded(tmp_path):
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data')
    selected={**corpus,'tasks':[corpus['tasks'][0],corpus['tasks'][-1]]}
    result=asyncio.run(validate_quality(selected,tmp_path/'quality'))
    assert result['state']=='PASS'
    assert len(result['tasks'])==2
    for row in result['tasks']:
        assert row['baseline_holdout']=='FAIL' and row['reference_public']==row['reference_holdout']=='PASS'
    assert verify_quality(tmp_path/'data',tmp_path/'quality')['result_hash']==result['result_hash']
    log=next((tmp_path/'quality'/'logs').glob('*.log'));log.write_text(log.read_text()+'forged')
    with pytest.raises(ValueError,match='摘要'):verify_quality(tmp_path/'data',tmp_path/'quality')


def test_three_mode_runner_real_sdk_separates_holdout_and_model_context(tmp_path):
    from nexus.contracts import CandidateProposal,file_hash
    from nexus.analysis.service import AnalysisService
    from tests.analysis.test_repair_localization import GraphTransport
    from nexus.benchmark.runner import plan_runs
    from nexus.benchmark.corpus import encoded
    from nexus.benchmark.cohort import build_batch_report
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data');case=corpus['tasks'][0]
    batch=tmp_path/'batch';batch.mkdir();plan=plan_runs(corpus,[case['id']],['direct','mcp','cegis'],max_model_requests=9,origin='FIXTURE')
    (batch/'plan.json').write_bytes(encoded(plan))
    for mode in ('direct','mcp','cegis'):
        captured=[]
        class Provider:
            def __init__(self,*args):pass
            async def propose(self,context):
                captured.append(context)
                assert 'holdout' not in context and 'reference' not in context and 'normalized_oracle' not in context
                assert all('verification/' not in p for p in context['files'])
                assert ('analysis' in context)==(mode!='direct')
                assert ('repair_focus' in context)==(mode!='direct')
                return CandidateProposal(edits=[dict(path=p,before_hash=context['files'][p]['file_hash'],content=raw.decode()) for p,raw in case['reference'].items()],requirement_refs=['REQ-UPLOAD'])
        output=batch/(case['id']+'-'+mode)
        result=asyncio.run(run_case(corpus,case,mode,output,origin='FIXTURE',provider_factory=Provider,
            analysis_factory=lambda store:AnalysisService(store.root,client_factory=GraphTransport),plan_hash=plan['plan_hash']))
        assert result['origin']=='FIXTURE' and result['verified_repair'] is True
        assert result['public_state']==result['holdout_state']=='PASS'
        assert result['model_requests']==0 and result['usage_state']=='UNKNOWN'
        assert result['independent_search_state']==('PASS' if mode=='cegis' else 'NOT_ENABLED')
        if mode=='cegis':
            from nexus.store import RunStore
            from nexus.repair.exploration import ExplorationService
            from nexus.repair.oracle import input_key
            search=ExplorationService(RunStore(output/'runtime')).verify(result['candidate_id'])
            held={input_key(e['args']) for e in case['holdout']}
            assert not held.intersection(input_key(a) for b in search['batches'] for a in b['inputs'])
        assert len(captured)==1
        assert verify_run(tmp_path/'data',output)['result_hash']==result['result_hash']
        with pytest.raises(FileExistsError):asyncio.run(run_case(corpus,case,mode,output,origin='FIXTURE',provider_factory=Provider))
    report=build_batch_report(tmp_path/'data',batch,tmp_path/'report')
    assert report['planned_runs']==3 and report['completion_state']=='COMPLETE' and report['comparison_state']=='FIXTURE_ONLY'
    assert all(m['tasks']==m['complete_runs']==m['verified_repairs']==1 for m in report['modes'])
    original=batch/(case['id']+'-direct')/'runtime/records';external=tmp_path/'external-records';original.rename(external);original.symlink_to(external,target_is_directory=True)
    try:
        with pytest.raises(ValueError,match='链接'):verify_run(tmp_path/'data',original.parent.parent)
    finally:
        original.unlink();external.rename(original)
