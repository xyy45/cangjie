import io
import pytest
from nexus.demo.app import create_demo_app

@pytest.fixture
def web(tmp_path):
    app=create_demo_app(tmp_path);app.config.update(TESTING=True,RUN_ANALYSES=False)
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
    return app,client,headers


def test_analysis_is_visible_and_starts_without_pairing(web):
    app,client,headers=web
    assert '源码分析' in client.get('/').text
    samples=client.get('/analysis/samples').json['samples']
    assert len(samples)>=3
    assert client.post('/api/analysis',json={'sample_id':samples[0]['id'],'request_key':'x'},headers=headers).status_code==202


def test_sample_start_keeps_source_identity_and_requires_csrf(web):
    app,client,headers=web
    sample=client.get('/analysis/samples').json['samples'][0]
    assert client.post('/api/analysis',json={'sample_id':sample['id'],'request_key':'x'}).status_code==403
    response=client.post('/api/analysis',json={'sample_id':sample['id'],'request_key':'x'},headers=headers)
    assert response.status_code==202,response.json
    detail=client.get('/api/analysis/'+response.json['id']).json
    assert detail['origin']=='SAMPLE' and detail['source']['filename'].endswith('.cj')


def test_upload_receives_its_own_source_and_rejects_unconsented_transfer(web):
    app,client,headers=web
    source=b'func marker(): Int64 { return 42 }\n'
    def data(consent):return {'file':(io.BytesIO(source),'marker.cj'),'request_key':'upload-1','consent':consent}
    assert client.post('/api/analysis',data=data('false'),headers=headers).status_code==400
    response=client.post('/api/analysis',data=data('true'),headers=headers)
    assert response.status_code==202,response.json
    result=client.get('/api/analysis/'+response.json['id']).json
    assert result['origin']=='UPLOAD' and result['source']['code'].encode()==source
    assert client.post('/api/analysis',data={'file':(io.BytesIO(source),'../escape.cj'),'request_key':'bad','consent':'true'},headers=headers).status_code==400


def test_saved_upload_can_be_reanalyzed_with_its_own_source(web):
    from tests.analysis.test_service import FakeClient
    app,client,headers=web
    source=b'func add(a: Int64, b: Int64): Int64 {\n let result = a + b\n return result\n}\n'
    response=client.post('/api/analysis',data={'file':(io.BytesIO(source),'add.cj'),'request_key':'upload-old','consent':'true'},headers=headers)
    identity=response.json['id'];service=app.extensions['analysis_service'];service.client_factory=FakeClient;service.run(identity)
    again=client.post('/api/analysis',json={'analysis_id':identity,'request_key':'upload-again'},headers=headers)
    assert again.status_code==202,again.json
    result=client.get('/api/analysis/'+again.json['id']).json
    assert result['source']['code'].encode()==source and result['origin']=='UPLOAD'


def test_selected_line_survives_upload_restore_and_json_reanalysis(web):
    app,client,headers=web
    source=b'func f(): Int64 {\n let x = 2\n return x\n}\n'
    response=client.post('/api/analysis',data={'file':(io.BytesIO(source),'target.cj'),'request_key':'target-1','consent':'true','slice_line':'2'},headers=headers)
    assert response.status_code==202,response.json
    identity=response.json['id'];app.extensions['analysis_service'].reconcile()
    assert client.get('/api/analysis/'+identity).json['slice_criterion']['line']==2
    again=client.post('/api/analysis',json={'analysis_id':identity,'request_key':'target-2'},headers=headers)
    assert again.status_code==202,again.json
    assert client.get('/api/analysis/'+again.json['id']).json['slice_criterion']['line']==2


@pytest.mark.parametrize('value',[True,0,9999,None,'2'])
def test_api_rejects_invalid_json_target_line(web,value):
    _,client,headers=web
    response=client.post('/api/analysis',json={'sample_id':'sum3','request_key':'bad','slice_line':value},headers=headers)
    assert response.status_code==400
