"""Durable suggestion requests, separate from repair tasks and approvals."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

from nexus.contracts import digest
from nexus.execution.ownership import owner_token,verify_write_owner
from nexus.policy.core import strict_json
from nexus.store import uid
from nexus.uploads.service import UploadService
from nexus.uploads.rule_contract import draft_snapshot,validate_suggestion,encoded,MAX_RESPONSE


class DraftConflict(ValueError):pass


class DraftCallError(RuntimeError):
    def __init__(self,code,*,uncertain=False,evidence=None):
        self.code=code;self.uncertain=uncertain;self.evidence=evidence
        super().__init__(code)


def stamp():return datetime.now(timezone.utc).isoformat()
def sha(raw):return hashlib.sha256(raw).hexdigest()


class RuleDraftService:
    def __init__(self,store,*,provider_factory=None):
        self.store=store;self.uploads=UploadService(store);self.owner=owner_token(store.root)
        self.root=store.root/'rule-drafts';self.provider_factory=provider_factory
        if self.root.is_symlink():raise ValueError('草案存储目录不可为链接')
        self.root.mkdir(exist_ok=True,mode=0o700)
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS rule_draft_requests(
                id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,request_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,effect_hash TEXT NOT NULL,call_state TEXT NOT NULL,
                payload TEXT NOT NULL,UNIQUE(actor_id,request_key))''')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS rule_draft_pending ON rule_draft_requests(actor_id,effect_hash) WHERE call_state IN ('CREATED','STARTED','IN_DOUBT')")

    def directory(self,identity):
        if not isinstance(identity,str) or not re.fullmatch('rd_[a-f0-9]{32}',identity):raise LookupError('草案不存在')
        path=self.root/identity
        if self.root.is_symlink() or path.is_symlink():raise ValueError('草案存储引用无效')
        return path

    def _write(self,identity,kind,value):
        verify_write_owner(self.store.root,self.owner)
        raw=encoded(value)
        limit=3*MAX_RESPONSE if kind=='response' else MAX_RESPONSE
        if len(raw)>limit:raise ValueError('草案原件大小超限')
        p=self.directory(identity)/(kind+'.json')
        with p.open('xb') as stream:p.chmod(0o600);stream.write(raw)
        return {kind+'_sha256':sha(raw)}

    def _read(self,identity,payload,kind):
        expected=payload.get(kind+'_sha256')
        if expected is None:return None
        p=self.directory(identity)/(kind+'.json')
        limit=3*MAX_RESPONSE if kind=='response' else MAX_RESPONSE
        if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:raise ValueError('草案原件引用无效')
        raw=p.read_bytes()
        if sha(raw)!=expected:raise ValueError('草案原件摘要变化')
        return strict_json(raw)

    def _row(self,identity,actor_id=None):
        self.directory(identity)
        with self.store.connect() as db:
            row=db.execute('SELECT actor_id,call_state,payload FROM rule_draft_requests WHERE id=?',(identity,)).fetchone()
        if not row or actor_id is not None and actor_id!=row[0]:raise LookupError('草案不存在')
        return row[0],row[1],json.loads(row[2])

    def _input(self,identity,payload):
        s=self._read(identity,payload,'input')
        if not s or s.get('binding_hash')!=payload['binding_hash'] or s['binding_hash']!=digest({k:v for k,v in s.items() if k!='binding_hash'}):
            raise ValueError('草案输入绑定变化')
        return s

    def _current(self,identity,payload,actor_id):
        old=self._input(identity,payload)
        paths=old['allowed_paths'] if self.uploads.get(old['upload_id'],actor_id=actor_id).get('kind')=='PROJECT' else None
        current=draft_snapshot(self.uploads,old['upload_id'],actor_id=actor_id,expected_version=old['upload_version'],function=old['signature']['name'],allowed_paths=paths)
        if current!=old:raise DraftConflict('源码、需求、函数或范围已变化，请重新准备')
        return current

    def create(self,upload_id,*,actor_id,expected_version,function,request_key,consent,allowed_paths=None):
        verify_write_owner(self.store.root,self.owner)
        if consent is not True or not isinstance(request_key,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',request_key):
            raise ValueError('请明确同意生成时发送所选源码与需求，并提供请求标识')
        snapshot=draft_snapshot(self.uploads,upload_id,actor_id=actor_id,expected_version=expected_version,function=function,allowed_paths=allowed_paths)
        fingerprint=snapshot['binding_hash']
        effect=digest({k:v for k,v in snapshot.items() if k not in ('upload_id','upload_version','binding_hash')})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id,request_hash FROM rule_draft_requests WHERE actor_id=? AND request_key=?',(actor_id,request_key)).fetchone()
            if old:
                if old[1]!=fingerprint:raise DraftConflict('同一草案请求不能绑定不同输入')
                return self.get(old[0],actor_id=actor_id)
            if db.execute("SELECT 1 FROM rule_draft_requests WHERE actor_id=? AND effect_hash=? AND call_state IN ('CREATED','STARTED','IN_DOUBT')",(actor_id,effect)).fetchone():
                raise DraftConflict('已有同输入待完成或待核实请求；查询原记录，不得重发')
            if db.execute("SELECT count(*) FROM rule_draft_requests WHERE actor_id=? AND json_extract(payload,'$.upload_id')=?",(actor_id,upload_id)).fetchone()[0]>=3:
                raise DraftConflict('每份上传最多3个草案请求；已有原件可继续查看，修复轮次预算不受影响')
            identity='rd_'+uid();self.directory(identity).mkdir(mode=0o700)
            payload=dict(schema_version=1,id=identity,upload_id=upload_id,binding_hash=fingerprint,
                created_at=stamp(),updated_at=stamp(),origin=None,model_id=None,usage={},error_code=None,
                **self._write(identity,'input',snapshot))
            db.execute('INSERT INTO rule_draft_requests VALUES (?,?,?,?,?,?,?)',(identity,actor_id,request_key,fingerprint,effect,'CREATED',json.dumps(payload,ensure_ascii=False)))
        return self.get(identity,actor_id=actor_id)

    def _save(self,identity,payload,state):
        verify_write_owner(self.store.root,self.owner)
        payload['updated_at']=stamp()
        with self.store.connect() as db:
            return db.execute("UPDATE rule_draft_requests SET call_state=?,payload=? WHERE id=? AND call_state='STARTED'",(state,json.dumps(payload,ensure_ascii=False),identity)).rowcount==1

    def run(self,identity):
        verify_write_owner(self.store.root,self.owner)
        with self.store.connect() as db:
            claimed=db.execute("UPDATE rule_draft_requests SET call_state='STARTED' WHERE id=? AND call_state='CREATED'",(identity,)).rowcount
        if not claimed:return False
        actor,_,payload=self._row(identity);wire_started=False
        try:
            snapshot=self._current(identity,payload,actor)
            if self.provider_factory is None:
                from nexus.demo.rule_draft_provider import RuleDraftProvider
                provider=RuleDraftProvider()
            else:provider=self.provider_factory()
            body=provider.prepare(deepcopy(snapshot))
            payload.update(self._write(identity,'request',body),origin=provider.origin)
            if not self._save(identity,payload,'STARTED'):return True
            # Complete request-body content is durable; HTTP serialization may differ.
            wire_started=True
            reply=asyncio.run(provider.complete(deepcopy(body)))
            payload.update(self._write(identity,'response',reply))
            result=validate_suggestion(reply['raw_text'],snapshot)
            payload.update(self._write(identity,'result',result),model_id=reply['model_id'],usage=reply.get('usage',{}))
            self._save(identity,payload,'SUCCEEDED')
        except DraftCallError as exc:
            if exc.evidence is not None:payload.update(self._write(identity,'response',exc.evidence))
            payload['error_code']=exc.code
            self._save(identity,payload,'IN_DOUBT' if exc.uncertain else 'FAILED')
        except Exception:
            # Error bodies, credentials and source snippets never become errors.
            payload['error_code']='REQUEST_UNRESOLVED' if wire_started else 'DRAFT_INPUT_OR_ENVIRONMENT_UNAVAILABLE'
            self._save(identity,payload,'IN_DOUBT' if wire_started else 'FAILED')
        return True

    def get(self,identity,*,actor_id):
        _,state,payload=self._row(identity,actor_id)
        snapshot=self._input(identity,payload)
        request=self._read(identity,payload,'request');reply=self._read(identity,payload,'response');result=self._read(identity,payload,'result')
        if result is not None:
            if (reply is None or type(result) is not dict or
                    result!=validate_suggestion(reply.get('raw_text'),snapshot,result_version=result.get('schema_version'))):
                raise ValueError('草案结果与原始响应不符')
        return {**payload,'call_state':state,'result':result,
                'binding':{k:v for k,v in snapshot.items() if k!='files'}}

    def list(self,upload_id,*,actor_id):
        self.uploads.get(upload_id,actor_id=actor_id)
        with self.store.connect() as db:
            rows=db.execute("SELECT id FROM rule_draft_requests WHERE actor_id=? AND json_extract(payload,'$.upload_id')=? ORDER BY rowid DESC LIMIT 10",(actor_id,upload_id)).fetchall()
        return [self.get(identity,actor_id=actor_id) for identity, in rows]

    def apply_preview(self,identity,*,actor_id,expected_version,function,allowed_paths=None,examples_only=False):
        if type(examples_only) is not bool:raise ValueError('草案应用方式无效')
        state=self.get(identity,actor_id=actor_id)
        actor,_,payload=self._row(identity,actor_id)
        snapshot=self._current(identity,payload,actor)
        if type(expected_version) is not int or expected_version!=snapshot['upload_version'] or function!=snapshot['signature']['name']:
            raise DraftConflict('草案不属于当前函数和上传版本')
        upload=self.uploads.get(snapshot['upload_id'],actor_id=actor_id)
        expected_paths=snapshot['allowed_paths'] if upload.get('kind')=='PROJECT' else None
        if allowed_paths!=expected_paths:raise DraftConflict('草案不属于当前选择的生产范围')
        result=state['result']
        if state['call_state']!='SUCCEEDED' or not result or result['status'] not in ('DRAFT_READY','EXAMPLES_READY'):
            raise DraftConflict('草案尚不可应用，请先核对问题或状态')
        examples_only=examples_only or result['status']=='EXAMPLES_READY'
        reference=dict(id=identity,binding_hash=snapshot['binding_hash'],result_sha256=state['result_sha256'])
        if examples_only:reference['examples_only']=True
        return dict(examples_json=result['examples_json'],oracle_json=None if examples_only else result['oracle_json'],
                    rule_draft_ref=reference,business_verified=False)

    def confirmation_material(self,reference,*,upload_id,actor_id,expected_version,function,allowed_paths,examples,oracle):
        fields={'id','binding_hash','result_sha256'}
        if type(reference) is not dict or (set(reference)!=fields and
                (set(reference)!=fields|{'examples_only'} or reference.get('examples_only') is not True)):
            raise ValueError('草案来源字段无效')
        examples_only=reference.get('examples_only',False)
        state=self.get(reference['id'],actor_id=actor_id)
        _,_,payload=self._row(reference['id'],actor_id)
        old=self._input(reference['id'],payload);upload=self.uploads.get(upload_id,actor_id=actor_id)
        if (state['upload_id']!=upload_id or reference['binding_hash']!=state['binding_hash'] or
                reference['result_sha256']!=state.get('result_sha256') or state['call_state']!='SUCCEEDED' or
                not state['result'] or state['result']['status'] not in
                (('DRAFT_READY','EXAMPLES_READY') if examples_only else ('DRAFT_READY',))):
            raise ValueError('草案来源与生成结果不符')
        paths=allowed_paths if upload.get('kind')=='PROJECT' else ['src/uploaded.cj']
        if (type(expected_version) is not int or expected_version!=old['upload_version'] or
                function!=old['signature']['name'] or paths!=old['allowed_paths'] or
                upload['source_sha256']!=old['source_sha256'] or upload['goal']!=old['goal']):
            raise ValueError('草案来源与当前上传、函数或范围不符')
        if upload['status']=='DRAFT':self._current(reference['id'],payload,actor_id)
        generated=dict(examples=state['result']['suggestion']['examples'],
                       oracle=None if examples_only else state['result']['normalized_oracle'])
        confirmed=dict(examples=examples,oracle=oracle)
        proof=dict(schema_version=1,rule_draft_id=reference['id'],source_binding_hash=old['binding_hash'],
                   result_sha256=state['result_sha256'],model_id=state['model_id'],origin=state['origin'],business_verified=False,
                   generated_payload_hash=digest(generated),confirmed_payload_hash=digest(confirmed),edited_by_user=digest(generated)!=digest(confirmed))
        files={}
        for kind in ('input','request','response','result'):
            # get() has already replay-validated these exact immutable originals.
            raw=(self.directory(reference['id'])/(kind+'.json')).read_bytes()
            if sha(raw)!=payload[kind+'_sha256']:raise ValueError('草案原件在确认前变化')
            files['verification/rule-draft/'+kind+'.json']=raw
        files['verification/rule-draft/provenance.json']=encoded(proof)
        return proof,files

    def reconcile(self):
        verify_write_owner(self.store.root,self.owner)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute("SELECT id,call_state,payload FROM rule_draft_requests WHERE call_state IN ('CREATED','STARTED')").fetchall()
            for identity,state,raw in rows:
                payload=json.loads(raw);payload.update(error_code='CONTROLLER_RESTARTED_NO_REPLAY',updated_at=stamp())
                db.execute('UPDATE rule_draft_requests SET call_state=?,payload=? WHERE id=?',('IN_DOUBT' if state=='STARTED' else 'FAILED',json.dumps(payload,ensure_ascii=False),identity))
        return len(rows)
