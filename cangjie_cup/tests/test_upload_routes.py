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


def test_upload_reads_functions_without_goal_then_binds_goal_for_repair(tmp_path):
    app,client,headers=page(tmp_path)
    app.config['RUN_RULE_DRAFTS']=False
    from tests.test_rule_drafts import FixtureDraftProvider
    drafts=app.extensions['rule_draft_service'];drafts.provider_factory=FixtureDraftProvider
    FixtureDraftProvider.calls=[];FixtureDraftProvider.inspect_before_send=None
    upload=client.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'fee.cj'),request_key='read-only'),headers=headers)
    assert upload.status_code==201,upload.json
    assert upload.json['goal']=='' and upload.json['functions'][0]['name']=='fee'
    base='/api/uploads/repair/'+upload.json['id']
    confirm=dict(expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True)
    assert client.post(base+'/confirm',json=confirm,headers=headers).status_code==400
    generation=dict(expected_version=1,function='fee',request_key='generate',consent=True)
    assert client.post(base+'/rule-drafts',json=generation,headers=headers).status_code==400
    goal=dict(expected_version=1,goal='按数量计算费用')
    stranger=app.test_client();stranger.get('/')
    with stranger.session_transaction() as s:foreign={'Origin':'http://localhost','X-CSRF-Token':s['csrf']}
    assert stranger.post(base+'/goal',json=goal,headers=foreign).status_code==404
    assert client.post(base+'/goal',json=goal,headers=headers).json['goal']==goal['goal']
    assert client.post(base+'/goal',json=goal,headers=headers).status_code==200
    assert client.post(base+'/goal',json={**goal,'goal':'不同需求'},headers=headers).status_code==409
    generated=client.post(base+'/rule-drafts',json=generation,headers=headers)
    assert generated.status_code==202
    assert drafts.run(generated.json['id']) and len(FixtureDraftProvider.calls)==1
    assert FixtureDraftProvider.calls[0]['context']['goal']==goal['goal']
    preview=client.post(base+'/rule-drafts/'+generated.json['id']+'/apply-preview',
        json=dict(expected_version=1,function='fee',examples_only=True),headers=headers)
    assert preview.status_code==200,preview.json
    confirmed=client.post(base+'/confirm',json={**confirm,'examples_json':preview.json['examples_json'],
        'rule_draft_ref':preview.json['rule_draft_ref']},headers=headers)
    assert confirmed.status_code==200 and confirmed.json['examples']==EXAMPLES
    repeat=client.post('/api/uploads/repair',data=dict(file=(io.BytesIO(SOURCE),'fee.cj'),request_key='read-only'),headers=headers)
    assert repeat.status_code==201 and repeat.json['id']==upload.json['id'] and repeat.json['goal']==goal['goal']


def test_reads_zip_and_directory_functions_without_goal(tmp_path):
    import zipfile
    from tests.test_project_index import project
    _,client,headers=page(tmp_path)
    files=project()
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:
        for name,raw in files.items():z.writestr(name,raw)
    archive.seek(0)
    forms=[dict(file=(archive,'billing.zip'),request_key='zip'),
           dict(files=[(io.BytesIO(raw),name.rsplit('/',1)[-1]) for name,raw in files.items()],
                paths_json=json.dumps(list(files)),request_key='directory')]
    for form in forms:
        response=client.post('/api/uploads/repair/project',data=form,headers=headers)
        assert response.status_code==201,response.json
        assert response.json['goal']=='' and response.json['functions'][0]['name']=='fee'


def test_unreadable_source_reports_parser_reason_without_requiring_goal(tmp_path):
    _,client,headers=page(tmp_path)
    response=client.post('/api/uploads/repair',data=dict(file=(io.BytesIO(b'// no function\n'),'empty.cj'),
        request_key='invalid'),headers=headers)
    assert response.status_code==400 and response.json['error']=='未找到支持的函数'
    assert client.get('/api/uploads/repair').json['uploads']==[]
