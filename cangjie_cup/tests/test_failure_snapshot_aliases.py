"""Pure log fixtures: failure summaries and observations must own their arrays."""
from copy import deepcopy
import pytest
from nexus.repair import oracle,sequence_trace
from nexus.repair.exploration import ExplorationService
from tests.test_array_trace import TOKEN,fixture,model,sequence_fixture


def oracle_result():
    signature=dict(name='identity',params=[dict(name='x',type='Array<Int64>')],return_type='Array<Int64>')
    contract=oracle.validate_contract(dict(version=4,function='identity',domains=dict(x=dict(values=[[1],[2]])),expression='x',seed=7,max_cases=16,excluded_inputs=[]),signature,[])
    inputs=[[[1]]];original=deepcopy(inputs)
    engine=ExplorationService.__new__(ExplorationService)
    engine.read_record=lambda *args:fixture('oracle',['a:1:9']).encode()
    result=engine.string_interpret(dict(inputs=inputs,token=TOKEN,log_ref='explicit-fixture.log',log_sha256='fixture',exit_code=0,problem=None),contract)
    assert result['state']=='FAIL' and inputs==original
    return result


@pytest.mark.parametrize('field',['args','actual_return'])
@pytest.mark.parametrize('direction',['failure_to_observation','observation_to_failure'])
def test_oracle_failure_summary_and_observation_arrays_are_independent(field,direction):
    result=oracle_result();failure=result['failures'][0];observation=result['observations'][0]
    source,target=(failure,observation) if direction=='failure_to_observation' else (observation,failure)
    before=deepcopy(target);changed=source[field][0] if field=='args' else source[field];changed.append(99)
    assert target==before


@pytest.mark.parametrize('field',['before_state','actual_return','expected_state'])
@pytest.mark.parametrize('direction',['failure_to_observation','observation_to_failure'])
def test_sequence_failure_summary_and_observed_last_step_arrays_are_independent(field,direction):
    contract,trace=model();before_trace=deepcopy(trace)
    log=sequence_fixture([[([1,2],[2,1]),([2,1],[2,1])]],[(2,'MODEL_MISMATCH')])
    result=sequence_trace.interpret(contract,[trace],TOKEN,log,0,None)
    assert result['state']=='FAIL' and trace==before_trace
    failure=result['failures'][0];observation=result['observations'][0]['steps'][-1]
    source,target=(failure,observation) if direction=='failure_to_observation' else (observation,failure)
    before=deepcopy(target);prefix=deepcopy(failure['steps']);source[field].append(99)
    assert target==before
    assert failure['steps']==prefix
