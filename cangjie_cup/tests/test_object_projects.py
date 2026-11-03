"""Frozen same-package objects and closed public-field projections."""
from copy import deepcopy
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.projects.index import inspect_project,validate_project_candidate
from tests.test_object_language import source


def project():
    text=source('class');declaration,entry=text.split('public func apply',1)
    tests='''package bench
import std.unittest.*
import std.unittest.testmacro.*
@Test
class Cases {
 @TestCase
 func amount() { @Expect(apply(OrderState(10, [1, 2]), 3).amount, 7) }
 @TestCase
 func items() { @Expect(apply(OrderState(10, []), 0).items, []) }
}
'''
    declaration+='public func helper(): Int64 { 0 }\n'
    return {'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/state.cj':declaration.encode(),'src/order.cj':('package bench\npublic func apply'+entry).encode(),'src/cases_test.cj':tests.encode()}


def test_same_package_objects_and_projected_tests_are_frozen_and_indexed():
    files=project();before=deepcopy(files);info=inspect_project(files)
    assert files==before and info['types']['OrderState']['kind']=='class'
    assert info['type_paths']=={'OrderState':'src/state.cj'}
    assert {m['name'] for m in info['methods']}=={'OrderState.net','OrderState.refund'}
    first,second=info['test_cases'];assert first['projection']==['amount'] and first['expected_type']=='Int64' and first['expected']==7
    assert first['args']==[{'$type':'OrderState','fields':{'amount':10,'items':[1,2]}},3]
    assert second['projection']==['items'] and second['expected_type']=='Array<Int64>' and second['expected']==[]
    changed={**files,'src/state.cj':files['src/state.cj'].replace(b'this.amount - n',b'this.amount - n - 1')}
    validate_project_candidate(changed,info)


@pytest.mark.parametrize('change',['kind','fields','method-interface','test-value','type-location'])
def test_project_object_interfaces_and_test_projection_cannot_change(change):
    files=project();baseline=inspect_project(files);changed=deepcopy(files)
    if change=='kind':changed['src/state.cj']=changed['src/state.cj'].replace(b'public class',b'public struct')
    elif change=='fields':changed['src/state.cj']=changed['src/state.cj'].replace(b'items',b'lines')
    elif change=='method-interface':changed['src/state.cj']=changed['src/state.cj'].replace(b'refund(n: Int64)',b'refund(quantity: Int64)').replace(b'amount - n',b'amount - quantity')
    elif change=='test-value':changed['src/cases_test.cj']=changed['src/cases_test.cj'].replace(b'.amount, 7',b'.amount, 8')
    else:
        declaration,_,helper=changed['src/state.cj'].partition(b'public func helper')
        changed['src/order.cj']+=declaration.removeprefix(b'package bench\n')
        changed['src/state.cj']=b'package bench\npublic func helper'+helper
    with pytest.raises(ValueError):validate_project_candidate(changed,baseline)


@pytest.mark.parametrize('expression',['apply(OrderState(10, []), 0), OrderState(10, [])','apply(OrderState(true, []), 0).amount, 10','apply(OrderState(10, []), 0).missing, 10','apply(OrderState(10, []), 0).net(), 10'])
def test_project_test_only_allows_typed_closed_field_projection(expression):
    files=project();text=files['src/cases_test.cj'].decode();text=text.replace('apply(OrderState(10, [1, 2]), 3).amount, 7',expression)
    with pytest.raises(ValueError):inspect_project({**files,'src/cases_test.cj':text.encode()})
