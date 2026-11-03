"""Native axes must drive search without changing exclusion or shrinking rules."""
import pytest
from nexus.repair import oracle


def contract():
    return oracle.validate_contract(dict(version=2,function='f',domains={'x':dict(min=0,max=8,points=[3])},expression='x',seed=7,max_cases=32,excluded_inputs=[[5]]),
        dict(name='f',params=[dict(name='x',type='Int64')],return_type='Int64'),[])


def test_supplied_axes_are_used_without_mutation_or_reserved_input_leak():
    c=contract();axes=[[0,8,3,2,4,1,7]]
    items=oracle.generate_inputs(c,axes=axes)
    assert items[:7]==[[0],[8],[3],[2],[4],[1],[7]]
    assert [5] not in items
    assert [5] not in oracle.shrink_inputs(c,[8],axes=axes)
    assert axes==[[0,8,3,2,4,1,7]]


@pytest.mark.parametrize('axes', [[],[[False,8,3,2,4,1,7]],[[0,8,3]],[[0,8,3,2,4,1,7,7]],[[0,9,3,2,4,1,7]]])
def test_partial_wrong_type_duplicate_or_out_of_domain_axes_are_not_search_evidence(axes):
    c=contract()
    with pytest.raises(ValueError):oracle.generate_inputs(c,axes=axes)
    with pytest.raises(ValueError):oracle.shrink_inputs(c,[8],axes=axes)
