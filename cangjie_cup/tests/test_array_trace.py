"""Explicit V3 log fixtures; never actual SDK/model claims."""
import importlib
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from nexus.repair import primitive_trace,property_trace,relation_trace,sequence_trace,properties,relations,sequences
from tests.test_primitive_trace import TOKEN,log as old_log,signature as old_signature
from tests.test_sequence_trace import contract as old_sequence,trajectory,log as old_sequence_log
from tests.test_string_trace import fixture as string_log,sig as string_sig,model as string_model,sequence_fixture as string_sequence_log
from tests.test_array_contracts import raw_property,raw_relation,signature,sequence_raw

LOW=-(1<<63);HIGH=(1<<63)-1;NL=chr(10)
PREFIXES=tuple('NEXUS_'+s+'_V3|' for s in ('ORACLE','PROPERTY','RELATION','SEQUENCE','SEQUENCE_END','VALUE_ERROR'))
NAMES={'oracle':('NEXUS_ORACLE_V3','NexusOracleV3'),'single':('NEXUS_PROPERTY_V3','NexusPropertiesV3'),'relation':('NEXUS_RELATION_V3','NexusRelationsV3')}


def codec():
    assert importlib.util.find_spec('nexus.repair.array_trace') is not None,'bounded Array observation codec missing'
    return importlib.import_module('nexus.repair.array_trace')


def sig(kind='Array<Int64>',name='identity'):return dict(name=name,params=[dict(name='x',type='Array<Int64>')],return_type=kind)


def wire(value):
    if type(value) is list:return 'a:'+str(len(value))+':'+','.join(str(n) for n in value)
    if type(value) is str:return 's:'+value.encode().hex()
    return str(value).lower() if type(value) is bool else str(value)


def fixture(kind,encoded,primitive='Array<Int64>',cls=None):
    prefix,name=NAMES[kind];lines=['EXPLICIT V3 LOG FIXTURE','TP: bench, RESULT:',' TCS: '+(cls or name+TOKEN)+', RESULT:']
    for i,value in enumerate(encoded):lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' '+prefix+'|'+TOKEN+'|case'+str(i)+'|'+primitive+'|'+value])
    count=len(encoded);lines.extend(['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return NL.join(lines)


def model():
    raw,s=sequence_raw();c=sequences.validate_contract(raw,s,[])
    trace=dict(initial_state=[1,2],context=['中'],steps=[dict(operation_id=i,args=[0 if i=='OP-SWAP' else 1,'中']) for i in ('OP-SWAP','OP-SWAP','OP-RESET','OP-SWAP')])
    return c,trace


def sequence_fixture(cases=None,ends=None,kind='Array<Int64>',cls=None):
    cases=[[([1,2],[2,1]),([2,1],[1,2]),([1,2],[]),([],[])]] if cases is None else cases
    ends=[(len(c),'COMPLETE') for c in cases] if ends is None else ends
    lines=['EXPLICIT V3 SEQUENCE FIXTURE','TP: bench, RESULT:',' TCS: '+(cls or 'NexusSequencesV3'+TOKEN)+', RESULT:']
    for i,(observations,end) in enumerate(zip(cases,ends)):
        lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:'])
        for step,(before,after) in enumerate(observations):lines.append(' NEXUS_SEQUENCE_V3|'+TOKEN+'|case'+str(i)+'|step'+str(step)+'|'+kind+'|'+wire(before)+'|'+wire(after))
        lines.append(' NEXUS_SEQUENCE_END_V3|'+TOKEN+'|case'+str(i)+'|'+str(end[0])+'|'+end[1])
    count=len(cases);lines.extend(['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return NL.join(lines)


@pytest.mark.parametrize('value',[[],[0],[-1,0,1],[LOW,HIGH],[LOW]*16])
def test_v3_array_codec_is_exact_bounded_and_copied(value):
    c=codec();encoded=wire(value);assert len(encoded)<=340 and c.encode(value,'Array<Int64>')==encoded
    result=c.decode(encoded,'Array<Int64>');assert result==value and result is not value

@pytest.mark.parametrize('text',['a:','a:0','a:0:0','a:00:','a:01:1','a:-1:','a:1:','a:1:+1','a:1:01','a:1:-0','a:1:true','a:1:1.0','a:1:9223372036854775808','a:1:-9223372036854775809','a:2:1','a:1:1,','a:1: 1','a:1:1 ','a:1:1|extra','a:1:[1]','a:17:'+','.join(['0']*17),'a:16:'+','.join([str(LOW)]*16)+'0'])
def test_bad_array_encoding_is_never_silently_normalized(text):
    with pytest.raises(ValueError):codec().decode(text,'Array<Int64>')

@pytest.mark.parametrize('kind,value',[('Bool',False),('Bool',True),('Int64',LOW),('Int64',HIGH),('String','中'+chr(0)+NL+'NEXUS_SEQUENCE_END_V3|fake')])
def test_v3_codec_preserves_other_primitive_values(kind,value):
    assert codec().decode(codec().encode(value,kind),kind)==value

@pytest.mark.parametrize('kind',['oracle','single','relation'])
def test_v3_actual_arrays_and_coordinates_are_separate_from_input_aliases(kind):
    inputs=[[[]],[[LOW]*16]];text=fixture(kind,[wire([]),wire([LOW]*16)])
    result=primitive_trace.read(sig(),inputs,TOKEN,kind,text,0,None,version=3)
    assert result['state']=='PASS' and [o['actual_return'] for o in result['observations']]==[[],[LOW]*16]
    inputs[0][0].append(99);assert result['observations'][0]['args']==[[]]
    for item in result['observations']:
        source=item['source'];assert text[source['start_char']:source['end_char']].strip().startswith(NAMES[kind][0]+'|')

@pytest.mark.parametrize('kind,encoded,want',[('Bool',['false','true'],[False,True]),('Int64',[str(LOW),str(HIGH)],[LOW,HIGH]),('String',['s:','s:e4b8ad'],['','中'])])
def test_v3_array_input_can_return_any_supported_primitive(kind,encoded,want):
    result=primitive_trace.read(sig(kind),[[[]],[[1]]],TOKEN,'single',fixture('single',encoded,kind),0,None,version=3)
    assert result['state']=='PASS' and [o['actual_return'] for o in result['observations']]==want

@pytest.mark.parametrize('change',['missing','duplicate','kind','nonce','case','type','stderr','footer','summary','exit','problem','limit','v2','trailing'])
def test_v3_incomplete_forged_or_noncanonical_batch_remains_unknown(change):
    marker='NEXUS_PROPERTY_V3|'+TOKEN+'|case0|Array<Int64>|a:1:1';text=fixture('single',['a:1:1']);code=0;problem=None
    if change=='missing':text=text.replace(marker,'')
    elif change=='duplicate':text=text.replace(marker,marker+NL+marker)
    elif change=='kind':text=text.replace('NEXUS_PROPERTY_V3|','NEXUS_ORACLE_V3|')
    elif change=='nonce':text=text.replace('|'+TOKEN+'|','|'+'f'*16+'|')
    elif change=='case':text=text.replace('|case0|','|case1|')
    elif change=='type':text=text.replace('|Array<Int64>|','|Int64|')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    elif change=='footer':text=text.replace('cjpm test success',marker+NL+'cjpm test success')
    elif change=='summary':text=text.split('Summary:',1)[0]
    elif change=='exit':code=1
    elif change=='problem':problem='TimeoutError'
    elif change=='limit':text=text.replace(marker,'NEXUS_VALUE_ERROR_V3|'+TOKEN+'|case0|VALUE_LIMIT')
    elif change=='v2':text=text.replace('NEXUS_PROPERTY_V3|','NEXUS_PROPERTY_V2|')
    else:text=text.replace(marker,marker+' ')
    result=primitive_trace.read(sig(),[[[1]]],TOKEN,'single',text,code,problem,version=3)
    assert result['state']=='UNKNOWN' and result['observations']==[]

@pytest.mark.parametrize('decoder',['v1-single','v1-relation','v1-sequence','v2-oracle','v2-single','v2-relation','v2-sequence'])
@pytest.mark.parametrize('prefix',PREFIXES)
@pytest.mark.parametrize('where',['stdout','footer','fake-header'])
def test_all_older_decoders_reject_every_v3_reserved_marker(decoder,prefix,where):
    version,kind=decoder.split('-');version=int(version[1:])
    if version==1:text=old_sequence_log() if kind=='sequence' else old_log(kind,('1',))
    else:text=string_sequence_log() if kind=='sequence' else string_log(kind,['s:61'])
    marker=' '+prefix+TOKEN+'|case0|VALUE_LIMIT'+NL
    if where=='fake-header':marker=' '+prefix+'TCS: '+('NexusProperties' if version==1 else 'NexusPropertiesV2')+TOKEN+', RESULT:'+NL
    text=text.replace('cjpm test success',marker+'cjpm test success') if where=='footer' else text.replace('Summary:',marker+'Summary:',1)
    if kind=='sequence':
        if version==1:result=sequence_trace.interpret(old_sequence(),[trajectory()],TOKEN,text,0,None)
        else:c,t=string_model();result=sequence_trace.interpret(c,[t],TOKEN,text,0,None)
    else:result=primitive_trace.read(old_signature() if version==1 else string_sig(),[[1]] if version==1 else [['a']],TOKEN,kind,text,0,None,version=version)
    assert result['state']=='UNKNOWN' and result['observations']==[]


def test_v3_property_and_relation_observe_actual_array_parameter_results():
    c=properties.validate_contract(raw_property(),signature(),[]);cases=[[[1,2],0]]
    assert b'NEXUS_PROPERTY_V3|' in property_trace.harness(c,cases,'bench',TOKEN)
    result=property_trace.interpret(c,cases,TOKEN,fixture('single',['1'],'Int64'),0,None)
    assert result['state']=='FAIL' and result['failures'][0]['actual_return']==1
    c=relations.validate_contract(raw_relation(),signature(),[]);pairs=[dict(left=[[1,2],0],right=[[2,1],0])]
    assert b'NEXUS_RELATION_V3|' in relation_trace.harness(c,pairs,'bench',TOKEN)
    result=relation_trace.interpret(c,pairs,TOKEN,fixture('relation',['1','2'],'Int64'),0,None)
    assert result['state']=='FAIL' and result['failures'][0]['left_actual_return']==1 and result['failures'][0]['right_actual_return']==2


def test_v3_sequence_uses_real_array_states_and_retains_only_executed_prefix():
    c,t=model();text=sequence_fixture();assert b'NEXUS_SEQUENCE_V3|' in sequence_trace.harness(c,[t],'bench',TOKEN)
    result=sequence_trace.interpret(c,[t],TOKEN,text,0,None);assert result['state']=='PASS' and result['observed_calls']==4
    assert [s['actual_return'] for s in result['observations'][0]['steps']]==[[2,1],[1,2],[],[]]
    t['initial_state'].append(99);assert result['observations'][0]['initial_state']==[1,2]
    c,t=model();text=sequence_fixture([[([1,2],[2,1]),([2,1],[2,1])]],[(2,'MODEL_MISMATCH')])
    result=sequence_trace.interpret(c,[t],TOKEN,text,0,None)
    assert result['state']=='FAIL' and (result['planned_calls'],result['observed_calls'],result['unexecuted_calls'])==(4,2,2)
    assert result['failures'][0]['actual_return']==[2,1] and result['failures'][0]['expected_state']==[1,2]

@pytest.mark.parametrize('change',['before','end','footer','old-protocol','oversize','missing-step','later-step','limit','trailing','fake-header'])
def test_v3_sequence_invalid_protocol_never_becomes_business_failure(change):
    c,t=model();text=sequence_fixture()
    if change=='before':text=text.replace('|step1|Array<Int64>|a:2:2,1|','|step1|Array<Int64>|a:2:1,2|')
    elif change=='end':text=text.replace('|4|COMPLETE','|3|COMPLETE')
    elif change=='footer':text=text.replace('cjpm test success','NEXUS_SEQUENCE_END_V3|'+TOKEN+'|case0|4|COMPLETE'+NL+'cjpm test success')
    elif change=='old-protocol':text=text.replace('NEXUS_SEQUENCE_V3|','NEXUS_SEQUENCE_V2|')
    elif change=='oversize':text=text.replace('|a:2:1,2|a:2:2,1','|a:2:1,2|a:17:'+','.join(['0']*17))
    elif change=='missing-step':text=NL.join(line for line in text.split(NL) if '|step1|' not in line)
    elif change=='later-step':text=text.replace('|step1|','|step2|')
    elif change=='limit':text=text.replace('NEXUS_SEQUENCE_END_V3|'+TOKEN+'|case0|4|COMPLETE','NEXUS_VALUE_ERROR_V3|'+TOKEN+'|case0|VALUE_LIMIT')
    elif change=='fake-header':text=text.replace('Summary:','NEXUS_VALUE_ERROR_V3|TCS: NexusSequencesV3'+TOKEN+', RESULT:'+NL+'Summary:',1)
    else:text=text.replace('|Array<Int64>|a:2:1,2|a:2:2,1'+NL,'|Array<Int64>|a:2:1,2|a:2:2,1 '+NL)
    result=sequence_trace.interpret(c,[t],TOKEN,text,0,None);assert result['state']=='UNKNOWN' and result['observations']==[] and result['failures']==[]


def test_v3_exact_case_budgets_explicit_selection_and_generated_name_collisions():
    assert len(primitive_trace.case_ids(TOKEN,256,'oracle',version=3))==256
    primitive_trace.harness(sig(),[[[]]]*256,'bench',TOKEN,'oracle',version=3)
    for kind in ('single','relation'):
        with pytest.raises(ValueError):primitive_trace.harness(sig(),[[[]]]*129,'bench',TOKEN,kind,version=3)
    for version in (None,True,'3',0,4,[],{}):
        with pytest.raises(ValueError):primitive_trace.harness(sig(),[[[]]],'bench',TOKEN,'single',version=version)
    for version in (1,2):
        with pytest.raises(ValueError):primitive_trace.harness(sig(),[[[]]],'bench',TOKEN,'single',version=version)
    with pytest.raises(ValueError):primitive_trace.harness(string_sig(),[['a']],'bench',TOKEN,'single',version=3)
    named=sig(name='NexusPropertiesV3'+TOKEN);ids=primitive_trace.case_ids(TOKEN,1,'single',version=3,signature=named)
    assert ids==['NexusPropertiesV3'+TOKEN+'Value.case0']
    result=primitive_trace.read(named,[[[]]],TOKEN,'single',fixture('single',['a:0:'],cls=ids[0].split('.')[0]),0,None,version=3)
    assert result['state']=='PASS'


def test_existing_v2_normal_harness_bytes_remain_unchanged():
    expected={'v2-oracle':'3bdd12048056194dc028912d75507c3906160280559ae60a1c2d470994d47d0a','v2-single':'1c66e3d351603a32c35e738891c33f34f607c0e316d6931eb61042bbdc66af23','v2-relation':'8ccb205d84cb1f0e9dfa437aaafc81936643f13e3cfdf09f5e6312025ac3c438','v2-sequence':'851d9f96991f88c87c72f5f3fdc63c51b07c3cfa76f2af402e700062eb7322a3'}
    for kind in ('oracle','single','relation'):
        assert hashlib.sha256(primitive_trace.harness(string_sig(),[['a'],['']],'bench',TOKEN,kind,version=2)).hexdigest()==expected['v2-'+kind]
    c,t=string_model();assert hashlib.sha256(sequence_trace.harness(c,[t],'bench',TOKEN)).hexdigest()==expected['v2-sequence']
