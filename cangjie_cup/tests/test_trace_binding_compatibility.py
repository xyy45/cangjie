"""Unscoped callers keep their original adapter signature without a new None kw."""
import pytest
from nexus.repair import primitive_trace,property_trace,relation_trace,properties,relations
from tests.test_object_contracts import raw_property,raw_relation,signature,state


@pytest.mark.parametrize('mode',['property','relation'])
def test_legacy_object_adapter_does_not_receive_scoped_binding_keyword(monkeypatch,mode):
    calls=[]
    def legacy(signature,cases,package,token,mode,*,version):
        calls.append((cases,version));return 'EXPLICIT LEGACY ADAPTER'
    monkeypatch.setattr(primitive_trace,'harness',legacy)
    args=[state(1),0]
    if mode=='property':
        contract=properties.validate_contract(raw_property(),signature(),[])
        result=property_trace.harness(contract,[args],'bench','0123456789abcdef')
    else:
        contract=relations.validate_contract(raw_relation(),signature(),[])
        result=relation_trace.harness(contract,[dict(left=args,right=args)],'bench','0123456789abcdef')
    assert result=='EXPLICIT LEGACY ADAPTER' and len(calls)==1 and calls[0][1]==4
