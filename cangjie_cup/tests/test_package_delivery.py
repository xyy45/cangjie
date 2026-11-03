"""Delivery rechecks scoped originals; subprocess observations are explicit fixtures."""
import hashlib,uuid
from types import SimpleNamespace
import pytest
from nexus.contracts import CheckResult,CandidateRecord,digest,source_manifest
from nexus.store import RunStore
from nexus.execution.workspace import WorkspaceStore
from nexus.execution.delivery import DeliveryService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.execution.package_validation import tool_identity
from nexus.repair.package_evidence import capture
from tests.test_package_verifier import evidence_fixture
from tests.test_package_reports import IDS


def test_scoped_delivery_gate_rebuilds_xml_before_approving_even_without_optional_rules(tmp_path,monkeypatch):
    root,index,proof=evidence_fixture(tmp_path,monkeypatch,passed=True)
    store=RunStore(tmp_path);task=store.create_task('b_'+'a'*32,'scoped delivery fixture',['src/order.cj'])
    identity=digest(source_manifest(root));candidate=SimpleNamespace(id='c_'+'b'*32,task_id=task.id,tree_hash=identity)
    store.append_record(task.id,'candidate',CandidateRecord(id=candidate.id,task_id=task.id,baseline_hash=identity,
        edits=[dict(path='src/order.cj',before_hash=identity,content=(root/'src/order.cj').read_bytes().decode())],
        tree_hash=identity,diff_ref='records/fixture.diff',attempt=1).model_dump())
    monkeypatch.setattr(WorkspaceStore,'candidate',lambda *_:candidate)
    monkeypatch.setattr(CangjieVerifier,'identity',lambda *_:(root,identity,'fixture-plan'))
    monkeypatch.setattr(CangjieVerifier,'_scoped_context',lambda *_:dict(project=root,index=index,expected=IDS))
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.property_service import PropertyService
    from nexus.repair.relation_service import RelationService
    from nexus.repair.sequence_service import SequenceService
    for cls in (ExplorationService,PropertyService,RelationService,SequenceService):monkeypatch.setattr(cls,'verify',lambda *_:None)
    tools=tool_identity();toolchain=digest({'cjc':tools['bin/cjc'],'cjpm':tools['tools/bin/cjpm']})
    scanned={**proof,'source_before':proof['input_manifest'],'source_after':proof['source_after_scan'],
        'tool_before':tools,'tool_after':tools,'state':'PASS','diagnostics':'','scans':[]}
    for item in proof['scans']:
        scanned['scans'].append({**item,'stdout':(tmp_path/item['stdout']['ref']).read_bytes(),'stderr':(tmp_path/item['stderr']['ref']).read_bytes()})
    build_proof=capture(tmp_path,project=root,index=index,scanned=scanned)
    for kind,package_proof in (('build',build_proof),('test',proof)):
        uid=uuid.uuid4().hex;log=b'cjpm build success' if kind=='build' else (tmp_path/proof['test']['stdout']['ref']).read_bytes()
        result=CheckResult(id=uid,subject_id=candidate.id,tree_hash=identity,plan_hash='fixture-plan',state='PASS',exit_code=0,kind=kind,
            argv=['cjpm','build','-V'] if kind=='build' else ['cjpm','test'],working_root='.',toolchain_hash=toolchain,
            execution_argv=[['cjpm','build','-V']] if kind=='build' else proof['test']['execution_argv'],
            counts={} if kind=='build' else dict(total=2,passed=2,failed=0,errors=0,skipped=0),
            case_results={} if kind=='build' else dict.fromkeys(IDS,'PASS'),diagnostics=log.decode(),package_evidence=package_proof,
            log_ref='records/'+uid+'.log',report_ref='records/'+uid+'.report.json')
        (tmp_path/result.log_ref).write_bytes(log);(tmp_path/result.report_ref).write_text(result.model_dump_json())
        store.append_record(task.id,'check',result.model_dump())
    delivery=DeliveryService(store);assert len(delivery.check_set_hash(candidate.id))==64
    xml=next(iter(proof['test']['reports'].values()))
    (tmp_path/xml['ref']).write_bytes(b'<tampered/>')
    with pytest.raises(ValueError):delivery.check_set_hash(candidate.id)
