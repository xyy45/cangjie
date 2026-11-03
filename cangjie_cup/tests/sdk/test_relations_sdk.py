"""Pinned Cangjie SDK evidence for two independent calls; no external requests."""
import asyncio
import json

import pytest

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.runner import run_command
from nexus.execution.workspace import WorkspaceStore
from nexus.repair import oracle,relations,relation_trace
from nexus.repair.relation_service import RelationService
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_relations import raw,EXAMPLES

pytestmark=pytest.mark.sdk
TOKEN='0123456789abcdef'


def execute(root,contract,pairs,source):
    project=root/'project';(project/'src').mkdir(parents=True)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench\n'+source)
    (project/'src/relation_observations_test.cj').write_bytes(relation_trace.harness(contract,pairs,'bench',TOKEN))
    before=source_manifest(project);commands=[]
    (root/'verification-input.json').write_text(json.dumps(dict(contract=contract,pairs=pairs,token=TOKEN,package='bench',project_manifest=before),sort_keys=True))
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/'sdk.log').write_text(log)
    result=relation_trace.interpret(contract,pairs,TOKEN,log,code,problem)
    (root/'verification-result.json').write_text(json.dumps(dict(result=result,exit_code=code,problem=problem,execution_argv=commands),sort_keys=True))
    assert result['execution_state']=='PASS',(code,problem,log[-3000:])
    assert commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    assert source_manifest(project)==before
    assert result['counts']['total']==len(pairs)*2 and len(result['observations'])==len(pairs)
    for observation in result['observations']:assert observation['left']['test_id']!=observation['right']['test_id']
    return result


@pytest.mark.parametrize('kind',['Bool','LOW','zero','128-calls'])
def test_sdk_pair_protocol_types_identical_inputs_and_maximum_case_budget(tmp_path,kind):
    primitive='Bool' if kind=='Bool' else 'Int64'
    signature=dict(name='identity',params=[] if kind=='zero' else [dict(name='x',type=primitive)],return_type=primitive)
    domains={} if kind=='zero' else {'x':{} if primitive=='Bool' else dict(min=oracle.LOW,max=oracle.LOW+1) if kind=='LOW' else dict(min=0,max=1000000)}
    source=dict(version=1,kind='relation',function='identity',domains=domains,relations=[dict(id='REL-IDENTITY',text='两个返回均保持各自输入',precondition='True',
        assertion='left_result == 3 and right_result == 3' if kind=='zero' else 'left_result == left_arg0 and right_result == right_arg0')],seed=0,max_pairs=64,excluded_inputs=[])
    contract=relations.validate_contract(source,signature,[]);pairs=relations.generate_pairs(contract)['pairs']
    code='public func identity(): Int64 { return 3 }\n' if kind=='zero' else 'public func identity(x: '+primitive+'): '+primitive+' { return x }\n'
    result=execute(tmp_path,contract,pairs,code);assert result['state']=='PASS'
    same=[o for o in result['observations'] if o['left']['args']==o['right']['args']]
    assert same and all(o['left']['actual_return']==o['right']['actual_return'] for o in same)
    if kind=='128-calls':assert len(pairs)==64 and result['counts']['passed']==128
    if kind=='LOW':assert any(o['left']['actual_return']==oracle.LOW for o in result['observations'])


def system(root,relation):
    store=RunStore(root);uploads=UploadService(store)
    bad='package bench\npublic func compute(quantity: Int64, price: Int64, promotion: Bool): Int64 {\n if (quantity >= 10) { return 0 }\n return quantity * price\n}\n'
    good=bad.replace(' if (quantity >= 10) { return 0 }\n','')
    wrapper=b'package bench\npublic func amount(quantity: Int64, price: Int64, promotion: Bool): Int64 { return compute(quantity, price, promotion) }\n'
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/math.cj':bad.encode(),'src/amount.cj':wrapper}
    draft=uploads.prepare_project('relation-pair',None,'固定正价且无优惠，增加数量总额不得下降',actor_id='alice',request_key='one',entries=files)
    uploads.confirm(draft['id'],expected_version=1,function='amount',examples_json=json.dumps(EXAMPLES),relations_json=json.dumps(relation),allowed_paths=['src/math.cj'],consent=True,actor_id='alice')
    source=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);rd=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(rd['id'],dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    def candidate(fixed=False):
        proposal=CandidateProposal(edits=[dict(path='src/math.cj',before_hash=file_hash(bad),content=(good if fixed else bad)+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD'])
        return ws.apply_candidate(store.get_task(task.id),proposal)
    return store,ws,task,candidate


def test_sdk_two_file_public_pass_relation_fail_then_reference_pass_with_retained_regressions(tmp_path):
    store,ws,task,apply=system(tmp_path,raw());engine=RelationService(store);verifier=CangjieVerifier(tmp_path,task.id)
    first=apply();assert asyncio.run(verifier.build(first.id)).state=='PASS';assert asyncio.run(verifier.test(first.id)).state=='PASS'
    before=source_manifest(ws.subject_path(first.id));failed=asyncio.run(engine.run(first.id))
    assert failed['state']=='FAIL' and failed['public_test_state']=='PASS' and failed['observed_calls']>=64
    assert failed['failures'][0]['left_actual_return']>failed['failures'][0]['right_actual_return']
    assert source_manifest(ws.subject_path(first.id))==before
    second=apply(True);assert asyncio.run(verifier.build(second.id)).state=='PASS';assert asyncio.run(verifier.test(second.id)).state=='PASS'
    passed=asyncio.run(engine.run(second.id));assert passed['state']=='PASS' and passed['regression_pairs']>0
    for report in (failed,passed):
        assert engine.verify(report['candidate_id'])==report
        for batch in report['batches']:
            assert {'src/math.cj','src/amount.cj'}<=set(batch['project_manifest'])
            text=(store.root/batch['log_ref']).read_text()
            assert 'NEXUS_EXECUTION_PHASE' in text and 'NEXUS_RELATION_V1|' in text and 'FIXTURE' not in text


def test_sdk_coordinated_shrink_really_reexecutes_both_sides_and_preserves_fixed_price_guard(tmp_path):
    source=raw();source['relations'][0]['precondition']+=' and left_arg1 >= 37'
    store,ws,task,apply=system(tmp_path,source);engine=RelationService(store);verifier=CangjieVerifier(tmp_path,task.id);candidate=apply()
    assert asyncio.run(verifier.build(candidate.id)).state=='PASS';assert asyncio.run(verifier.test(candidate.id)).state=='PASS'
    report=asyncio.run(engine.run(candidate.id));assert report['state']=='FAIL' and report['shrink_pairs']>0
    initial=min(report['batches'][0]['result']['failures'],key=lambda f:(sum(abs(int(v)) for side in ('left_args','right_args') for v in f[side]),tuple(int(v) for side in ('left_args','right_args') for v in f[side]),f['relation_id']))
    final=report['failures'][0]
    assert 37<=final['left_args'][1]==final['right_args'][1]<initial['left_args'][1]
    assert final['left_actual_return']>final['right_actual_return']
    assert all(b['result']['execution_state']=='PASS' for b in report['batches'])
    assert engine.verify(candidate.id)==report
