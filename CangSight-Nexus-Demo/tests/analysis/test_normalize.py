"""Input-bound tool observations; fixtures are protocol examples, not live evidence."""
import copy
import pytest
from nexus.analysis.normalize import validate_source, normalize

SOURCE=b'func add(a: Int64, b: Int64): Int64 {\n    let result = a + b\n    return result\n}\n'


def test_source_preserves_bytes_and_filename_identity():
    from hashlib import sha256
    item=validate_source('求和.cj',SOURCE)
    assert item['filename']=='求和.cj' and item['code'].encode()==SOURCE
    assert item['source_sha256']==sha256(SOURCE).hexdigest() and item['line_count']==4

@pytest.mark.parametrize('name,data',[('../x.cj',SOURCE),('x\\a.cj',SOURCE),('x.py',SOURCE),('x.cj\n',SOURCE),('x.cj',b'\xff'),('x.cj',b' '),('x.cj',b'\x00'),('x.cj',b'a'*65537),('x.cj',b'a\n'*1001)])
def test_invalid_uploads_are_rejected(name,data):
    with pytest.raises(ValueError):validate_source(name,data)


def slice_result(lines=None):
    return {'status':'success','data':{'backward_slices':{'result@add':{'add.cj':[1,2,3] if lines is None else lines}}}}


def graph_result():
    return {'status':'success','json_graphs':[{'graph_type':'Ddg','node_count':2,'edge_count':1,
        'nodes':[{'id':'n1','label':'[L2]: result = a + b'},{'id':'n2','label':'[L3]: return result'}],
        'edges':[{'from':'n1','to':'n2'}]}]}


def test_slice_rows_are_the_actual_tool_rows():
    result=normalize('sympas_slice',slice_result(),'add.cj',4)
    assert result['status']=='VALID' and result['data']['slices']=={'result@add':[1,2,3]}

@pytest.mark.parametrize('lines',[[0],[5],[True],['2']])
def test_invalid_slice_lines_do_not_become_valid(lines):
    assert normalize('sympas_slice',slice_result(lines),'add.cj',4)['status']=='INVALID'


def test_wrong_file_and_empty_slice_are_not_success():
    assert normalize('sympas_slice',slice_result(),'other.cj',4)['status']=='INVALID'
    assert normalize('sympas_slice',{'status':'success','data':{'backward_slices':{}}},'add.cj',4)['status']=='EMPTY'


def test_internal_failure_overrides_success_and_data():
    response=slice_result();response['engine_log']='SIL syntax error: unexpected token ,; Found 0 source files'
    assert normalize('sympas_slice',response,'add.cj',4)['status']=='FAILED'


def test_graph_preserves_edges_and_only_explicit_source_locations():
    payload=graph_result();payload['json_graphs'][0]['nodes'][0]['label']='(formal-in)%a'
    result=normalize('sympas_dep_graph',payload,'add.cj',4)
    assert result['status']=='VALID'
    assert result['data']['graphs'][0]['nodes'][0]['line'] is None
    assert result['data']['graphs'][0]['nodes'][1]['line']==3
    assert result['data']['graphs'][0]['edges']==[{'from':'n1','to':'n2'}]

@pytest.mark.parametrize('mutation',['orphan','duplicate','range','count'])
def test_unbound_or_corrupt_graphs_are_invalid(mutation):
    response=graph_result();graph=response['json_graphs'][0]
    if mutation=='orphan':graph['edges'][0]['to']='missing'
    if mutation=='duplicate':graph['nodes'][1]['id']='n1'
    if mutation=='range':graph['nodes'][0]['label']='[L999]: fake'
    if mutation=='count':graph['node_count']=999
    assert normalize('sympas_dep_graph',response,'add.cj',4)['status']=='INVALID'
