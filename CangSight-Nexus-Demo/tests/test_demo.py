"""Demo provenance, offline behavior and real execution boundaries."""
import asyncio
import io
import json
import zipfile

import pytest

from nexus.demo.app import create_demo_app
from nexus.demo.provider import RuleProvider
from nexus.store import RunStore


@pytest.fixture
def client(tmp_path):
    app = create_demo_app(tmp_path)
    app.config['TESTING'] = True
    return app.test_client()


def test_minimal_workbench_and_offline_cases_need_no_pairing(client):
    page = client.get('/')
    assert page.status_code == 200
    assert 'CangSight' in page.text
    assert '让修改，经得起真实验证' not in page.text
    cases = client.get('/demo/cases').json['cases']
    assert {c['origin'] for c in cases} == {'LIVE_REPLAY', 'SIMULATED', 'NATIVE_REPLAY', 'SAMPLE'}
    assert all('stages' not in c for c in cases)
    assert client.get('/api/tasks').status_code == 200


def test_historical_replay_preserves_original_and_never_claims_current_execution(client):
    case = client.get('/demo/cases/order').json
    assert case['origin'] == 'LIVE_REPLAY'
    assert case['metrics']['tests'] == 11
    assert case['metrics']['files'] == 1
    assert case['metrics']['tokens'] == 4529
    assert case['approval_origin'].startswith('AUTOMATED_')
    response = client.get('/demo/download/order')
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.data)) as z:
        provenance = json.loads(z.read('demo-provenance.json'))
        assert provenance['origin'] == 'LIVE_REPLAY'
        assert provenance['current_execution'] is False
        assert z.read('original-export.zip').startswith(b'PK')


def test_simulation_download_is_labeled_and_has_no_real_test_attestation(client):
    case = client.get('/demo/cases/multifile').json
    assert case['origin'] == 'SIMULATED' and len(case['files']) == 2
    assert all(c['state'].startswith('SIMULATED_') for c in case['checks'])
    response = client.get('/demo/download/multifile')
    with zipfile.ZipFile(io.BytesIO(response.data)) as z:
        provenance = json.loads(z.read('demo-provenance.json'))
        assert provenance['current_execution'] is False
        assert provenance['origin'] == 'SIMULATED'
        assert '未运行' in z.read('README.md').decode()
        assert 'project/src/quantity.cj' in z.namelist()


def test_rejection_and_bad_case_never_export(client):
    case = client.get('/demo/cases/policy').json
    assert case['verdict'] == 'DENY' and case['metrics']['files'] == 0
    assert case['files'][0]['before'] == case['files'][0]['after']
    assert client.get('/demo/download/policy').status_code == 409
    assert client.get('/demo/cases/missing').status_code == 404
    assert client.get('/demo/download/../../etc/passwd').status_code == 404


def test_rule_provider_is_explicitly_recorded_without_model_call(tmp_path):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'quantity', ['src/quantity.cj'])
    original = 'quantity >= 0 && quantity <= 1000'
    proposal = asyncio.run(RuleProvider(store, task.id).propose({
        'files': {'src/quantity.cj': {'content': original, 'file_hash': 'a'*64}},
        'allowed_paths': ['src/quantity.cj']}))
    assert proposal.edits[0].content == 'quantity >= 1 && quantity <= 1000'
    assert store.records(task.id, 'model_call') == []
    assert store.records(task.id, 'event')[-1]['type'] == 'RULE_PROPOSAL'


def test_demo_can_prepare_work_without_pairing_but_requires_csrf(client):
    client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
    assert client.get('/api/tasks').status_code==200
    assert client.get('/api/analysis').status_code==200
    assert client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'修复边界'},headers=headers).status_code==200
    assert client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'修复边界'}).status_code==403
    assert client.post('/api/operator/authorize',json={'key':'a'*64},headers=headers).status_code==404
    assert client.get('/demo/environment').json['provider']=='DeepSeek'


def test_demo_direct_access_preserves_localhost_and_readonly_guards(tmp_path):
    app=create_demo_app(tmp_path,writes_enabled=False,provider='rule');client=app.test_client()
    assert client.get('/',base_url='http://evil.example').status_code==403
    assert client.get('/',environ_overrides={'REMOTE_ADDR':'192.0.2.1'}).status_code==403
    client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    response=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'修复'},
        headers={'Origin':'http://localhost','X-CSRF-Token':csrf})
    assert response.status_code==503 and response.json['code']=='OWNER_UNCONFIRMED'


def test_missing_sdk_keeps_offline_cases_available_and_real_mode_blocked(client, monkeypatch):
    monkeypatch.setattr('nexus.execution.environment.readiness', lambda: {
        'ready':False,'missing':[{'code':'SDK_NOT_READY','message':'SDK unavailable'},
                                {'code':'MODEL_NOT_CONFIGURED','message':'No model'}]})
    assert client.get('/').status_code==200
    assert client.get('/demo/cases').status_code==200
    report=client.get('/demo/environment').json
    assert report['ready'] is False
    assert [m['code'] for m in report['missing']]==['SDK_NOT_READY']


def test_missing_deepseek_blocks_generation_without_automatic_rule_fallback(client,monkeypatch):
    monkeypatch.setattr('nexus.demo.app.model_config',lambda:dict(DEEPSEEK_API_KEY='',DEEPSEEK_BASE_URL='',DEEPSEEK_MODEL=''))
    report=client.get('/demo/environment').json
    assert report['provider']=='DeepSeek' and not report['ready']
    assert 'MODEL_NOT_CONFIGURED' in [m['code'] for m in report['missing']]
    assert client.post('/api/demo/probes/policy',json={}).status_code==403


def test_new_samples_do_not_include_a_fixed_repaired_answer(client):
    case=client.get('/demo/cases/cross-stock').json
    assert not case['can_replay'] and case['project_id']=='cross-stock'
    assert all(f['after']=='' for f in case['real_files'])
    assert client.get('/demo/download/cross-stock').status_code==409


def test_demo_fresh_analysis_session_is_initialized_without_pairing(client):
    fresh=client.application.test_client()
    response=fresh.get('/api/analysis')
    assert response.status_code==200 and response.json['jobs']==[]


def test_demo_restart_keeps_session_without_repairing(tmp_path):
    key=b's'*32
    client=create_demo_app(tmp_path,session_key=key,provider='rule').test_client()
    client.get('/')
    cookie=client.get_cookie('session')
    restarted=create_demo_app(tmp_path,session_key=key,provider='rule').test_client()
    restarted.set_cookie('session',cookie.value)
    assert restarted.get('/api/tasks').status_code==200
    assert restarted.get('/api/analysis').status_code==200
