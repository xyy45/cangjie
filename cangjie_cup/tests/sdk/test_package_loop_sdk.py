"""Scoped end-to-end loop: real SDK/core/stdio; explicit model/graph fixtures."""
import asyncio
import json
import zipfile

import httpx
import pytest

from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.contracts import file_hash, source_manifest
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.focus_service import FocusService
from nexus.uploads.service import UploadService
from tests.analysis.test_repair_bridge import Transport
from tests.sdk.test_package_reports_sdk import save
from tests.sdk.test_package_services_sdk import MODULES, rule, state
from tests.test_package_context import setup

pytestmark = pytest.mark.sdk


def system(root, monkeypatch, mode):
    original = UploadService.confirm

    def confirm(self, *args, **kwargs):
        contracts = {kind: rule(kind) for kind in MODULES}
        if mode == 'unknown':
            contracts['oracle']['domains']['state']['values'].append(state((1 << 63) - 1))
            contracts['oracle']['expression'] = ('object_with(state,"amount",'
                'object_get(state,"amount") if n > 9223372036854775807-object_get(state,"amount") '
                'else object_get(state,"amount")+n)')
        for kind, key in dict(oracle='oracle_json', property='properties_json',
                              relation='relations_json', sequence='sequences_json').items():
            kwargs[key] = json.dumps(contracts[kind])
        return original(self, *args, **kwargs)

    with monkeypatch.context() as preparation:
        preparation.setattr(UploadService, 'confirm', confirm)
        return setup(root)


@pytest.mark.parametrize('mode', ['normal', 'unknown'])
def test_scoped_two_round_loop_all_four_gates_and_owned_download(tmp_path, monkeypatch, mode):
    import importlib
    root = tmp_path.resolve()
    store, ws, task, upload = system(root, monkeypatch, mode)
    contexts = []
    for key, value in dict(DEEPSEEK_API_KEY='fixture-only', DEEPSEEK_BASE_URL='https://fixture.invalid',
                           DEEPSEEK_MODEL='test-model').items():
        monkeypatch.setenv(key, value)

    def response(request):
        assert request.url.host == 'fixture.invalid'
        body = json.loads(request.content)
        context = json.loads(body['messages'][1]['content'])
        contexts.append(context)
        original = context['files']['src/step.cj']['content']
        content = original if len(contexts) == 1 else original.replace('state.amount+n+1', 'state.amount+n')
        refs = [t['evidence_id'] for entry in context.get('analysis', {}).get('files', [])
                for t in entry['tools'] if t.get('included') and t['status'] == 'VALID'][:1]
        payload = dict(schema_version=1, summary='Explicit HTTP FIXTURE scoped candidate',
            suggestions=[dict(path='src/step.cj', reason='Explicit HTTP FIXTURE')], analysis_refs=refs,
            proposal=dict(edits=[dict(path='src/step.cj', before_hash=file_hash(original),
                content=content+'\n// explicit HTTP FIXTURE candidate\n')], requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200, json=dict(model='test-model',
            usage=dict(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            choices=[dict(finish_reason='stop', message=dict(content=json.dumps(payload)))]))

    def provider(store, identity):
        return DeepSeekProvider(store, identity, transport=httpx.MockTransport(response))

    Transport.calls = []
    bridge = RepairAnalysis(store, AnalysisService(root, client_factory=Transport))
    loop = RepairLoop(store, provider_factory=provider, context_enricher=bridge.enrich,
                      focus_enricher=FocusService(store).enrich)
    result = asyncio.run(loop.run(task.id))
    save(root, 'http-model-fixture-contexts', contexts)
    save(root, 'immutable-loop-originals', {p.name: p.read_bytes() for p in (root/'records').iterdir() if p.is_file()})
    assert all(record['origin'] == 'TEST' for record in store.records(task.id, 'model_call'))
    encoded = json.dumps(contexts)
    for hidden in ('NONSELECTED_BODY_SECRET_87632', 'ORIGINAL_TEST_BODY_NOT_FOR_MODEL',
                   'excluded_inputs', 'oracle_contract', 'properties_contract', 'relations_contract', 'sequences_contract'):
        assert hidden not in encoded
    assert all(set(context['files']) == {'src/step.cj', upload['public_test_path']} for context in contexts)
    assert all(call[1]['code'] == ws.read_file(task.baseline_id, 'src/step.cj') for call in Transport.calls)
    if mode == 'unknown':
        assert result.status == 'BLOCKED' and len(contexts) == 1, store.records(task.id, 'event')[-1]
        assert not any('selected_candidate_id' in event for event in store.records(task.id, 'event'))
        return

    assert result.status == 'REVIEW_PENDING' and len(contexts) == 2, store.records(task.id, 'event')[-1]
    feedback = contexts[1]['feedback'][0]
    assert feedback['failure_cases'] and feedback['failure_cases'][0]['kind'] == 'independent_rule'
    assert contexts[1]['repair_focus']['targets'][0]['function'] == 'bench.step'
    first = feedback['previous_candidate_id']
    selected = next(event['selected_candidate_id'] for event in store.records(task.id, 'event') if 'selected_candidate_id' in event)
    reports = {}
    for kind, (module, name) in MODULES.items():
        service = getattr(importlib.import_module('nexus.repair.'+module), name)(store)
        report = service.verify(selected)
        assert report['state'] == 'PASS' and asyncio.run(service.run(selected)) == report
        for batch in report['batches']:
            scoped = batch['scoped']
            assert (root/scoped['derived_source_ref']).read_bytes() == (root/batch['project_path']/scoped['binding']['bridge_path']).read_bytes()
        reports[kind] = report
    failed = getattr(importlib.import_module('nexus.repair.exploration'), 'ExplorationService')(store).verify(first)
    assert failed['state'] == 'FAIL' and len(failed['batches']) >= 2
    assert reports['oracle']['regression_cases'] > 0
    for identity in (first, selected):
        assert not any('bridge' in name or 'nexus_verify_' in name for name in source_manifest(ws.subject_path(identity)))

    delivery = DeliveryService(store)
    with pytest.raises(ValueError):
        delivery.check_set_hash(first)
    from nexus.web.app import create_app
    app = create_app(store, loop, delivery, require_operator=False)
    app.testing = True
    app.config['RUN_TASKS'] = False
    web = app.test_client()
    web.get('/')
    with web.session_transaction() as session:
        session['actor_id'] = 'alice'
        csrf = session['csrf']
    headers = {'Origin': 'http://localhost', 'X-CSRF-Token': csrf}
    accepted = web.post('/api/candidates/'+selected+'/accept', headers=headers,
        json=dict(check_set_hash=delivery.check_set_hash(selected), task_revision=store.get_task(task.id).revision))
    assert accepted.status_code == 200, accepted.json
    exported = web.post('/api/candidates/'+selected+'/export', headers=headers, json=dict(acceptance_id=accepted.json['id']))
    assert exported.status_code == 200, exported.json
    url = exported.json['download_url']
    assert web.get(url).status_code == 200
    with zipfile.ZipFile(root/exported.json['download_ref']) as package:
        names = set(package.namelist())
        assert not any('bridge' in name or 'nexus_verify_' in name for name in names if name.startswith('project/'))
        for report in reports.values():
            for batch in report['batches']:
                assert package.read('evidence/native/'+batch['scoped']['derived_source_ref']) == (root/batch['scoped']['derived_source_ref']).read_bytes()
        assert package.read('project/src/model/state.cj') == ws.read_file(task.baseline_id, 'src/model/state.cj').encode()
    public = next(record for record in reversed(store.records(task.id, 'check')) if record['subject_id'] == selected and record['kind'] == 'test')
    xml = next(iter(public['package_evidence']['test']['reports'].values()))['ref']
    batch = reports['oracle']['batches'][0]
    controls = [('xml', root/xml), ('bridge-original', root/batch['scoped']['derived_source_ref']),
        ('bridge-live', root/batch['project_path']/batch['scoped']['binding']['bridge_path']),
        ('readonly-source', ws.verify_baseline(task.baseline_id)/'src/model/state.cj'),
        ('frozen-contract', ws.verify_baseline(task.baseline_id)/'verification/oracle.json')]
    outcomes = []
    for name, path in controls:
        original = path.read_bytes()
        path.write_bytes(original+b'\nDISPOSABLE TAMPER\n')
        try:
            status = web.get(url).status_code
            outcomes.append(dict(control=name, http_status=status))
            assert status == 400
        finally:
            path.write_bytes(original)
    assert web.get(url).status_code == 200
    save(root, 'download-tamper-controls', outcomes)
    save(root, 'four-service-loop-reports', reports)
