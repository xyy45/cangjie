"""Real fixed SDK V3 observations; no model, remote graph or native policy calls."""
import asyncio,json
from itertools import product
import pytest
from nexus.adapters.cangjie.report_parser import ANSI,parse_test_report
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import primitive_trace,property_trace,relation_trace,sequence_trace,sequences
from nexus.uploads.language import inspect_source
from tests.test_primitive_trace import TOKEN
from tests.test_array_trace import sig,model
from tests.test_array_contracts import signature,raw_property,raw_relation,sequence_raw
from nexus.repair import properties,relations

pytestmark=pytest.mark.sdk
NL=chr(10);LOW=-(1<<63);HIGH=(1<<63)-1


def execute(root,source,program,metadata,interpret,state,ids,*,exception=False,defensive=False):
    root=root.resolve();project=root/'project';(project/'src').mkdir(parents=True)
    if defensive:
        with pytest.raises(ValueError):inspect_source('package bench'+NL+source)
    else:inspect_source('package bench'+NL+source)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench'+NL+source);(project/'src/array_observations_test.cj').write_bytes(program)
    before=source_manifest(project);commands=[]
    (root/'verification-input.json').write_text(json.dumps(dict(**metadata,token=TOKEN,package='bench',project_manifest=before,defensive_gate_bypass_fixture=defensive,expected_exception=exception),ensure_ascii=True,indent=2))
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/'sdk.log').write_text(log);result=interpret(log,code,problem);parsed=parse_test_report(log)
    (root/'verification-result.json').write_text(json.dumps(dict(result=result,exit_code=code,problem=problem,execution_argv=commands),ensure_ascii=True,indent=2))
    assert problem is None,(problem,log[-6000:])
    if exception:assert code!=0 and parsed.state=='UNKNOWN' and result['state']=='UNKNOWN',(result,log[-6000:])
    else:assert code==0 and parsed.state=='PASS',(result,log[-6000:])
    assert set(parsed.case_results)==set(ids),(parsed.case_results,ids,log[-6000:])
    assert result['state']==state,(result,log[-6000:])
    assert source_manifest(project)==before and commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    return result


@pytest.mark.parametrize('name',['identity','case0','__nexusObserved','__nexusArrayEncode'+TOKEN,'__nexusV3Bound'+TOKEN,'__nexusPrint'+TOKEN,'NexusPropertiesV3'+TOKEN])
def test_sdk_v3_array_roundtrip_extremes_empty_and_name_collisions(tmp_path,name):
    s=sig(name=name);parameter='__nexusPrint'+TOKEN;s['params'][0]['name']=parameter
    cases=[[[]],[[LOW,HIGH]],[[LOW]*16],[[1,1,-1]]]
    source='public func '+name+'('+parameter+': Array<Int64>): Array<Int64> { '+parameter+' }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'single',version=3),dict(kind='primitive',protocol_kind='single',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'single',log,code,problem,version=3),'PASS',primitive_trace.case_ids(TOKEN,4,'single',3,s))
    assert [o['actual_return'] for o in r['observations']]==[row[0] for row in cases]
    text=ANSI.sub('',(tmp_path/'sdk.log').read_text())
    for item in r['observations']:
        source=item['source'];assert text[source['start_char']:source['end_char']].strip().startswith('NEXUS_PROPERTY_V3|')
    assert 'a:16:'+','.join([str(LOW)]*16) in text

@pytest.mark.parametrize('kind',['Int64','Bool','String'])
def test_sdk_v3_array_inputs_with_scalar_and_control_string_returns(tmp_path,kind):
    s=dict(name='selectValue',params=[dict(name='items',type='Array<Int64>'),dict(name='value',type=kind)],return_type=kind)
    if kind=='Bool':values=[False,True]
    elif kind=='Int64':values=[LOW,HIGH]
    else:values=['',chr(0)+NL+'NEXUS_SEQUENCE_END_V3|fake|case0|1|COMPLETE'+NL+'中😀${fake}']
    cases=[[[],v] for v in values];source='public func selectValue(items: Array<Int64>, value: '+kind+'): '+kind+' { value }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'single',version=3),dict(kind='primitive',protocol_kind='single',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'single',log,code,problem,version=3),'PASS',primitive_trace.case_ids(TOKEN,2,'single',3,s))
    assert [o['actual_return'] for o in r['observations']]==values


def test_sdk_v3_empty_array_return_without_parameters(tmp_path):
    s=dict(name='empty',params=[],return_type='Array<Int64>');cases=[[]];source='public func empty(): Array<Int64> { [] }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'single',version=3),dict(kind='primitive',protocol_kind='single',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'single',log,code,problem,version=3),'PASS',primitive_trace.case_ids(TOKEN,1,'single',3,s))
    assert r['observations'][0]['actual_return']==[]


def test_sdk_v3_oracle_executes_256_actual_cases(tmp_path):
    s=dict(name='counter',params=[dict(name='items',type='Array<Int64>'),dict(name='value',type='Int64')],return_type='Int64');cases=[[[],i] for i in range(256)];source='public func counter(items: Array<Int64>, value: Int64): Int64 { value }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'oracle',version=3),dict(kind='primitive',protocol_kind='oracle',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'oracle',log,code,problem,version=3),'PASS',primitive_trace.case_ids(TOKEN,256,'oracle',3,s))
    assert len(r['observations'])==256 and r['counts']['passed']==256


@pytest.mark.parametrize('kind',['array','string'])
def test_sdk_v3_return_limits_are_unknown_without_truncation(tmp_path,kind):
    s=sig();cases=[[[]]]
    if kind=='array':source='public func identity(x: Array<Int64>): Array<Int64> { ['+', '.join('0' for _ in range(17))+'] }'+NL
    else:s['return_type']='String';source='public func identity(x: Array<Int64>): String { "'+'a'*256+'" + "!" }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'single',version=3),dict(kind='primitive',protocol_kind='single',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'single',log,code,problem,version=3),'UNKNOWN',primitive_trace.case_ids(TOKEN,1,'single',3,s),defensive=kind=='array')
    assert r['execution_state']=='PASS' and r['observations']==[]
    assert 'NEXUS_VALUE_ERROR_V3|'+TOKEN+'|case0|VALUE_LIMIT' in (tmp_path/'sdk.log').read_text()


@pytest.mark.parametrize('issue',['overflow','index'])
def test_sdk_v3_actual_arithmetic_or_index_exception_remains_unknown(tmp_path,issue):
    s=sig('Int64');cases=[[[HIGH,1]]] if issue=='overflow' else [[[]]]
    source='public func identity(x: Array<Int64>): Int64 { var total: Int64 = 0; for (v in x) { total = total + v }; return total }'+NL if issue=='overflow' else 'public func identity(x: Array<Int64>): Int64 { x[0] }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(s,cases,'bench',TOKEN,'single',version=3),dict(kind='primitive',protocol_kind='single',signature=s,inputs=cases),lambda log,code,problem:primitive_trace.read(s,cases,TOKEN,'single',log,code,problem,version=3),'UNKNOWN',primitive_trace.case_ids(TOKEN,1,'single',3,s),exception=True)
    assert r['observations']==[]
    assert ('OverflowException' if issue=='overflow' else 'IndexOutOfBoundsException') in (tmp_path/'sdk.log').read_text()


@pytest.mark.parametrize('kind',['property','relation'])
def test_sdk_v3_business_predicates_use_actual_returns_from_array_calls(tmp_path,kind):
    if kind=='property':
        c=properties.validate_contract(raw_property(),signature(),[]);inputs=[[[1,2],1]];source='public func orderTotal(values: Array<Int64>, bonus: Int64): Int64 { bonus }'+NL
        program=property_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:property_trace.interpret(c,inputs,TOKEN,log,code,problem);ids=primitive_trace.case_ids(TOKEN,1,'single',3,c['signature'])
    else:
        c=relations.validate_contract(raw_relation(),signature(),[]);inputs=[dict(left=[[1,2],0],right=[[2,1],0])];source='public func orderTotal(values: Array<Int64>, bonus: Int64): Int64 { if (values.size == 0) { return bonus }; return values[0] + bonus }'+NL
        program=relation_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:relation_trace.interpret(c,inputs,TOKEN,log,code,problem);ids=primitive_trace.case_ids(TOKEN,2,'relation',3,c['signature'])
    r=execute(tmp_path,source,program,dict(kind=kind,contract=c,inputs=inputs),interpret,'FAIL',ids)
    assert r['execution_state']=='PASS' and len(r['failures'])==1


def rotation_source(fixed=True):
    return NL.join(['public func rotateState(op: Int64, current: Array<Int64>, label: String): Array<Int64> {',
        'if (op == 1) { return [] }','if (current.size == 2) {',
        '' if fixed else 'if (current[0] == 2) { return current }',
        'return [current[1], current[0]]','}','return current','}',''])


@pytest.mark.parametrize('fixed',[False,True])
def test_sdk_v3_array_state_chains_actual_return_and_stops_first_mismatch(tmp_path,fixed):
    c,trace=model();source=rotation_source(fixed)
    r=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS' if fixed else 'FAIL',[sequence_trace._class(c['signature'],TOKEN,3)+'.case0'])
    assert (r['planned_calls'],r['observed_calls'],r['unexecuted_calls'])==(4,4,0) if fixed else (r['planned_calls'],r['observed_calls'],r['unexecuted_calls'])==(4,2,2)
    steps=r['observations'][0]['steps'];assert [s['actual_return'] for s in steps]==([[2,1],[1,2],[],[]] if fixed else [[2,1],[2,1]])
    assert all(steps[i]['before_state']==steps[i-1]['actual_return'] for i in range(1,len(steps)))


def test_sdk_v3_128_actual_array_state_calls_preserve_counts(tmp_path):
    raw,s=sequence_raw();raw['max_steps']=8;c=sequences.validate_contract(raw,s,[]);traces=[]
    for ids in product(('OP-SWAP','OP-RESET'),repeat=8):
        traces.append(dict(initial_state=[1,2],context=['a'],steps=[dict(operation_id=i,args=[0 if i=='OP-SWAP' else 1,'a']) for i in ids]))
        if len(traces)==16:break
    r=execute(tmp_path,rotation_source(),sequence_trace.harness(c,traces,'bench',TOKEN),dict(kind='sequence',contract=c,inputs=traces),lambda log,code,problem:sequence_trace.interpret(c,traces,TOKEN,log,code,problem),'PASS',[sequence_trace._class(s,TOKEN,3)+'.case'+str(i) for i in range(16)])
    assert r['planned_calls']==r['observed_calls']==128 and r['unexecuted_calls']==0


@pytest.mark.parametrize('kind',['Bool','Int64'])
def test_sdk_v3_scalar_state_with_fixed_array_context(tmp_path,kind):
    initial=False if kind=='Bool' else 0;s=dict(name='advance',params=[dict(name='current',type=kind),dict(name='items',type='Array<Int64>')],return_type=kind)
    domain={} if kind=='Bool' else dict(min=0,max=4,points=[])
    transition='not state if array_len(arg1) > 0 else state' if kind=='Bool' else 'min(state + array_len(arg1), 4)'
    raw=dict(version=3,kind='sequence',function='advance',state_param='current',domains=dict(current=domain,items=dict(values=[[],[1,2]])),initial_states=[initial],initial_precondition='True',context_params=['items'],operations=[dict(id='OP-ADVANCE',text='数组固定上下文与显式状态',args=[{'context':'items'}],transition=transition)],invariants=[dict(id='INV-REFERENCE',text='实际等于参考',precondition='True',assertion='result == expected_state')],seed=0,max_sequences=16,max_steps=3,excluded_inputs=[])
    c=sequences.validate_contract(raw,s,[]);trace=dict(initial_state=initial,context=[[1,2]],steps=[dict(operation_id='OP-ADVANCE',args=[[1,2]]) for _ in range(3)])
    source='public func advance(current: Bool, items: Array<Int64>): Bool { if (items.size > 0) { return !current }; return current }'+NL if kind=='Bool' else NL.join(['public func advance(current: Int64, items: Array<Int64>): Int64 {','if (current + items.size > 4) { return 4 }','return current + items.size','}',''])
    r=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS',[sequence_trace._class(s,TOKEN,3)+'.case0'])
    assert [item['actual_return'] for item in r['observations'][0]['steps']]==([True,False,True] if kind=='Bool' else [2,4,4])
