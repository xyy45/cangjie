from copy import deepcopy
from itertools import product
import pytest
from nexus.repair import oracle,relations,sequences,values
from tests.test_string_contracts import signature,raw_oracle,raw_relation,sequence_raw


def test_string_and_full_int64_domain_search_remains_budgeted_and_deterministic():
    raw=raw_oracle();raw['expression']='code';raw['domains']['qty']=dict(min=oracle.LOW,max=oracle.HIGH,points=[0]);c=oracle.validate_contract(raw,signature(),[])
    inputs=oracle.generate_inputs(c);assert inputs==oracle.generate_inputs(c) and 1<=len(inputs)<=16
    assert {row[0] for row in inputs}=={'','a','中'}
    assert all(type(row[0]) is str and type(row[1]) is int for row in inputs)
    bad=oracle.checked_axes(c);bad[0][0]=False
    with pytest.raises(ValueError):oracle.checked_axes(c,bad)


def test_string_shrink_only_uses_confirmed_values_and_strictly_less_weight():
    raw=raw_oracle();raw['domains']['code']['values']=['abc','ab','','中'];raw['expression']='code';c=oracle.validate_contract(raw,signature(),[])
    original=['abc',2];items=oracle.shrink_inputs(c,original)
    score=lambda args:sum(values.primitive_weight(v) for v in args)
    assert ['',2] in items and ['ab',2] in items
    assert all(row[0] in raw['domains']['code']['values'] and score(row)<score(original) for row in items)
    assert all(row[0]!='a' for row in items)


def test_string_pairs_retain_typed_exclusion_and_can_shrink_both_sides():
    c=relations.validate_contract(raw_relation(),signature(),[]);pair=dict(left=['a',2],right=['中',2]);original=relations.pair_score(pair)
    shrunk=relations.shrink_pairs(c,pair,'REL-DISTINCT');assert shrunk
    assert all(relations.pair_score(p)<original for p in shrunk)
    generated=relations.generate_pairs(c);assert generated==relations.generate_pairs(c) and len(generated['pairs'])<=16
    assert generated['candidate_checks']<=8192


def test_string_sequence_history_nine_prefixes_is_not_reduced_to_eight():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[]);history=[]
    for depth in (1,2,3,4):
        for ids in product(('OP-APPEND','OP-RESET'),repeat=depth):
            history.append(dict(initial_state='a',context=['a'],steps=[dict(operation_id=i,args=[0 if i=='OP-APPEND' else 1,'a']) for i in ids]))
    history=history[:9];result=sequences.generate_traces(c,cumulative=history)
    assert result['regression_traces']==9 and result['traces'][:9]==history and result['candidate_checks']<=8192
    raw['max_sequences']=8;c=sequences.validate_contract(raw,sig,[])
    with pytest.raises(ValueError):sequences.generate_traces(c,cumulative=history)


def test_string_sequence_shrink_stays_reachable_from_confirmed_initial_state():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state='a',context=['a'],steps=[dict(operation_id='OP-APPEND',args=[0,'a']) for _ in range(4)])
    items=sequences.shrink_traces(c,trace,'MODEL-OP-APPEND');assert items
    assert all(sequences.trace_score(t)<sequences.trace_score(trace) and t['initial_state'] in c['initial_states'] and sequences.reference_trace(c,t)['eligible'] for t in items)
    assert sequences.trace_key(dict(initial_state='',context=['a'],steps=[dict(operation_id='OP-APPEND',args=[0,'a'])]))
