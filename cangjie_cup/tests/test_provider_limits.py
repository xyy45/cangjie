"""No HTTP calls: context bytes are rejected before recording a paid request."""
import asyncio
import pytest
from nexus.llm.provider import ModelProvider, ProviderUnavailable
from nexus.store import RunStore


def test_context_byte_limit_blocks_before_any_http_or_model_record(tmp_path,monkeypatch):
    for key,value in [('DEEPSEEK_API_KEY','synthetic-not-a-key'),
                      ('DEEPSEEK_BASE_URL','https://example.invalid'),
                      ('DEEPSEEK_MODEL','synthetic-limit-test')]:
        monkeypatch.setenv(key,value)
    def unexpected_http(*args,**kwargs):
        raise AssertionError('HTTP must not be initialized for oversized context')
    monkeypatch.setattr('nexus.llm.provider.httpx.AsyncClient',unexpected_http)
    store=RunStore(tmp_path)
    task=store.create_task('base','fix',['src/a.cj'])
    async def run():
        with pytest.raises(ProviderUnavailable,match='256 KiB'):
            await ModelProvider(store,task.id).propose({'required_goal':'仓'*100000})
    asyncio.run(run())
    assert store.records(task.id,'model_call') == []
    assert not list((tmp_path/'records').glob('*.request.json'))
