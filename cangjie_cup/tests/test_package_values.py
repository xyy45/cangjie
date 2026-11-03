"""V5 canonical wire data and reserved headers; fixtures are not SDK results."""
from copy import deepcopy
import importlib
import pytest

from nexus.repair import object_trace,primitive_trace,sequence_trace
from tests.test_package_contracts import contract,canonical
from tests.test_object_contracts import signature,state
from tests.test_primitive_trace import TOKEN,log as legacy_log,signature as legacy_signature
from tests.test_sequence_trace import contract as seq_contract,trajectory,log as seq_log


def codec():return importlib.import_module('nexus.repair.scoped_values')


def test_maximum_qualified_object_wire_is_2333_while_v4_stays_2141():
    m=codec();identifier='.'.join(['a'*23]*8)+'.'+'b'*64
    fields=[dict(name='p'+str(i),type='String') for i in range(4)]
    types={identifier:dict(kind='class',fields=fields,constructor=deepcopy(fields),methods=[])}
    value={'$type':identifier,'fields':{f['name']:'x'*256 for f in fields}}
    encoded=m.encode(value,identifier,types)
    assert m.MAX_WIRE==2333 and len(encoded)==2333 and m.decode(encoded,identifier,types)==value
    assert object_trace.MAX_WIRE==2141
    with pytest.raises(ValueError):object_trace.decode(encoded,identifier,types)
    with pytest.raises(ValueError):m.decode(encoded+'x',identifier,types)


@pytest.mark.parametrize('kind,value',[
    ('Int64',-(1<<63)),('Int64',(1<<63)-1),('Bool',False),
    ('String','中\x00\n|NEXUS_SEQUENCE_V5|'),('Array<Int64>',[-(1<<63),(1<<63)-1])])
def test_v5_leaf_roundtrip_and_canonical_encoding(kind,value):
    m=codec();encoded=m.encode(value,kind,{})
    assert m.decode(encoded,kind,{})==value and type(m.decode(encoded,kind,{})) is type(value)


def test_v5_nominal_tags_fields_lengths_and_canonical_text_are_strict():
    m=codec();sig=canonical(signature());types=sig['types'];kind='bench.model.OrderState';value=canonical(state(2))
    # canonical(signature()) only moves the type to the same canonical model package.
    encoded=m.encode(value,kind,types)
    assert m.decode(encoded,kind,types)==value
    for bad in [encoded+'x',encoded.replace('bench.model','bench.other',1),encoded.replace(':1:2',':01:2',1)]:
        with pytest.raises(ValueError):m.decode(bad,kind,types)
    wrong=deepcopy(value);wrong['fields']['amount']=True
    with pytest.raises(ValueError):m.encode(wrong,kind,types)
    with pytest.raises(ValueError):m.encode(state(2),'OrderState',signature()['types'])


@pytest.mark.parametrize('prefix',['NEXUS_ORACLE_V5|','NEXUS_PROPERTY_V5|','NEXUS_RELATION_V5|','NEXUS_SEQUENCE_V5|','NEXUS_SEQUENCE_END_V5|','NEXUS_VALUE_ERROR_V5|'])
def test_v5_headers_cannot_be_ignored_by_legacy_primitive_or_sequence_readers(prefix):
    text=legacy_log('single').replace(' STDOUT:\n',' STDOUT:\n '+prefix+'unexpected\n',1)
    assert primitive_trace.read(legacy_signature(),[[1],[1]],TOKEN,'single',text,0,None)['state']=='UNKNOWN'
    text=seq_log().replace(' STDOUT:\n',' STDOUT:\n '+prefix+'unexpected\n',1)
    assert sequence_trace.interpret(seq_contract(),[trajectory()],TOKEN,text,0,None)['state']=='UNKNOWN'
