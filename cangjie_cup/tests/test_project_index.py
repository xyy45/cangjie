import copy
import importlib
import importlib.util

import pytest


def indexer():
    assert importlib.util.find_spec('nexus.projects.index') is not None, 'project symbol index missing'
    return importlib.import_module('nexus.projects.index')


def project():
    return {
        'cjpm.toml': b'[package]\nname="billing"\nversion="1.0.0"\ncjc-version="1.0.5"\noutput-type="static"\n[dependencies]\n',
        'cjpm.lock': b'version = 0\n[requires]\n',
        'src/order.cj': b'package billing\npublic func total(x: Int64): Int64 { fee(x) + 100 }\n',
        'src/fee.cj': b'package billing\npublic func fee(x: Int64): Int64 { x + 1 }\n',
        'src/cases_test.cj': b'package billing\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass BillingTests {\n @TestCase func amount() { @Expect(total(2), 102) }\n @TestCase func zero() { @Expect(fee(0), 0) }\n}\n',
        'README.md': b'Original project documentation\n',
    }


def test_cross_file_functions_and_frozen_tests_are_indexed_without_rewriting_bytes():
    files=project();before=copy.deepcopy(files);m=indexer();info=m.inspect_project(files)
    assert info['package']=='billing'
    assert info['production_paths']==['src/fee.cj','src/order.cj']
    assert [(f['name'],f['path'],f['line']) for f in info['functions']]==[('fee','src/fee.cj',2),('total','src/order.cj',2)]
    assert info['test_cases']==[
        dict(id='BillingTests.amount',function='total',args=[2],expected=102,path='src/cases_test.cj',line=6),
        dict(id='BillingTests.zero',function='fee',args=[0],expected=0,path='src/cases_test.cj',line=7),
    ]
    assert files==before
    assert set(info['frozen_manifest'])=={'cjpm.toml','cjpm.lock','src/cases_test.cj','README.md'}
    fixed={**files,'src/fee.cj':files['src/fee.cj'].replace(b'x + 1',b'x')}
    m.validate_project_candidate(fixed,info)


@pytest.mark.parametrize('path,replacement',[
    ('src/order.cj',b'package billing\nfunc total(x: Int64): Int64 { missing(x) }'),
    ('src/order.cj',b'package billing\nfunc total(x: Int64): Int64 { fee(true) }'),
    ('src/order.cj',b'package other\nfunc total(x: Int64): Int64 { x }'),
    ('src/order.cj',b'package billing\nfunc fee(x: Int64): Int64 { x }'),
    ('src/order.cj',b'package billing\nimport std.fs.*\nfunc total(x: Int64): Int64 { x }'),
    ('src/cases_test.cj',b'package billing\nimport std.fs.*\n@Test class Bad { @TestCase func bad() { @Expect(total(1),1) } }'),
    ('src/cases_test.cj',b'package billing\n@Test class Bad { @TestCase func bad() { println(1) } }'),
    ('src/cases_test.cj',b'package billing\n@Test class Bad { @TestCase func bad() { @Expect(missing(1),1) } }'),
    ('src/cases_test.cj',b'package billing\n@Test class Bad { @TestCase func bad() { @Expect(total(true),1) } }'),
    ('src/cases_test.cj',b'package billing\n@Test class Bad { @TestCase func bad() { @Expect(total(1),true) } }'),
])
def test_unknown_calls_capabilities_and_unmappable_tests_are_rejected(path,replacement):
    with pytest.raises(ValueError):indexer().inspect_project({**project(),path:replacement})


@pytest.mark.parametrize('suffix',[
    '\n[dependencies.evil]\npath="/tmp/evil"\n',
    '\n[scripts]\nbuild="touch /tmp/bad"\n',
    '\n[target]\nx="bad"\n',
])
def test_external_dependencies_and_dynamic_build_configuration_are_rejected(suffix):
    files=project();files['cjpm.toml']+=suffix.encode()
    with pytest.raises(ValueError):indexer().inspect_project(files)


def test_configuration_lock_and_candidate_identity_are_bound():
    m=indexer();files=project();info=m.inspect_project(files)
    for path,content in [
        ('src/fee.cj',b'package billing\nfunc fee(x: Bool): Int64 { 1 }'),
        ('src/cases_test.cj',files['src/cases_test.cj'].replace(b'102',b'103')),
        ('cjpm.toml',files['cjpm.toml'].replace(b'static',b'executable')),
        ('README.md',b'changed'),
    ]:
        with pytest.raises(ValueError):m.validate_project_candidate({**files,path:content},info)
    with pytest.raises(ValueError):m.validate_project_candidate({k:v for k,v in files.items() if k!='README.md'},info)
    for key,val in [('compile-option','--import-path /tmp'),('target-dir','/tmp/escape'),('package-configuration',{'x':'bad'})]:
        import tomllib
        original=files['cjpm.toml'].decode().replace('[dependencies]','')
        import json
        if isinstance(val,dict):line=key+' = {x="bad"}\n'
        else:line=key+' = '+json.dumps(val)+'\n'
        with pytest.raises(ValueError):m.inspect_project({**files,'cjpm.toml':(original+line+'[dependencies]\n').encode()})
    with pytest.raises(ValueError):m.inspect_project({**files,'cjpm.lock':b'version=0\n[requires.evil]\npath="/tmp"\n'})
    with pytest.raises(ValueError):m.inspect_project({**files,'src/sub/other.cj':b'package billing\nfunc other(x: Int64): Int64 { x }'})


def test_single_file_gate_still_rejects_undeclared_cross_file_calls():
    from nexus.uploads.language import inspect_source
    with pytest.raises(ValueError):inspect_source(project()['src/order.cj'].decode())


def test_repeated_test_class_across_files_and_non_text_material_are_rejected():
    files=project();files['src/extra_test.cj']=files['src/cases_test.cj'].replace(b'amount',b'otherAmount').replace(b'zero',b'otherZero')
    with pytest.raises(ValueError):indexer().inspect_project(files)
    with pytest.raises(ValueError):indexer().inspect_project({**project(),'README.md':b'\xff'})


@pytest.mark.parametrize('public',[True,False])
def test_candidate_must_preserve_export_visibility(public):
    files=project()
    if not public:files['src/fee.cj']=files['src/fee.cj'].replace(b'public func',b'func')
    m=indexer();baseline=m.inspect_project(files)
    changed=files['src/fee.cj'].replace(b'public func',b'func') if public else files['src/fee.cj'].replace(b'func',b'public func')
    with pytest.raises(ValueError):m.validate_project_candidate({**files,'src/fee.cj':changed},baseline)
