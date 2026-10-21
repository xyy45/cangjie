import pytest

SOURCE='''package calculator
public func bounded(value: Int64, lower: Int64, upper: Int64): Int64 {
    if (value < lower) { return lower }
    if (value > upper) { return upper }
    return value
}
func total(count: Int64): Int64 {
    var i: Int64 = 0
    var sum: Int64 = 0
    while (i < count) {
        sum = sum + bounded(i, 0, 10)
        i = i + 1
    }
    return sum
}
'''


def test_restricted_functions_preserve_signatures_and_allow_local_control_flow():
    from nexus.uploads.language import inspect_source
    result=inspect_source(SOURCE)
    assert result['package']=='calculator'
    assert result['functions'][0]['name']=='bounded'
    assert result['functions'][0]['params']==[{'name':'value','type':'Int64'},{'name':'lower','type':'Int64'},{'name':'upper','type':'Int64'}]
    assert result['functions'][1]['return_type']=='Int64'


@pytest.mark.parametrize('source',[
 'import std.fs.*\nfunc f(): Int64 { 1 }',
 'func f(): Int64 { File.readFrom("/tmp/secret") }',
 'func f(): Int64 { execute(1) }',
 'func f(): Int64 { Int64(1) }',
 'let value = 1\nfunc f(): Int64 { value }',
 '@Test\nfunc f(): Int64 { 1 }',
 'class A {}\nfunc f(): Int64 { 1 }',
 'func f(): String { "hello" }',
 'func f(): Int64 { let p = unsafe { 1 }; p }',
 'func f(): Int64 { f(1) }',
 'func main(): Int64 { 1 }',
 'func f(): Int64 { std.process.execute(1) }',
 'func f(): Int64 { /* missing comment ',
 'func f(): Int64 { 1 } garbage',
 '//comment\rimport std.fs.*\nfunc f(): Int64 { 1 }',
 'func f(): Int64 { //comment\u2028println(1)\n 1 }',
 '/* outer /* nested */ hidden */ func f(): Int64 { 1 }',
 'func print(x: Bool): Int64 { 1 } func f(): Int64 { print(123); 1 }',
 'func helper(x: Bool): Int64 { 1 } func f(): Int64 { helper(123) }',
 'func helper(x: Int64): Int64 { x } func f(): Int64 { helper(true) }',
])
def test_outside_subset_is_rejected_before_any_compilation(source):
    from nexus.uploads.language import inspect_source
    with pytest.raises(ValueError):inspect_source(source)


def test_comments_cannot_hide_external_calls_and_candidates_cannot_change_interface():
    from nexus.uploads.language import inspect_source,validate_candidate
    info=inspect_source(SOURCE)
    validate_candidate(SOURCE.replace('i < count','i <= count'),info)
    with pytest.raises(ValueError):validate_candidate(SOURCE.replace('count: Int64','count: Bool'),info)
    with pytest.raises(ValueError):validate_candidate(SOURCE.replace('return sum','return /* harmless */ read(1)'),info)


def test_examples_are_data_not_code_and_primitive_types_are_strict():
    from nexus.uploads.language import inspect_source,validate_examples
    info=inspect_source(SOURCE)
    tests=[{'args':[1,0,10],'expected':1,'suite':'target'},{'args':[-1,0,10],'expected':0,'suite':'regression'}]
    assert validate_examples(info,'bounded',tests)==tests
    for bad in ([{**tests[0],'args':[True,0,10]},tests[1]],
                [{**tests[0],'expected':'1); evil()'},tests[1]],
                [tests[0]], [{**tests[0],'args':[1<<63,0,10]},tests[1]]):
        with pytest.raises(ValueError):validate_examples(info,'bounded',bad)
