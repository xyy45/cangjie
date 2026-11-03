import pytest
from nexus.repair import values
from nexus.uploads.language import literal

LOW=-(1<<63);HIGH=(1<<63)-1

@pytest.mark.parametrize('array',[[],[0],[-1,0,1],[LOW,HIGH],[LOW]*16])
def test_bounded_arrays_are_copied_typed_values(array):
    result=values.primitive(array,'Array<Int64>')
    assert result==array and result is not array
    assert values.array(array)==array and values.array(array) is not array
    assert values.typed_key(array)==('Array<Int64>',tuple(array))
    assert values.primitive_weight(array)==len(array)+sum(abs(n) for n in array)
    assert literal(array)=='['+', '.join(str(n) for n in array)+']'
    assert values.has_arrays(dict(params=[dict(name='a',type='Array<Int64>')],return_type='Int64'))
    assert values.has_arrays(dict(params=[],return_type='Array<Int64>'))
    result.append(4);assert result!=array

@pytest.mark.parametrize('value',[None,True,0,'[]',(),[False],[1.0],['1'],[[1]],[LOW-1],[HIGH+1],[0]*17])
def test_arrays_reject_implicit_casts_nested_values_and_limits(value):
    with pytest.raises(ValueError):values.primitive(value,'Array<Int64>')

@pytest.mark.parametrize('value',[[False],[HIGH+1],[0]*17])
def test_array_source_literal_rejects_invalid_elements(value):
    with pytest.raises(ValueError):literal(value)

def test_old_primitive_semantics_and_signature_detection_are_preserved():
    assert values.typed_key(False)!=values.typed_key(0)
    assert values.typed_key('')!=values.typed_key([])
    assert not values.has_arrays(dict(params=[dict(name='s',type='String')],return_type='Bool'))
    assert literal(True)=='true' and literal(LOW)==str(LOW)
    assert literal('a')=='"\\u{61}"'
