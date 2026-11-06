"""Output instructions reflect the already enforced scalar example contract."""
import json

import httpx
import pytest

from nexus.demo.rule_draft_provider import RuleDraftProvider
from nexus.store import RunStore
from nexus.uploads.rule_contract import draft_snapshot, validate_suggestion
from nexus.uploads.service import UploadService
from tests.test_rule_drafts import prepared, snapshot, suggestion


@pytest.mark.parametrize('source,kinds,result_kind', [
    ('public func calc(x: Int64, y: Int64): Int64 { x + y }',
     ['integer', 'integer'], 'integer'),
    ('public func calc(enabled: Bool, count: Int64): Bool { enabled && count > 0 }',
     ['boolean', 'integer'], 'boolean'),
    ('public func calc(): Int64 { 1 }', [], 'integer'),
])
def test_wire_example_schema_has_scalar_suite_and_signature_types(tmp_path, monkeypatch,
                                                                 source, kinds, result_kind):
    monkeypatch.setattr('nexus.demo.rule_draft_provider.model_config', lambda: dict(
        DEEPSEEK_API_KEY='fixture-only', DEEPSEEK_BASE_URL='https://model.example',
        DEEPSEEK_MODEL='fixture-model'))
    uploads = UploadService(RunStore(tmp_path))
    upload = uploads.prepare('calc.cj', source.encode(), '仅检查格式契约，不调用模型',
                             actor_id='alice', request_key='upload')
    bound = draft_snapshot(uploads, upload['id'], actor_id='alice', expected_version=1,
                           function='calc')
    provider = RuleDraftProvider(transport=httpx.MockTransport(
        lambda request: pytest.fail('preparing a schema must not send a request')))
    body = provider.prepare(bound)
    instructions = body['messages'][0]['content']
    schema = json.loads(instructions.split('JSON schema:\n', 1)[1])
    examples = next(s for s in schema['properties']['examples']['anyOf']
                    if s.get('type') == 'array')
    item = examples['items']
    assert item['properties']['suite'] == dict(type='string', enum=['target', 'regression'])
    assert set(item['required']) == {'args', 'expected', 'suite'}
    assert item['additionalProperties'] is False
    assert examples['minItems'] == 2 and examples['maxItems'] == 12
    args = item['properties']['args']
    assert args['minItems'] == args['maxItems'] == len(kinds)
    assert args['items'] is False
    assert [p['type'] for p in args['prefixItems']] == kinds
    assert item['properties']['expected']['type'] == result_kind
    for value in args['prefixItems'] + [item['properties']['expected']]:
        if value['type'] == 'integer':
            assert value['minimum'] == -(2**63) and value['maximum'] == 2**63-1
    assert schema['properties']['schema_version']['const'] == 1
    assert 'rule-draft-prompt-v3' in instructions
    assert 'oracle是可选增强' in instructions and '120个语法树节点' in instructions
    assert '覆盖每个公开用例的每个实参' in instructions
    assert '"suite":"target"' in instructions and '"suite":"regression"' in instructions


def test_non_scalar_suite_observed_in_live_trial_still_cannot_be_applied(prepared):
    payload = suggestion()
    for example in payload['examples']:
        example['suite'] = dict(target=['business example'], regression=['boundary'])
    result = validate_suggestion(json.dumps(payload), snapshot(prepared))
    assert result['status'] == 'INVALID' and result['code'] == 'EXAMPLES_INVALID'
    assert result['examples_json'] is None and result['oracle_json'] is None
    assert result['business_verified'] is False
