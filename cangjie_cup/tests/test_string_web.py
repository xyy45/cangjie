"""Exact String display and owner-bound GET over explicit SDK fixtures."""
import asyncio
from copy import deepcopy
import json
import pytest
from nexus.web.property_view import primitive_text


def test_exact_string_display_preserves_empty_control_unicode_and_large_int64():
    value=dict(initial_state='',before_state='中😀',reference_before='中',expected_state='中a',actual_return='',expected_value='a',context=['',2**63-1,True],args=['中',2**63-2,False],
        left_actual_return='',right_actual_return=chr(0)+'"'+chr(10),left_args=[''],right_args=['中'],steps=[dict(actual_return=None)])
    before=deepcopy(value);shown=primitive_text(value)
    for field in ('initial_state','before_state','reference_before','expected_state','actual_return','expected_value','left_actual_return','right_actual_return'):
        assert shown[field+'_text']==json.dumps(value[field],ensure_ascii=False,separators=(',',':'))
    assert shown['context_text']=='["",9223372036854775807,true]' and shown['args_text']=='["中",9223372036854775806,false]'
    assert shown['left_args_text']=='[""]' and shown['right_args_text']=='["中"]'
    assert 'actual_return_text' not in shown['steps'][0] and value==before


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_string_candidate_get_is_typed_quoted_owner_bound_and_read_only(kind,tmp_path,monkeypatch):
    from nexus.execution.delivery import DeliveryService
    from nexus.web.app import create_app
    from tests.test_web import Loop
    if kind=='sequence':
        from tests.test_string_sequence_services import setup,sdk
        store,ws,c,engine=setup(tmp_path);calls=sdk(monkeypatch,False)
    else:
        from tests.test_string_services import setup,fake_sdk
        store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL';before=len(calls)
    app=create_app(store,Loop(),DeliveryService(store),require_operator=False);app.testing=True;client=app.test_client();client.get('/')
    with client.session_transaction() as session:session['actor_id']='alice'
    field=dict(oracle='exploration',property='properties',relation='relations',sequence='sequences')[kind]
    result=client.get('/api/candidates/'+c.id);assert result.status_code==200
    rendered=result.json[field];assert rendered['state']=='FAIL'
    summary=client.get('/api/tasks/'+c.task_id).json
    assert next(r for r in summary['candidates'] if r['id']==c.id)[field]['state']=='FAIL'
    f=rendered['failures'][0]
    if kind=='relation':assert f['left_actual_return_text']=='"collision"'
    elif kind=='sequence':assert f['steps'][-1]['actual_return_text']==json.dumps(f['steps'][-1]['actual_return'],ensure_ascii=False)
    else:assert f['actual_return_text']=='""'
    other=app.test_client();other.get('/');assert other.get('/api/candidates/'+c.id).status_code==404
    (store.root/report['batches'][0]['log_ref']).write_text('changed copied fixture log')
    invalid=client.get('/api/candidates/'+c.id);assert invalid.status_code==200 and invalid.json[field]['state']=='UNKNOWN' and invalid.json['check_set_hash'] is None
    assert len(calls)==before
