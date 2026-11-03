"""Independent rules must have deterministic domains and primitive semantics."""
import importlib
import importlib.util
import pytest

def api():
    assert importlib.util.find_spec('nexus.repair.oracle') is not None, 'independent rule engine missing'
    return importlib.import_module('nexus.repair.oracle')

def signature():
    return dict(name='shippingFee',params=[dict(name='weight',type='Int64'),dict(name='distance',type='Int64'),dict(name='express',type='Bool')],return_type='Int64')

def contract(**changes):
    value=dict(version=1,function='shippingFee',domains={'weight':dict(min=1,max=30000,points=[1000,1500]),'distance':dict(min=1,max=2000,points=[500]),'express':{}},expression='(800 + ceil_div(max(weight - 1000, 0), 500) * 200 + (300 if distance > 500 else 0)) * (150 if express else 100) // 100',seed=7,max_cases=96)
    return {**value,**changes}

def test_boundaries_boolean_combinations_and_reproducible_search():
    m=api();c=m.validate_contract(contract(),signature(),[])
    inputs=m.generate_inputs(c)
    assert inputs==m.generate_inputs(c) and 16<=len(inputs)<=96
    assert {1000,1001,1499,1500,1501}<={x[0] for x in inputs}
    assert {499,500,501}<={x[1] for x in inputs}
    assert {False,True}=={x[2] for x in inputs}
    assert m.expected(c,[1001,500,False])==1000
    assert m.expected(c,[1501,501,True])==2250

def test_expression_rejects_executable_and_unbounded_syntax():
    m=api()
    for expr in ["__import__('os')",'weight.real','[weight][0]','weight ** 1000000','sum(weight)','(x for x in weight)']:
        with pytest.raises(ValueError):m.validate_contract(contract(expression=expr),signature(),[])

def test_inconsistent_examples_types_domains_and_partial_oracles_are_rejected():
    m=api()
    with pytest.raises(ValueError,match='示例'):m.validate_contract(contract(),signature(),[dict(args=[1001,500,False],expected=800)])
    for changes in [dict(seed=True),dict(max_cases=10000),dict(domains={}),dict(expression='express + weight'),dict(expression='weight // (distance - 500)'),dict(expression='weight * 9223372036854775807')]:
        with pytest.raises(ValueError):m.validate_contract(contract(**changes),signature(),[])
    c=m.validate_contract(contract(),signature(),[])
    for args in [[True,1,False],[1,1,0],[0,1,False]]:
        with pytest.raises(ValueError):m.expected(c,args)

def test_signed_division_remainder_and_return_types_match_primitive_semantics():
    m=api();sig=dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64')
    raw=dict(version=1,function='f',domains={'x':dict(min=-8,max=8,points=[-7,7])},expression='x // 3',seed=0,max_cases=32)
    c=m.validate_contract(raw,sig,[])
    assert m.expected(c,[-7])==-2
    c=m.validate_contract({**raw,'expression':'x % 3'},sig,[])
    assert m.expected(c,[-7])==-1
    with pytest.raises(ValueError):m.validate_contract({**raw,'expression':'x > 0'},sig,[])

def test_shrink_is_domain_preserving_and_strictly_simplifies():
    m=api();c=m.validate_contract(contract(),signature(),[])
    original=[1001,501,True];items=m.shrink_inputs(c,original)
    assert items and len(items)<=32 and original not in items
    assert all(sum(abs(int(v)) for v in x)<sum(abs(int(v)) for v in original) for x in items)
    assert [1000,501,True] in items
    assert all(type(m.expected(c,x)) is int for x in items)

@pytest.mark.parametrize('expression',[[],{},None,42])
def test_malformed_expression_is_a_validation_error(expression):
    with pytest.raises(ValueError):api().validate_contract(contract(expression=expression),signature(),[])
def test_reserved_holdout_rows_never_enter_generation_or_shrinking():
    from nexus.repair.oracle import validate_contract,generate_inputs,shrink_inputs
    sig=dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64')
    raw=dict(version=2,function='f',domains={'x':dict(min=0,max=1000,points=[10])},expression='x',seed=7,max_cases=32,excluded_inputs=[[0],[1],[5],[10]])
    c=validate_contract(raw,sig,[]);sealed={tuple(x) for x in raw['excluded_inputs']}
    assert not sealed.intersection(map(tuple,generate_inputs(c)))
    for x in range(1001):assert not sealed.intersection(map(tuple,shrink_inputs(c,[x])))
    for excluded in ([[True]],[[1001]],[[0],[0]],[],[[i] for i in range(129)]):
        import pytest
        with pytest.raises(ValueError):validate_contract({**raw,'excluded_inputs':excluded},sig,[])


def test_reserved_input_is_rejected_before_any_probe_execution(tmp_path):
    import asyncio
    import pytest
    from nexus.store import RunStore
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.oracle import validate_contract
    sig=dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64')
    c=validate_contract(dict(version=2,function='f',domains={'x':dict(min=0,max=1000)},expression='x',seed=7,max_cases=32,excluded_inputs=[[5]]),sig,[])
    with pytest.raises(ValueError,match='保留'):asyncio.run(ExplorationService(RunStore(tmp_path/'run')).batch(tmp_path/'absent',c,[[5]],9999999999999,'shrink'))

