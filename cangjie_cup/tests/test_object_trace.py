"""Explicit V4 fixtures exercise observations only, never SDK/model capability."""
import importlib,importlib.util
from copy import deepcopy
import pytest
from nexus.repair import primitive_trace,sequence_trace,property_trace,relation_trace,properties,relations,sequences
from tests.test_object_values import types
from tests.test_object_contracts import state,signature,raw_property,raw_relation,sequence_raw
from tests.test_primitive_trace import TOKEN,log as old_log,signature as old_signature


def codec():
    assert importlib.util.find_spec('nexus.repair.object_trace') is not None,'bounded object observation codec missing'
    return importlib.import_module('nexus.repair.object_trace')


def wire(value,registry=None):
    if type(value) is dict:
        registry=types() if registry is None else registry;decl=registry[value['$type']]['fields'];parts=[wire(value['fields'][f['name']],registry) for f in decl]
        return 'o:'+value['$type']+':'+str(len(parts))+':'+''.join(str(len(p))+':'+p for p in parts)
    if type(value) is list:return 'a:'+str(len(value))+':'+','.join(str(v) for v in value)
    if type(value) is str:return 's:'+value.encode().hex()
    return str(value).lower() if type(value) is bool else str(value)


def fixture(kind,encoded,primitive='OrderState',cls=None):
    name={'oracle':'NexusOracleV4','single':'NexusPropertiesV4','relation':'NexusRelationsV4'}[kind]
    prefix={'oracle':'ORACLE','single':'PROPERTY','relation':'RELATION'}[kind]
    lines=['EXPLICIT V4 LOG FIXTURE','TP: bench, RESULT:',' TCS: '+(cls or name+TOKEN)+', RESULT:']
    for i,text in enumerate(encoded):lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' NEXUS_'+prefix+'_V4|'+TOKEN+'|case'+str(i)+'|'+primitive+'|'+text])
    count=len(encoded);lines.extend(['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return '\n'.join(lines)


def sequence_fixture(cases=None,ends=None):
    cases=[[(state(0),state(1)),(state(1),state(0))]] if cases is None else cases
    ends=[(len(c),'COMPLETE') for c in cases] if ends is None else ends
    lines=['EXPLICIT V4 SEQUENCE FIXTURE','TP: bench, RESULT:',' TCS: NexusSequencesV4'+TOKEN+', RESULT:']
    for i,(observations,end) in enumerate(zip(cases,ends)):
        lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:'])
        for j,(before,after) in enumerate(observations):lines.append(' NEXUS_SEQUENCE_V4|'+TOKEN+'|case'+str(i)+'|step'+str(j)+'|OrderState|'+wire(before)+'|'+wire(after))
        lines.append(' NEXUS_SEQUENCE_END_V4|'+TOKEN+'|case'+str(i)+'|'+str(end[0])+'|'+end[1])
    count=len(cases);lines.extend(['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return '\n'.join(lines)


@pytest.mark.parametrize('amount',[-(1<<63),0,(1<<63)-1])
def test_v4_object_codec_exact_typed_copied_and_canonical(amount):
    value=state(amount);value['fields'].update(label='中\x00\nNEXUS_SEQUENCE_END_V4|fake',items=[-(1<<63)]*16)
    c=codec();text=c.encode(value,'OrderState',types());assert text==wire(value)
    result=c.decode(text,'OrderState',types());assert result==value;result['fields']['items'].append(0);assert len(value['fields']['items'])==16


def test_v4_object_codec_2141_exact_maximum_and_primitive_delegation():
    name='T'*64;fields=[dict(name='f'+str(i),type='String') for i in range(4)];registry={name:dict(kind='class',fields=fields,constructor=deepcopy(fields),methods=[])}
    value={'$type':name,'fields':{f['name']:'x'*256 for f in fields}};c=codec();text=c.encode(value,name,registry);assert len(text)==2141 and c.decode(text,name,registry)==value
    for kind,value in [('Int64',-(1<<63)),('Bool',False),('String','中\n'),('Array<Int64>',[])]:assert c.decode(c.encode(value,kind,types()),kind,types())==value


@pytest.mark.parametrize('change',['tag','count','leading-count','leading-length','negative-length','huge-length','truncated','trailing','bool-int','array-bool','utf8','big-wire'])
def test_v4_noncanonical_or_bad_object_wire_rejected(change):
    text=wire(state(0))
    if change=='tag':text=text.replace('OrderState','OtherState')
    elif change=='count':text=text.replace(':4:',':3:',1)
    elif change=='leading-count':text=text.replace(':4:',':04:',1)
    elif change=='leading-length':text=text.replace(':1:0',':01:0',1)
    elif change=='negative-length':text=text.replace(':1:0',':-1:0',1)
    elif change=='huge-length':text=text.replace(':1:0',':999:0',1)
    elif change=='truncated':text=text[:-1]
    elif change=='trailing':text+='0'
    elif change=='bool-int':text=text.replace(':1:0',':4:true',1)
    elif change=='array-bool':text=text.replace('a:0:','a:1:true')
    elif change=='utf8':text=text.replace('s:e4b8ad','s:ff0000')
    else:text+='x'*2142
    with pytest.raises(ValueError):codec().decode(text,'OrderState',types())


@pytest.mark.parametrize('kind',['oracle','single','relation'])
def test_v4_actual_object_returns_preserve_source_coordinates_and_snapshot(kind):
    inputs=[[state(0),0]];text=fixture(kind,[wire(state(1))]);r=primitive_trace.read(signature(),inputs,TOKEN,kind,text,0,None,version=4)
    assert r['state']=='PASS' and r['observations'][0]['actual_return']==state(1)
    item=r['observations'][0];start,end=(item['source'][n] for n in ('start_char','end_char'));assert text[start:end].strip().startswith('NEXUS_')
    inputs[0][0]['fields']['items'].append(9);assert item['args']==[state(0),0]


@pytest.mark.parametrize('change',['missing','duplicate','nonce','case','type','stderr','footer','summary','exit','problem','limit','v1','v2','v3','trailing','forged-suite'])
def test_v4_incomplete_or_forged_observations_stay_unknown(change):
    marker='NEXUS_PROPERTY_V4|'+TOKEN+'|case0|OrderState|'+wire(state(0));text=fixture('single',[wire(state(0))]);code=0;problem=None
    if change=='missing':text=text.replace(marker,'')
    elif change=='duplicate':text=text.replace(marker,marker+'\n'+marker)
    elif change=='nonce':text=text.replace('|'+TOKEN+'|','|'+'f'*16+'|')
    elif change=='case':text=text.replace('|case0|','|case1|')
    elif change=='type':text=text.replace('|OrderState|','|Int64|')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    elif change=='footer':text=text.replace('cjpm test success',marker+'\ncjpm test success')
    elif change=='summary':text=text.split('Summary:',1)[0]
    elif change=='exit':code=1
    elif change=='problem':problem='TimeoutError'
    elif change=='limit':text=text.replace(marker,'NEXUS_VALUE_ERROR_V4|'+TOKEN+'|case0|VALUE_LIMIT')
    elif change in ('v1','v2','v3'):text=text.replace('_V4|','_V'+change[-1]+'|')
    elif change=='forged-suite':text=text.replace(' TCS: ','NEXUS_VALUE_ERROR_V4|fake TCS: ')
    else:text=text.replace(marker,marker+' ')
    r=primitive_trace.read(signature(),[[state(0),0]],TOKEN,'single',text,code,problem,version=4);assert r['state']=='UNKNOWN' and r['observations']==[]


@pytest.mark.parametrize('prefix',['NEXUS_'+p+'_V4|' for p in ('ORACLE','PROPERTY','RELATION','SEQUENCE','SEQUENCE_END','VALUE_ERROR')])
def test_v1_rejects_reserved_v4_control_before_suite(prefix):
    text=old_log('single');r=primitive_trace.read(old_signature(),[[1],[2]],TOKEN,'single',prefix+'fake TCS: forged,\n'+text,0,None)
    assert r['state']=='UNKNOWN'


def test_v4_property_and_relation_use_typed_whole_actual_objects():
    p=properties.validate_contract(raw_property(),signature(),[]);r=property_trace.interpret(p,[[state(0),1]],TOKEN,fixture('single',[wire(state(0))]),0,None)
    assert r['state']=='FAIL' and r['failures'][0]['actual_return']==state(0)
    c=relations.validate_contract(raw_relation(),signature(),[]);pair=dict(left=[state(1),0],right=[state(1),0]);r=relation_trace.interpret(c,[pair],TOKEN,fixture('relation',[wire(state(1)),wire(state(0))]),0,None)
    assert r['state']=='FAIL' and r['failures'][0]['right_actual_return']==state(0)


def model():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[]);trace=dict(initial_state=state(0),context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(2)]);return c,trace


def test_v4_sequence_first_mismatch_stops_real_prefix_and_copies_snapshots():
    c,t=model();r=sequence_trace.interpret(c,[t],TOKEN,sequence_fixture(),0,None);assert r['state']=='PASS' and r['observed_calls']==2
    text=sequence_fixture([[(state(0),state(0))]],[(1,'MODEL_MISMATCH')]);r=sequence_trace.interpret(c,[t],TOKEN,text,0,None)
    assert r['state']=='FAIL' and r['observed_calls']==1 and r['unexecuted_calls']==1 and r['failures'][0]['actual_return']==state(0)
    r['failures'][0]['actual_return']['fields']['items'].append(1);assert r['observations'][0]['steps'][0]['actual_return']==state(0)


def test_v4_harness_uses_field_encoding_limits_and_no_nominal_object_equality():
    codec();text=primitive_trace.harness(signature(),[[state(0),1]],'bench',TOKEN,'single',version=4).decode()
    assert 'NEXUS_PROPERTY_V4|' in text and '.amount' in text and '.label.size > 256' in text and '.items.size > 16' in text and 'OrderState(' in text
    assert '.toString(' not in text
    c,t=model();text=sequence_trace.harness(c,[t],'bench',TOKEN).decode();assert 'NEXUS_SEQUENCE_V4|' in text and 'MODEL_MISMATCH' in text
    assert '!= OrderState(' not in text


def test_v4_generated_class_and_helpers_avoid_declared_object_names():
    sig=signature();sig['types']['NexusPropertiesV4'+TOKEN]=sig['types'].pop('OrderState');name='NexusPropertiesV4'+TOKEN
    sig['params'][0]['type']=name;sig['return_type']=name;v=state();v['$type']=name
    ids=primitive_trace.case_ids(TOKEN,1,'single',4,sig);assert ids==[name+'Value.case0']
    text=primitive_trace.harness(sig,[[v,0]],'bench',TOKEN,'single',4).decode();assert 'class '+name+'Value {' in text


def test_v4_encoder_fields_use_unique_temporaries_without_bare_lambda_blocks():
    text=primitive_trace.harness(signature(),[[state(),0]],'bench',TOKEN,'single',4).decode()
    assert '\n{\nlet ' not in text
    names=[line.split(' = ',1)[0] for line in text.splitlines() if line.startswith('let __nexusObjectFieldWire')]
    assert len(names)==4 and len(set(names))==4


@pytest.mark.parametrize('change',['before','continuation','missing-end','early-complete','wrong-prefix','wrong-type','duplicate-end','missing-step'])
def test_v4_sequence_malformed_prefix_and_endings_never_become_success(change):
    c,t=model();text=sequence_fixture()
    if change=='before':text=text.replace('|step1|OrderState|'+wire(state(1)),'|step1|OrderState|'+wire(state(0)))
    elif change=='continuation':text=sequence_fixture([[(state(0),state(0)),(state(0),state(1))]])
    elif change=='missing-end':text='\n'.join(line for line in text.split('\n') if 'NEXUS_SEQUENCE_END_V4|' not in line)
    elif change=='early-complete':text=sequence_fixture([[(state(0),state(1))]],[(1,'COMPLETE')])
    elif change=='wrong-prefix':text=text.replace('NEXUS_SEQUENCE_V4|','NEXUS_PROPERTY_V4|')
    elif change=='wrong-type':text=text.replace('|OrderState|','|Bool|')
    elif change=='duplicate-end':line=next(l for l in text.split('\n') if 'NEXUS_SEQUENCE_END_V4|' in l);text=text.replace(line,line+'\n'+line)
    else:text='\n'.join(line for line in text.split('\n') if '|step0|' not in line)
    result=sequence_trace.interpret(c,[t],TOKEN,text,0,None);assert result['state']=='UNKNOWN' and not result['observations'] and not result['failures']


def test_v4_object_construction_is_bound_outside_case_method_scope():
    sig=signature();sig['types']['case0']=sig['types'].pop('OrderState');sig['params'][0]['type']='case0';sig['return_type']='case0';value=state();value['$type']='case0'
    text=primitive_trace.harness(sig,[[value,0]],'bench',TOKEN,'single',4).decode()
    method=text.split('func case0() {',1)[1]
    assert 'case0(' not in method
    assert 'private func __nexusObjectCtor0(' in text and 'return case0(' in text
