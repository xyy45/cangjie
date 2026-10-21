"""Actual SDK/MCP rule repair; test-operator acceptance, zero model calls."""
import io
import json
import time
import zipfile

import pytest

from nexus.demo.app import create_demo_app
from nexus.execution.ownership import RuntimeOwner
from nexus.store import RunStore

pytestmark = pytest.mark.sdk


def test_real_rule_journey_requires_review_and_exports_same_tree(tmp_path):
    owner=RuntimeOwner(tmp_path)
    assert owner.acquire()
    try:
        client=create_demo_app(tmp_path,provider='rule').test_client()
        client.get('/')
        with client.session_transaction() as session:csrf=session['csrf']
        headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
        draft=client.post('/api/requirements/drafts',json={'project':'order-demo-bug','goal':'修复数量边界'},headers=headers).json
        response=client.post('/api/requirements/drafts/'+draft['id']+'/confirm',json={
            'schema_version':1,'expected_version':draft['version'],
            'requirements':draft['requirements'],'allowed_paths':draft['allowed_paths']},headers=headers)
        assert response.status_code==200,response.json
        spec=response.json
        response=client.post('/agents/runs',json={'schema_version':1,'team_profile':'cangjie-repair',
            'payload':{'project':'order-demo-bug','spec_id':spec['id'],
            'idempotency_key':'demo-sdk-journey'}},headers=headers)
        assert response.status_code==200,response.json
        task=response.json
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            task=client.get('/api/tasks/'+task['id']).json
            if task['status'] in {'REVIEW_PENDING','BLOCKED','IN_DOUBT','UNREPAIRED'}:break
            time.sleep(.1)
        assert task['status']=='REVIEW_PENDING',task
        candidate=client.get('/api/candidates/'+task['candidate_id']).json
        source=client.get('/api/demo/candidates/'+candidate['id']).json
        assert len(source['edits'])==1
        assert 'quantity >= 1' in source['edits'][0]['content']
        assert 'quantity >= 0' in source['source_files'][0]['before']
        assert all(c['state']=='PASS' for c in candidate['checks'])
        assert next(c for c in candidate['checks'] if c['kind']=='test')['counts']['passed']==11
        assert task['download_url'] is None
        store=RunStore(tmp_path)
        assert store.records(task['id'],'model_call')==[]
        assert any(e['type']=='RULE_PROPOSAL' for e in store.records(task['id'],'event'))
        a=client.post('/api/candidates/'+candidate['id']+'/accept',json={
            'check_set_hash':candidate['check_set_hash'],'task_revision':task['revision']},headers=headers)
        assert a.status_code==200,a.json
        export=client.post('/api/candidates/'+candidate['id']+'/export',json={'acceptance_id':a.json['id']},headers=headers)
        assert export.status_code==200,export.json
        download=client.get(export.json['download_url'])
        assert download.status_code==200
        with zipfile.ZipFile(io.BytesIO(download.data)) as z:
            manifest=json.loads(z.read('manifest.json'))
            assert manifest['project_tree_hash']==candidate['tree_hash']
            assert b'quantity >= 1' in z.read('project/src/quantity.cj')
            sessions=json.loads(z.read('evidence/sessions.json'))
            assert sessions['model_evidence']=='NO_MODEL_CALL_RECORDED'
    finally:owner.close()
