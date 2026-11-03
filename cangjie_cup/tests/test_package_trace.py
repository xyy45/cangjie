"""Explicit V5 protocol fixtures; actual SDK scenarios live under tests/sdk."""
from copy import deepcopy
import importlib
import pytest

from nexus.repair import primitive_trace,scoped_values
from tests.test_package_material import selected,NONCE
from tests.test_package_index import project
from nexus.repair.scoped_material import material


def api():return importlib.import_module('nexus.repair.scoped_trace')


def example():return [{'$type':'bench.sale.State','fields':{'amount':10}},2]


def fixture(sig,mode,values):
    module=api();ids=module.case_ids(sig,len(values),NONCE,mode);package,cls,_=ids[0].rsplit('.',2)
    prefix=scoped_values.PROTOCOLS[mode][0]
    text='EXPLICIT LOG FIXTURE\nTP: '+package+', RESULT:\n TCS: '+cls+', RESULT:\n'
    for i,(identity,value) in enumerate(zip(ids,values)):
        text+=' [ PASSED ] CASE: case'+str(i)+' (1 ns)\n STDOUT:\n '+prefix+NONCE+'|'+identity+'|'+sig['return_type']+'|'+scoped_values.encode(value,sig['return_type'],sig.get('types',{}))+'\n'
    return text+f'Summary: TOTAL: {len(ids)} PASSED: {len(ids)}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'


@pytest.mark.parametrize('mode',['oracle','single','relation'])
def test_canonical_case_ids_and_object_observations_are_bound_to_synthetic_package(mode):
    sig=selected(project());m=api();value={'$type':'bench.refund.State','fields':{'amount':16}}
    text=fixture(sig,mode,[value,value]);expected=m.case_ids(sig,2,NONCE,mode)
    result=m.read(text,sig,expected,nonce=NONCE,mode=mode,exit_code=0,problem=None)
    assert result['state']=='PASS' and [o['test_id'] for o in result['observations']]==expected
    assert [o['actual_return'] for o in result['observations']]==[value,value]
    assert all(i.startswith('bench.nexus_verify_'+NONCE+'.') for i in expected)
    for item in result['observations']:
        source=item['source'];assert source['coordinate']=='ANSI_STRIPPED_FULL_LOG'
        assert text[source['start_char']:source['end_char']].strip().startswith(scoped_values.PROTOCOLS[mode][0])
    result['observations'][0]['actual_return']['fields']['amount']=99
    assert result['observations'][1]['actual_return']==value


@pytest.mark.parametrize('mode',['oracle','single','relation'])
def test_v5_harness_uses_real_aliases_and_package_level_factories(mode):
    files=project();sig=selected(files);derived=material(files,sig,NONCE);m=api()
    rendered=m.render(sig,[example()],nonce=NONCE,mode=mode,binding=derived['binding'])
    source=rendered['source'].decode();binding=derived['binding']
    assert 'package '+binding['package'] in source
    assert rendered['path']=='src/nexus_verify_'+NONCE+'/nexus_observations_test.cj'
    assert 'import '+binding['target']+' as '+binding['target_alias'] in source
    assert ' = bench.apply' not in source and 'bench.sale.State(' not in source
    assert source.index('private func ')<source.index('@Test\nclass ')
    assert rendered['case_ids']==m.case_ids(sig,1,NONCE,mode)
    assert rendered['case_ids'][0] in source
    assert primitive_trace.harness(sig,[example()],binding['package'],NONCE,mode,version=5,binding=binding)==rendered['source']
    observed=primitive_trace.read(sig,[example()],NONCE,mode,fixture(sig,mode,[{'$type':'bench.refund.State','fields':{'amount':16}}]),0,None,version=5)
    assert observed['observations'][0]['args']==example()


@pytest.mark.parametrize('change',['missing','duplicate','other-package','other-suite','wrong-id','short-id','wrong-nonce','wrong-type','wrong-protocol','stderr','extra-after-summary','not-canonical','bad-counts','no-summary','exit','bool-exit','problem','huge-count','oversize-log'])
def test_forged_partial_or_mixed_v5_observations_are_unknown(change):
    sig=selected(project());m=api();value={'$type':'bench.refund.State','fields':{'amount':16}}
    expected=m.case_ids(sig,1,NONCE,'single');text=fixture(sig,'single',[value]);code=0;problem=None
    line=next(line for line in text.splitlines() if 'NEXUS_PROPERTY_V5|' in line)
    if change=='missing':text=text.replace(line,'')
    elif change=='duplicate':text=text.replace(line,line+'\n'+line)
    elif change=='other-package':text=text.replace('TP: bench.nexus_verify_'+NONCE,'TP: bench.other')
    elif change=='other-suite':text=text.replace('TCS: NexusPropertiesV5','TCS: OtherPropertiesV5')
    elif change=='wrong-id':text=text.replace('|'+expected[0]+'|','|'+expected[0]+'Extra|')
    elif change=='short-id':text=text.replace('|'+expected[0]+'|','|case0|')
    elif change=='wrong-nonce':text=text.replace('|'+NONCE+'|','|'+'f'*16+'|')
    elif change=='wrong-type':text=text.replace('|bench.refund.State|','|bench.sale.State|')
    elif change=='wrong-protocol':text=text.replace('NEXUS_PROPERTY_V5|','NEXUS_PROPERTY_V4|')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    elif change=='extra-after-summary':text+=line+'\n'
    elif change=='not-canonical':text=text.replace('2:16','02:16')
    elif change=='bad-counts':text=text.replace('TOTAL: 1 PASSED: 1','TOTAL: 2 PASSED: 2')
    elif change=='no-summary':text=text.split('Summary:',1)[0]
    elif change=='exit':code=1
    elif change=='bool-exit':code=False
    elif change=='huge-count':text=text.replace('TOTAL: 1','TOTAL: '+'9'*5000)
    elif change=='oversize-log':text+='x'*(2*1024*1024)
    else:problem='TimeoutError'
    result=m.read(text,sig,expected,nonce=NONCE,mode='single',exit_code=code,problem=problem)
    assert result['state']=='UNKNOWN' and result['observations']==[]


@pytest.mark.parametrize('change',['target','package','nonce','type-alias','extra-type','imports','signature','bridge-path','source-hash','extra-key'])
def test_source_binding_shape_cannot_interpolate_foreign_symbols_or_imports(change):
    files=project();sig=selected(files);binding=deepcopy(material(files,sig,NONCE)['binding'])
    if change=='target':binding['target']='bench.refund.fee'
    elif change=='package':binding['package']='bench.other'
    elif change=='nonce':binding['nonce']='f'*16
    elif change=='type-alias':binding['type_names']['bench.sale.State']='Type; println(1)'
    elif change=='extra-type':binding['type_names']['bench.other.State']='Other'
    elif change=='imports':binding['imports'].append('import std.fs.*')
    elif change=='signature':binding['signature_hash']='f'*64
    elif change=='bridge-path':binding['bridge_path']='src/refund/inject.cj'
    elif change=='source-hash':binding['source_tree_hash']='not-a-hash'
    else:binding['approved']=True
    with pytest.raises(ValueError):api().render(sig,[example()],nonce=NONCE,mode='single',binding=binding)


def test_v5_requires_scoped_source_and_binding_and_enforces_case_budget():
    sig=selected(project());m=api()
    for raw in (None,{},dict(sig,scope=None)):
        with pytest.raises(ValueError):m.case_ids(raw,1,NONCE,'single')
    for count in (0,True,129):
        with pytest.raises(ValueError):m.case_ids(sig,count,NONCE,'single')
    assert len(m.case_ids(sig,256,NONCE,'oracle'))==256
    with pytest.raises(ValueError):primitive_trace.harness(sig,[example()],'bench',NONCE,'single',version=5)
