"""Durable MCP write ownership in the existing database, never auto-replayed."""
import hashlib
import json
from pathlib import Path

from nexus.contracts import ToolResult
from nexus.store import RunStore, uid


class RequestLedger:
    def __init__(self, store: RunStore):
        self.store=store
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS tool_requests(
                task_id TEXT NOT NULL, request_id TEXT NOT NULL, identity TEXT NOT NULL,
                tool TEXT NOT NULL, state TEXT NOT NULL, request_ref TEXT NOT NULL, result_ref TEXT,
                PRIMARY KEY(task_id,request_id))''')

    def _hash(self, ref: str) -> str:
        path=Path(ref)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] not in ('records','exports'):
            raise ValueError('Invalid operation artifact reference')
        return hashlib.sha256((self.store.root/path).read_bytes()).hexdigest()

    def _artifacts(self, value) -> dict[str,str]:
        refs=set()
        def collect(item):
            if isinstance(item,dict):
                for key,child in item.items():
                    if key.endswith('_ref') and isinstance(child,str) and child:
                        refs.add(child)
                    elif key=='record_refs':
                        refs.update(child)
                    else:
                        collect(child)
            elif isinstance(item,list):
                for child in item:collect(child)
        collect(value)
        return {ref:self._hash(ref) for ref in refs}

    def claim(self, task_id: str, request_id: str, tool: str, identity: str, request: dict):
        self.store.get_task(task_id)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT identity,state,result_ref FROM tool_requests WHERE task_id=? AND request_id=?',
                           (task_id,request_id)).fetchone()
            if row:
                if row[0]!=identity:
                    raise ValueError('REQUEST_ID_REUSED_WITH_CHANGED_INPUT')
                if row[1]!='COMPLETED':
                    return False,ToolResult(operation_status='IN_DOUBT',error='REQUEST_IN_FLIGHT_OR_INTERRUPTED')
                try:
                    saved=json.loads((self.store.root/row[2]).read_text())
                    if any(self._hash(ref)!=expected for ref,expected in saved['artifacts'].items()):
                        raise ValueError('Operation artifact changed')
                    result=ToolResult.model_validate(saved['result'])
                except (OSError,ValueError,KeyError,TypeError):
                    result=ToolResult(operation_status='IN_DOUBT',error='REQUEST_EVIDENCE_MISSING_OR_CHANGED')
                return False,result
            ref=f'records/{uid()}.mcp-request.json'
            with (self.store.root/ref).open('x') as stream:json.dump({'tool':tool,'arguments':request},stream,ensure_ascii=False)
            db.execute('INSERT INTO tool_requests VALUES (?,?,?,?,?,?,NULL)',
                       (task_id,request_id,identity,tool,'STARTED',ref))
        return True,None

    def complete(self, task_id: str, request_id: str, result: ToolResult):
        payload=result.model_dump()
        artifacts=self._artifacts(payload)
        with self.store.connect() as db:
            row=db.execute('SELECT request_ref FROM tool_requests WHERE task_id=? AND request_id=?',
                           (task_id,request_id)).fetchone()
        if row is None:
            raise ValueError('Request ownership missing')
        artifacts[row[0]]=self._hash(row[0])
        ref=f'records/{uid()}.mcp-operation.json'
        with (self.store.root/ref).open('x') as stream:
            json.dump({'result':payload,'artifacts':artifacts},stream,ensure_ascii=False)
        with self.store.connect() as db:
            cursor=db.execute("UPDATE tool_requests SET state='COMPLETED',result_ref=? WHERE task_id=? AND request_id=? AND state='STARTED'",
                              (ref,task_id,request_id))
            if cursor.rowcount!=1:
                raise ValueError('Request ownership changed')
