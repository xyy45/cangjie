"""Genuine fixed SDK V2 String observations; no model or remote analysis."""
import asyncio
import json
import pytest
from nexus.adapters.cangjie.report_parser import ANSI,parse_test_report
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import primitive_trace,property_trace,relation_trace,sequence_trace,properties,relations,sequences
from nexus.uploads.language import inspect_source
from tests.test_primitive_trace import TOKEN
from tests.test_string_contracts import signature,raw_property,raw_relation,sequence_raw
from tests.test_string_trace import sig,model

pytestmark=pytest.mark.sdk
NL=chr(10)


def execute(root,source,program,metadata,interpret,expected,ids):
    root=root.resolve();project=root/'project';(project/'src').mkdir(parents=True)
    inspect_source('package bench'+NL+source)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench'+NL+source)
    (project/'src/string_observations_test.cj').write_bytes(program)
    before=source_manifest(project);commands=[]
    (root/'verification-input.json').write_text(json.dumps(dict(**metadata,token=TOKEN,package='bench',project_manifest=before),ensure_ascii=True,indent=2))
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/'sdk.log').write_text(log);result=interpret(log,code,problem);parsed=parse_test_report(log)
    record=dict(result=result,exit_code=code,problem=problem,execution_argv=commands)
    (root/'verification-result.json').write_text(json.dumps(record,ensure_ascii=True,indent=2))
    assert code==0 and problem is None and parsed.state=='PASS',(record,log[-6000:])
    assert set(parsed.case_results)==set(ids),(parsed.case_results,ids)
    assert result['state']==expected,(result,log[-6000:])
    assert source_manifest(project)==before
    assert commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    return result


@pytest.mark.parametrize('name',['identity','case0','__nexusObserved','__nexusStringEncode'+TOKEN,'NexusPropertiesV2'+TOKEN,'__nexusV2Bound'+TOKEN,'__nexusPrint'+TOKEN])
def test_sdk_v2_string_roundtrip_and_generated_name_collisions(tmp_path,name):
    signature=sig(name=name);parameter='__nexusPrint'+TOKEN;signature['params'][0]['name']=parameter
    control=chr(0)+NL+'NEXUS_SEQUENCE_END_V2|fake|case0|1|COMPLETE'+NL+'Summary: TOTAL: 1'+NL+'中😀"'+chr(92)+'${fake}'
    cases=[[''],[control],['x'*256],['中'*85+'x']]
    source='public func '+name+'('+parameter+': String): String { '+parameter+' }'+NL
    program=primitive_trace.harness(signature,cases,'bench',TOKEN,'single',version=2)
    r=execute(tmp_path,source,program,dict(kind='primitive',protocol_kind='single',signature=signature,inputs=cases),lambda log,code,problem:primitive_trace.read(signature,cases,TOKEN,'single',log,code,problem,version=2),'PASS',primitive_trace.case_ids(TOKEN,len(cases),'single',2,signature))
    assert [o['actual_return'] for o in r['observations']]==[row[0] for row in cases]
    for item in r['observations']:
        source=item['source'];assert source['coordinate']=='ANSI_STRIPPED_FULL_LOG'
        log=ANSI.sub('',(tmp_path/'sdk.log').read_text());assert log[source['start_char']:source['end_char']].strip().startswith('NEXUS_PROPERTY_V2|')


@pytest.mark.parametrize('kind',['Bool','Int64'])
def test_sdk_v2_string_parameters_with_scalar_results(tmp_path,kind):
    signature=dict(name='scalar',params=[dict(name='text',type='String'),dict(name='value',type=kind)],return_type=kind)
    cases=[['中',False],['',True]] if kind=='Bool' else [['中',-(1<<63)],['',(1<<63)-1]]
    source='public func scalar(text: String, value: '+kind+'): '+kind+' { value }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(signature,cases,'bench',TOKEN,'single',version=2),dict(kind='primitive',protocol_kind='single',signature=signature,inputs=cases),lambda log,code,problem:primitive_trace.read(signature,cases,TOKEN,'single',log,code,problem,version=2),'PASS',primitive_trace.case_ids(TOKEN,2,'single',2,signature))
    assert [o['actual_return'] for o in r['observations']]==[row[1] for row in cases]


def test_sdk_v2_overlong_return_is_unknown_without_truncating_other_cases(tmp_path):
    signature=sig();cases=[['ok'],['x'*256]];source='public func identity(x: String): String { x + "!" }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(signature,cases,'bench',TOKEN,'single',version=2),dict(kind='primitive',protocol_kind='single',signature=signature,inputs=cases),lambda log,code,problem:primitive_trace.read(signature,cases,TOKEN,'single',log,code,problem,version=2),'UNKNOWN',primitive_trace.case_ids(TOKEN,2,'single',2,signature))
    assert r['observations']==[] and r['execution_state']=='PASS'
    assert 'NEXUS_VALUE_ERROR_V2|'+TOKEN+'|case1|VALUE_LIMIT' in (tmp_path/'sdk.log').read_text()


def test_sdk_v2_oracle_executes_all_256_real_cases(tmp_path):
    signature=dict(name='oracleEcho',params=[dict(name='text',type='String'),dict(name='count',type='Int64')],return_type='String')
    cases=[['',i] for i in range(256)];source='public func oracleEcho(text: String, count: Int64): String { text }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(signature,cases,'bench',TOKEN,'oracle',version=2),dict(kind='primitive',protocol_kind='oracle',signature=signature,inputs=cases),lambda log,code,problem:primitive_trace.read(signature,cases,TOKEN,'oracle',log,code,problem,version=2),'PASS',primitive_trace.case_ids(TOKEN,256,'oracle',2,signature))
    assert len(r['observations'])==256 and r['counts']['passed']==256 and r['observations'][-1]['test_id'].endswith('.case255')


@pytest.mark.parametrize('kind',['property','relation'])
def test_sdk_string_business_judgment_requires_actual_single_or_both_returns(tmp_path,kind):
    if kind=='property':
        c=properties.validate_contract(raw_property(),signature(),[]);inputs=[['中',0]];source='public func ticket(code: String, qty: Int64): String { "" }'+NL
        program=property_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:property_trace.interpret(c,inputs,TOKEN,log,code,problem)
        ids=primitive_trace.case_ids(TOKEN,1,'single',2,c['signature'])
    else:
        c=relations.validate_contract(raw_relation(),signature(),[]);inputs=[dict(left=['a',0],right=['中',0])];source='public func ticket(code: String, qty: Int64): String { "collision" }'+NL
        program=relation_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:relation_trace.interpret(c,inputs,TOKEN,log,code,problem)
        ids=primitive_trace.case_ids(TOKEN,2,'relation',2,c['signature'])
    r=execute(tmp_path,source,program,dict(kind=kind,contract=c,inputs=inputs),interpret,'FAIL',ids)
    assert len(r['failures'])==1 and r['execution_state']=='PASS'
    if kind=='relation':assert r['failures'][0]['left_actual_return']==r['failures'][0]['right_actual_return']=='collision'
    else:assert r['failures'][0]['actual_return']=='' and r['observations'][0]['source']


@pytest.mark.parametrize('fixed',[False,True])
def test_sdk_string_sequence_uses_real_previous_return_and_stops_mismatch(tmp_path,fixed):
    c,trace=model();source=NL.join(['public func appendState(op: Int64, current: String, label: String): String {','if (op == 1) { return "" }','if (current.size < 3) { return current + label }','return current','}',''])
    if not fixed:source=source.replace('current.size < 3','current.size < 1')
    r=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS' if fixed else 'FAIL',[sequence_trace._class(c['signature'],TOKEN,2)+'.case0'])
    assert r['planned_calls']==4 and r['observed_calls']==(4 if fixed else 2)
    steps=r['observations'][0]['steps'];assert [s['actual_return'] for s in steps]==(['a','aa','aaa',''] if fixed else ['a','a'])
    assert all(steps[i]['before_state']==steps[i-1]['actual_return'] for i in range(1,len(steps)))
    assert len({s['test_id'] for s in steps})==1
    if not fixed:assert r['unexecuted_calls']==2 and 'MODEL-OP-APPEND' in r['failures'][0]['failure_ids']


def test_sdk_128_string_sequence_calls_preserve_plan_and_real_observations(tmp_path):
    raw,s=sequence_raw();raw['max_steps']=8;c=sequences.validate_contract(raw,s,[]);traces=sequences.generate_traces(c)['traces']
    # Select 16 distinct length8 paths, all from confirmed initial states.
    from itertools import product
    traces=[]
    for ids in product(('OP-APPEND','OP-RESET'),repeat=8):
        traces.append(dict(initial_state='',context=['a'],steps=[dict(operation_id=i,args=[0 if i=='OP-APPEND' else 1,'a']) for i in ids]))
        if len(traces)==16:break
    source=NL.join(['public func appendState(op: Int64, current: String, label: String): String {','if (op == 1) { return "" }','if (current.size < 3) { return current + label }','return current','}',''])
    r=execute(tmp_path,source,sequence_trace.harness(c,traces,'bench',TOKEN),dict(kind='sequence',contract=c,inputs=traces),lambda log,code,problem:sequence_trace.interpret(c,traces,TOKEN,log,code,problem),'PASS',[sequence_trace._class(s,TOKEN,2)+'.case'+str(i) for i in range(16)])
    assert r['planned_calls']==r['observed_calls']==128 and r['unexecuted_calls']==0


@pytest.mark.parametrize('state_type',['Bool','Int64'])
def test_sdk_v2_scalar_state_with_string_fixed_context(tmp_path,state_type):
    initial=False if state_type=='Bool' else 0
    s=dict(name='advance',params=[dict(name='current',type=state_type),dict(name='label',type='String')],return_type=state_type)
    domain={} if state_type=='Bool' else dict(min=0,max=2,points=[])
    transition='not state if arg1 != "" else state' if state_type=='Bool' else 'min(state + 1, 2)'
    raw=dict(version=2,kind='sequence',function='advance',state_param='current',domains=dict(current=domain,label=dict(values=['中'])),initial_states=[initial],initial_precondition='True',context_params=['label'],operations=[dict(id='OP-ADVANCE',text='String上下文和原始状态',args=[{'context':'label'}],transition=transition)],invariants=[dict(id='INV-REFERENCE',text='匹配显式模型',precondition='True',assertion='result == expected_state')],seed=0,max_sequences=16,max_steps=3,excluded_inputs=[])
    c=sequences.validate_contract(raw,s,[]);trace=dict(initial_state=initial,context=['中'],steps=[dict(operation_id='OP-ADVANCE',args=['中']) for _ in range(3)])
    source='public func advance(current: Bool, label: String): Bool { if (label != "") { return !current }; return current }'+NL if state_type=='Bool' else NL.join(['public func advance(current: Int64, label: String): Int64 {','if (current < 2) { return current + 1 }','return current','}',''])
    r=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS',[sequence_trace._class(s,TOKEN,2)+'.case0'])
    assert [x['actual_return'] for x in r['observations'][0]['steps']]==([True,False,True] if state_type=='Bool' else [1,2,2])
    assert r['observed_calls']==3
