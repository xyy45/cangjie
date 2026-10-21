from pathlib import Path
from pydantic import Field
from nexus.contracts import ToolRequest, file_hash, source_manifest
from nexus.execution.workspace import WorkspaceStore


class ListRequest(ToolRequest):
    baseline_id: str
    task_id: str | None = None
    prefix: str = ''


class ReadRequest(ToolRequest):
    baseline_id: str
    task_id: str | None = None
    path: str
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class SearchRequest(ListRequest):
    query: str = Field(min_length=1, max_length=256)


def list_files(ws: WorkspaceStore, request: ListRequest) -> dict:
    root = ws.verify_baseline(request.baseline_id)
    visible=visible_paths(ws,request.baseline_id,request.task_id)
    return {'files': [{'path': name, 'size': (root / name).stat().st_size}
                      for name in source_manifest(root) if name in visible and name.startswith(request.prefix)], 'build_root': '.'}


def read_file(ws: WorkspaceStore, request: ReadRequest) -> dict:
    if request.path not in visible_paths(ws,request.baseline_id,request.task_id):
        raise ValueError('Source is verification-only or outside the context profile')
    content = ws.read_file(request.baseline_id, request.path)
    lines = content.splitlines(keepends=True)
    end = request.end_line or len(lines)
    if end < request.start_line:
        raise ValueError('invalid line range')
    return {'content': ''.join(lines[request.start_line-1:end]), 'start_line': request.start_line,
            'end_line': min(end, len(lines)), 'file_hash': file_hash(content)}


def search(ws: WorkspaceStore, request: SearchRequest) -> dict:
    matches = []
    for item in list_files(ws, ListRequest(schema_version=request.schema_version,tool_version=request.tool_version,
        request_id=request.request_id,deadline_at=request.deadline_at,baseline_id=request.baseline_id,
        prefix=request.prefix,task_id=request.task_id))['files']:
        for number, line in enumerate(ws.read_file(request.baseline_id, item['path']).splitlines(), 1):
            if request.query in line:
                matches.append({'path': item['path'], 'line': number, 'text': line[:1000]})
            if len(matches) >= 100:
                return {'matches': matches, 'truncated': True}
    return {'matches': matches, 'truncated': False}


def visible_paths(ws: WorkspaceStore, baseline_id: str, task_id: str | None) -> set[str]:
    from nexus.store import RunStore
    from nexus.requirements.service import RequirementService
    if task_id:
        task=RunStore(ws.root).get_task(task_id)
        if task.baseline_id!=baseline_id:
            raise ValueError('foreign baseline')
        if task.schema_version==2:
            _,plan=RequirementService(RunStore(ws.root)).task_context(task)
            return {path for path,visibility in plan.context_visibility.items()
                    if visibility in ('PRODUCTION','PUBLIC_TEST')}
    elif (ws.root/'runs.sqlite3').exists():
        store=RunStore(ws.root)
        with store.connect() as db:
            owners=db.execute("SELECT id FROM tasks WHERE json_extract(payload,'$.baseline_id')=?",(baseline_id,)).fetchall()
        if any(store.get_task(row[0]).schema_version==2 for row in owners):
            raise ValueError('Task ID required for a bound workspace context')
    return set(source_manifest(ws.verify_baseline(baseline_id)))
