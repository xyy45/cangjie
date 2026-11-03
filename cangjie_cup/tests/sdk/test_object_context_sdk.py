"""Additional real V4 scalar/array/string returns and object-valued context."""
import pytest
from nexus.repair import primitive_trace,sequence_trace,sequences
from tests.sdk.test_objects_sdk import execute,declaration
from tests.test_object_values import types
from tests.test_object_contracts import state
from tests.test_primitive_trace import TOKEN

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('kind,field',[('Int64','amount'),('Bool','active'),('String','label'),('Array<Int64>','items')])
def test_sdk_v4_object_input_returns_any_supported_leaf(tmp_path,kind,field):
    sig=dict(name='inspectState',params=[dict(name='x',type='OrderState')],return_type=kind,types=types());a=state(-(1<<63));a['fields'].update(active=False,label='中\x00\n|',items=[-(1<<63)]*16);inputs=[[a],[state(0)]]
    source=declaration()+'public func inspectState(x: OrderState): '+kind+' { x.'+field+' }\n'
    result=execute(tmp_path,source,primitive_trace.harness(sig,inputs,'bench',TOKEN,'single',4),dict(kind='primitive',protocol_kind='single',signature=sig,inputs=inputs),lambda log,code,problem:primitive_trace.read(sig,inputs,TOKEN,'single',log,code,problem,4),'PASS',primitive_trace.case_ids(TOKEN,2,'single',4,sig))
    assert [o['actual_return'] for o in result['observations']]==[a[0]['fields'][field] for a in inputs]


def test_sdk_v4_scalar_state_with_fixed_object_context(tmp_path):
    sig=dict(name='advance',params=[dict(name='current',type='Int64'),dict(name='context',type='OrderState')],return_type='Int64',types=types())
    raw=dict(version=4,kind='sequence',function='advance',state_param='current',domains=dict(current=dict(min=0,max=4,points=[]),context=dict(values=[state(1),state(2)])),initial_states=[0],initial_precondition='True',context_params=['context'],
        operations=[dict(id='OP-ADVANCE',text='按固定对象上下文递增并封顶',args=[{'context':'context'}],transition='min(state + object_get(arg1,"amount"), 4)')],
        invariants=[dict(id='INV-REFERENCE',text='等于参考状态',precondition='True',assertion='result == expected_state')],seed=0,max_sequences=8,max_steps=3,excluded_inputs=[])
    c=sequences.validate_contract(raw,sig,[]);trace=dict(initial_state=0,context=[state(2)],steps=[dict(operation_id='OP-ADVANCE',args=[state(2)]) for _ in range(3)])
    source=declaration()+'public func advance(current: Int64, context: OrderState): Int64 { if (current + context.amount > 4) { return 4 }; return current + context.amount }\n'
    result=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS',[sequence_trace._class(sig,TOKEN,4)+'.case0'])
    assert result['observed_calls']==3 and [s['actual_return'] for s in result['observations'][0]['steps']]==[2,4,4]


def test_sdk_v4_case0_type_can_be_constructed_as_sequence_initial_state(tmp_path):
    import json
    from tests.test_object_contracts import sequence_raw
    raw,sig=json.loads(json.dumps(sequence_raw()).replace('OrderState','case0'));sig['types']['case0']['kind']='class';c=sequences.validate_contract(raw,sig,[])
    initial=state(0);initial['$type']='case0';trace=dict(initial_state=initial,context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(3)])
    source=declaration('class','case0')+'public func advance(mode: Int64, state: case0, label: String): case0 { return case0(1 - state.amount, state.label, state.active, state.items) }\n'
    result=execute(tmp_path,source,sequence_trace.harness(c,[trace],'bench',TOKEN),dict(kind='sequence',contract=c,inputs=[trace]),lambda log,code,problem:sequence_trace.interpret(c,[trace],TOKEN,log,code,problem),'PASS',[sequence_trace._class(sig,TOKEN,4)+'.case0'])
    assert result['observed_calls']==3 and [s['actual_return']['fields']['amount'] for s in result['observations'][0]['steps']]==[1,0,1]
