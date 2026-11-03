"""Real analysis persistence with a labelled transport fixture; no remote calls."""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from nexus.analysis.service import AnalysisService,AnalysisConflict
from nexus.analysis.normalize import validate_source
from tests.analysis.test_service import FakeClient,SOURCE


class CacheClient(FakeClient):
    scope='fixture-endpoint-and-credential-v1'
    calls=[]
    @classmethod
    def cache_identity(cls):
        import hashlib
        return hashlib.sha256(cls.scope.encode()).hexdigest()
    def cache_scope(self):return type(self).cache_identity()


@pytest.fixture
def cached(tmp_path):
    CacheClient.scope='fixture-endpoint-and-credential-v1';CacheClient.calls=[]
    service=AnalysisService(tmp_path,client_factory=CacheClient)
    first=service.create(validate_source('add.cj',SOURCE),actor_id='owner',request_key='first',origin='UPLOAD')
    service.run(first['id']);assert len(CacheClient.calls)==3
    return service,first['id']


def create(service,key='again',**changes):
    values=dict(source=validate_source('add.cj',SOURCE),actor_id='owner',request_key=key,origin='UPLOAD',reuse_cache=True)
    values.update(changes)
    return service.create(**values)


def test_verified_complete_result_is_reused_without_new_tool_calls_and_alias_is_bound(cached):
    service,identity=cached;before=service.get(identity,actor_id='owner')
    reused=create(service)
    assert reused['id']==identity and reused['cache_hit'] is True
    assert reused['cached_at']==before['completed_at']
    assert service.run(identity) is False and len(CacheClient.calls)==3
    assert create(service)==reused
    with pytest.raises(AnalysisConflict):create(service,source=validate_source('add.cj',SOURCE.replace(b'a + b',b'a - b')))
    with pytest.raises(LookupError):service.get(identity,actor_id='other')
    assert len(service.list('owner'))==1


@pytest.mark.parametrize('change',['actor','source','filename','criterion','origin','scope','profile'])
def test_cache_never_crosses_source_session_or_execution_scope(cached,monkeypatch,change):
    service,identity=cached;kwargs={}
    if change=='actor':kwargs['actor_id']='other'
    elif change=='source':kwargs['source']=validate_source('add.cj',SOURCE.replace(b'a + b',b'a - b'))
    elif change=='filename':kwargs['source']=validate_source('other.cj',SOURCE)
    elif change=='criterion':kwargs['slice_line']=2
    elif change=='origin':kwargs['origin']='SAMPLE'
    elif change=='scope':CacheClient.scope='fixture-other-credential'
    else:
        from nexus.analysis import cache
        monkeypatch.setattr(cache,'PROFILE',cache.PROFILE+1)
    job=create(service,**kwargs)
    assert job['id']!=identity and not job.get('cache_hit')
    assert len(CacheClient.calls)==3, 'creation must not execute tools'


def test_expired_cache_and_explicit_fresh_request_create_new_jobs(cached,monkeypatch):
    from nexus.analysis import cache
    service,identity=cached
    completed=service.get(identity,actor_id='owner')['completed_at']
    from datetime import datetime
    monkeypatch.setattr(cache,'time',SimpleNamespace(time=lambda:datetime.fromisoformat(completed).timestamp()+301))
    assert create(service)['id']!=identity
    service.reconcile()
    assert create(service,key='fresh',reuse_cache=False)['id']!=identity


@pytest.mark.parametrize('artifact',['source.cj','result.json','observations/sympas_dep_graph.json'])
def test_corrupted_cache_is_rejected_instead_of_success_or_silent_replay(cached,artifact):
    service,identity=cached
    (service.directory(identity)/artifact).write_text('corrupt')
    with pytest.raises(ValueError):create(service)
    assert len(service.list('owner'))==1 and len(CacheClient.calls)==3


@pytest.mark.parametrize('state',['PARTIAL','FAILED','IN_DOUBT'])
def test_noncomplete_runs_are_never_reused(cached,state):
    service,identity=cached
    with service.store.connect() as db:db.execute('UPDATE analysis_jobs SET status=? WHERE id=?',(state,identity))
    assert create(service)['id']!=identity


def test_forged_complete_status_or_cache_metadata_does_not_pass_artifact_validation(cached):
    service,identity=cached
    with service.store.connect() as db:
        status,payload=service._row(identity);payload['completed_at']='2099-01-01T00:00:00+00:00'
        db.execute('UPDATE analysis_jobs SET payload=? WHERE id=?',(json.dumps(payload),identity))
    with pytest.raises(ValueError):create(service)


def test_multiple_request_keys_can_bind_the_same_verified_result(cached):
    service,identity=cached
    with ThreadPoolExecutor(2) as workers:
        jobs=list(workers.map(lambda i:create(service,key='request-'+str(i)),range(2)))
    assert all(j['id']==identity and j['cache_hit'] for j in jobs)
    assert len(service.list('owner'))==1 and len(CacheClient.calls)==3


def test_reuse_does_not_bypass_active_tool_lease(cached):
    service,identity=cached
    create(service,key='new-active',reuse_cache=False)
    with pytest.raises(AnalysisConflict):create(service,key='reuse-during-active')


def test_changed_scope_between_create_and_run_is_bound_to_actual_client(tmp_path):
    CacheClient.calls=[];CacheClient.scope='before'
    service=AnalysisService(tmp_path,client_factory=CacheClient)
    first=create(service,key='first');CacheClient.scope='after';service.run(first['id'])
    assert create(service)['id']==first['id']
    CacheClient.scope='before'
    assert create(service,key='older-scope')['id']!=first['id']


def test_source_claim_cannot_reuse_another_code_body(cached):
    service,identity=cached;forged=validate_source('add.cj',SOURCE);forged['code']=forged['code'].replace('a + b','a - b')
    with pytest.raises(ValueError):create(service,source=forged)
