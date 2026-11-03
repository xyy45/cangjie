"""Real native qualified nominal axes; names remain bounded data, never code."""
import asyncio,json
from copy import deepcopy
import pytest

from nexus.policy.core import NativeCoreClient,LIMIT
from nexus.repair import oracle
from nexus.repair.exploration import boundary_payload
from tests.test_package_contracts import contract,canonical
from tests.test_object_contracts import state
from tests.test_object_core import rejection


def payload():
    raw,sig=contract(oracle)
    return boundary_payload(oracle.validate_contract(raw,sig,[]))


@pytest.mark.parametrize('identifier',['bench.model.OrderState','.'.join(['a'*23]*8)+'.'+'b'*64])
def test_native_qualified_type_axes_preserve_identity_and_maximum_name(tmp_path,identifier):
    p=payload();old='bench.model.OrderState';p['types'][identifier]=p['types'].pop(old)
    p['domains'][0]['type']=identifier
    for item in p['domains'][0]['domain']['values']:item['$type']=identifier
    core=NativeCoreClient();proof=asyncio.run(core.call('boundary.axes',p))
    (tmp_path/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    assert core.verify_proof(proof,'boundary.axes',p)==dict(axes=[p['domains'][0]['domain']['values'],[0,1]])


def test_native_two_same_named_types_are_nominally_distinct(tmp_path):
    p=payload();p['types']['bench.other.OrderState']=deepcopy(p['types']['bench.model.OrderState'])
    p['domains'][0]['domain']['values'][0]['$type']='bench.other.OrderState'
    rejection(p,tmp_path)


@pytest.mark.parametrize('identifier',[
    'bench..State','bench.State.','.bench.State','bench.1State','bench.非ASCII',
    'std.model.State','cangjie.model.State','bench.class.State','bench.as.State',
    'bench.nexus_verify_user.State','bench.NEXUS_VERIFY_user.State',
    'a.b.c.d.e.f.g.h.i.State','bench.'+'x'*65,'.'.join(['a'*24]*8)+'.State',
])
def test_native_rejects_invalid_qualified_type_names_with_matching_tags(tmp_path,identifier):
    p=payload();p['types'][identifier]=p['types'].pop('bench.model.OrderState')
    p['domains'][0]['type']=identifier
    for item in p['domains'][0]['domain']['values']:item['$type']=identifier
    rejection(p,tmp_path)


def test_native_field_names_cannot_be_qualified_and_bool_is_not_int(tmp_path):
    first=tmp_path/'qualified-field';first.mkdir();second=tmp_path/'bool-leaf';second.mkdir()
    p=payload();p['types']['bench.model.OrderState']['fields'][0]['name']='bench.amount'
    rejection(p,first)
    p=payload();p['domains'][0]['domain']['values'][0]['fields']['amount']=True
    rejection(p,second)


def test_qualified_axes_do_not_expand_ipc_budget():
    assert LIMIT==65536
    p=payload();p['padding']='x'*65536
    with pytest.raises(ValueError):asyncio.run(NativeCoreClient().call('boundary.axes',p))
