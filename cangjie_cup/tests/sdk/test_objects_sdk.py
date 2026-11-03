"""Actual V4 SDK observations, fixed self-built programs; no LLM/remote calls."""
import asyncio,json
from copy import deepcopy
import pytest
from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import oracle,primitive_trace,property_trace,relation_trace,sequence_trace,sequences,properties,relations
from nexus.uploads.language import inspect_source,literal
from tests.test_primitive_trace import TOKEN
from tests.test_object_contracts import state,signature,raw_property,raw_relation,sequence_raw
from tests.test_object_values import types

pytestmark=pytest.mark.sdk
NL=chr(10)


def declaration(kind='struct',name='OrderState'):
    return NL.join(['public '+kind+' '+name+' {','public let amount: Int64','public let label: String','public let active: Bool','public let items: Array<Int64>',
        'public init(amount: Int64, label: String, active: Bool, items: Array<Int64>) {','this.amount = amount','this.label = label','this.active = active','this.items = items','}',
        'public func net(): Int64 { this.amount }','}',''])


def execute(root,source,program,metadata,interpret,state,ids,*,exception=False,defensive=False):
    root=root.resolve();project=root/'project';(project/'src').mkdir(parents=True)
    if defensive:
        with pytest.raises(ValueError):inspect_source('package bench'+NL+source)
    else:
        info=inspect_source('package bench'+NL+source);sig=metadata.get('signature',metadata.get('contract',{}).get('signature'))
        selected=next(f for f in info['functions'] if f['name']==sig['name']);assert oracle.stable_signature(selected)==oracle.stable_signature(sig)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench'+NL+source);(project/'src/object_observations_test.cj').write_bytes(program)
    before=source_manifest(project);commands=[]
    (root/'verification-input.json').write_text(json.dumps(dict(**metadata,token=TOKEN,package='bench',project_manifest=before,defensive_gate_bypass_fixture=defensive,expected_exception=exception),ensure_ascii=True,indent=2))
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands));(root/'sdk.log').write_text(log)
    result=interpret(log,code,problem);parsed=parse_test_report(log)
    (root/'verification-result.json').write_text(json.dumps(dict(result=result,exit_code=code,problem=problem,execution_argv=commands),ensure_ascii=True,indent=2))
    assert problem is None,(problem,log[-6000:])
    if exception:assert code!=0 and parsed.state=='UNKNOWN' and result['state']=='UNKNOWN',(result,log[-6000:])
    else:assert code==0 and parsed.state=='PASS',(result,log[-6000:])
    assert set(parsed.case_results)==set(ids),(parsed.case_results,ids,log[-6000:])
    assert result['state']==state,(result,log[-6000:])
    assert source_manifest(project)==before and commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    return result


@pytest.mark.parametrize('kind,name,type_name',[
 ('struct','identity','OrderState'),('class','case0','OrderState'),('class','identity','case0'),
 ('class','__nexusObserved','NexusPropertiesV4'+TOKEN),
 ('struct','__nexusV4Bound'+TOKEN,'__nexusObjectEncode'+TOKEN),
 ('class','__nexusPrint'+TOKEN,'__nexusObjectValue'),
])
def test_sdk_v4_object_roundtrip_fields_and_generated_name_collisions(tmp_path,kind,name,type_name):
    t=types();t[type_name]=t.pop('OrderState');t[type_name]['kind']=kind;parameter='__nexusPrint'+TOKEN
    sig=dict(name=name,params=[dict(name=parameter,type=type_name)],return_type=type_name,types=t)
    inputs=[]
    for amount,items,label,active in [(0,[],'',False),(-(1<<63),[-(1<<63),(1<<63)-1],'中\x00\n"|NEXUS_SEQUENCE_V4|',True),((1<<63)-1,[-(1<<63)]*16,'😀',True)]:
        value=state(amount);value['$type']=type_name;value['fields'].update(items=items,label=label,active=active);inputs.append([value])
    source=declaration(kind,type_name)+'public func '+name+'('+parameter+': '+type_name+'): '+type_name+' { '+parameter+' }'+NL
    r=execute(tmp_path,source,primitive_trace.harness(sig,inputs,'bench',TOKEN,'single',4),dict(kind='primitive',protocol_kind='single',signature=sig,inputs=inputs),lambda log,code,problem:primitive_trace.read(sig,inputs,TOKEN,'single',log,code,problem,4),'PASS',primitive_trace.case_ids(TOKEN,len(inputs),'single',4,sig))
    assert [o['actual_return'] for o in r['observations']]==[row[0] for row in inputs]


@pytest.mark.parametrize('kind',['single','relation'])
def test_sdk_v4_properties_and_relations_report_real_object_business_failure(tmp_path,kind):
    if kind=='single':
        c=properties.validate_contract(raw_property(),signature(),[]);inputs=[[state(0),1]];source=declaration()+'public func adjust(state: OrderState, n: Int64): OrderState { state }'+NL
        program=property_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:property_trace.interpret(c,inputs,TOKEN,log,code,problem);count=1
    else:
        c=relations.validate_contract(raw_relation(),signature(),[])
        # Equal complete inputs require equal fields. Use differing inputs with an always-active relation to expose the defect.
        raw=raw_relation();raw['relations'][0]['precondition']='True';c=relations.validate_contract(raw,signature(),[])
        inputs=[dict(left=[state(0),0],right=[state(1),0])];source=declaration()+'public func adjust(state: OrderState, n: Int64): OrderState { state }'+NL
        program=relation_trace.harness(c,inputs,'bench',TOKEN);interpret=lambda log,code,problem:relation_trace.interpret(c,inputs,TOKEN,log,code,problem);count=2
    result=execute(tmp_path,source,program,dict(kind=kind,contract=c,inputs=inputs),interpret,'FAIL',primitive_trace.case_ids(TOKEN,count,kind,4,c['signature']));assert result['execution_state']=='PASS' and len(result['failures'])==1


@pytest.mark.parametrize('kind',['struct','class'])
@pytest.mark.parametrize('fixed',[False,True])
def test_sdk_v4_object_state_chains_actual_return_and_stops_first_mismatch(tmp_path,kind,fixed):
    raw,sig=sequence_raw();sig['types']['OrderState']['kind']=kind;c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state=state(0),context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(4)])
    source=declaration(kind)+NL.join(['public func advance(mode: Int64, state: OrderState, label: String): OrderState {',
        '' if fixed else 'if (state.amount == 1) { return state }',
        'return OrderState(1 - state.amount, state.label, state.active, state.items)','}',''])
    result=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS' if fixed else 'FAIL',[sequence_trace._class(sig,TOKEN,4)+'.case0'])
    assert result['observed_calls']==(4 if fixed else 2) and result['unexecuted_calls']==(0 if fixed else 2)
    steps=result['observations'][0]['steps'];assert all(steps[i]['before_state']==steps[i-1]['actual_return'] for i in range(1,len(steps)))


def test_sdk_v4_zero_argument_object_return_exact_2141_wire(tmp_path):
    name='T'*64;fields=[dict(name='f'+str(i),type='String') for i in range(4)];t={name:dict(kind='class',fields=fields,constructor=deepcopy(fields),methods=[])}
    value={'$type':name,'fields':{f['name']:'x'*256 for f in fields}};sig=dict(name='makeState',params=[],return_type=name,types=t)
    source=NL.join(['public class '+name+' {',*(('public let '+f['name']+': String') for f in fields),
        'public init('+', '.join(f['name']+': String' for f in fields)+') {',*('this.'+f['name']+' = '+f['name'] for f in fields),'}','}',
        'public func makeState(): '+name+' { '+literal(value,t)+' }',''])
    r=execute(tmp_path,source,primitive_trace.harness(sig,[[]],'bench',TOKEN,'oracle',4),dict(kind='primitive',protocol_kind='oracle',signature=sig,inputs=[[]]),lambda log,code,problem:primitive_trace.read(sig,[[]],TOKEN,'oracle',log,code,problem,4),'PASS',primitive_trace.case_ids(TOKEN,1,'oracle',4,sig));assert r['observations'][0]['actual_return']==value


@pytest.mark.parametrize('kind',['String','Array<Int64>'])
def test_sdk_v4_overlimit_object_fields_are_unknown_defense_fixture(tmp_path,kind):
    sig=dict(name='identity',params=[dict(name='x',type='OrderState')],return_type='OrderState',types=types());inputs=[[state()]]
    expression='OrderState(x.amount, "'+('x'*257)+'", x.active, x.items)' if kind=='String' else 'OrderState(x.amount, x.label, x.active, ['+', '.join('0' for _ in range(17))+'])'
    source=declaration()+'public func identity(x: OrderState): OrderState { '+expression+' }'+NL
    execute(tmp_path,source,primitive_trace.harness(sig,inputs,'bench',TOKEN,'single',4),dict(kind='primitive',protocol_kind='single',signature=sig,inputs=inputs),lambda log,code,problem:primitive_trace.read(sig,inputs,TOKEN,'single',log,code,problem,4),'UNKNOWN',primitive_trace.case_ids(TOKEN,1,'single',4,sig),defensive=True)


@pytest.mark.parametrize('fault',['overflow','index'])
def test_sdk_v4_runtime_object_field_errors_are_unknown(tmp_path,fault):
    sig=dict(name='identity',params=[dict(name='x',type='OrderState')],return_type='OrderState',types=types());value=state((1<<63)-1);inputs=[[value]]
    expression='x.amount + 1' if fault=='overflow' else 'x.items[0]';source=declaration()+'public func identity(x: OrderState): OrderState { OrderState('+expression+', x.label, x.active, x.items) }'+NL
    execute(tmp_path,source,primitive_trace.harness(sig,inputs,'bench',TOKEN,'single',4),dict(kind='primitive',protocol_kind='single',signature=sig,inputs=inputs),lambda log,code,problem:primitive_trace.read(sig,inputs,TOKEN,'single',log,code,problem,4),'UNKNOWN',primitive_trace.case_ids(TOKEN,1,'single',4,sig),exception=True)
