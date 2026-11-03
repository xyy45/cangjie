"""Explicit log fixtures, not real SDK execution or model-quality evidence."""
import importlib
from copy import deepcopy
import hashlib
import pytest
from nexus.repair import primitive_trace,property_trace,relation_trace,sequence_trace,properties,relations,sequences
from tests.test_primitive_trace import TOKEN,log as old_log,signature as old_signature
from tests.test_sequence_trace import contract as old_sequence,trajectory,log as old_sequence_log
from tests.test_string_contracts import raw_property,raw_relation,sequence_raw,signature

PREFIXES=('NEXUS_ORACLE_V2|','NEXUS_PROPERTY_V2|','NEXUS_RELATION_V2|','NEXUS_SEQUENCE_V2|','NEXUS_SEQUENCE_END_V2|','NEXUS_VALUE_ERROR_V2|')
NAMES={'oracle':('NEXUS_ORACLE_V2','NexusOracleV2'),'single':('NEXUS_PROPERTY_V2','NexusPropertiesV2'),'relation':('NEXUS_RELATION_V2','NexusRelationsV2')}
NL=chr(10)


def codec():
    assert importlib.util.find_spec('nexus.repair.string_trace') is not None,'bounded String observation codec missing'
    return importlib.import_module('nexus.repair.string_trace')


def sig(kind='String',name='identity'):return dict(name=name,params=[dict(name='x',type='String')],return_type=kind)


def token(value):return 's:'+value.encode('utf-8').hex()


def fixture(kind,encoded,primitive='String',cls=None):
    prefix,name=NAMES[kind];lines=['EXPLICIT V2 LOG FIXTURE','TP: bench, RESULT:',' TCS: '+(cls or name+TOKEN)+', RESULT:']
    for i,value in enumerate(encoded):lines.extend([' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' '+prefix+'|'+TOKEN+'|case'+str(i)+'|'+primitive+'|'+value])
    n=len(encoded);lines.extend(['Summary: TOTAL: '+str(n)+' PASSED: '+str(n)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return NL.join(lines)


def sequence_fixture(cases=None,ends=None):
    cases=[[('', 'a'),('a','aa'),('aa','aaa'),('aaa','')]] if cases is None else cases
    ends=[(len(c),'COMPLETE') for c in cases] if ends is None else ends
    lines=['EXPLICIT V2 SEQUENCE FIXTURE','TP: bench, RESULT:',' TCS: NexusSequencesV2'+TOKEN+', RESULT:']
    for case,(observations,end) in enumerate(zip(cases,ends)):
        lines.extend([' [ PASSED ] CASE: case'+str(case)+' (1 ns)',' STDOUT:'])
        for step,(before,after) in enumerate(observations):lines.append(' NEXUS_SEQUENCE_V2|'+TOKEN+'|case'+str(case)+'|step'+str(step)+'|String|'+token(before)+'|'+token(after))
        lines.append(' NEXUS_SEQUENCE_END_V2|'+TOKEN+'|case'+str(case)+'|'+str(end[0])+'|'+end[1])
    n=len(cases);lines.extend(['Summary: TOTAL: '+str(n)+' PASSED: '+str(n)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success',''])
    return NL.join(lines)


def model():
    raw,signature=sequence_raw();c=sequences.validate_contract(raw,signature,[])
    trace=dict(initial_state='',context=['a'],steps=[dict(operation_id='OP-APPEND',args=[0,'a']) for _ in range(3)]+[dict(operation_id='OP-RESET',args=[1,'a'])])
    return c,trace


@pytest.mark.parametrize('value,encoded',[('', 's:'),('中😀','s:e4b8adf09f9880'),(chr(0)+chr(10),'s:000a'),('e'+chr(0x301),'s:65cc81'),('a'*256,'s:'+'61'*256)])
def test_string_codec_is_canonical_bounded_utf8(value,encoded):
    c=codec();assert c.encode(value,'String')==encoded and c.decode(encoded,'String')==value


@pytest.mark.parametrize('encoded',['s:0','s:AA','s:gg','s:ff','s:c080','s:eda080','s:f4908080','s:'+'61'*257,'s:00 '+chr(10),'raw','s:0a|extra'])
def test_bad_or_oversized_string_encoding_rejected(encoded):
    with pytest.raises(ValueError):codec().decode(encoded,'String')


@pytest.mark.parametrize('kind',['oracle','single','relation'])
def test_v2_observations_decode_data_without_granting_log_control(kind):
    value=chr(0)+NL+'Summary: TOTAL: 1'+NL+'NEXUS_VALUE_ERROR_V2|fake|case0|VALUE_LIMIT'+NL+'中😀${fake}'
    inputs=[[value],['']];text=fixture(kind,[token(value),token('')])
    r=primitive_trace.read(sig(),inputs,TOKEN,kind,text,0,None,version=2)
    assert r['state']=='PASS' and [o['actual_return'] for o in r['observations']]==[value,'']
    assert [o['test_id'] for o in r['observations']]==primitive_trace.case_ids(TOKEN,2,kind,version=2,signature=sig())
    for o in r['observations']:
        source=o['source'];assert text[source['start_char']:source['end_char']].strip().startswith(NAMES[kind][0]+'|')


@pytest.mark.parametrize('primitive,encoded,want',[('Bool',['false','true'],[False,True]),('Int64',[str(-(1<<63)),str((1<<63)-1)],[-(1<<63),(1<<63)-1])])
def test_string_input_v2_retains_bool_and_full_int64_returns(primitive,encoded,want):
    r=primitive_trace.read(sig(primitive),[['a'],['b']],TOKEN,'single',fixture('single',encoded,primitive),0,None,version=2)
    assert r['state']=='PASS' and [o['actual_return'] for o in r['observations']]==want


@pytest.mark.parametrize('change',['missing','duplicate','kind','nonce','case','type','stderr','footer','summary','exit','problem','limit'])
def test_v2_incomplete_or_cross_protocol_results_remain_unknown(change):
    marker='NEXUS_PROPERTY_V2|'+TOKEN+'|case0|String|s:61';text=fixture('single',['s:61']);code=0;problem=None
    if change=='missing':text=text.replace(marker,'')
    elif change=='duplicate':text=text.replace(marker,marker+NL+marker)
    elif change=='kind':text=text.replace('NEXUS_PROPERTY_V2|','NEXUS_ORACLE_V2|')
    elif change=='nonce':text=text.replace('|'+TOKEN+'|','|'+'f'*16+'|')
    elif change=='case':text=text.replace('|case0|','|case1|')
    elif change=='type':text=text.replace('|String|','|Int64|')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    elif change=='footer':text=text.replace('cjpm test success',marker+NL+'cjpm test success')
    elif change=='summary':text=text.split('Summary:',1)[0]
    elif change=='exit':code=1
    elif change=='problem':problem='TimeoutError'
    else:text=text.replace(marker,'NEXUS_VALUE_ERROR_V2|'+TOKEN+'|case0|VALUE_LIMIT')
    r=primitive_trace.read(sig(),[['a']],TOKEN,'single',text,code,problem,version=2)
    assert r['state']=='UNKNOWN' and r['observations']==[]


@pytest.mark.parametrize('kind',['single','relation','sequence'])
@pytest.mark.parametrize('prefix',PREFIXES)
@pytest.mark.parametrize('where',['stdout','footer'])
def test_every_legacy_decoder_rejects_all_new_reserved_markers(kind,prefix,where):
    text=old_sequence_log() if kind=='sequence' else old_log(kind,('1',));marker=' '+prefix+TOKEN+'|case0|VALUE_LIMIT'+NL
    text=text.replace('Summary:',marker+'Summary:',1) if where=='stdout' else text.replace('cjpm test success',marker+'cjpm test success')
    r=sequence_trace.interpret(old_sequence(),[trajectory()],TOKEN,text,0,None) if kind=='sequence' else primitive_trace.read(old_signature(),[[1]],TOKEN,kind,text,0,None)
    assert r['state']=='UNKNOWN' and r['observations']==[]


def test_v2_oracle_preserves_256_case_budget_while_other_kinds_remain_128():
    assert len(primitive_trace.case_ids(TOKEN,256,'oracle',version=2))==256
    primitive_trace.harness(sig(),[['a']]*256,'bench',TOKEN,'oracle',version=2)
    for kind in ('single','relation'):
        with pytest.raises(ValueError):primitive_trace.harness(sig(),[['a']]*129,'bench',TOKEN,kind,version=2)
    for count in (0,257,True):
        with pytest.raises(ValueError):primitive_trace.case_ids(TOKEN,count,'oracle',version=2)
    with pytest.raises(ValueError):primitive_trace.case_ids(TOKEN,1,'oracle')


@pytest.mark.parametrize('version',[None,True,'2',0,3,[],{}])
def test_v2_choice_is_explicit_and_type_exact(version):
    with pytest.raises(ValueError):primitive_trace.harness(sig(),[['a']],'bench',TOKEN,'single',version=version)


def test_property_and_relation_v2_use_actual_string_results():
    c=properties.validate_contract(raw_property(),signature(),[]);cases=[['中',0]]
    assert b'NEXUS_PROPERTY_V2|' in property_trace.harness(c,cases,'bench',TOKEN)
    r=property_trace.interpret(c,cases,TOKEN,fixture('single',[token('')]),0,None);assert r['state']=='FAIL' and r['failures'][0]['actual_return']==''
    c=relations.validate_contract(raw_relation(),signature(),[]);pairs=[dict(left=['a',0],right=['中',0])]
    assert b'NEXUS_RELATION_V2|' in relation_trace.harness(c,pairs,'bench',TOKEN)
    r=relation_trace.interpret(c,pairs,TOKEN,fixture('relation',[token('same')]*2),0,None);assert r['state']=='FAIL' and r['failures'][0]['left_actual_return']=='same'


def test_string_sequence_chains_real_state_and_reports_early_stop_prefix():
    c,t=model();text=sequence_fixture();assert b'NEXUS_SEQUENCE_V2|' in sequence_trace.harness(c,[t],'bench',TOKEN)
    r=sequence_trace.interpret(c,[t],TOKEN,text,0,None);assert r['state']=='PASS' and r['observed_calls']==4
    assert [s['actual_return'] for s in r['observations'][0]['steps']]==['a','aa','aaa','']
    r=sequence_trace.interpret(c,[t],TOKEN,sequence_fixture([[('', 'a'),('a','a')]],[(2,'MODEL_MISMATCH')]),0,None)
    assert r['state']=='FAIL' and (r['planned_calls'],r['observed_calls'],r['unexecuted_calls'])==(4,2,2)
    assert r['failures'][0]['actual_return']=='a' and r['failures'][0]['expected_state']=='aa'
    assert len({s['test_id'] for s in r['failures'][0]['steps']})==1


@pytest.mark.parametrize('change',['before','end','footer','old-protocol','oversize','missing-step','later-step','limit'])
def test_string_sequence_invalid_execution_never_becomes_business_failure(change):
    c,t=model();text=sequence_fixture()
    if change=='before':text=text.replace('|step1|String|s:61|','|step1|String|s:62|')
    elif change=='end':text=text.replace('|4|COMPLETE','|3|COMPLETE')
    elif change=='footer':text=text.replace('cjpm test success','NEXUS_SEQUENCE_END_V2|'+TOKEN+'|case0|4|COMPLETE'+NL+'cjpm test success')
    elif change=='old-protocol':text=text.replace('NEXUS_SEQUENCE_V2|','NEXUS_SEQUENCE_V1|')
    elif change=='oversize':text=text.replace('|step0|String|s:|s:61','|step0|String|s:|s:'+'61'*257)
    elif change=='missing-step':text=NL.join(line for line in text.split(NL) if '|step1|' not in line)
    elif change=='later-step':text=text.replace('|step1|','|step2|')
    else:text=text.replace('NEXUS_SEQUENCE_END_V2|'+TOKEN+'|case0|4|COMPLETE','NEXUS_VALUE_ERROR_V2|'+TOKEN+'|case0|VALUE_LIMIT')
    r=sequence_trace.interpret(c,[t],TOKEN,text,0,None);assert r['state']=='UNKNOWN' and r['observations']==[] and r['failures']==[]


def test_v2_class_collision_ids_are_bound_to_the_same_actual_class():
    s=sig(name='NexusPropertiesV2'+TOKEN);identities=primitive_trace.case_ids(TOKEN,1,'single',version=2,signature=s)
    assert identities==['NexusPropertiesV2'+TOKEN+'Value.case0']
    r=primitive_trace.read(s,[['a']],TOKEN,'single',fixture('single',['s:61'],cls=identities[0].split('.')[0]),0,None,version=2)
    assert r['state']=='PASS' and r['observations'][0]['test_id']==identities[0]


def test_all_numeric_v1_harness_bytes_stay_frozen():
    want={'single-Int64':'dc654ddb01c3f3975938c8f07ef9aae35b4b4f28212ffa6eac57eb3bc106f00d','single-Bool':'32080677e8ca85742e67fe5ac19f729892aa793c28f11d5e610f0b61347822ab','relation-Int64':'a4fafe4e342b7ed4b7dfb51e69d28d16f4accf2a3845213b8a3193faac96adea','relation-Bool':'248b0fbb4f2f394d3032483b06ed48bd33a35dc0b127abca527ed6ada98a6350','sequence':'94ae780c550e6fd5aadff8b51d87a7c4f8e7f0a0b6d8aa66f25f4b4607b8f196'}
    for kind in ('single','relation'):
        for typ in ('Int64','Bool'):
            inputs=[[1],[2]] if typ=='Int64' else [[False],[True]]
            assert hashlib.sha256(primitive_trace.harness(old_signature(typ),inputs,'bench',TOKEN,kind)).hexdigest()==want[kind+'-'+typ]
    assert hashlib.sha256(sequence_trace.harness(old_sequence(),[trajectory()],'bench',TOKEN)).hexdigest()==want['sequence']


@pytest.mark.parametrize('decoder',['single','sequence'])
def test_v2_field_whitespace_is_not_silently_canonicalized(decoder):
    if decoder=='single':
        text=fixture('single',['s:61 '])
        assert primitive_trace.read(sig(),[['a']],TOKEN,'single',text,0,None,version=2)['state']=='UNKNOWN'
    else:
        c,t=model();text=sequence_fixture().replace('|String|s:|s:61'+NL,'|String|s:|s:61 '+NL)
        assert sequence_trace.interpret(c,[t],TOKEN,text,0,None)['state']=='UNKNOWN'


def test_string_property_success_keeps_actual_source_coordinates():
    c=properties.validate_contract(raw_property(),signature(),[]);text=fixture('single',[token('中:N')])
    result=property_trace.interpret(c,[['中',0]],TOKEN,text,0,None)
    assert result['state']=='PASS';source=result['observations'][0]['source']
    assert text[source['start_char']:source['end_char']].strip().startswith('NEXUS_PROPERTY_V2|')
