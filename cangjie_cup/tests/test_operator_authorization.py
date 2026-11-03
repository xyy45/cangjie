"""Operator boundary probes; synthetic checked records are not LIVE evidence."""
from nexus.web.app import create_app
from test_delivery import checked
from test_web import Loop

KEY='a'*64  # Explicit synthetic operator credential, never a model/API key.


def headers(client):
    client.get('/')
    with client.session_transaction() as session:token=session['csrf']
    return {'Origin':'http://localhost','X-CSRF-Token':token}


def test_fresh_local_session_cannot_read_or_review_with_valid_csrf(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=KEY)
    client=app.test_client();h=headers(client)
    assert KEY not in client.get('/').text
    for path in ['/api/tasks','/api/tasks/'+c.task_id,'/api/candidates/'+c.id,'/downloads/'+'0'*32]:
        response=client.get(path)
        assert response.status_code==403 and response.json['code']=='OPERATOR_REQUIRED'
    response=client.post('/api/candidates/'+c.id+'/accept',json={
        'check_set_hash':delivery.check_set_hash(c.id)},headers=h)
    assert response.status_code==403 and response.json['code']=='OPERATOR_REQUIRED'
    assert store.records(c.task_id,'acceptance')==[]
    assert client.get('/api/environment').status_code==200


def test_pairing_requires_real_credential_and_csrf_and_never_echoes_secret(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=KEY)
    client=app.test_client();h=headers(client)
    endpoint='/api/operator/authorize'
    assert client.post(endpoint,json={'key':KEY}).status_code==403
    for body in ({'key':'b'*64},{'key':'中'*64},{'key':KEY,'actor_id':'forged'}):
        denied=client.post(endpoint,json=body,headers=h)
        assert denied.status_code==403 and KEY not in denied.text
    assert client.post(endpoint,json={'key':KEY},headers=h).status_code==200
    assert client.get('/api/candidates/'+c.id).status_code==200
    approved=client.post('/api/candidates/'+c.id+'/accept',json={
        'check_set_hash':delivery.check_set_hash(c.id)},headers=h)
    assert approved.status_code==200
    another=app.test_client();headers(another)
    assert another.get('/api/candidates/'+c.id).status_code==403
    assert all(KEY not in str(r) for r in store.records(c.task_id,'event'))
    assert len(store.records(c.task_id,'acceptance'))==1


def test_restart_invalidates_old_paired_cookie_even_with_same_signing_key(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    app=create_app(store,Loop(),delivery,operator_key=KEY,session_key=b's'*32)
    client=app.test_client();h=headers(client)
    assert client.post('/api/operator/authorize',json={'key':KEY},headers=h).status_code==200
    cookie=client.get_cookie('session')
    restarted=create_app(store,Loop(),delivery,operator_key=KEY,session_key=b's'*32).test_client()
    restarted.set_cookie('session',cookie.value)
    assert restarted.get('/api/tasks').status_code==403


def test_default_app_never_implicitly_authorizes_local_session(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    client=create_app(store,Loop(),delivery).test_client();headers(client)
    assert client.get('/api/tasks').status_code==403


def test_authorized_readonly_instance_can_view_but_never_execute(tmp_path):
    ws,store,c,delivery=checked(tmp_path)
    loop=Loop()
    app=create_app(store,loop,delivery,operator_key=KEY,writes_enabled=False)
    client=app.test_client();h=headers(client)
    assert client.post('/api/operator/authorize',json={'key':KEY},headers=h).status_code==200
    assert client.get('/api/tasks').status_code==200
    response=client.post('/api/candidates/'+c.id+'/accept',json={},headers=h)
    assert response.status_code==503 and response.json['code']=='OWNER_UNCONFIRMED'
    assert store.records(c.task_id,'acceptance')==[] and loop.calls==0


def test_operator_file_is_private_persistent_and_rejects_symlinks_or_public_mode(tmp_path):
    import os
    import pytest
    from nexus.execution.ownership import RuntimeOwner
    owner=RuntimeOwner(tmp_path);assert owner.acquire()
    try:
        key=owner.operator_key();assert len(key)==64
        path=tmp_path/'.operator-key'
        assert path.stat().st_mode&0o777==0o600
        assert owner.operator_key()==key
        path.chmod(0o644)
        with pytest.raises(ValueError):owner.operator_key()
        path.chmod(0o600);path.rename(tmp_path/'original-key')
        path.symlink_to(tmp_path/'original-key')
        with pytest.raises(OSError):owner.operator_key()
        path.unlink();os.mkfifo(path,0o600)
        with pytest.raises(ValueError):owner.operator_key()
    finally:owner.close()


def test_native_child_cannot_read_controller_credential_or_self_approve(tmp_path):
    import subprocess
    import threading
    from werkzeug.serving import make_server
    from nexus.execution.runner import sandbox_profile
    from nexus.execution.ownership import RuntimeOwner
    root=tmp_path/'runtime'
    ws,store,c,delivery=checked(root)
    owner=RuntimeOwner(root);assert owner.acquire()
    try:
        key=owner.operator_key()
        app=create_app(store,Loop(),delivery,operator_key=key)
        server=make_server('127.0.0.1',0,app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        project=ws.subject_path(c.id)
        script='''import sys,os,urllib.request,urllib.error,http.cookiejar,json,re
for path in sys.argv[2:]:
    try:
        open(path).read()
    except PermissionError:
        pass
    else:
        raise AssertionError('Controller data readable')
    try:
        os.link(path,'target/private-link')
    except PermissionError:
        pass
    else:
        raise AssertionError('Controller data hard-linkable')
base=sys.argv[1]
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
page=client.open(base+'/').read().decode()
csrf=re.search('name="csrf-token" content="([^"]+)"',page).group(1)
for endpoint,body in [('/api/tasks',None),('/api/operator/authorize',{'key':'0'*64}),('/api/candidates/unknown/accept',{}),('/api/candidates/unknown/export',{})]:
    request=urllib.request.Request(base+endpoint,data=None if body is None else json.dumps(body).encode(),headers={'Origin':base,'Content-Type':'application/json','X-CSRF-Token':csrf})
    try:
        client.open(request)
    except urllib.error.HTTPError as error:
        assert error.code==403,error.code
        assert json.load(error)['code']=='OPERATOR_REQUIRED'
    else:
        raise AssertionError('Unpaired child gained controller access')
print('NATIVE_CHILD_DENIED')
'''
        try:
            (project/'target').mkdir(exist_ok=True)
            result=subprocess.run(['/usr/bin/sandbox-exec','-p',sandbox_profile(project,private_root=root),
                '/usr/bin/python3','-c',script,f'http://127.0.0.1:{server.server_port}',
                str(root/'.operator-key'),str(root/'runs.sqlite3')],capture_output=True,text=True,timeout=10,cwd=project)
            assert result.returncode==0,result.stdout+result.stderr
            assert 'NATIVE_CHILD_DENIED' in result.stdout
            assert store.records(c.task_id,'acceptance')==[]
            assert list((root/'exports').glob('*.zip'))==[]
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
    finally:owner.close()
