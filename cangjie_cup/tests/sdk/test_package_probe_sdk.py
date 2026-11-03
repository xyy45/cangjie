"""Actual compiler graph/XML/V5 observation over controller-derived probes."""
import asyncio,time
import pytest
from nexus.execution.package_validation import scan,run_scoped_tests,tool_identity
from nexus.repair import scoped_probe,primitive_trace,property_trace,relation_trace,sequence_trace
from nexus.repair.package_evidence import capture,rebuild
from tests.test_package_probe_material import prepared,TOKEN
from tests.sdk.test_package_reports_sdk import save

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('mode',['oracle','single','relation','sequence'])
def test_derived_probe_executes_real_four_model_observations_with_complete_xml(tmp_path,mode):
    files,signature,contract,items=prepared(mode)
    derived=scoped_probe.prepare(files,signature,TOKEN,mode,items,contract=contract)
    root=tmp_path/'project';root.mkdir()
    for name,raw in derived['files'].items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    save(tmp_path,'material',{k:v for k,v in derived.items() if k!='files'})
    scanned=asyncio.run(scan(root,derived['scan_index'],deadline=time.monotonic()+60,private_root=tmp_path));save(tmp_path,'scans',scanned)
    assert scanned['state']=='PASS',scanned
    remaining=2*1024*1024-sum(len(s['stdout'])+len(s['stderr']) for s in scanned['scans'])
    executed=asyncio.run(run_scoped_tests(root,expected=derived['case_ids'],deadline=time.monotonic()+60,private_root=tmp_path,output_limit=remaining))
    save(tmp_path,'test',executed);assert executed['parsed']['state']=='PASS',executed
    (tmp_path/'records').mkdir();proof=capture(tmp_path,project=root,index=derived['scan_index'],scanned=scanned,execution=executed)
    rebuilt=rebuild(tmp_path,project=root,index=derived['scan_index'],evidence=proof,expected=derived['case_ids'],tools=tool_identity())
    assert rebuilt==executed['parsed'];save(tmp_path,'package-evidence',proof)
    log=executed['stdout'].decode();args=(TOKEN,log,executed['exit_code'],executed['problem'])
    if mode=='oracle':result=primitive_trace.read(signature,items,TOKEN,mode,log,executed['exit_code'],executed['problem'],version=5)
    elif mode=='single':result=property_trace.interpret(contract,items,*args)
    elif mode=='relation':result=relation_trace.interpret(contract,items,*args)
    else:result=sequence_trace.interpret(contract,items,*args)
    save(tmp_path,'business-observations',result)
    assert result['state']=='PASS',result
