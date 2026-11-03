"""Statement slices follow verified PDG predecessors, never line truncation."""
import copy
import hashlib
import io
import json
from pathlib import Path
import zipfile
import pytest
from nexus.analysis.normalize import normalize,validate_source

CODE='func f(): Int64 {\n let a = 1\n let first = a * 2\n let b = 3\n let second = b * 4\n return first + second\n}\n'
PDG=dict(graph_type='Pdg',nodes=[dict(id='entry',label='ENTER f'),dict(id='a',label='[L2]: a = 1'),dict(id='first',label='[L3]: first = a * 2'),dict(id='b',label='[L4]: b = 3'),dict(id='second',label='[L5]: second = b * 4')],edges=[{'from':'entry','to':'a'},{'from':'a','to':'first'},{'from':'entry','to':'b'},{'from':'b','to':'second'}])


def report(tmp_path,graph=None,ddg=None,response_status="success",http_status=200):
    from nexus.analysis.point import attach_point_graph
    source=validate_source('f.cj',CODE.encode())
    response={'status':response_status,'json_graphs':[ddg if ddg is not None else dict(graph_type='Ddg',nodes=[dict(id='x',label='[L2]: a = 1')],edges=[]),graph or copy.deepcopy(PDG)]}
    raw=json.dumps(dict(tool='sympas_dep_graph',http_status=http_status,source_sha256=source['source_sha256'],input=dict(code=CODE,filename='f.cj',lang='cangjie',graph_types='Ddg,Cg,Pdg'),response=response)).encode()
    path=tmp_path/'observations/sympas_dep_graph.json';path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    observation=dict(tool='sympas_dep_graph',http_status=200,source_sha256=source['source_sha256'],raw_sha256=hashlib.sha256(raw).hexdigest(),raw_ref='observations/sympas_dep_graph.json',**normalize('sympas_dep_graph',response,'f.cj',7))
    return attach_point_graph(dict(id='record',status='COMPLETE',source=source,observations=[observation]),tmp_path)


def test_two_program_positions_have_independent_dependencies_and_no_future_lines(tmp_path):
    from nexus.analysis.point import point_slice
    r=report(tmp_path);a=point_slice(r,3);b=point_slice(r,5)
    assert a['lines']==[2,3] and a['seed_nodes']==['first']
    assert b['lines']==[4,5] and b['seed_nodes']==['second']
    assert a['origin']=='LOCAL_PDG_BACKWARD' and a['scope']=='STATEMENT'
    assert a['source_sha256']==r['source']['source_sha256']
    assert a['raw_sha256']==r['observations'][0]['raw_sha256']


def test_control_dependencies_and_loop_cycles_terminate_without_cutting_future_dependencies(tmp_path):
    from nexus.analysis.point import point_slice
    graph=copy.deepcopy(PDG)
    graph['edges'] += [{'from':'first','to':'second'},{'from':'second','to':'b'}]
    r=report(tmp_path,graph)
    assert point_slice(r,4)['lines']==[2,3,4,5]  # Cycle reaches a later line: no <= target filter.


@pytest.mark.parametrize('change',['orphan','duplicate','range','count','multiple'])
def test_corrupt_pdg_does_not_inherit_a_good_ddg_or_enable_partial_slices(tmp_path,change):
    from nexus.analysis.point import point_slice
    graph=copy.deepcopy(PDG)
    if change=='orphan':graph['edges'].append({'from':'missing','to':'first'})
    if change=='duplicate':graph['nodes'].append(graph['nodes'][0])
    if change=='range':graph['nodes'][0]['label']='[L999]: bad'
    if change=='count':graph['node_count']=999
    if change=='multiple':graph['nodes']=[]
    r=report(tmp_path,graph)
    assert r['observations'][0]['status']=='VALID'
    assert point_slice(r,3)['status']!='VALID' and point_slice(r,3)['lines']==[]


def test_no_mapped_statement_and_old_records_do_not_reuse_another_target(tmp_path):
    from nexus.analysis.point import point_slice
    r=report(tmp_path)
    assert point_slice(r,7)['status']=='EMPTY' and point_slice(r,7)['lines']==[]
    del r['point_graph']
    assert point_slice(r,3)['status']=='UNAVAILABLE' and point_slice(r,3)['lines']==[]
    for line in (True,0,-1,8,'3'):
        with pytest.raises(ValueError):point_slice(r,line)


def test_projection_detects_source_and_raw_hash_tampering(tmp_path):
    from nexus.analysis.point import attach_point_graph
    r=report(tmp_path);r['source']['code']='other source'
    with pytest.raises(ValueError):attach_point_graph(r,tmp_path)
    r=report(tmp_path);(tmp_path/'observations/sympas_dep_graph.json').write_text('{}')
    with pytest.raises(ValueError):attach_point_graph(r,tmp_path)


def test_point_download_preserves_original_bytes_and_hashes_derived_result(tmp_path):
    from nexus.analysis.point import point_archive
    r=report(tmp_path);original=io.BytesIO()
    with zipfile.ZipFile(original,'w') as z:z.writestr('manifest.json',b'original manifest');z.writestr('source.cj',CODE.encode())
    original.seek(0)
    with zipfile.ZipFile(point_archive(original,r,5)) as z:
        assert z.read('manifest.json')==b'original manifest'
        assert json.loads(z.read('point-slice.json'))['lines']==[4,5]
        manifest=json.loads(z.read('point-manifest.json'))
        assert all(hashlib.sha256(z.read(n)).hexdigest()==sha for n,sha in manifest['files'].items())


def test_session_point_route_and_download_bind_the_requested_line_and_actor(tmp_path):
    from nexus.demo.app import create_demo_app
    from tests.analysis.test_service import FakeClient
    class Client(FakeClient):
        def analyze(self,tool,args):
            reply=super().analyze(tool,args)
            if tool=='sympas_dep_graph':reply['response']['json_graphs'].append(copy.deepcopy(PDG))
            return reply
    app=create_demo_app(tmp_path,provider='rule');client=app.test_client();client.get('/')
    with client.session_transaction() as state:actor=state['actor_id']
    service=app.extensions['analysis_service'];service.client_factory=Client
    job=service.create(validate_source('f.cj',CODE.encode()),actor_id=actor,request_key='point',origin='UPLOAD');service.run(job['id'])
    base='/api/analysis/'+job['id']+'/point-slice'
    response=client.get(base+'?line=3');assert response.status_code==200,response.json
    assert response.json['lines']==[2,3]
    response=client.get(base+'?line=5&download=1');assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.data)) as z:assert json.loads(z.read('point-slice.json'))['lines']==[4,5]
    assert app.test_client().get(base+'?line=3').status_code==404
    for suffix in ('','?line=0','?line=9999','?line=true','?line=2&extra=1'):
        assert client.get(base+suffix).status_code==400
    assert client.get(base+'?line=7').json['status']=='EMPTY'
    assert client.get(base+'?line=7&download=1').status_code==409


def test_condition_node_is_included_even_when_it_is_not_a_data_definition(tmp_path):
    from nexus.analysis.point import point_slice
    graph=dict(graph_type='Pdg',nodes=[dict(id='cond',label='[L2]: <Cond> (amount >= 9900)'),dict(id='set',label='[L4]: fee = 0')],edges=[{'from':'cond','to':'set'}])
    assert point_slice(report(tmp_path,graph),4)['lines']==[2,4]


def test_multiple_statements_on_one_line_are_all_seeds_without_inventing_nodes(tmp_path):
    from nexus.analysis.point import point_slice
    graph=copy.deepcopy(PDG);graph['nodes'].append(dict(id='extra',label='[L3]: first = 0'))
    r=point_slice(report(tmp_path,graph),3)
    assert r['seed_nodes']==['extra','first'] and r['node_ids']==['a','entry','extra','first']


def test_browser_and_download_traversal_produce_identical_results(tmp_path):
    import subprocess
    from nexus.analysis.point import point_slice
    r=report(tmp_path)
    js="const c=require('./nexus/demo/static/analysis-core.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const r=JSON.parse(s);console.log(JSON.stringify([3,5,7].map(n=>c.pointSlice(r,n))));});"
    result=subprocess.run(['node','-e',js],input=json.dumps(r),text=True,capture_output=True,check=True)
    assert json.loads(result.stdout)==[point_slice(r,line) for line in (3,5,7)]


@pytest.mark.parametrize('ddg_status,nodes',[('EMPTY',[]),('INVALID',[dict(id='bad',label='[L999]: bad')])])
def test_valid_pdg_is_independent_of_empty_or_invalid_ddg(tmp_path,ddg_status,nodes):
    from nexus.analysis.point import point_slice
    r=report(tmp_path,ddg=dict(graph_type='Ddg',nodes=nodes,edges=[]))
    assert r['observations'][0]['status']==ddg_status
    assert r['point_graph']['status']=='VALID'
    assert point_slice(r,5)['lines']==[4,5]


@pytest.mark.parametrize('response_status,http_status',[('failed',200),('unknown',200),('success',503)])
def test_failed_tool_or_transport_never_enables_valid_looking_pdg(tmp_path,response_status,http_status):
    from nexus.analysis.point import point_slice
    r=report(tmp_path,response_status=response_status,http_status=http_status)
    assert point_slice(r,5)['status']=='UNAVAILABLE'
    assert point_slice(r,5)['lines']==[]
