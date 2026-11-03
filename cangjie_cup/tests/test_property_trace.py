"""Pinned log format fixtures; real execution is checked in SDK tests."""
import asyncio
import importlib
import importlib.util

import pytest

from nexus.repair import properties
from tests.test_property_contract import raw,SIG,EXAMPLES

TOKEN='0123456789abcdef'
CLASS='NexusProperties'+TOKEN
CASES=[[1000,900,200],[1000,800,100]]


def api():
    assert importlib.util.find_spec('nexus.repair.property_trace') is not None,'property observation protocol missing'
    return importlib.import_module('nexus.repair.property_trace')


def log(values=('1100','900')):
    text='TP: bench, RESULT:\n    TCS: '+CLASS+', RESULT:\n'
    for i,value in enumerate(values):
        text+=f'    [ PASSED ] CASE: case{i} (1 ns)\n    STDOUT:\n    NEXUS_PROPERTY_V1|{TOKEN}|case{i}|Int64|{value}\n'
    return text+'Summary: TOTAL: 2 PASSED: 2, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'


def test_execution_pass_is_not_property_pass_and_actual_returns_are_typed():
    module=api();contract=properties.validate_contract(raw(),SIG,EXAMPLES)
    source=module.harness(contract,CASES,'bench',TOKEN).decode()
    assert '(Int64, Int64, Int64) -> Int64 = refundState' in source
    assert '__nexusTarget'+TOKEN+'(1000, 900, 200)' in source and 'NEXUS_PROPERTY_V1|' in source
    result=module.interpret(contract,CASES,TOKEN,log(),0,None)
    assert result['execution_state']=='PASS' and result['state']=='FAIL'
    assert [o['actual_return'] for o in result['observations']]==[1100,900]
    assert len(result['failures'])==2
    assert all(p['generated']==2 for p in result['per_property'])
    assert all(f['test_id']==CLASS+'.case0' and f['actual_return']==1100 for f in result['failures'])
    assert module.interpret(contract,CASES,TOKEN,log(('900','900')),0,None)['state']=='PASS'


@pytest.mark.parametrize('change',['missing','duplicate','wrong-token','wrong-case','wrong-type','overflow','float','leading-zero','extra-before-suite','outside-stdout','truncated','sdk-failed','wrong-exit','problem'])
def test_incomplete_or_mismatched_observations_are_unknown(change):
    module=api();contract=properties.validate_contract(raw(),SIG,EXAMPLES);text=log();code=0;problem=None
    marker=f'NEXUS_PROPERTY_V1|{TOKEN}|case0|Int64|1100'
    if change=='missing':text=text.replace(marker,'')
    elif change=='duplicate':text=text.replace(marker,marker+'\n    '+marker)
    elif change=='wrong-token':text=text.replace('|'+TOKEN+'|','|'+'f'*16+'|',1)
    elif change=='wrong-case':text=text.replace('|case0|','|case1|')
    elif change=='wrong-type':text=text.replace('|Int64|1100','|Bool|true')
    elif change=='overflow':text=text.replace('|Int64|1100','|Int64|9223372036854775808')
    elif change=='float':text=text.replace('|Int64|1100','|Int64|1100.0')
    elif change=='leading-zero':text=text.replace('|Int64|1100','|Int64|01100')
    elif change=='extra-before-suite':text=marker+'\n'+text
    elif change=='outside-stdout':text=text.replace('STDOUT:','OTHER:',1)
    elif change=='truncated':text=text.rsplit('Summary:',1)[0]
    elif change=='sdk-failed':text=text.replace('PASSED: 2','PASSED: 1').replace('FAILED: 0','FAILED: 1').replace('cjpm test success','Error: cjpm test failed');code=1
    elif change=='wrong-exit':code=1
    else:problem='TimeoutError'
    result=module.interpret(contract,CASES,TOKEN,text,code,problem)
    assert result['state']=='UNKNOWN' and result['failures']==[]


def test_boolean_return_and_signed_int64_minimum_observations():
    module=api();sig=dict(name='flag',params=[dict(name='x',type='Bool')],return_type='Bool')
    contract=properties.validate_contract(dict(version=1,kind='single',function='flag',domains={'x':{}},properties=[
        dict(id='PROP-SAME',text='保持Bool',precondition='True',assertion='result == arg0')],seed=0,max_cases=16,excluded_inputs=[]),sig,[])
    text=log(('false','true')).replace('|Int64|','|Bool|')
    assert module.interpret(contract,[[False],[True]],TOKEN,text,0,None)['state']=='PASS'
    assert module.interpret(contract,[[False],[True]],TOKEN,text.replace('|Bool|true','|Bool|1'),0,None)['state']=='UNKNOWN'
    signature=dict(name='identity',params=[dict(name='x',type='Int64')],return_type='Int64')
    value=dict(version=1,kind='single',function='identity',domains={'x':dict(min=-(2**63),max=-(2**63)+1)},properties=[
        dict(id='PROP-SAME',text='保持整数',precondition='True',assertion='result == arg0')],seed=0,max_cases=16,excluded_inputs=[])
    contract=properties.validate_contract(value,signature,[])
    values=[-(2**63),-(2**63)+1]
    assert module.interpret(contract,[[v] for v in values],TOKEN,log(tuple(map(str,values))),0,None)['state']=='PASS'


def test_harness_cannot_execute_reserved_or_duplicate_inputs_or_interpolate_source():
    module=api();value=raw();value['excluded_inputs']=[CASES[0]];contract=properties.validate_contract(value,SIG,EXAMPLES)
    for cases,package,token in [(CASES,'bench',TOKEN),([CASES[1],CASES[1]],'bench',TOKEN),([CASES[1]],'bench;import evil',TOKEN),([CASES[1]],'bench','"bad')]:
        with pytest.raises(ValueError):module.harness(contract,cases,package,token)


def test_runner_all_output_is_closed_and_records_actual_phase_argv(tmp_path,monkeypatch):
    from nexus.execution import runner
    project=tmp_path/'project';directory=project/'target/release/unittest_bin';directory.mkdir(parents=True)
    binary=directory/'fixture';binary.write_bytes(b'\xcf\xfa\xed\xfeexplicit-not-executed-fixture');binary.chmod(0o700)
    actual=[]
    async def phase(project,argv,*args,**kwargs):actual.append(list(argv));return 0,'fixture phase\n',None
    monkeypatch.setattr(runner,'_run_phase',phase)
    for mode in ('failures','all'):
        actual.clear();recorded=[]
        code,text,problem=asyncio.run(runner.run_command(project,['cjpm','test'],test_output=mode,execution_argv=recorded))
        assert code==0 and problem is None and recorded==actual
        assert actual==[['cjpm','test','--no-run'],['cjpm','test','--skip-build']+(['--show-all-output'] if mode=='all' else [])]
    for mode in ('verbose',True,None,[],{}):
        with pytest.raises(ValueError):asyncio.run(runner.run_command(project,['cjpm','test'],test_output=mode))
    with pytest.raises(ValueError):asyncio.run(runner.run_command(project,['cjpm','build','-V'],test_output='all'))
    with pytest.raises(ValueError):asyncio.run(runner.run_command(project,['cjpm','test','--arbitrary'],test_output='all'))


def test_shrink_scope_requires_target_property_without_claiming_all_coverage():
    module=api();contract=properties.validate_contract(raw(),SIG,EXAMPLES)
    # This legal refund does not satisfy PROP-INVALID's precondition; a bad
    # negative return still violates PROP-RANGE and is a useful shrink probe.
    text=log(('-1','900'))
    cases=[[1000,800,100],[1000,800,200]]
    assert module.interpret(contract,cases,TOKEN,text,0,None)['state']=='UNKNOWN'
    scoped=module.interpret(contract,cases,TOKEN,text,0,None,required_ids=['PROP-RANGE'])
    assert scoped['state']=='FAIL' and scoped['per_property'][1]['observed']==0
    for ids in ([],['UNKNOWN'],['PROP-RANGE','PROP-RANGE']):
        with pytest.raises(ValueError):module.interpret(contract,cases,TOKEN,text,0,None,required_ids=ids)
