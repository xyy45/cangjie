import pytest
from pydantic import ValidationError
from nexus.contracts import CandidateProposal, ModelCall, tree_hash


def test_proposal_cannot_set_verified_or_approval():
    valid = dict(edits=[dict(path='src/a.cj', before_hash='a'*64, content='package a')],
                 requirement_refs=['goal'])
    CandidateProposal(**valid)  # The control proposal is otherwise valid.
    for key in ('verified', 'approval', 'origin', 'candidate_id'):
        with pytest.raises(ValidationError) as caught:
            CandidateProposal(**valid, **{key: True})
        assert [(e['loc'], e['type']) for e in caught.value.errors()] == [((key,), 'extra_forbidden')]


def test_proposal_requires_existing_cj_paths_and_bounded_edits():
    for path in ('/tmp/x.cj', '../x.cj', 'src/x_test.cj', 'cjpm.toml'):
        with pytest.raises(ValidationError):
            CandidateProposal(edits=[dict(path=path, before_hash='a'*64, content='x')], requirement_refs=['goal'])


def test_wrong_origin_rejected():
    with pytest.raises(ValidationError):
        ModelCall(id='m', task_id='t', origin='MOCK', model_id='deepseek', request_ref='x', status='STARTED')


def test_hash_covers_tests_and_config_but_not_build_products(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/a.cj').write_text('a')
    (tmp_path / 'src/a_test.cj').write_text('tests')
    (tmp_path / 'cjpm.toml').write_text('config')
    first = tree_hash(tmp_path)
    (tmp_path / 'target').mkdir()
    (tmp_path / 'target/a').write_text('binary')
    assert tree_hash(tmp_path) == first
    (tmp_path / 'src/a_test.cj').write_text('changed tests')
    assert tree_hash(tmp_path) != first
