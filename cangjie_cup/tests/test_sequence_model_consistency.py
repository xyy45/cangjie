"""Review reproduction: operation labels cannot change a pure function's output."""
from copy import deepcopy
import pytest
from nexus.repair import sequences


def contract(kind='Int64'):
    sig=dict(name='step',params=[dict(name='state',type=kind)],return_type=kind)
    raw=dict(version=1,kind='sequence',function='step',state_param='state',domains={'state':{} if kind=='Bool' else dict(min=0,max=1)},initial_states=[False if kind=='Bool' else 0],initial_precondition='True',context_params=[],operations=[
        dict(id='OP-ZERO',text='归零',args=[],transition='False' if kind=='Bool' else '0'),
        dict(id='OP-ONE',text='置一',args=[],transition='True' if kind=='Bool' else '1')],
        invariants=[dict(id='INV-RANGE',text='模型范围',precondition='True',assertion='True')],seed=0,max_sequences=8,max_steps=2,excluded_inputs=[])
    return raw,sig


@pytest.mark.parametrize('kind',['Int64','Bool'])
def test_operation_ids_cannot_prescribe_different_outputs_for_same_visible_input(kind):
    raw,sig=contract(kind)
    with pytest.raises(ValueError,match='矛盾|不一致|冲突'):sequences.validate_contract(raw,sig,[])


def test_overlapping_domain_and_literal_operation_templates_must_agree():
    raw,sig=contract();sig['params'].append(dict(name='amount',type='Int64'));raw['domains']['amount']=dict(min=0,max=1)
    raw['operations'][0].update(args=[dict(domain='amount')],transition='state');raw['operations'][1].update(args=[0],transition='1')
    with pytest.raises(ValueError,match='矛盾|不一致|冲突'):sequences.validate_contract(raw,sig,[])


def test_different_but_equivalent_visible_transition_expressions_are_allowed():
    raw,sig=contract();raw['operations'][0]['transition']='state';raw['operations'][1]['transition']='arg0'
    checked=sequences.validate_contract(raw,sig,[]);assert len(sequences.generate_traces(checked)['traces'])>0


def test_reference_chain_checks_other_matching_operations_at_reachable_middle_state():
    raw,sig=contract();sig['params'].append(dict(name='operation',type='Int64'));raw['domains']['operation']=dict(min=0,max=1)
    raw['operations']=[dict(id='OP-SET',text='置一',args=[1],transition='1'),dict(id='OP-KEEP',text='保持',args=[0],transition='state')]
    checked=sequences.validate_contract(raw,sig,[])
    checked['operations'].append(dict(id='OP-ZERO',text='归零',args=[0],transition='0'))
    trace=dict(initial_state=0,context=[],steps=[dict(operation_id='OP-SET',args=[1]),dict(operation_id='OP-KEEP',args=[0])])
    with pytest.raises(ValueError,match='矛盾|不一致|冲突'):sequences.reference_trace(checked,trace)
