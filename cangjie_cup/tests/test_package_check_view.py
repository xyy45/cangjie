"""Candidate display rechecks scoped originals, using explicit SDK/XML fixtures."""
import uuid

from nexus.contracts import CandidateRecord, CheckResult, digest, source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.execution.package_validation import tool_identity
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from nexus.web.app import create_app
from tests.test_package_reports import IDS
from tests.test_package_verifier import evidence_fixture


def test_candidate_check_display_downgrades_tampered_xml_before_showing_pass(tmp_path, monkeypatch):
    root, index, proof = evidence_fixture(tmp_path, monkeypatch, passed=True)
    store = RunStore(tmp_path)
    task = store.create_task('b_'+'a'*32, 'Scoped display fixture', ['src/order.cj'])
    tree = digest(source_manifest(root))
    candidate = CandidateRecord(id='c_'+'b'*32, task_id=task.id, baseline_hash=tree,
        edits=[dict(path='src/order.cj', before_hash=tree, content=(root/'src/order.cj').read_bytes().decode())],
        tree_hash=tree, diff_ref='records/fixture.diff', attempt=1)
    store.append_record(task.id, 'candidate', candidate.model_dump())
    monkeypatch.setattr(WorkspaceStore, 'candidate', lambda *_: candidate)
    monkeypatch.setattr(WorkspaceStore, 'diff', lambda *_: 'EXPLICIT FIXTURE DIFF')
    monkeypatch.setattr(CangjieVerifier, 'identity', lambda *_: (root, tree, 'fixture-plan'))
    monkeypatch.setattr(CangjieVerifier, '_scoped_context', lambda *_: dict(project=root, index=index, expected=IDS))
    tools = tool_identity()
    identity = uuid.uuid4().hex
    log = (tmp_path/proof['test']['stdout']['ref']).read_bytes()
    check = CheckResult(id=identity, subject_id=candidate.id, tree_hash=tree, plan_hash='fixture-plan', state='PASS', exit_code=0, kind='test',
        argv=['cjpm', 'test'], working_root='.', toolchain_hash=digest(dict(cjc=tools['bin/cjc'], cjpm=tools['tools/bin/cjpm'])),
        execution_argv=proof['test']['execution_argv'], counts=dict(total=2, passed=2, failed=0, errors=0, skipped=0),
        case_results=dict.fromkeys(IDS, 'PASS'), diagnostics=log.decode(), package_evidence=proof,
        log_ref='records/'+identity+'.log', report_ref='records/'+identity+'.report.json')
    (tmp_path/check.log_ref).write_bytes(log)
    (tmp_path/check.report_ref).write_text(check.model_dump_json())
    store.append_record(task.id, 'check', check.model_dump())
    app = create_app(store, RepairLoop(store), DeliveryService(store), require_operator=False)
    web = app.test_client()
    web.get('/')
    before = web.get('/api/candidates/'+candidate.id)
    assert before.status_code == 200 and before.json['checks'][-1]['state'] == 'PASS'
    xml = next(iter(proof['test']['reports'].values()))
    (tmp_path/xml['ref']).write_bytes(b'<tampered original/>')
    after = web.get('/api/candidates/'+candidate.id)
    assert after.status_code == 200 and after.json['checks'][-1]['state'] == 'UNKNOWN'
    assert after.json['check_set_hash'] is None
