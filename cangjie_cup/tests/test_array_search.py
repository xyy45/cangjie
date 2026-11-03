from itertools import product
import pytest
from nexus.repair import oracle,relations,sequences,values
from tests.test_array_contracts import signature,raw_oracle,raw_relation,sequence_raw


def test_array_search_is_typed_budgeted_deterministic_and_has_no_mutable_alias():
    raw=raw_oracle();raw['expression']='array_len(values)';raw['domains']['bonus']=dict(min=oracle.LOW,max=oracle.HIGH,points=[0]);c=oracle.validate_contract(raw,signature(),[])
    rows=oracle.generate_inputs(c);assert rows==oracle.generate_inputs(c) and len(rows)<=16
    keys={oracle.input_key(row) for row in rows};assert len(keys)==len(rows)
    assert oracle.input_key([[0],False])!=oracle.input_key([[0],0])
    with pytest.raises(ValueError):oracle.input_key([[True],0])
    axes=oracle.checked_axes(c);axes[0][0].append(99);assert c['domains']['values']['values'][0]==[]
    first=rows[0][0];first.append(99);assert c['domains']['values']['values'][0]==[]
    assert all(row[0] is not first for row in rows[1:])


def test_array_shrink_uses_only_domain_values_and_respects_reserved_inputs():
    raw=raw_oracle();raw['excluded_inputs']=[[[],2]];c=oracle.validate_contract(raw,signature(),[])
    original=[[1,2],2];rows=oracle.shrink_inputs(c,original);score=lambda row:sum(values.primitive_weight(v) for v in row)
    assert rows and all(row[0] in c['domains']['values']['values'] and score(row)<score(original) for row in rows)
    assert [[],2] not in rows and oracle.permitted_input(c,[[],2]) is False
    assert all(row[0]!=[2] for row in rows)


def test_nested_native_axes_reject_bool_integer_equivalence_and_order_change():
    c=oracle.validate_contract(raw_oracle(),signature(),[]);axes=oracle.checked_axes(c)
    axes[0][1]=[True]
    with pytest.raises(ValueError):oracle.checked_axes(c,axes)
    axes=oracle.checked_axes(c);axes[0].reverse()
    with pytest.raises(ValueError):oracle.checked_axes(c,axes)


def test_array_pairs_shrink_both_sides_and_preserve_history_without_alias():
    c=relations.validate_contract(raw_relation(),signature(),[]);pair=dict(left=[[1,2],2],right=[[2,1],2]);score=relations.pair_score(pair)
    shrunk=relations.shrink_pairs(c,pair,'REL-PERMUTATION');assert shrunk and all(relations.pair_score(p)<score for p in shrunk)
    result=relations.generate_pairs(c,cumulative=[pair]);assert result['regression_pairs']==1 and result['pairs'][0]==pair
    result['pairs'][0]['left'][0].append(99);assert pair['left'][0]==[1,2]


def test_array_sequence_history_nine_prefixes_and_reachable_shrink():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[]);history=[]
    for depth in (1,2,3,4):
        for ids in product(('OP-SWAP','OP-RESET'),repeat=depth):
            history.append(dict(initial_state=[1,2],context=['a'],steps=[dict(operation_id=i,args=[0 if i=='OP-SWAP' else 1,'a']) for i in ids]))
    history=history[:9];result=sequences.generate_traces(c,cumulative=history)
    assert result['regression_traces']==9 and result['traces'][:9]==history and result['candidate_checks']<=8192
    shrunk=sequences.shrink_traces(c,history[-1],'MODEL-OP-SWAP');assert shrunk
    assert all(sequences.trace_score(t)<sequences.trace_score(history[-1]) and sequences.reference_trace(c,t)['eligible'] for t in shrunk)
    raw['max_sequences']=8;c=sequences.validate_contract(raw,sig,[])
    with pytest.raises(ValueError):sequences.generate_traces(c,cumulative=history)



def test_array_shrink_results_cannot_mutate_confirmed_initial_state():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state=[1,2],context=['中'],steps=[dict(operation_id='OP-SWAP',args=[0,'中'])])
    smaller=sequences.shrink_traces(c,trace,'MODEL-OP-SWAP');assert smaller
    for item in smaller:item['initial_state'].append(99)
    assert c['initial_states']==[[],[1,2]]
    assert trace['initial_state']==[1,2]
