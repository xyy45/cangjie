"""Exact Array display and owner-bound read-only queries over SDK log fixtures."""
import asyncio
from copy import deepcopy
import json
import pytest
from nexus.web.property_view import primitive_text


def test_array_exact_text_keeps_nested_arguments_empty_states_and_int64():
    low,high=-(1<<63),(1<<63)-1
    value=dict(initial_state=[],before_state=[low,high],reference_before=[1,2],expected_state=[2,1],actual_return=[],expected_value=[high],
               context=[[low],"中",True],args=[[low,high],False,high],left_actual_return=[],right_actual_return=[high],left_args=[[]],right_args=[[low]],
               steps=[dict(args=[[high]],before_state=[],actual_return=[high])])
    original=deepcopy(value);shown=primitive_text(value)
    for name in ('initial_state','before_state','reference_before','expected_state','actual_return','expected_value','context','args','left_actual_return','right_actual_return','left_args','right_args'):
        assert shown[name+'_text']==json.dumps(value[name],ensure_ascii=False,separators=(',',':'))
    assert shown['steps'][0]['args_text']=='[[9223372036854775807]]'
    assert shown['steps'][0]['before_state_text']=='[]' and shown['steps'][0]['actual_return_text']=='[9223372036854775807]'
    assert value==original


@pytest.mark.parametrize('invalid',[[True],[1.0],[[1]],list(range(17)),[1<<63],None])
def test_array_display_does_not_grant_canonical_primitive_text_to_invalid_arrays(invalid):
    result=primitive_text(dict(actual_return=invalid,args=[invalid]))
    assert 'actual_return_text' not in result and 'args_text' not in result


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_get_exact_values_and_current_unknown_without_execution(kind,tmp_path,monkeypatch):
    from tests.test_array_services import setup,fake_sdk
    from tests.test_web import Loop
    from nexus.execution.delivery import DeliveryService
    from nexus.web.app import create_app
    store,ws,task,apply,engine=setup(tmp_path,kind,array_return=kind=='oracle');calls=fake_sdk(monkeypatch,kind);candidate=apply()
    report=asyncio.run(engine.run(candidate.id));assert report['state']=='FAIL';before=len(calls)
    app=create_app(store,Loop(),DeliveryService(store),require_operator=False);app.testing=True
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:session['actor_id']='alice'
    field=dict(oracle='exploration',property='properties',relation='relations',sequence='sequences')[kind]
    response=client.get('/api/candidates/'+candidate.id);assert response.status_code==200
    shown=response.json[field];assert shown['state']=='FAIL'
    failure=shown['failures'][0]
    if kind=='sequence':
        assert failure['initial_state_text']==json.dumps(failure['initial_state'],separators=(',',':'))
        for step in failure['steps']:
            assert step['before_state_text']==json.dumps(step['before_state'],separators=(',',':'))
            assert step['actual_return_text']==json.dumps(step['actual_return'],separators=(',',':'))
    elif kind=='relation':
        assert failure['left_args_text']==json.dumps(failure['left_args'],separators=(',',':'))
        assert failure['right_args_text']==json.dumps(failure['right_args'],separators=(',',':'))
    else:
        assert failure['args_text']==json.dumps(failure['args'],separators=(',',':'))
        assert failure['actual_return_text']==json.dumps(failure['actual_return'],separators=(',',':'))
    other=app.test_client();other.get('/');assert other.get('/api/candidates/'+candidate.id).status_code==404
    path=store.root/report['batches'][0]['log_ref'];raw=path.read_bytes();path.write_bytes(b'changed copied Array fixture log')
    try:
        detail=client.get('/api/candidates/'+candidate.id).json
        summary=client.get('/api/tasks/'+task.id).json
        assert detail[field]['state']=='UNKNOWN' and detail['check_set_hash'] is None
        assert next(c for c in summary['candidates'] if c['id']==candidate.id)[field]['state']=='UNKNOWN'
    finally:path.write_bytes(raw)
    assert client.get('/api/candidates/'+candidate.id).json[field]['state']=='FAIL' and len(calls)==before
