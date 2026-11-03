"""Real SDK combined non-first Array state, String context and candidate history."""
import json
import pytest
from tests.sdk import test_array_loop_sdk as loop

pytestmark=pytest.mark.sdk


def test_array_public_pass_independent_context_state_history(tmp_path,monkeypatch):
    original=loop.scenario
    def contextual(kind):
        data=original(kind)
        assert kind=='sequence'
        old='advance(state: Array<Int64>, quantity: Int64)'
        new='advance(quantity: Int64, state: Array<Int64>, label: String)'
        data['files'][data['path']]=data['files'][data['path']].replace(old.encode(),new.encode())
        data['fixed']=data['fixed'].replace(old,new)
        data['model']['domains']['label']={'values':['a','中']}
        data['model']['context_params']=['label']
        data['model']['operations'][0]['args'].append({'context':'label'})
        for case in data['examples']:
            state,quantity=case['args'];case['args']=[quantity,state,'中']
        return data
    monkeypatch.setattr(loop,'scenario',contextual)
    loop.test_array_public_pass_independent_failure_reference_fix_and_all_history(tmp_path,'sequence')
    failed=json.loads((tmp_path/'defect-report.json').read_bytes())
    passed=json.loads((tmp_path/'fixed-report.json').read_bytes())
    assert passed['regression_traces']>0
    for report in (failed,passed):
        for batch in report['batches']:
            for path in batch['result']['observations']:
                assert path['context'] in (['a'],['中'])
                previous=path['initial_state']
                for step in path['steps']:
                    assert step['args'][1]==previous==step['before_state']
                    assert step['args'][2]==path['context'][0]
                    previous=step['actual_return']
