"""Actual SIGKILL/restart; the provider side effect is a local fixture, not HTTP."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from nexus.execution.ownership import RuntimeOwner
from nexus.store import RunStore
from nexus.uploads.rule_drafts import DraftConflict, RuleDraftService
from nexus.uploads.service import UploadService
from tests.test_rule_drafts import SOURCE


WORKER = r'''
import asyncio
from pathlib import Path
import sys
from nexus.execution.ownership import RuntimeOwner
from nexus.store import RunStore
from nexus.uploads.rule_drafts import RuleDraftService

root = Path(sys.argv[1])
owner = RuntimeOwner(root)
assert owner.acquire()

class InterruptedFixture:
    origin = 'PROCESS_FIXTURE_NOT_LIVE'
    def prepare(self, snapshot):
        return {'snapshot': snapshot, 'kind': 'LOCAL_PROCESS_FIXTURE'}
    async def complete(self, body):
        # Signal only after RuleDraftService has persisted STARTED and request.
        with (root / 'fixture-dispatches.txt').open('a') as stream:
            stream.write('DISPATCHED\n')
            stream.flush()
        await asyncio.sleep(30)
        raise AssertionError('parent must terminate this process before completion')

RuleDraftService(RunStore(root), provider_factory=InterruptedFixture).run(sys.argv[2])
'''


@pytest.mark.skipif(os.name != 'posix', reason='requires POSIX SIGKILL and flock')
def test_killed_draft_worker_recovers_unknown_without_replaying_or_applying(tmp_path):
    store = RunStore(tmp_path)
    uploads = UploadService(store)
    uploaded = uploads.prepare('fee.cj', SOURCE, '返回quantity乘price',
                               actor_id='alice', request_key='upload')
    drafts = RuleDraftService(store)
    body = dict(actor_id='alice', expected_version=1, function='fee',
                request_key='generate', consent=True)
    job = drafts.create(uploaded['id'], **body)
    originals = drafts.directory(job['id'])
    marker = tmp_path / 'fixture-dispatches.txt'
    worker = subprocess.Popen([sys.executable, '-c', WORKER, str(tmp_path), job['id']],
                              cwd=Path(__file__).resolve().parents[2],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and worker.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists(), 'fixture dispatch was not reached'
        assert worker.poll() is None
        started = drafts.get(job['id'], actor_id='alice')
        assert started['call_state'] == 'STARTED'
        assert started['request_sha256'] == hashlib.sha256((originals / 'request.json').read_bytes()).hexdigest()
        assert json.loads((originals / 'request.json').read_bytes())['snapshot']['binding_hash'] == job['binding_hash']
        assert not (originals / 'response.json').exists()
        preserved = {p.name: p.read_bytes() for p in originals.glob('*.json')}
        worker.kill()
        assert worker.wait(timeout=5) == -signal.SIGKILL
    finally:
        if worker.poll() is None:
            worker.kill()
        worker.communicate(timeout=5)

    # A genuinely new controller must acquire the OS lock released by SIGKILL.
    owner = RuntimeOwner(tmp_path)
    assert owner.acquire()
    try:
        def forbidden_provider():
            with marker.open('a') as stream:
                stream.write('REPLAY_ATTEMPT\n')
            raise AssertionError('restart must not dispatch any provider')

        owner.reconcile(store)
        recovered = RuleDraftService(store, provider_factory=forbidden_provider)
        assert recovered.reconcile() == 1
        state = recovered.get(job['id'], actor_id='alice')
        assert state['call_state'] == 'IN_DOUBT'
        assert state['error_code'] == 'CONTROLLER_RESTARTED_NO_REPLAY'
        assert state['result'] is None
        assert recovered.run(job['id']) is False
        assert recovered.create(uploaded['id'], **body)['id'] == job['id']
        with pytest.raises(DraftConflict):
            recovered.create(uploaded['id'], **{**body, 'request_key': 'new-key'})
        with pytest.raises(DraftConflict):
            recovered.apply_preview(job['id'], actor_id='alice', expected_version=1,
                                    function='fee')
        assert recovered.reconcile() == 0
        assert marker.read_text() == 'DISPATCHED\n'
        assert {p.name: p.read_bytes() for p in originals.glob('*.json')} == preserved
        assert UploadService(store).get(uploaded['id'], actor_id='alice')['status'] == 'DRAFT'
        assert not (tmp_path / 'uploads' / uploaded['id'] / 'project').exists()
        with store.connect() as db:
            assert db.execute('SELECT count(*) FROM tasks').fetchone()[0] == 0
    finally:
        owner.close()
