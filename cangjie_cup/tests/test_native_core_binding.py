"""Legacy task readers must not grant old approvals current execution rights."""
import pytest

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.policy.core import NativeCoreClient
from test_delivery import checked


@pytest.mark.parametrize('unavailable',[False,True])
def test_legacy_approval_is_invalid_after_active_core_changes(tmp_path,monkeypatch,unavailable):
    ws,store,c,delivery=checked(tmp_path)
    assert store.get_task(c.task_id).schema_version==1
    acceptance=delivery.accept(c.id,delivery.check_set_hash(c.id))
    previous=CangjieVerifier(tmp_path,c.task_id).identity(c.id)[2]
    actual=NativeCoreClient().component_identity()
    def changed(self):
        if unavailable:raise ValueError('Native core unavailable')
        return {**actual,'core_component_hash':'f'*64}
    monkeypatch.setattr(NativeCoreClient,'component_identity',changed)
    current=CangjieVerifier(tmp_path,c.task_id).identity(c.id)[2]
    assert current!=previous, 'active legacy verification plan did not bind its actual native core'
    with pytest.raises(ValueError):delivery.check_set_hash(c.id)
    with pytest.raises(ValueError):delivery.acceptance(c.id,acceptance.id)
    with pytest.raises(ValueError):delivery.export(c.id,acceptance.id)
    assert store.get_task(c.task_id).status=='REVIEW_PENDING'
