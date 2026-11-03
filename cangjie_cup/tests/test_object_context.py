"""Bounded source registry reaches model constraints; no model sends."""
from copy import deepcopy
import pytest
from nexus.repair import cegis_loop
from tests.test_object_values import types


def base():return dict(types=['Int64','Bool','String','Array<Int64>'],allowed='原始值和数组只读',forbidden='导入、类、宏',readonly_arrays=True,preserve_all_function_signatures=True)


def test_object_context_constraints_allow_existing_pure_types_and_freeze_registry():
    raw=types();prior=base();before=deepcopy(prior)
    assert hasattr(cegis_loop,'object_constraints'),'object constraints helper missing'
    result=cegis_loop.object_constraints(prior,raw)
    assert prior==before and result['types']==before['types']+['OrderState'] and result['object_registry']==raw
    assert result['readonly_object_fields'] and result['preserve_all_type_declarations'] and result['preserve_constructor_and_method_signatures']
    assert '仓颉具名struct/class' in result['allowed'] and '字段赋值' in result['forbidden'] and '引用身份' in result['forbidden']
    raw['OrderState']['fields'][0]['name']='forged';assert result['object_registry']==types()


def test_no_object_constraints_preserve_existing_output():
    assert hasattr(cegis_loop,'object_constraints')
    prior=base();assert cegis_loop.object_constraints(prior,{})==prior


def test_model_context_rejects_unregistered_nested_object_field():
    assert hasattr(cegis_loop,'object_constraints')
    raw=types();raw['OrderState']['fields'][0]['type']='OtherState'
    with pytest.raises(ValueError):cegis_loop.object_constraints(base(),raw)


def test_object_loop_context_uses_verified_baseline_registry_before_any_model_send(tmp_path):
    import asyncio
    from nexus.llm.provider import ProviderUnavailable
    from tests.test_repair_loop import Client
    from tests.test_object_services import setup
    store,ws,task,_,_=setup(tmp_path,'oracle');contexts=[]
    class Stop:
        async def propose(self,context):contexts.append(context);raise ProviderUnavailable('EXPLICIT STOP BEFORE MODEL REQUEST')
    result=asyncio.run(cegis_loop.RepairLoop(store,provider_factory=lambda *_:Stop(),client_factory=Client).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    assert contexts[0]['upload_constraints']['object_registry']==types() and contexts[0]['upload_constraints']['readonly_object_fields']


def test_unknown_sdk_fixture_contains_all_public_examples_before_execution(tmp_path):
    from tests.sdk.test_object_loop_sdk import setup
    store,ws,task,_,data=setup(tmp_path.resolve(),'oracle','unknown')
    assert store.get_task(task.id).status=='READY' and len(data['model']['domains']['state']['values'])==3
