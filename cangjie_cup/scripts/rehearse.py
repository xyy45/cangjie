"""Three LIVE repetitions from clean baselines, with native MCP verification/export.
This command makes paid model requests. It stops on the first unsuccessful run.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore, uid
from nexus.requirements.service import RequirementService

ROOT = Path(__file__).resolve().parents[1]
GOAL = ('Fix order validation. Quantity must be 1–1000; unit price 0–1000000. '
        'Invalid inputs return -1. Valid order total is quantity multiplied by unit price. '
        'Preserve all frozen tests.')


async def rehearse() -> Path:
    session = ROOT / '.runtime/rehearsals' / uid()
    session.mkdir(parents=True)
    summary = {'origin': 'LIVE', 'completed': False, 'runs': []}
    report = session / 'summary.json'
    for number in range(1, 4):
        started = time.monotonic()
        root = session / str(number)
        source = ROOT / 'fixtures/order-demo-bug'
        ws = WorkspaceStore(root, registered=[source])
        baseline = ws.import_project(source, '.')
        store = RunStore(root)
        service = RequirementService(store)
        draft = service.prepare_requirement('order-demo-bug',GOAL)
        spec = service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=draft['version'],
            requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='CLI_REHEARSAL_OPERATOR')
        task = service.prepare_task('order-demo-bug',spec.id,baseline)
        with store.connect() as db:
            db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
        entry = {'number': number, 'task_id': task.id, 'run_directory': str(root)}
        summary['runs'].append(entry)
        try:
            result = await RepairLoop(store).run(task.id)
            entry.update(status=result.status, attempts=result.attempt_count)
            if result.status != 'REVIEW_PENDING':
                raise RuntimeError(f'LIVE run {number} stopped: {result.status}; inspect {root}')
            selected = [e['selected_candidate_id'] for e in store.records(task.id, 'event')
                        if 'selected_candidate_id' in e][-1]
            calls = [r for r in store.records(task.id, 'model_call') if r['status'] == 'SUCCEEDED']
            if not calls or any(c['origin'] != 'LIVE' for c in calls):
                raise RuntimeError('LIVE model evidence missing')
            delivery = DeliveryService(store)
            acceptance = delivery.accept(selected, delivery.check_set_hash(selected),actor_id='EXPLICIT_CLI_REHEARSAL')
            store.append_record(task.id, 'event', {'acceptance_origin': 'CLI_REHEARSAL'})
            async with ToolClient(root) as client:
                exported = await client.call_tool('candidate.export', dict(task_id=task.id,
                    request_id=uid(), candidate_id=selected, acceptance_id=acceptance.id))
            if exported.operation_status != 'OK' or exported.data.get('status') != 'DELIVERED':
                raise RuntimeError(f'MCP export stopped: {exported.operation_status}')
            archive = delivery.verify_archive(exported.data['export_id'], acceptance)
            checks = [r for r in store.records(task.id, 'check') if r['subject_id'] == selected]
            entry.update(status='DELIVERED', candidate_id=selected, tree_hash=ws.candidate(selected).tree_hash,
                archive=str(archive), archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                model_ids=[c['model_id'] for c in calls], usage=[c['usage'] for c in calls],
                checks=[{'kind':c['kind'], 'state':c['state'], 'counts':c['counts']} for c in checks])
        except BaseException:
            entry['elapsed_seconds'] = round(time.monotonic()-started, 3)
            report.write_text(json.dumps(summary, indent=2))
            raise
        entry['elapsed_seconds'] = round(time.monotonic()-started, 3)
        report.write_text(json.dumps(summary, indent=2))
        print(json.dumps(entry), flush=True)
    summary['completed'] = True
    report.write_text(json.dumps(summary, indent=2))
    print('LIVE rehearsal summary: ' + str(report), flush=True)
    return report


if __name__ == '__main__':
    asyncio.run(rehearse())
