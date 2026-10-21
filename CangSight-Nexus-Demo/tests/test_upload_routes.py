import io,json
from nexus.demo.app import create_demo_app
from tests.test_upload_service import SOURCE,EXAMPLES


def page(tmp_path):
    app=create_demo_app(tmp_path,provider='rule');app.config.update(TESTING=True,RUN_TASKS=False)
    alice=app.test_client();alice.get('/')
    with alice.session_transaction() as s:headers={'Origin':'http://localhost','X-CSRF-Token':s['csrf']}
    return app,alice,headers


def test_upload_is_local_until_confirmation_and_private_across_all_task_views(tmp_path):
    app,alice,headers=page(tmp_path)
    response=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'pricing.cj'),'goal':'计算费用','request_key':'upload'},headers=headers)
    assert response.status_code==201
    draft=response.json;identity=draft['id']
    body=dict(expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True)
    assert alice.post('/api/uploads/repair/'+identity+'/confirm',json=body,headers=headers).status_code==200
    case=alice.get('/demo/cases/'+identity);assert case.status_code==200 and case.json['project_id']==identity
    req=alice.post('/api/requirements/drafts',json={'project':identity,'goal':'计算费用'},headers=headers).json
    spec=alice.post('/api/requirements/drafts/'+req['id']+'/confirm',json=dict(schema_version=1,expected_version=1,requirements=req['requirements'],allowed_paths=req['allowed_paths']),headers=headers).json
    start={'project':identity,'spec_id':spec['id'],'idempotency_key':'start-upload'}
    task=alice.post('/api/tasks',json=start,headers=headers)
    assert task.status_code==200 and task.json['status']=='READY'
    assert alice.post('/api/tasks',json=start,headers=headers).json['id']==task.json['id']
    bob=app.test_client();bob.get('/')
    with bob.session_transaction() as s:foreign={'Origin':'http://localhost','X-CSRF-Token':s['csrf']}
    for url in ['/api/uploads/repair/'+identity,'/demo/cases/'+identity,'/api/tasks/'+task.json['id'],
                '/api/tasks/'+task.json['id']+'/events','/api/demo/tasks/'+task.json['id']+'/analysis','/agents/runs/'+task.json['id']]:
        assert bob.get(url).status_code==404,url
    assert bob.post('/api/tasks',json=start,headers=foreign).status_code==404
    assert bob.post('/api/requirements/drafts',json={'project':identity,'goal':'计算费用'},headers=foreign).status_code==404
    assert all(t['id']!=task.json['id'] for t in bob.get('/api/tasks').json['tasks'])
    assert bob.get('/api/uploads/repair').json['uploads']==[]
    assert alice.get('/api/tasks/'+task.json['id']).status_code==200


def test_upload_requires_csrf_and_rejects_external_capabilities_before_artifacts(tmp_path):
    _,client,headers=page(tmp_path)
    assert client.post('/api/uploads/repair',data={}).status_code==403
    result=client.post('/api/uploads/repair',data={'file':(io.BytesIO(b'import std.fs.*\nfunc f(): Int64 { 1 }'),'bad.cj'),
        'goal':'计算','request_key':'bad'},headers=headers)
    assert result.status_code==400 and result.json['code']=='UPLOAD_INPUT_INVALID'
    assert client.get('/api/uploads/repair').json['uploads']==[]
