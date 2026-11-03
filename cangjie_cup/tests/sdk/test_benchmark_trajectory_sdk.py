"""HTTP/model and graph fixtures, real pinned SDK and native search execution."""
import asyncio
import json

import httpx
import pytest

from nexus.analysis.service import AnalysisService
from nexus.benchmark.corpus import load_corpus
from nexus.benchmark.hard_corpus import build_hard_corpus
from nexus.benchmark.runner import run_case,verify_run,record_manifest
from nexus.benchmark.trajectory import analyze_run
from nexus.demo import deepseek
from nexus.store import RunStore
from tests.analysis.test_repair_localization import GraphTransport

pytestmark=pytest.mark.sdk


def test_trajectory_first_round_miss_then_real_counterexample_feedback(tmp_path,monkeypatch):
    data=tmp_path/'data';build_hard_corpus(data,10);corpus=load_corpus(data);case=corpus['tasks'][9]
    requests=[]
    def reply(request):
        assert request.url.host=='fixture.invalid'
        body=json.loads(request.content);context=json.loads(body['messages'][1]['content']);requests.append(context)
        assert 'holdout' not in context and 'reference' not in context and 'oracle' not in context
        assert all(not p.startswith('verification/') for p in context['files'])
        content=(case['source']['src/logic.cj'].decode()+'\n// First candidate keeps the defect.\n') if len(requests)==1 else case['reference']['src/logic.cj'].decode()
        refs=[t['evidence_id'] for f in context['analysis']['files'] for t in f['tools'] if t.get('included') and t['status']=='VALID']
        response=dict(schema_version=1,summary='Explicit fixed HTTP fixture',analysis_refs=refs,
                      suggestions=[dict(path='src/logic.cj',reason='Fixture proposal')],
                      proposal=dict(edits=[dict(path='src/logic.cj',before_hash=context['files']['src/logic.cj']['file_hash'],content=content)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='fixture-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),
            choices=[dict(finish_reason='stop',message=dict(content=json.dumps(response)))]))
    real_client=httpx.AsyncClient
    monkeypatch.setattr(deepseek,'model_config',lambda:dict(DEEPSEEK_API_KEY='fixture-placeholder',DEEPSEEK_BASE_URL='https://fixture.invalid/v1',DEEPSEEK_MODEL='fixture-model'))
    monkeypatch.setattr(deepseek.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(reply),**kw))
    run=tmp_path/'run'
    result=asyncio.run(run_case(corpus,case,'cegis',run,origin='FIXTURE',
        analysis_factory=lambda store:AnalysisService(store.root,client_factory=GraphTransport)))
    assert result['verified_repair'] and result['attempt_count']==2 and len(requests)==2
    assert requests[0]['feedback']==[] and requests[1]['feedback'][-1]['failure_cases']
    before=record_manifest(RunStore(run/'runtime'))
    report=analyze_run(data,run)
    assert report['state']=='KNOWN' and report['origin']=='FIXTURE'
    assert report['first_round_missed'] and report['observed_counterexample_feedback'] and report['later_repaired']
    assert report['rounds'][0]['public_state']=='PASS' and report['rounds'][0]['search_state']=='FAIL'
    assert report['rounds'][1]['public_state']==report['rounds'][1]['search_state']=='PASS'
    assert report==analyze_run(data,run)
    assert before==record_manifest(RunStore(run/'runtime'))
    assert verify_run(data,run)['result_hash']==result['result_hash']
