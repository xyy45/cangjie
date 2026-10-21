from nexus.contracts import ToolRequest
from nexus.adapters.cangjie.verifier import CangjieVerifier


class DiagnoseRequest(ToolRequest):
    task_id: str
    request_id: str
    subject_id: str


async def diagnose(root, request: DiagnoseRequest) -> dict:
    verifier = CangjieVerifier(root, request.task_id, deadline_at=request.deadline_at)
    build = await verifier.build(request.subject_id)
    test = await verifier.test(request.subject_id)
    return {'build': build.model_dump(), 'test': test.model_dump(),
            'analysis': [], 'limitations': ['未启用课题组仓颉分析']}
