"""Canonical scope locations reuse the existing bounded focus and model view."""
import json
import pytest
from nexus.contracts import file_hash
from nexus.repair import localization
from tests.test_package_index import project
from nexus.projects.index import inspect_project
from tests.test_package_public_fields import fixture,api


def sources(files):return {p:dict(content=raw.decode(),file_hash=file_hash(raw.decode())) for p,raw in files.items() if p.endswith('.cj') and not p.endswith('_test.cj')}


def test_same_local_function_and_method_names_have_distinct_scoped_locations():
    files=project();index=inspect_project(files)
    functions,unavailable=localization.source_index(sources(files),scoped_index=index)
    assert not unavailable
    assert functions['bench.sale.fee']['path']=='src/sale/state.cj'
    assert functions['bench.refund.fee']['path']=='src/refund/state.cj'
    assert functions['bench.sale.State.advance']['receiver_type']=='bench.sale.State'
    changed=sources(files);changed['src/order.cj']['content']+='\nchanged'
    with pytest.raises(ValueError):localization.source_index(changed,scoped_index=index)


def test_public_xml_field_focus_keeps_canonical_function_and_discards_bodies_for_model(tmp_path):
    value,index,files,check,parsed=fixture(tmp_path);mapped=api().resolve(check,value,index,files,parsed)
    failures=[f for f in mapped['failures'] if f['visibility']=='PUBLIC'];cases=[c for c in mapped['cases'] if c['visibility']=='PUBLIC']
    report=localization.build_focus(sources(files),cases,failures,{},dict(baseline_id='baseline'),scoped_index=index)
    assert report['status']=='PARTIAL' and report['targets'][0]['function']=='bench.step'
    assert report['targets'][0]['locations'][0]['path']=='src/step.cj'
    assert report['algorithm']=='confirmed-case-scoped-baseline-pdg-v2'
    view=localization.model_view(report)
    assert not any('source_lines' in p for target in view['targets'] for p in target['locations'])
    assert 'ORIGINAL_TEST_BODY_NOT_FOR_MODEL' not in json.dumps(view)
