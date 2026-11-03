"""Scoped HTTP draft fixture through apply-preview and frozen provenance; no SDK."""
import json

import httpx
import pytest

from nexus.demo.rule_draft_provider import RuleDraftProvider
from nexus.store import RunStore
from nexus.uploads.rule_drafts import RuleDraftService
from nexus.uploads.service import UploadService
from tests.test_package_drafts import fixture


@pytest.mark.parametrize('kind', ['object', 'primitive'])
def test_scoped_http_draft_confirm_is_source_bound_owned_and_idempotent(tmp_path, monkeypatch, kind):
    from nexus.demo import rule_draft_provider as provider
    monkeypatch.setattr(provider, 'model_config', lambda: dict(DEEPSEEK_API_KEY='fixture-key',
        DEEPSEEK_MODEL='fixture-model', DEEPSEEK_BASE_URL='https://fixture.invalid'))
    snapshot, raw = fixture(tmp_path, kind)
    requests = []

    def response(request):
        assert request.url.host == 'fixture.invalid'
        context = json.loads(json.loads(request.content)['messages'][1]['content'])
        requests.append(context)
        assert context == snapshot
        return httpx.Response(200, json=dict(model='fixture-model',
            usage=dict(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            choices=[dict(finish_reason='stop', message=dict(content=json.dumps(raw)))]))

    store = RunStore(tmp_path)
    uploads = UploadService(store)
    drafts = RuleDraftService(store, provider_factory=lambda: RuleDraftProvider(transport=httpx.MockTransport(response)))
    args = dict(actor_id='alice', expected_version=1, function=snapshot['signature']['name'], allowed_paths=snapshot['allowed_paths'])
    job = drafts.create(snapshot['upload_id'], **args, request_key='fixture-draft', consent=True)
    assert drafts.create(snapshot['upload_id'], **args, request_key='fixture-draft', consent=True)['id'] == job['id']
    assert drafts.run(job['id']) is True and drafts.run(job['id']) is False
    preview = drafts.apply_preview(job['id'], **args)
    with pytest.raises(LookupError):
        drafts.apply_preview(job['id'], **{**args, 'actor_id': 'bob'})
    frozen = uploads.confirm(snapshot['upload_id'], **args, examples_json=preview['examples_json'],
        oracle_json=preview['oracle_json'], rule_draft_ref=preview['rule_draft_ref'], consent=True)
    assert len(requests) == 1 and frozen['oracle_contract']['version'] == 6
    assert frozen['rule_draft_provenance']['origin'] == 'HTTP_FIXTURE_NOT_LIVE'
    assert frozen['rule_draft_provenance']['edited_by_user'] is False
    root = uploads.source(snapshot['upload_id'], actor_id='alice')
    original = (root/'verification/rule-draft/provenance.json').read_bytes()
    assert json.loads(original)['source_binding_hash'] == snapshot['binding_hash']
    (root/'verification/rule-draft/provenance.json').write_bytes(b'{}')
    with pytest.raises(ValueError):
        uploads.profile(snapshot['upload_id'])
