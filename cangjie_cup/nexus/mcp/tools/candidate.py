"""Candidate route contracts. Mutations remain gated in the server."""
from nexus.contracts import CandidateProposal, ToolRequest


class ApplyRequest(ToolRequest):
    task_id: str
    request_id: str
    proposal: CandidateProposal


class DiffRequest(ToolRequest):
    task_id: str
    request_id: str
    candidate_id: str


class CheckRequest(DiffRequest):
    expected_tree_hash: str


class ExportRequest(DiffRequest):
    acceptance_id: str
