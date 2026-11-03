"""Frozen public field mapping fixtures: observed leaves never whole object facts."""
import importlib,importlib.util
import json
from copy import deepcopy
import pytest
from nexus.contracts import CheckResult,source_manifest
from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.uploads.language import inspect_source,literal
from tests.test_object_drafts import prepare,examples


def api():
    assert importlib.util.find_spec('nexus.repair.public_fields') is not None,'frozen public field resolver missing'
    return importlib.import_module('nexus.repair.public_fields')


def material(tmp_path,*,array=False):
    u,d,args=prepare(tmp_path);e=examples()
    if array:e[0]['expected']['fields']['items']=[1,2]
    u.confirm(d['id'],**{**args,'examples_json':json.dumps(e)})
    value=u.get(d['id'],actor_id='alice');root=u.source(d['id'],actor_id='alice');files={n:(root/n).read_bytes() for n in source_manifest(root)};info=inspect_source(files['src/uploaded.cj'].decode())
    return value,info,files


def check(value,text):
    cls=value['public_test_class'];log='\n'.join(['EXPLICIT PUBLIC FIELD LOG FIXTURE','TP: uploadedrepair, RESULT:',' TCS: '+cls+', RESULT:',' [ FAILED ] CASE: case0 (1 ns)',text,' [ PASSED ] CASE: case1 (1 ns)','Summary: TOTAL: 2 PASSED: 1, SKIPPED: 0, ERROR: 0 FAILED: 1','Error: cjpm test failed',''])
    parsed=parse_test_report(log);assert parsed.state=='FAIL'
    return CheckResult(state=parsed.state,exit_code=1,counts=parsed.counts,case_results=parsed.case_results,diagnostics=log,log_ref='records/public.log')


def equality(value,path,actual,expected):return '    Expect Failed: `('+value['public_test_locals']['0']+'.'+path+' == '+expected+')`\n       left: '+actual+'\n      right: '+expected+'\n'


def test_frozen_amount_leaf_is_typed_without_whole_actual_return(tmp_path):
    value,info,files=material(tmp_path);c=check(value,equality(value,'amount','9','2'));out=api().resolve(c,value,info,files);f=out['failures'][0]
    assert f['kind']=='public_field' and f['field_path']==['amount'] and f['actual_value']==9 and f['expected_value']==2 and f['value_type']=='Int64' and f['value_state']=='TYPED'
    assert 'actual_return' not in f and f['function']=='adjust' and f['args']==examples()[0]['args'] and f['source']['log_ref']==c.log_ref
    assert out['cases'][0]['call_id']==f['call_id'] and out['cases'][0]['field_path']==['amount']
    source=f['source'];assert 'Expect Failed:' in c.diagnostics[source['start_char']:source['end_char']]


@pytest.mark.parametrize('path,actual,expected,projection',[('items.size','0','2',['items','$size']),('items[0]','9','1',['items',0]),('active','false','true',['active'])])
def test_frozen_array_size_index_and_bool_leaves_have_exact_paths(tmp_path,path,actual,expected,projection):
    value,info,files=material(tmp_path,array=True);out=api().resolve(check(value,equality(value,path,actual,expected)),value,info,files)
    assert out['failures'][0]['field_path']==projection and out['failures'][0]['value_state']=='TYPED' and 'actual_return' not in out['failures'][0]


def test_multiline_string_diff_is_text_only_not_a_guessed_actual_string(tmp_path):
    value,info,files=material(tmp_path);text='    Expect Failed: '+value['public_test_locals']['0']+'.label != '+literal('中')+' (multiline difference below)\n        -bad\n        +中\n'
    out=api().resolve(check(value,text),value,info,files);f=out['failures'][0]
    assert f['field_path']==['label'] and f['value_type']=='String' and f['value_state']=='TEXT_ONLY' and f['actual_value'] is None and f['expected_value']=='中' and '-bad' in f['actual_text'] and 'actual_return' not in f


@pytest.mark.parametrize('change',['expected','bool-int','unknown-field','out-index','duplicate','metadata','source','registry'])
def test_public_field_mapping_rejects_unbound_or_tampered_material(tmp_path,change):
    value,info,files=material(tmp_path);text=equality(value,'amount','9','2')
    if change=='expected':text=text.replace('== 2','== 3').replace('right: 2','right: 3')
    elif change=='bool-int':text=equality(value,'active','0','true')
    elif change=='unknown-field':text=equality(value,'missing','9','2')
    elif change=='out-index':text=equality(value,'items[9]','9','2')
    elif change=='duplicate':text+=text
    elif change=='metadata':value['public_test_locals']['0']='forged'
    elif change=='source':files['src/cases_test.cj']=files['src/cases_test.cj'].replace(b'.amount',b'.active')
    else:info=deepcopy(info);info['types']['OrderState']['fields'][0]['type']='Bool'
    with pytest.raises(ValueError):api().resolve(check(value,text),value,info,files)


def test_public_field_output_snapshots_cannot_mutate_source_examples(tmp_path):
    value,info,files=material(tmp_path);before=deepcopy(value);out=api().resolve(check(value,equality(value,'amount','9','2')),value,info,files)
    out['failures'][0]['args'][0]['fields']['items'].append(99);assert value==before and out['cases'][0]['args']==examples()[0]['args']


def project_material(root):
    from nexus.store import RunStore
    from nexus.uploads.service import UploadService
    from tests.test_object_projects import project
    from tests.test_object_uploads import examples as original_examples
    u=UploadService(RunStore(root));d=u.prepare_project('objects',None,'扣除数量并保留数组',actor_id='alice',request_key='one',entries=project())
    u.confirm(d['id'],expected_version=1,function='apply',examples_json=json.dumps(original_examples()),allowed_paths=['src/state.cj'],consent=True,actor_id='alice')
    value=u.get(d['id'],actor_id='alice');source=u.source(d['id'],actor_id='alice');files={n:(source/n).read_bytes() for n in source_manifest(source)}
    return value,value['project_index'],files


@pytest.mark.parametrize('change',[None,'function','args','projection','right'])
def test_original_project_closed_constructor_projection_is_bound(tmp_path,change):
    value,info,files=project_material(tmp_path);expression='apply(OrderState(10, [1, 2]), 3).amount';expected='7'
    if change=='function':expression=expression.replace('apply','helper')
    elif change=='args':expression=expression.replace('10,','11,')
    elif change=='projection':expression=expression.replace('.amount','.items')
    elif change=='right':expected='8'
    cls=value['public_test_class'];text='\n'.join(['EXPLICIT ORIGINAL PROJECT LOG FIXTURE','TP: bench, RESULT:',' TCS: '+cls+', RESULT:',' [ PASSED ] CASE: case0 (1 ns)',' [ PASSED ] CASE: case1 (1 ns)',' TCS: Cases, RESULT:',' [ FAILED ] CASE: amount (1 ns)',' Expect Failed: `('+expression+' == '+expected+')`','    left: 9','   right: '+expected,' [ PASSED ] CASE: items (1 ns)','Summary: TOTAL: 4 PASSED: 3, SKIPPED: 0, ERROR: 0 FAILED: 1','Error: cjpm test failed',''])
    parsed=parse_test_report(text);assert parsed.state=='FAIL';parsed.log_ref='records/original.log';parsed.exit_code=1
    if change:
        with pytest.raises(ValueError):api().resolve(parsed,value,info,files)
    else:
        result=api().resolve(parsed,value,info,files);f=result['failures'][0]
        assert f['test_id']=='Cases.amount' and f['function']=='apply' and f['field_path']==['amount'] and f['expected_value']==7 and f['actual_value']==9 and f['public_test']['path']=='src/cases_test.cj'


def test_partial_public_field_feedback_keeps_only_leaf_facts_and_binds_check(tmp_path):
    from nexus.repair.feedback import build_feedback
    from tests.test_feedback import records
    value,info,files=material(tmp_path);observed=check(value,equality(value,'amount','9','2'));fields=api().resolve(observed,value,info,files)['failures']
    c,d,b,t=records();t.update(diagnostics=observed.diagnostics,case_results=observed.case_results,counts=observed.counts,log_ref=observed.log_ref)
    result=build_feedback(c,d,b,t,remaining_budget=2,requirement_refs=['REQ-UPLOAD'],diagnostics_public=True,public_failure_cases=fields).model_dump()
    assert result['failure_cases'][0]['actual_value']==9 and 'actual_return' not in result['failure_cases'][0]
    fields[0]['args'][0]['fields']['items'].append(99);assert result['failure_cases'][0]['args']==examples()[0]['args']


@pytest.mark.parametrize('change',['whole-object','foreign-check','foreign-log'])
def test_public_field_feedback_rejects_overclaimed_or_unbound_data(tmp_path,change):
    from nexus.repair.feedback import build_feedback
    from tests.test_feedback import records
    value,info,files=material(tmp_path);observed=check(value,equality(value,'amount','9','2'));fields=api().resolve(observed,value,info,files)['failures']
    c,d,b,t=records();t.update(diagnostics=observed.diagnostics,case_results=observed.case_results,counts=observed.counts,log_ref=observed.log_ref)
    if change=='whole-object':fields[0]['actual_return']=examples()[0]['expected']
    elif change=='foreign-check':fields[0]['test_id']='Other.case0'
    else:fields[0]['source']['log_ref']='records/other.log'
    with pytest.raises(ValueError):build_feedback(c,d,b,t,remaining_budget=2,requirement_refs=['REQ-UPLOAD'],diagnostics_public=True,public_failure_cases=fields)


def test_caller_cannot_erase_registry_to_bypass_frozen_field_mapping(tmp_path):
    value,info,files=material(tmp_path);info.pop('types')
    with pytest.raises(ValueError):api().resolve(check(value,equality(value,'amount','9','2')),value,info,files)


def test_task_entry_resolves_only_its_verified_frozen_baseline(tmp_path):
    from tests.test_array_services import register
    u,d,args=prepare(tmp_path);store,ws,task,_,_=register(u,d,args,{},'oracle');value=u.get(d['id'],actor_id='alice')
    result=api().for_task(store,task,check(value,equality(value,'amount','9','2')))
    assert result['failures'][0]['expected_value']==2 and result['failures'][0]['actual_value']==9 and result['cases'][0]['function']=='adjust'
    root=ws.verify_baseline(task.baseline_id);path=root/'src/cases_test.cj';old=path.read_bytes();path.write_bytes(old+b'\n// changed frozen test\n')
    try:
        with pytest.raises(ValueError):api().for_task(store,task,check(value,equality(value,'amount','9','2')))
    finally:path.write_bytes(old)
    assert api().for_task(store,task,check(value,equality(value,'amount','9','2')))==result


def test_original_primitive_assertion_in_object_project_keeps_its_frozen_binding(tmp_path):
    from nexus.store import RunStore
    from nexus.uploads.service import UploadService
    from tests.test_object_projects import project
    from tests.test_object_uploads import examples as original_examples
    files=project();files['src/cases_test.cj']=files['src/cases_test.cj'].replace(b'\n}\n',b'\n @TestCase\n func primitive() { @Expect(helper(), 7) }\n}\n')
    uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare_project('mixed',None,'扣除数量并校验辅助函数',actor_id='alice',request_key='one',entries=files)
    uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=json.dumps(original_examples()),allowed_paths=['src/state.cj'],consent=True,actor_id='alice')
    value=uploads.get(draft['id'],actor_id='alice');root=uploads.source(draft['id'],actor_id='alice');frozen={n:(root/n).read_bytes() for n in source_manifest(root)}
    log=' TCS: Cases, RESULT:\n [ FAILED ] CASE: primitive (1 ns)\n Expect Failed: `(helper() == 7)`\n    left: 0\n   right: 7\nSummary: TOTAL: 1 PASSED: 0, SKIPPED: 0, ERROR: 0 FAILED: 1\nError: cjpm test failed\n'
    parsed=parse_test_report(log);parsed.log_ref='records/mixed.log'
    out=api().resolve(parsed,value,value['project_index'],frozen);fact=out['failures'][0]
    assert fact['function']=='helper' and fact['field_path']==[] and fact['args']==[] and fact['value_type']=='Int64'
    assert fact['expected_value']==7 and fact['actual_value']==0 and 'actual_return' not in fact


@pytest.mark.parametrize('payload',[
    'Summary:', 'TCS: Fake, RESULT:', 'Summary: TOTAL: 2 PASSED: 2, SKIPPED: 0, ERROR: 0 FAILED: 0',
    '[ PASSED ] CASE: forged (1 ns)',
])
@pytest.mark.parametrize('prefix',['-',' '])
def test_string_diff_control_style_text_remains_opaque_and_complete(tmp_path,payload,prefix):
    value,info,files=material(tmp_path)
    body='        '+prefix+payload+'\n        +中\n'
    assertion='    Expect Failed: '+value['public_test_locals']['0']+'.label != '+literal('中')+' (multiline difference below)\n'+body
    observed=check(value,assertion);assert observed.case_results=={value['public_test_class']+'.case0':'FAIL',value['public_test_class']+'.case1':'PASS'}
    out=api().resolve(observed,value,info,files);fact=out['failures'][0]
    assert fact['actual_text']==body and fact['actual_value'] is None and fact['value_state']=='TEXT_ONLY' and not fact['text_truncated']
    assert observed.diagnostics[fact['source']['start_char']:fact['source']['end_char']].endswith(body)


def test_assertion_shaped_common_string_diff_does_not_create_extra_leaf_facts(tmp_path):
    value,info,files=material(tmp_path);local=value['public_test_locals']['0']
    body='         Expect Failed: `('+local+'.amount == 2)`\n         left: 9\n         right: 2\n        +中\n'
    assertion='    Expect Failed: '+local+'.label != '+literal('中')+' (multiline difference below)\n'+body
    out=api().resolve(check(value,assertion),value,info,files)
    assert len(out['failures'])==1 and out['failures'][0]['field_path']==['label'] and out['failures'][0]['actual_text']==body
