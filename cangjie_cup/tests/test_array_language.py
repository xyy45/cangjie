import pytest
from nexus.uploads.language import inspect_source,validate_candidate,validate_examples

@pytest.mark.parametrize('source',[
 'func echo(x: Array<Int64>): Array<Int64> { x }',
 'func empty(): Array<Int64> { [] }',
 'func size(x: Array<Int64>): Int64 { x.size }',
 'func first(x: Array<Int64>, i: Int64): Int64 { x[i] }',
 'func first(): Int64 { [1, 2][0] }',
 'func build(x: Int64): Array<Int64> { [x, -1, x + 1] }',
 'func same(a: Array<Int64>, b: Array<Int64>): Bool { a == b }',
 'func sum(x: Array<Int64>): Int64 { var total: Int64 = 0; for (value in x) { total = total + value }; return total }',
 'func sum(x: Array<Int64>): Int64 { var total = 0; var i = 0; while (i < x.size) { total = total + x[i]; i = i + 1 }; return total }',
 'func copy(x: Array<Int64>, label: String, enabled: Bool): Array<Int64> { var y: Array<Int64> = []; if (enabled && label != "") { y = x }; return y }',
 'func sum(x: Array<Int64>): Int64 { var total = 0; for (v in x) { if (v < 0) { continue }; total = total + v }; return total }',
])
def test_readonly_array_functions_and_loops_are_indexed(source):
    info=inspect_source(source);assert len(info['functions'])==1 and info['functions'][0]['calls']==[]

@pytest.mark.parametrize('body',[
 'x[0] = 1; return x', 'let y = x; y[0] = 1; return y',
 'x.clone()', 'x.append(1)', 'x.toArray()', 'x.size()', 'Array<Int64>([])',
 'x + x', 'x < x', 'x == 1', 'x[true]', 'x["0"]', 'x[0:1]', 'x[0][0]',
 'x.size.size', '[true]', '["x"]', '[[1]]', '['+','.join('0' for _ in range(17))+']',
 'for (v in "text") { v }; return x', 'for (v in x) { v }; return [v]',
 'for (x in x) { x }; return x',
])
def test_array_subset_rejects_mutation_general_api_and_bad_types(body):
    with pytest.raises(ValueError):inspect_source('func f(x: Array<Int64>): Array<Int64> { '+body+' }')

@pytest.mark.parametrize('kind',['Array<Bool>','Array<String>','Array<Array<Int64>>','Array','Array<Int32>'])
def test_only_single_dimension_int64_array_type_is_permitted(kind):
    with pytest.raises(ValueError):inspect_source('func f(x: '+kind+'): '+kind+' { x }')

def test_array_function_interface_callgraph_and_examples_remain_frozen():
    source='func echo(x: Array<Int64>): Array<Int64> { x }\nfunc other(y: Array<Int64>): Array<Int64> { echo(y) }'
    info=inspect_source(source)
    assert info['functions'][0]['params']==[dict(name='x',type='Array<Int64>')]
    assert [c['name'] for c in info['functions'][1]['calls']]==['echo']
    validate_candidate(source.replace('{ x }','{ [] }'),info)
    with pytest.raises(ValueError):validate_candidate(source.replace('x: Array<Int64>','x: Int64'),info)
    good=[dict(args=[[]],expected=[],suite='target'),dict(args=[[1,-2]],expected=[1,-2],suite='regression')]
    assert validate_examples(info,'echo',good)==good
    for changed in (dict(args=[[True]]),dict(expected=[0]*17),dict(args=[[1],[]]),dict(expected=None)):
        with pytest.raises(ValueError):validate_examples(info,'echo',[{**good[0],**changed},good[1]])

def test_loop_element_cannot_shadow_or_leak_but_name_can_be_reused_after_loop():
    source='func f(x: Array<Int64>): Int64 { var total = 0; for (v in x) { total = total + v }; let v = 1; return total + v }'
    assert inspect_source(source)['functions'][0]['return_type']=='Int64'
