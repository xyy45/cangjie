"""Real pinned SDK checks authored defects; no model or remote MCP requests."""
import asyncio

import pytest

from nexus.benchmark.hard_corpus import build_hard_corpus
from nexus.benchmark.corpus import load_corpus
from nexus.benchmark.quality import validate_quality, verify_quality

pytestmark=pytest.mark.sdk


def test_hard_baseline_reference_quality(tmp_path):
    root=tmp_path/'data';build_hard_corpus(root,count=10)
    corpus=load_corpus(root)
    selected={**corpus,'tasks':[corpus['tasks'][i] for i in (0,2,8)]}
    result=asyncio.run(validate_quality(selected,tmp_path/'quality'))
    assert result['state']=='PASS',result['tasks']
    assert len(result['tasks'])==3
    for row in result['tasks']:
        assert row['baseline_build']==row['baseline_public']=='PASS'
        assert row['baseline_holdout']=='FAIL'
        assert row['reference_build']==row['reference_public']==row['reference_holdout']=='PASS'
    replay=verify_quality(root,tmp_path/'quality')
    assert replay['result_hash']==result['result_hash']
    assert replay['kind']=='CORPUS_QUALITY_NOT_MODEL_EVALUATION'


def test_hard_cross_file_three_mode_runner_with_real_sdk(tmp_path):
    from nexus.analysis.service import AnalysisService
    from nexus.benchmark.runner import run_case,verify_run
    from nexus.contracts import CandidateProposal
    from tests.analysis.test_repair_localization import GraphTransport
    root=tmp_path/'data';build_hard_corpus(root,10);corpus=load_corpus(root);case=corpus['tasks'][8]
    for mode in ('direct','mcp','cegis'):
        captured=[]
        class Provider:
            def __init__(self,*args):pass
            async def propose(self,context):
                captured.append(context)
                assert not set(context).intersection({'holdout','reference','oracle','normalized_oracle'})
                assert all(not p.startswith('verification/') for p in context['files'])
                assert ('analysis' in context)==(mode!='direct')
                return CandidateProposal(edits=[dict(path=p,before_hash=context['files'][p]['file_hash'],content=raw.decode())
                    for p,raw in case['reference'].items()],requirement_refs=['REQ-UPLOAD'])
        output=tmp_path/mode
        result=asyncio.run(run_case(corpus,case,mode,output,origin='FIXTURE',provider_factory=Provider,
            analysis_factory=lambda store:AnalysisService(store.root,client_factory=GraphTransport)))
        assert len(captured)==1 and result['verified_repair'] and result['origin']=='FIXTURE'
        assert result['model_requests']==0 and result['holdout_state']=='PASS'
        assert verify_run(root,output)['result_hash']==result['result_hash']
