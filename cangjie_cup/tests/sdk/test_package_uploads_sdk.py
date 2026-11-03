"""Actual public SDK checks after scoped upload confirmation, no model calls."""
import asyncio,hashlib,json
import pytest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import source_manifest,digest
from tests.test_package_index import project
from tests.test_package_uploads import model,state
from tests.sdk.test_package_reports_sdk import save

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('kind',['oracle','properties','relations','sequences'])
def test_confirmed_scoped_project_has_complete_actual_public_checks_and_rebuilt_originals(tmp_path,kind):
    files=project();files['src/sale/state.cj']+=b'\npublic func step(state: State, n: Int64): State { State(state.amount+n) }'
    store=RunStore(tmp_path);uploads=UploadService(store)
    draft=uploads.prepare_project('packages',None,'按增量改变状态',actor_id='alice',request_key='one',entries=files)
    values=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1),1],expected=state(2),suite='regression')]
    frozen=uploads.confirm(draft['id'],expected_version=1,function='bench.sale.step',examples_json=json.dumps(values),
        consent=True,actor_id='alice',allowed_paths=['src/sale/state.cj'],**{kind+'_json':json.dumps(model(kind))})
    source=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],frozen['goal'])
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    before=source_manifest(ws.subject_path(baseline))
    async def run():
        verifier=CangjieVerifier(tmp_path,task.id)
        build=await verifier.build(baseline);assert build.state=='PASS',build
        check=await verifier.test(baseline);assert check.state=='PASS',check
        assert len(check.case_results)==5 and all(s['state']=='PASS' for s in check.suite_results.values())
        assert check.package_evidence['graph_hash']==frozen['project_index']['graph_hash']
        from nexus.repair.verification_evidence import public_evidence
        plan=requirements.get_plan(task.verification_plan_id)
        proof=public_evidence(store,check.model_dump(),task,plan)
        assert proof['state']=='PASS',proof
        assert (await verifier.test(baseline)).model_dump()==check.model_dump()
        return check.model_dump(),proof
    check,proof=asyncio.run(run())
    assert before==source_manifest(ws.subject_path(baseline))
    save(tmp_path,'immutable-public-check-originals',{p.name:p.read_bytes() for p in (tmp_path/'records').iterdir() if p.is_file()})
    save(tmp_path,'result',dict(upload=frozen,task=task.model_dump(),check=check,proof=proof,
        source_before=before,source_after=source_manifest(ws.subject_path(baseline)),model_requests=0,remote_analysis_requests=0))
