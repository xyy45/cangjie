"""V5 sequence protocol fixtures, explicitly not live SDK results."""
from copy import deepcopy
import pytest

from nexus.repair import sequences,sequence_trace,scoped_trace,scoped_values
from tests.test_package_contracts import contract,canonical
from tests.test_object_contracts import state
from tests.test_package_material import NONCE


def model():
    raw,sig=contract(sequences);sig['params'][2]['type']='Array<Int64>'
    raw['domains']['label']={'values':[[],[1,2]]}
    return sequences.validate_contract(raw,sig,[])


def trace():
    return dict(initial_state=canonical(state(0)),context=[[1,2]],steps=[dict(operation_id='OP-FLIP',args=[0,[1,2]]) for _ in range(3)])


def fixture(actual=(1,0,1),*,before=None,end=None):
    c=model();kind=c['signature']['return_type'];identity=scoped_trace.case_ids(c['signature'],1,NONCE,'sequence')[0]
    package,cls,_=identity.rsplit('.',2)
    text='EXPLICIT V5 SEQUENCE FIXTURE\nTP: '+package+', RESULT:\n TCS: '+cls+', RESULT:\n [ PASSED ] CASE: case0 (1 ns)\n STDOUT:\n'
    for i,value in enumerate(actual):
        previous=0 if i==0 else actual[i-1]
        if before and i in before:previous=before[i]
        text+=' '+scoped_values.SEQUENCE+NONCE+'|'+identity+'|step'+str(i)+'|'+kind+'|'+scoped_values.encode(canonical(state(previous)),kind,c['signature']['types'])+'|'+scoped_values.encode(canonical(state(value)),kind,c['signature']['types'])+'\n'
    text+=' '+scoped_values.END+NONCE+'|'+identity+'|'+str(len(actual))+'|'+(end or ('COMPLETE' if len(actual)==3 else 'MODEL_MISMATCH'))+'\n'
    return text+'Summary: TOTAL: 1 PASSED: 1, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'


def test_complete_v5_object_state_and_array_context_path():
    result=sequence_trace.interpret(model(),[trace()],NONCE,fixture(),0,None)
    assert result['state']=='PASS' and result['observed_calls']==3 and result['unexecuted_calls']==0
    path=result['observations'][0]
    assert path['test_id'].startswith('bench.nexus_verify_') and path['context']==[[1,2]]
    assert [s['before_state'] for s in path['steps']]==[canonical(state(0)),canonical(state(1)),canonical(state(0))]


def test_v5_first_model_mismatch_stops_and_retains_real_prefix():
    text=fixture((1,2));result=sequence_trace.interpret(model(),[trace()],NONCE,text,0,None)
    assert result['state']=='FAIL' and result['observed_calls']==2 and result['unexecuted_calls']==1
    failure=result['failures'][0]
    assert failure['step_index']==1 and failure['actual_return']==canonical(state(2)) and failure['expected_state']==canonical(state(0))
    assert failure['test_id'].startswith('bench.nexus_verify_')
    assert text[failure['source']['start_char']:failure['source']['end_char']].strip().startswith(scoped_values.SEQUENCE)


@pytest.mark.parametrize('change',['wrong-before','after-mismatch','fake-complete','missing-end','extra-end','old-protocol','wrong-package','short-id','wrong-nonce','stderr','exit'])
def test_v5_sequence_cannot_fabricate_state_chaining_or_completion(change):
    text=fixture();code=0
    if change=='wrong-before':text=fixture(before={1:0})
    elif change=='after-mismatch':text=fixture((1,2,3),end='MODEL_MISMATCH')
    elif change=='fake-complete':text=fixture((1,2),end='COMPLETE')
    elif change=='missing-end':text='\n'.join(l for l in text.splitlines() if not l.strip().startswith(scoped_values.END))+'\n'
    elif change=='extra-end':text=text.replace('Summary:',' '+next(l.strip() for l in text.splitlines() if l.strip().startswith(scoped_values.END))+'\nSummary:')
    elif change=='old-protocol':text=text.replace('NEXUS_SEQUENCE_V5|','NEXUS_SEQUENCE_V4|')
    elif change=='wrong-package':text=text.replace('TP: bench.nexus_verify_'+NONCE,'TP: bench.other')
    elif change=='short-id':text=text.replace('|'+scoped_trace.case_ids(model()['signature'],1,NONCE,'sequence')[0]+'|','|case0|')
    elif change=='wrong-nonce':text=text.replace('|'+NONCE+'|','|'+'f'*16+'|')
    elif change=='stderr':text=text.replace('STDOUT:','STDERR:')
    else:code=1
    result=sequence_trace.interpret(model(),[trace()],NONCE,text,code,None)
    assert result['state']=='UNKNOWN' and result['observations']==[]


def test_v5_sequence_model_cannot_use_legacy_protocol():
    c=model();c['version']=4
    with pytest.raises(ValueError):sequence_trace.interpret(c,[trace()],NONCE,fixture(),0,None)
