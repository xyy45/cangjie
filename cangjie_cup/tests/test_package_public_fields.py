"""Frozen scoped assertion mapping from explicit parsed-XML fixtures."""
import importlib,json,hashlib
from copy import deepcopy
import pytest
from nexus.contracts import CheckResult,source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.sdk.test_package_services_sdk import material,state


def fixture(root):
    files=material();u=UploadService(RunStore(root));d=u.prepare_project('scoped',None,'按增量改变状态且保持数组',actor_id='alice',request_key='one',entries=files)
    examples=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1,[]),1],expected=state(2,[]),suite='regression')]
    v=u.confirm(d['id'],expected_version=1,function='bench.step',examples_json=json.dumps(examples),consent=True,actor_id='alice',allowed_paths=['src/step.cj'])
    source=u.source(d['id'],actor_id='alice');files={p:(source/p).read_bytes() for p in source_manifest(source)}
    identity=v['public_test_case_ids']['target'][0];report='test-'+identity.rsplit('.',1)[0]+'.xml'
    text='Expect Failed: `('+v['public_test_locals']['0']+'.amount == 1)`\n   left: 2\n  right: 1\n'
    original='Expect Failed: `(step(State(0, [1, 2]), 1).amount == 1)`\n   left: 2\n  right: 1\n'
    parsed=dict(state='FAIL',counts={},case_results={identity:'FAIL','bench.Cases.case0':'FAIL'},failures={
        identity:[dict(text=text,source=dict(report=report,case_id=identity,failure_index=0,coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(text)))],
        'bench.Cases.case0':[dict(text=original,source=dict(report='test-bench.Cases.xml',case_id='bench.Cases.case0',failure_index=0,coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(original)))]})
    refs={name:dict(ref='records/'+str(i)*32+'.xml',sha256=hashlib.sha256(name.encode()).hexdigest(),bytes=1000) for i,name in enumerate((report,'test-bench.Cases.xml'),1)}
    check=CheckResult(kind='test',state='FAIL',case_results=parsed['case_results'],log_ref='records/sdk.log',package_evidence=dict(test=dict(reports=refs)))
    return v,v['project_index'],files,check,parsed


def api():return importlib.import_module('nexus.repair.scoped_public_fields')


def test_xml_leaf_maps_to_canonical_function_and_original_spelling_with_source_binding(tmp_path):
    value,index,files,check,parsed=fixture(tmp_path)
    result=api().resolve(check,value,index,files,parsed)
    public=next(f for f in result['failures'] if f['visibility']=='PUBLIC')
    original=next(f for f in result['failures'] if f['visibility']=='VERIFICATION_ONLY')
    assert public['function']==original['function']=='bench.step'
    assert public['actual_value']==original['actual_value']==2 and public['expected_value']==1
    assert public['field_path']==['amount'] and 'actual_return' not in public
    assert original['function_spelling']=='step' and original['call_tokens']
    assert public['source']['coordinate']=='XML_FAILURE_TEXT'
    assert public['source']['xml_ref'] in {v['ref'] for v in check.package_evidence['test']['reports'].values()}
    assert public['source']['xml_sha256'] in {v['sha256'] for v in check.package_evidence['test']['reports'].values()}


@pytest.mark.parametrize('change',['wrong-expression','wrong-expected','wrong-case','wrong-report','wrong-type','missing-source','original-spelling'])
def test_unbound_or_untyped_xml_failure_cannot_become_field_feedback(tmp_path,change):
    value,index,files,check,parsed=fixture(tmp_path);identity=value['public_test_case_ids']['target'][0]
    item=parsed['failures'][identity][0]
    if change=='wrong-expression':item['text']=item['text'].replace('.amount','.other')
    elif change=='wrong-expected':item['text']=item['text'].replace('== 1','== 99')
    elif change=='wrong-case':item['source']['case_id']='bench.Foreign.case0'
    elif change=='wrong-report':item['source']['report']='test-foreign.xml'
    elif change=='wrong-type':item['text']=item['text'].replace('left: 2','left: true')
    elif change=='missing-source':item.pop('source')
    else:parsed['failures']['bench.Cases.case0'][0]['text']=parsed['failures']['bench.Cases.case0'][0]['text'].replace('step(','other(')
    with pytest.raises(ValueError):api().resolve(check,value,index,files,parsed)


def test_sdk_short_string_display_escapes_bind_source_tokens_but_never_complete_actual_string(tmp_path):
    from nexus.benchmark.corpus import CONFIG,LOCK
    from nexus.uploads.language import literal
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/entry.cj':b'package bench\npublic func upper(s: String): String { s }',
           'src/helper/anchor.cj':b'package bench.helper\npublic func anchor(x: Int64): Int64 { x }'}
    u=UploadService(RunStore(tmp_path));d=u.prepare_project('strings',None,'按公开示例大写',actor_id='alice',request_key='one',entries=files)
    v=u.confirm(d['id'],expected_version=1,function='bench.upper',examples_json=json.dumps([dict(args=['hello'],expected='HELLO',suite='target'),dict(args=['ok'],expected='OK',suite='regression')]),consent=True,actor_id='alice',allowed_paths=['src/entry.cj'])
    root=u.source(d['id'],actor_id='alice');files={p:(root/p).read_bytes() for p in source_manifest(root)}
    identity=v['public_test_case_ids']['target'][0];report='test-'+identity.rsplit('.',1)[0]+'.xml'
    expression=v['public_test_target']+'('+literal('hello').replace('\\','\\\\')+')'
    expected=literal('HELLO').replace('\\','\\\\')
    text='Expect Failed: '+expression+' != '+expected+'\n    '+expression+': "hello"\n    '+expected+': "HELLO"\n\n'
    parsed=dict(state='FAIL',case_results={identity:'FAIL'},failures={identity:[dict(text=text,source=dict(report=report,case_id=identity,failure_index=0,coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(text)))]})
    reference=dict(ref='records/'+'a'*32+'.xml',sha256='f'*64,bytes=4096)
    check=CheckResult(kind='test',state='FAIL',case_results=parsed['case_results'],log_ref='records/log',package_evidence=dict(test=dict(reports={report:reference})))
    fact=api().resolve(check,v,v['project_index'],files,parsed)['failures'][0]
    assert fact['function']=='bench.upper' and fact['args']==['hello'] and fact['expected_value']=='HELLO'
    assert fact['value_state']=='TEXT_ONLY' and fact['actual_value'] is None and 'actual_return' not in fact
    typed_text='Expect Failed: `('+expression+' == '+expected+')`\n   left: '+literal('hello')+'\n  right: '+expected+'\n'
    parsed['failures'][identity][0].update(text=typed_text, source=dict(report=report, case_id=identity,
        failure_index=0, coordinate='XML_FAILURE_TEXT', start_char=0, end_char=len(typed_text)))
    typed_fact=api().resolve(check,v,v['project_index'],files,parsed)['failures'][0]
    assert typed_fact['value_state']=='TEXT_ONLY' and typed_fact['actual_value'] is None
    assert typed_fact['actual_text']==literal('hello')


@pytest.mark.parametrize('argument', ['back`tick', 'left == "right"', 'left )` == "right"'])
def test_typed_xml_delimiters_inside_original_string_argument_keep_frozen_binding(tmp_path, argument):
    from nexus.benchmark.corpus import CONFIG, LOCK
    from nexus.uploads.language import literal
    files = {'cjpm.toml': CONFIG, 'cjpm.lock': LOCK,
        'src/entry.cj': b'package bench\npublic func upper(s: String): Int64 { 0 }',
        'src/helper/anchor.cj': b'package bench.helper\npublic func anchor(x: Int64): Int64 { x }',
        'src/original_test.cj': ('package bench\nimport std.unittest.*\nimport std.unittest.testmacro.*\n'
            '@Test\nclass OriginalCases {\n    @TestCase\n    func case0() {\n'
            '        @Expect(upper(' + json.dumps(argument) + '), 3)\n    }\n}\n').encode()}
    uploads = UploadService(RunStore(tmp_path))
    prepared = uploads.prepare_project('typed-delimiters', None, '遵循确认示例且保留原测试',
        actor_id='alice', request_key='one', entries=files)
    value = uploads.confirm(prepared['id'], expected_version=1, function='bench.upper',
        examples_json=json.dumps([dict(args=['public'], expected=1, suite='target'),
                                  dict(args=['ok'], expected=0, suite='regression')]),
        consent=True, actor_id='alice', allowed_paths=['src/entry.cj'])
    root = uploads.source(value['id'], actor_id='alice')
    frozen = {path:(root/path).read_bytes() for path in source_manifest(root)}
    identities = [value['public_test_case_ids']['target'][0], 'bench.OriginalCases.case0']
    expressions = [value['public_test_target'] + '(' + literal('public') + ')', 'upper(' + json.dumps(argument) + ')']
    failures = {}; references = {}
    for index, (identity, expression, expected) in enumerate(zip(identities, expressions, [1, 3])):
        report = 'test-' + identity.rsplit('.',1)[0] + '.xml'
        text = 'Expect Failed: `(' + expression + ' == ' + str(expected) + ')`\n   left: 0\n  right: ' + str(expected) + '\n'
        failures[identity] = [dict(text=text, source=dict(report=report, case_id=identity,
            failure_index=0, coordinate='XML_FAILURE_TEXT', start_char=0, end_char=len(text)))]
        references[report] = dict(ref='records/'+str(index+1)*32+'.xml', sha256='a'*64, bytes=4096)
    parsed = dict(state='FAIL', case_results={identity:'FAIL' for identity in identities}, failures=failures)
    checked = CheckResult(kind='test', state='FAIL', case_results=parsed['case_results'],
        log_ref='records/log', package_evidence=dict(test=dict(reports=references)))
    result = api().resolve(checked, value, value['project_index'], frozen, parsed)
    assert len(result['failures']) == 2
    original = next(f for f in result['failures'] if f['visibility']=='VERIFICATION_ONLY')
    assert original['args'] == [argument] and original['actual_value'] == 0 and original['expected_value'] == 3
    assert original['value_state'] == 'TYPED' and original['function'] == 'bench.upper'
