import copy
import importlib
import importlib.util

import pytest

from nexus.contracts import file_hash


def api():
    assert importlib.util.find_spec('nexus.repair.localization') is not None,'failure localization module missing'
    return importlib.import_module('nexus.repair.localization')


def inputs():
    codes={
        'src/order.cj':'package billing\npublic func total(x: Int64): Int64 {\n    fee(x) + 101\n}\n',
        'src/fee.cj':'package billing\npublic func fee(x: Int64): Int64 {\n    if (x < 0) { return 0 }\n    return x + 1\n}\n',
    }
    sources={p:dict(content=s,file_hash=file_hash(s)) for p,s in codes.items()}
    cases=[dict(test_id='BillingTests.amount',function='total',args=[2],expected=102,requirement_refs=['REQ-UPLOAD'])]
    failures=[dict(test_id='BillingTests.amount',args=[2],actual='104',expected='102',source=dict(log_ref='records/test.log'))]
    binding=dict(task_id='task',baseline_id='b_'+'a'*32,baseline_hash='a'*64,spec_hash='b'*64,
        subject_id='c_'+'c'*32,subject_tree_hash='c'*64)
    return sources,cases,failures,{},binding


def test_confirmed_case_selects_baseline_function_and_bounded_cross_file_source_clues():
    args=inputs();before=copy.deepcopy(args);report=api().build_focus(*args)
    assert report['status']=='PARTIAL' and report['binding']==args[-1]
    assert args==before
    target=report['targets'][0]
    assert target['test_id']=='BillingTests.amount' and target['requirement_refs']==['REQ-UPLOAD']
    assert target['function']=='total' and target['args']==[2] and target['actual']=='104' and target['expected']=='102'
    assert [(f['function'],f['path']) for f in target['locations']]==[('total','src/order.cj'),('fee','src/fee.cj')]
    root,callee=target['locations']
    assert root['coordinate_subject_id']==args[-1]['baseline_id'] and root['start_line']==2 and root['end_line']==4
    assert root['anchors'][0]['line']==3 and root['anchors'][0]['slice']['status']=='UNAVAILABLE'
    assert callee['call_origin']=='LOCAL_SOURCE_INDEX' and callee['anchors'][0]['line']==3
    assert len(callee['anchors'])==2 and '候选' in report['limitations'][0]


def test_unknown_or_unconfirmed_failure_never_uses_log_expression_as_a_guessed_function():
    args=list(inputs());args[2]=[dict(test_id='Unknown.case',input='total(2)',actual='104',expected='102')]
    report=api().build_focus(*args)
    assert report['status']=='UNMAPPED' and report['targets'][0]['locations']==[]
    assert report['targets'][0]['mapping']=='UNMAPPED'


@pytest.mark.parametrize('change',['args','expected','source_hash','graph_source'])
def test_value_or_source_binding_mismatch_is_rejected(change):
    args=list(inputs())
    if change=='args':args[2][0]['args']=[8]
    elif change=='expected':args[2][0]['expected']='1'
    elif change=='source_hash':args[0]['src/order.cj']['file_hash']='f'*64
    else:args[3]['src/order.cj']=dict(source=dict(code='wrong',source_sha256='f'*64))
    with pytest.raises(ValueError):api().build_focus(*args)


def test_recursive_source_clues_terminate_and_source_spans_ignore_comment_braces_and_crlf():
    args=list(inputs());code='package billing\r\n// } func fake(x: Int64): Int64 {\r\npublic func total(x: Int64): Int64 {\r\n /* } return 3 */\r\n if (x > 0) { return total(x - 1) }\r\n return x\r\n}\r\n'
    args[0]={'src/order.cj':dict(content=code,file_hash=file_hash(code))}
    report=api().build_focus(*args);locations=report['targets'][0]['locations']
    assert len(locations)==1 and locations[0]['start_line']==3 and locations[0]['end_line']==7
    assert [a['line'] for a in locations[0]['anchors']]==[5,6]


def test_valid_point_graph_contributes_actual_static_dependencies_without_creating_cross_file_edges():
    args=list(inputs());source=args[0]['src/order.cj']['content'];identity=file_hash(source)
    graph=dict(nodes=[dict(id='param',line=2,label='x'),dict(id='return',line=3,label='fee(x)+101')],edges=[dict(from_='param',to='return')])
    graph['edges']=[{'from':'param','to':'return'}]
    args[3]['src/order.cj']=dict(id='analysis',status='COMPLETE',source=dict(code=source,source_sha256=identity,line_count=4,filename='order.cj'),
        point_graph=dict(status='VALID',source_sha256=identity,graph=graph,raw_ref='observations/sympas_dep_graph.json',raw_sha256='d'*64,graph_sha256='e'*64))
    report=api().build_focus(*args);point=report['targets'][0]['locations'][0]['anchors'][0]['slice']
    assert point['status']=='VALID' and point['node_ids']==['param','return'] and point['lines']==[2,3]
    assert point['origin']=='LOCAL_PDG_BACKWARD' and point['raw_sha256']=='d'*64
    assert report['targets'][0]['locations'][1]['anchors'][0]['slice']['status']=='UNAVAILABLE'


def test_location_and_target_budgets_are_explicit_not_unbounded_context():
    args=list(inputs());args[1]*=10;args[2]*=10
    report=api().build_focus(*args)
    assert len(report['targets'])<=8 and report['truncated'] is True
    for t in report['targets']:
        for f in t['locations']:
            assert len(f['anchors'])<=4 and len(f['source_lines'])<=40


def test_model_projection_is_content_bound_under_16k_and_keeps_full_evidence_unchanged():
    m=api();report=m.build_focus(*inputs());before=copy.deepcopy(report)
    assert hasattr(m,'model_view'),'bounded model focus projection missing'
    for location in report['targets'][0]['locations']:
        for anchor in location['anchors']:
            anchor['slice'].update(node_ids=['node'+str(i)+'x'*100 for i in range(500)],lines=list(range(1,501)),edges=[{'from':'a','to':'b'}]*3000)
    report['targets']*=8;original=copy.deepcopy(report)
    view=m.model_view(report)
    import json
    from nexus.contracts import digest
    assert len(json.dumps(view,ensure_ascii=False).encode())<=16384
    assert view['context_hash']==digest(report) and view['truncated'] is True
    assert report==original and view['targets'][0]['locations'][0]['coordinate_subject_id']==before['binding']['baseline_id']


@pytest.mark.parametrize('case',['unmapped_id','empty_targets_metadata','unmapped_values'])
def test_oversized_unmapped_projection_is_bounded_without_invented_locations(case):
    import json
    from nexus.contracts import digest
    args=list(inputs());args[2]=[dict(test_id='unknown',actual='1',expected='2')]
    report=api().build_focus(*args)
    if case=='unmapped_id':report['targets'][0]['test_id']='unknown-'+'x'*18000
    elif case=='empty_targets_metadata':report.update(targets=[],unavailable_sources={'unavailable':'x'*18000})
    else:report['targets'][0].update(actual='x'*18000,expected='y'*18000)
    original=copy.deepcopy(report)
    view=api().model_view(report)
    assert len(json.dumps(view,ensure_ascii=False).encode())<=16384
    assert view['context_hash']==digest(report) and view['truncated'] is True
    assert not any(target['locations'] for target in view['targets'])
    assert report==original


@pytest.mark.parametrize('expression',['fee(2)','total(99)','total(true)','total(2 + 0)'])
def test_log_call_must_match_confirmed_function_and_literal_input(expression):
    args=list(inputs());args[2][0].pop('args');args[2][0]['expression']=expression
    with pytest.raises(ValueError):api().build_focus(*args)


def test_missing_call_and_input_remains_unmapped_and_cannot_inherit_confirmed_positions():
    args=list(inputs());args[2][0].pop('args')
    report=api().build_focus(*args)
    assert report['status']=='UNMAPPED' and report['targets'][0]['locations']==[]


def test_native_literal_call_allows_spacing_and_negative_zero_but_not_bool_int_coercion():
    args=list(inputs());args[1][0]['args']=[0];args[2][0]['args']=[0];args[2][0]['expression']=' total ( - 0 ) '
    assert api().build_focus(*args)['targets'][0]['mapping']=='CONFIRMED_CASE'
    args[1][0]['args']=[1];args[2][0]['args']=[True];args[2][0]['expression']='total(1)'
    with pytest.raises(ValueError):api().build_focus(*args)


def test_current_native_slice_profile_does_not_invent_local_statement_slices(monkeypatch):
    args=list(inputs())
    for path,item in args[0].items():
        args[3][path]=dict(source=dict(code=item['content'],source_sha256=item['file_hash']),slice_scope='MCP_NATIVE',analysis_profile=8,
            observations=[dict(tool='sympas_slice',status='VALID',data=dict(slices={'v':[2,3]}))])
    module=api()
    monkeypatch.setattr(module,'point_slice',lambda *a:pytest.fail('current native profile traversed PDG locally'))
    report=module.build_focus(*args)
    for target in report['targets']:
        for location in target['locations']:
            for anchor in location['anchors']:
                assert anchor['slice']['status']=='UNAVAILABLE'
                assert anchor['slice']['origin']=='MCP_SYMPAS_SLICE'
                assert '变量' in anchor['slice']['reason']
