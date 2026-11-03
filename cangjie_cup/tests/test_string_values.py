"""Strict bounded values, not executable data."""
import importlib
import pytest


def values():
    assert importlib.util.find_spec('nexus.repair.values') is not None, 'bounded String value semantics missing'
    return importlib.import_module('nexus.repair.values')


@pytest.mark.parametrize('text',['', 'abc', '中😀', 'é', 'é', '\x00\n\r\t"\\', '${not_code}', 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', '中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中中', '中'*85+'x'])
def test_bounded_strings_preserve_exact_scalars(text):
    v=values();assert v.string(text)==text
    assert v.byte_len(text)==len(text.encode('utf-8'))
    assert v.rune_len(text)==len(text)
    assert v.primitive(text,'String')==text
    assert v.primitive_weight(text)==len(text.encode('utf-8'))
    encoded=v.string_literal(text)
    assert encoded=='"'+''.join('\\u{'+format(ord(c),'x')+'}' for c in text)+'"'
    assert v.decode_string_literal(encoded)==text


@pytest.mark.parametrize('text',[None,1,True,b'x','x'*257,'中'*86,'中'*85+'xx','\ud800','\udfff'])
def test_strings_reject_wrong_type_size_and_surrogates(text):
    v=values()
    for function in (v.string,v.string_literal,v.byte_len,v.rune_len):
        with pytest.raises(ValueError):function(text)


@pytest.mark.parametrize('raw', ['"${escape}"', '"\\q"', '"\\u{}"', '"\\u{110000}"', '"\\u{d800}"', '"line\nbreak"', '"unterminated', 'x', '"a" trailing'])
def test_source_string_decoder_is_a_closed_non_interpolating_grammar(raw):
    with pytest.raises(ValueError):values().decode_string_literal(raw)


def test_primitive_types_are_exact_and_keep_numeric_semantics():
    v=values()
    for kind,value in [('Bool',True),('Bool',False),('Int64',-(1<<63)),('Int64',(1<<63)-1)]:
        assert v.primitive(value,kind) is value
        assert v.primitive_weight(value)==abs(int(value))
    for value,kind in [(True,'Int64'),(0,'Bool'),('0','Int64'),(1,'String'),(None,'Unit'),(1<<63,'Int64')]:
        with pytest.raises(ValueError):v.primitive(value,kind)
    assert len({v.typed_key(1),v.typed_key(True),v.typed_key('1')})==3
    assert v.typed_key('é')!=v.typed_key('e\u0301')
