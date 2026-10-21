import asyncio
from nexus.contracts import CandidateProposal, ToolResult
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore


class Client:
    def __init__(self, root):
        self.attempt = 0
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def call_tool(self, name, arguments):
        data = {}
        if name == 'project.diagnose':
            data = {'build': {'state': 'PASS'}, 'test': {'state': 'FAIL', 'diagnostics': 'zero quantity accepted'}}
        elif name == 'workspace.list_files': data = {'files': [{'path': 'src/a.cj'}]}
        elif name == 'workspace.read_file': data = {'content': 'source', 'file_hash': 'a'*64}
        elif name == 'candidate.apply':
            self.attempt += 1
            data = dict(id=f'c{self.attempt}', task_id=arguments['task_id'], tree_hash='d'*64,
                        baseline_hash='b'*64, edits=arguments['proposal']['edits'],
                        diff_ref='records/test.diff', attempt=self.attempt)
        elif name == 'candidate.diff': data = {'tree_hash':'d'*64, 'diff':f'+new {self.attempt}'}
        elif name == 'candidate.build': data = {'kind':'build', 'state':'PASS',
            'subject_id':arguments['candidate_id'], 'tree_hash':'d'*64}
        elif name == 'candidate.test': data = {'state': 'PASS' if self.attempt >= self.pass_at else 'FAIL', 'diagnostics': f'regression failure {self.attempt}', 'kind':'test',
            'subject_id':arguments['candidate_id'], 'tree_hash':'d'*64}
        return ToolResult(operation_status='OK', data=data)
    pass_at = 1


class Provider:
    def __init__(self, store, task_id): self.contexts = []
    async def propose(self, context):
        self.contexts.append(context)
        return CandidateProposal(edits=[dict(path='src/a.cj', before_hash='a'*64,
            content=f'new {len(self.contexts)}')], requirement_refs=['goal'])


def run_case(tmp_path, pass_at):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    provider = Provider(store, task.id)
    class TestClient(Client): pass
    TestClient.pass_at = pass_at
    result = asyncio.run(RepairLoop(store, provider_factory=lambda *_: provider, client_factory=TestClient).run(task.id))
    return result, provider


def test_real_fail_feedback_enters_next_prompt(tmp_path):
    result, provider = run_case(tmp_path, 2)
    assert result.status == 'REVIEW_PENDING'
    feedback = provider.contexts[1]['feedback'][0]
    assert 'regression failure' in str(feedback)
    assert feedback['diff'] == '+new 1'
    assert feedback['edited_files'][0]['content'] == 'new 1'
    assert feedback['edited_files'][0]['before_hash'] == 'a'*64
    assert provider.contexts[1]['files'] == provider.contexts[0]['files']
    assert feedback['remaining_budget'] == 2
    store = RunStore(tmp_path)
    assert any('repair_feedback' in e for e in store.records(result.id, 'event'))


def test_first_pass_stops_without_forced_retry(tmp_path):
    result, provider = run_case(tmp_path, 1)
    assert result.status == 'REVIEW_PENDING' and len(provider.contexts) == 1


def test_analysis_enrichment_reaches_the_actual_provider_before_generation(tmp_path):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj']);provider=Provider(store,task.id)
    async def enrich(current,context):
        assert current.id==task.id
        context['analysis']={'status':'PARTIAL','files':[]}
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:provider,client_factory=Client,
        context_enricher=enrich).run(task.id))
    assert result.status=='REVIEW_PENDING'
    assert provider.contexts[0]['analysis']=={'status':'PARTIAL','files':[]}


def test_three_candidates_stop(tmp_path):
    result, provider = run_case(tmp_path, 99)
    assert result.status == 'UNREPAIRED'
    assert len(provider.contexts) == 3


def test_late_response_cannot_overwrite_cancelled_task(tmp_path):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    class LateProvider(Provider):
        async def propose(self, context):
            store.update_task(task.id, status='CANCELLED')
            return await super().propose(context)
    result = asyncio.run(RepairLoop(store, provider_factory=LateProvider, client_factory=Client).run(task.id))
    assert result.status == 'CANCELLED' and result.attempt_count == 0


def test_unchanged_feedback_ignores_candidate_ids_and_timing():
    from nexus.repair.cegis_loop import feedback_identity
    a={'diagnostics':'c_'+'a'*32+' failed zeroQuantity (100 ns) 00:00:01'}
    b={'diagnostics':'c_'+'b'*32+' failed zeroQuantity (999 ns) 00:00:05'}
    assert feedback_identity({},a)==feedback_identity({},b)


def test_not_run_test_blocks_without_requesting_another_candidate(tmp_path):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    provider = Provider(store, task.id)
    class NotRunClient(Client):
        async def call_tool(self, name, arguments):
            if name == 'candidate.test':
                return ToolResult(operation_status='OK', data={'state': 'NOT_RUN'})
            return await super().call_tool(name, arguments)
    result = asyncio.run(RepairLoop(store, provider_factory=lambda *_: provider,
                                    client_factory=NotRunClient).run(task.id))
    assert result.status == 'BLOCKED'
    assert len(provider.contexts) == 1


def test_cancellation_between_phase_read_and_write_cannot_be_overwritten(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    store.update_task(task.id, status='GENERATING')
    update = store.update_task
    def cancel_before_commit(task_id, **changes):
        update(task_id, status='CANCELLED')
        return update(task_id, **changes)
    monkeypatch.setattr(store, 'update_task', cancel_before_commit)
    assert RepairLoop(store).phase(task.id, 'APPLYING') is False
    assert store.get_task(task.id).status == 'CANCELLED'


def test_repeated_failure_stops_after_two_complete_feedback_packages(tmp_path):
    store = RunStore(tmp_path)
    task = store.create_task('base', 'fix', ['src/a.cj'])
    provider = Provider(store, task.id)
    class SameFailureClient(Client):
        pass_at = 99
        async def call_tool(self, name, arguments):
            result = await super().call_tool(name, arguments)
            if name == 'candidate.test':
                result.data['diagnostics'] = f'zeroQuantity failed at src/a.cj:17 ({self.attempt*100} ns)'
            return result
    result = asyncio.run(RepairLoop(store, provider_factory=lambda *_: provider,
                                    client_factory=SameFailureClient).run(task.id))
    assert result.status == 'UNREPAIRED' and len(provider.contexts) == 2
    feedback = [e['repair_feedback'] for e in store.records(task.id,'event') if 'repair_feedback' in e]
    assert len(feedback) == 2
    assert feedback[0]['diff'] != feedback[1]['diff']
    assert 'src/a.cj:17' in feedback[1]['diagnostic_snippets'][0]['text']


def test_round_context_and_stop_reason_are_explicit(tmp_path):
    result,provider=run_case(tmp_path,99)
    assert [c['iteration']['round'] for c in provider.contexts]==[1,2,3]
    assert provider.contexts[1]['iteration']['apply_base']=='IMMUTABLE_BASELINE'
    assert provider.contexts[2]['iteration']['remaining_model_requests']==1
    assert any(e.get('stop_reason')=='Candidate budget exhausted' for e in RunStore(tmp_path).records(result.id,'event'))
