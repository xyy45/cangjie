import pytest
from nexus.uploads.language import inspect_source,validate_candidate,validate_examples,literal


@pytest.mark.parametrize('source',[
 'func echo(x: String): String { x }',
 'func empty(x: String): Bool { x == "" }',
 'func bytes(x: String): Int64 { x.size }',
 'func runes(x: String): Int64 { x.toRuneArray().size }',
 'func both(a: String, b: String, count: Int64, enabled: Bool): String { if (enabled && count > 0) { return a + b }; return "" }',
 'func text(): String { "(){}// /* not code */" }',
 'func size(x: String): Int64 { (x + "中").size }',
 'func label(x: String): String { var y: String = ""; var i = 0; while (i < 2) { y = y + x; i = i + 1 }; return y }',
])
def test_safe_string_functions_are_indexed(source):
    info=inspect_source(source);assert len(info['functions'])==1
    assert info['functions'][0]['calls']==[]


def test_string_literals_cannot_forge_calls_or_change_candidate_interface():
    source='func inner(x: String): String { x }\nfunc outer(x: String): String { inner(x) + "fake(1)//" }'
    info=inspect_source(source);assert [x['name'] for x in info['functions'][1]['calls']]==['inner']
    validate_candidate(source.replace('fake(1)//','new(2)/*'),info)
    with pytest.raises(ValueError):validate_candidate(source.replace('x: String','x: Int64'),info)


@pytest.mark.parametrize('body',[
 'x.trim()', 'x.toArray()', 'x.toRuneArray()', 'x.toRuneArray().size()', 'x.size()', 'x.unknown', 'x.size.size',
 'x + 1', 'x == 1', 'x < "z"', '"${x}"', 'String(x)', 'readln()', 'x[0]', '"\\u{d800}"', '"'+ 'x'*257+'"',
])
def test_new_string_subset_rejects_other_capabilities(body):
    with pytest.raises(ValueError):inspect_source('func f(x: String): String { '+body+' }')


@pytest.mark.parametrize('source',['func f(): String { """text""" }','func f(): String { "a""b" }'])
def test_adjacent_or_multiline_string_literals_are_not_supported(source):
    with pytest.raises(ValueError):inspect_source(source)


def test_string_examples_and_literal_are_typed_data():
    info=inspect_source('func echo(x: String): String { x }')
    good=[dict(args=[''],expected='',suite='target'),dict(args=['中\n${text}'],expected='中\n${text}',suite='regression')]
    assert validate_examples(info,'echo',good)==good
    assert literal(True)=='true' and literal(-(1<<63))=='-9223372036854775808'
    assert literal('a\n${bad}')=='"'+''.join('\\u{'+format(ord(c),'x')+'}' for c in 'a\n${bad}')+'"'
    for key,value in [('args',[0]),('expected',None),('expected','x'*257),('args',['\ud800'])]:
        with pytest.raises(ValueError):validate_examples(info,'echo',[{**good[0],key:value},good[1]])
