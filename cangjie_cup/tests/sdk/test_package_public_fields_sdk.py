"""Actual SDK XML failure/source mapping, including withheld original tests."""
import asyncio,json
import pytest
from nexus.store import RunStore
from nexus.contracts import CandidateProposal,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.uploads.service import UploadService
from nexus.requirements.service import RequirementService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair.public_fields import for_task
from tests.sdk.test_package_services_sdk import material,state
from tests.sdk.test_package_reports_sdk import save
from nexus.benchmark.corpus import CONFIG,LOCK

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('kind',['object-and-original','string'])
def test_actual_scoped_xml_failure_leaves_keep_canonical_source_and_visibility(tmp_path,kind):
    if kind=='object-and-original':
        files=material();files['src/step.cj']=files['src/step.cj'].replace(b'if (state.amount >= 2)',b'if (state.amount >= 0)')
        function='bench.step';editable='src/step.cj'
        examples=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1,[]),1],expected=state(2,[]),suite='regression')]
    else:
        files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/entry.cj':b'package bench\npublic func upper(s: String): String { s }',
            'src/helper/anchor.cj':b'package bench.helper\npublic func anchor(x: Int64): Int64 { x }'}
        function='bench.upper';editable='src/entry.cj'
        examples=[dict(args=['hello'],expected='HELLO',suite='target'),dict(args=['ok'],expected='OK',suite='regression')]
    store=RunStore(tmp_path);u=UploadService(store);d=u.prepare_project('scoped',None,'按确认的公开示例修复',actor_id='alice',request_key='one',entries=files)
    value=u.confirm(d['id'],expected_version=1,function=function,examples_json=json.dumps(examples),consent=True,actor_id='alice',allowed_paths=[editable])
    root=u.source(d['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    req=RequirementService(store);draft=req.prepare_requirement(d['id'],value['goal'])
    spec=req.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='alice')
    task=req.prepare_task(d['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    c=ws.apply_candidate(task,CandidateProposal(edits=[dict(path=editable,before_hash=file_hash(files[editable].decode()),content=files[editable].decode()+'\n// explicit local candidate')],requirement_refs=['REQ-UPLOAD']))
    async def run():
        verifier=CangjieVerifier(tmp_path,task.id);built=await verifier.build(c.id);assert built.state=='PASS',built
        checked=await verifier.test(c.id);assert checked.state=='FAIL',checked
        save(tmp_path,'immutable-field-originals',{p.name:p.read_bytes() for p in (tmp_path/'records').iterdir() if p.is_file()})
        mapped=for_task(store,task,checked);save(tmp_path,'mapped-fields',mapped)
        public=[f for f in mapped['failures'] if f['visibility']=='PUBLIC']
        assert len(public)==2 and all(f['function']==function and 'actual_return' not in f for f in public)
        assert all(f['source']['coordinate']=='XML_FAILURE_TEXT' for f in public)
        if kind=='object-and-original':
            assert len(mapped['failures'])==3 and any(f['visibility']=='VERIFICATION_ONLY' for f in mapped['failures'])
            assert all(f['actual_value']==e['expected']['fields']['amount']+1 for f,e in zip(public,examples))
        else:assert all(f['value_state']=='TEXT_ONLY' and f['actual_value'] is None for f in public)
        from nexus.repair.focus_service import FocusService
        focus=FocusService(store).prepare(task.id,c.id);save(tmp_path,'scoped-focus',focus)
        assert focus['status']=='PARTIAL' and len(focus['targets'])==2,focus
        assert all(t['function']==function and t['mapping']=='CONFIRMED_CASE' for t in focus['targets'])
    asyncio.run(run())


@pytest.mark.parametrize('return_type,argument,expected', [
    ('String', 'hello', 'a != b'),
    ('String', 'left != "right"', 'a " != " b'),
    ('String', 'a' * 40, 'm != ' * 8),
    ('String', 'first\nline', 'a != \nb'),
    ('Int64', 'left != "right"', 3),
    ('String', 'folder\\file', 'a\\ != b'),
    ('Int64', 'back`tick', 3),
], ids=['short-separator', 'escaped-quotes', 'long-separator', 'multiline-separator', 'typed-string-argument', 'backslash-data', 'typed-backtick-argument'])
def test_actual_original_string_assertions_keep_literal_separators_in_bound_feedback(tmp_path, return_type, argument, expected):
    """A separator inside a source literal must not destroy all XML feedback."""
    files = {'cjpm.toml': CONFIG, 'cjpm.lock': LOCK,
        'src/entry.cj': ('package bench\npublic func upper(s: String): '+return_type+
                         (' { s }' if return_type == 'String' else ' { 0 }')).encode(),
        'src/helper/anchor.cj': b'package bench.helper\npublic func anchor(x: Int64): Int64 { x }',
        'src/original_test.cj': ('package bench\nimport std.unittest.*\nimport std.unittest.testmacro.*\n'
            '@Test\nclass OriginalCases {\n    @TestCase\n    func case0() {\n        @Expect(upper('
            + json.dumps(argument) + '), ' + json.dumps(expected) + ')\n    }\n}\n').encode()}
    store = RunStore(tmp_path); uploads = UploadService(store)
    prepared = uploads.prepare_project('literal-operators', None, '按确认示例修复，保留原测试',
        actor_id='alice', request_key='one', entries=files)
    uploaded = uploads.confirm(prepared['id'], expected_version=1, function='bench.upper',
        examples_json=json.dumps([dict(args=['public'], expected='PUBLIC' if return_type == 'String' else 1, suite='target'),
                                  dict(args=['ok'], expected='ok' if return_type == 'String' else 0, suite='regression')]),
        consent=True, actor_id='alice', allowed_paths=['src/entry.cj'])
    source = uploads.source(uploaded['id'], actor_id='alice')
    ws = WorkspaceStore(tmp_path, registered=[source]); baseline = ws.import_project(source, '.')
    requirements = RequirementService(store)
    draft = requirements.prepare_requirement(uploaded['id'], uploaded['goal'])
    spec = requirements.confirm_requirement(draft['id'], dict(schema_version=1, expected_version=1,
        requirements=draft['requirements'], allowed_paths=draft['allowed_paths']), actor_id='alice')
    task = requirements.prepare_task(uploaded['id'], spec.id, baseline)
    with store.connect() as db:
        db.execute('INSERT INTO tasks VALUES (?,?)', (task.id, task.model_dump_json()))
    original = files['src/entry.cj'].decode()
    candidate = ws.apply_candidate(task, CandidateProposal(edits=[dict(path='src/entry.cj',
        before_hash=file_hash(original), content=original+'\n// explicit local candidate')],
        requirement_refs=['REQ-UPLOAD']))

    async def verify():
        verifier = CangjieVerifier(tmp_path, task.id)
        built = await verifier.build(candidate.id); assert built.state == 'PASS', built
        checked = await verifier.test(candidate.id); assert checked.state == 'FAIL', checked
        save(tmp_path, 'immutable-literal-originals',
             {p.name: p.read_bytes() for p in (tmp_path/'records').iterdir() if p.is_file()})
        mapped = for_task(store, task, checked); save(tmp_path, 'literal-feedback', mapped)
        assert len(mapped['failures']) == 2
        original_fact = next(f for f in mapped['failures'] if f['visibility'] == 'VERIFICATION_ONLY')
        assert original_fact['test_id'] == 'bench.OriginalCases.case0'
        assert original_fact['function'] == 'bench.upper' and original_fact['args'] == [argument]
        assert original_fact['expected_value'] == expected
        assert original_fact['value_state'] == ('TEXT_ONLY' if return_type == 'String' else 'TYPED')
        assert original_fact['actual_value'] == (None if return_type == 'String' else 0)
        public_fact = next(f for f in mapped['failures'] if f['visibility'] == 'PUBLIC')
        assert public_fact['args'] == ['public'] and public_fact['expected_value'] == ('PUBLIC' if return_type == 'String' else 1)
        assert all(f['source']['coordinate'] == 'XML_FAILURE_TEXT' for f in mapped['failures'])
        from nexus.repair.feedback import build_feedback
        feedback = build_feedback(candidate, dict(tree_hash=candidate.tree_hash, diff=ws.diff(candidate.id)),
            built.model_dump(), checked.model_dump(), remaining_budget=2, requirement_refs=['REQ-UPLOAD'],
            diagnostics_public=False, public_failure_cases=[public_fact])
        assert len(feedback.failure_cases) == 1 and feedback.failure_cases[0]['args'] == ['public']
        assert all(s['text'] == '' and s['visibility'] == 'WITHHELD' for s in feedback.diagnostic_snippets)
        from nexus.repair.focus_service import FocusService
        focus = FocusService(store).prepare(task.id, candidate.id)
        assert focus['status'] == 'PARTIAL' and len(focus['targets']) == 1, focus
        assert focus['targets'][0]['function'] == 'bench.upper'
        save(tmp_path, 'literal-public-feedback', feedback.model_dump())
        save(tmp_path, 'literal-public-focus', focus)
    asyncio.run(verify())
