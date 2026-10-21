"""One disclosed deterministic proposal. No model, key or paid request."""
from nexus.contracts import CandidateProposal
from nexus.llm.provider import ProviderUnavailable


class RuleProvider:
    def __init__(self, store, task_id):
        self.store, self.task_id = store, task_id

    async def propose(self, context):
        source = context.get('files', {}).get('src/quantity.cj', {})
        before = source.get('content', '')
        if ('src/quantity.cj' not in context.get('allowed_paths', []) or
                before.count('quantity >= 0') != 1):
            raise ProviderUnavailable('Registered rule does not match the baseline')
        proposal = CandidateProposal(edits=[dict(path='src/quantity.cj',
            before_hash=source['file_hash'], content=before.replace('quantity >= 0', 'quantity >= 1', 1))],
            requirement_refs=['REQ-QTY'])
        self.store.append_record(self.task_id, 'event', dict(type='RULE_PROPOSAL',
            provider='RULE', model_called=False, rule='quantity-lower-bound-v1'))
        return proposal
