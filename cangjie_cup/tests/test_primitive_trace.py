"""Primitive SDK protocol fixtures; no business-assertion or SDK claims here."""
import importlib
import importlib.util
from pathlib import Path

import pytest

from tests.test_property_contract import SIG,raw,EXAMPLES

TOKEN='0123456789abcdef'


def api():
    assert importlib.util.find_spec('nexus.repair.primitive_trace') is not None,'shared primitive observation protocol missing'
    return importlib.import_module('nexus.repair.primitive_trace')


def log(kind,values=('1','2'),primitive='Int64'):
    prefix,cls=('NEXUS_PROPERTY_V1','NexusProperties') if kind=='single' else ('NEXUS_RELATION_V1','NexusRelations')
    result='EXPLICIT LOG FIXTURE\nTP: bench, RESULT:\n TCS: '+cls+TOKEN+', RESULT:\n'
    for i,value in enumerate(values):result+=f' [ PASSED ] CASE: case{i} (1 ns)\n STDOUT:\n {prefix}|{TOKEN}|case{i}|{primitive}|{value}\n'
    count=len(values)
    return result+f'Summary: TOTAL: {count} PASSED: {count}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'


def signature(primitive='Int64'):
    return dict(name='f',params=[dict(name='x',type=primitive)],return_type=primitive)


@pytest.mark.parametrize('kind',['single','relation'])
def test_duplicate_input_occurrences_remain_separate_actual_observations(kind):
    module=api();inputs=[[1],[1]];program=module.harness(signature(),inputs,'bench',TOKEN,kind).decode()
    expected='NexusProperties' if kind=='single' else 'NexusRelations'
    assert 'class '+expected+TOKEN in program and 'func case0()' in program and 'func case1()' in program
    result=module.read(signature(),inputs,TOKEN,kind,log(kind),0,None)
    assert result['state']=='PASS' and result['execution_state']=='PASS'
    assert [o['actual_return'] for o in result['observations']]==[1,2]
    assert [o['args'] for o in result['observations']]==inputs
    assert [o['test_id'] for o in result['observations']]==module.case_ids(TOKEN,2,kind)
    assert result['observations'][0]['source']['start_char']<result['observations'][1]['source']['start_char']
    assert 'failures' not in result,'raw execution completion is not a business assertion'


def test_single_harness_keeps_accepted_3a_bytes_and_outer_uniqueness():
    module=api();inputs=[[1000,900,200],[1000,800,100]]
    assert module.harness(SIG,inputs,'bench',TOKEN,'single')==(Path(__file__).parent/'fixtures/single_observer_v1.cj').read_bytes()
    from nexus.repair import properties,property_trace
    contract=properties.validate_contract(raw(),SIG,EXAMPLES)
    with pytest.raises(ValueError):property_trace.harness(contract,[inputs[0],inputs[0]],'bench',TOKEN)


@pytest.mark.parametrize('change',['missing','duplicate','wrong-kind','wrong-token','wrong-case','wrong-type','overflow','noncanonical','stderr','no-summary','exit','problem'])
def test_incomplete_wrong_side_or_wrong_protocol_cannot_complete(change):
    module=api();text=log('relation');marker='NEXUS_RELATION_V1|'+TOKEN+'|case0|Int64|1';code=0;problem=None
    if change=='missing':text=text.replace(marker,'')
    elif change=='duplicate':text=text.replace(marker,marker+'\n'+marker)
    elif change=='wrong-kind':text=text.replace('NEXUS_RELATION_V1','NEXUS_PROPERTY_V1')
    elif change=='wrong-token':text=text.replace('|'+TOKEN+'|','|'+'f'*16+'|')
    elif change=='wrong-case':text=text.replace('|case0|','|case1|')
    elif change=='wrong-type':text=text.replace('|Int64|1','|Bool|true')
    elif change=='overflow':text=text.replace('|Int64|1','|Int64|9223372036854775808')
    elif change=='noncanonical':text=text.replace('|Int64|1','|Int64|01')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:',1)
    elif change=='no-summary':text=text.split('Summary:',1)[0]
    elif change=='exit':code=1
    else:problem='TimeoutError'
    result=module.read(signature(),[[1],[1]],TOKEN,'relation',text,code,problem)
    assert result['state']=='UNKNOWN' and result['observations']==[]


@pytest.mark.parametrize('kind',[None,True,[],{},'unsupported'])
def test_kind_is_closed_before_any_hash_or_source_interpolation(kind):
    module=api()
    with pytest.raises(ValueError):module.harness(signature(),[[1]],'bench',TOKEN,kind)
    with pytest.raises(ValueError):module.case_ids(TOKEN,1,kind)


def test_primitive_types_zero_arguments_limits_and_names_are_closed():
    module=api()
    for values,primitive in [(['false','true'],'Bool'),([str(-(2**63)),str(2**63-1)],'Int64')]:
        inputs=[[False],[True]] if primitive=='Bool' else [[-(2**63)],[2**63-1]]
        assert module.read(signature(primitive),inputs,TOKEN,'relation',log('relation',values,primitive),0,None)['state']=='PASS'
    zero=dict(name='zero',params=[],return_type='Int64')
    assert module.read(zero,[[],[]],TOKEN,'relation',log('relation'),0,None)['state']=='PASS'
    for inputs in ([],[[1]]*129,[[True]],[[None]],[[2**63]],[[]]):
        with pytest.raises(ValueError):module.harness(signature(),inputs,'bench',TOKEN,'relation')
    for count in (0,129,True,None):
        with pytest.raises(ValueError):module.case_ids(TOKEN,count,'relation')
    for package,token in [('bench;import evil',TOKEN),('bench','bad'),('bench',{})]:
        with pytest.raises(ValueError):module.harness(signature(),[[1]],package,token,'relation')
    for bad in ({**signature(),'name':'f;evil'},dict(name='f',params=[dict(name=str(i),type='Int64') for i in range(5)],return_type='Int64'),{**signature(),'return_type':'String'}):
        with pytest.raises(ValueError):module.harness(bad,[[1]],'bench',TOKEN,'relation')


@pytest.mark.parametrize('prefix',['NEXUS_SEQUENCE_V1','NEXUS_SEQUENCE_END_V1'])
def test_old_primitive_protocol_rejects_sequence_markers_inside_its_stdout(prefix):
    text=log('single',('1',));marker=prefix+'|'+TOKEN+'|case0|1|COMPLETE'
    text=text.replace('Summary:',marker+'\nSummary:')
    assert api().read(signature(),[[1]],TOKEN,'single',text,0,None)['state']=='UNKNOWN'


@pytest.mark.parametrize('kind',['single','relation'])
@pytest.mark.parametrize('prefix',['NEXUS_SEQUENCE_V1','NEXUS_SEQUENCE_END_V1'])
def test_sequence_markers_after_summary_cannot_be_ignored_by_old_protocol(kind,prefix):
    marker=(prefix+'|'+TOKEN+'|case0|step0|Int64|0|1' if prefix=='NEXUS_SEQUENCE_V1' else prefix+'|'+TOKEN+'|case0|1|COMPLETE')
    text=log(kind,('1',)).replace('cjpm test success',' '+marker+'\ncjpm test success')
    result=api().read(signature(),[[1]],TOKEN,kind,text,0,None)
    assert result['state']=='UNKNOWN' and result['observations']==[]
