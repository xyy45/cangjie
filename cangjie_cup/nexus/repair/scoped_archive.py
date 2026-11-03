"""Collect scoped byte originals only from task-owned controller records.

Generic remote JSON `ref` fields never grant local file access. The ordinary
archive walker remains unchanged for legacy records.
"""
import hashlib
import os
from pathlib import PurePosixPath
import re
import stat
from nexus.contracts import CheckResult
from nexus.policy.core import strict_json
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.package_evidence import _records,PARSER

# Aggregate controller JSON repeats bounded inputs/observations/failures across
# up to3 batches; it is not an SDK stdout/XML original. Those remain2MiB/packet.
MAX_CONTROLLER_REPORT=128*1024*1024


def references(store,task):
    directory=_records(store.root);result=set();ws=WorkspaceStore(store.root)
    def owned(identity):
        if identity!=task.baseline_id and ws.candidate(identity).task_id!=task.id:raise ValueError('Scoped归档引用其他任务候选')
    def read(ref,identity,limit):
        path=PurePosixPath(ref)
        if type(ref) is not str or path.as_posix()!=ref or len(path.parts)!=2 or path.parts[0]!='records':
            raise ValueError('Scoped归档原件引用无效')
        actual=directory/path.name
        descriptor=os.open(actual,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise ValueError('Scoped归档原件类型或大小无效')
            raw=stream.read(limit+1);after=os.fstat(stream.fileno())
        binding=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if (len(raw)>limit or binding(before)!=binding(after) or actual.is_symlink() or binding(actual.stat())!=binding(after) or
                hashlib.sha256(raw).hexdigest()!=identity):raise ValueError('Scoped归档原件摘要变化')
        return raw
    def packet(proof):
        if proof.get('version')!=1 or type(proof['version']) is not int or proof.get('parser')!=PARSER:
            raise ValueError('Scoped归档协议无效')
        descriptors=[]
        if type(proof.get('scans')) is not list or len(proof['scans'])>16:raise ValueError('Scoped扫描原件数量无效')
        for scan in proof['scans']:descriptors.extend([scan['stdout'],scan['stderr']])
        if proof['test'] is not None:
            test=proof['test']
            if type(test['reports']) is not dict or len(test['reports'])>257:raise ValueError('Scoped XML原件数量无效')
            descriptors.extend([test['stdout'],*test['reports'].values()])
        total=0
        for item in descriptors:
            if (type(item) is not dict or set(item)!={'ref','sha256','bytes'} or
                    type(item['bytes']) is not int or not 0<=item['bytes']<=2*1024*1024 or
                    type(item['ref']) is not str or not re.fullmatch(r'records/[0-9a-f]{32}\.(scan|stderr|log|xml)',item['ref'])):
                raise ValueError('Scoped原件描述无效')
            total+=item['bytes']
            if total>2*1024*1024:raise ValueError('Scoped原件总量超限')
            if len(read(item['ref'],item['sha256'],item['bytes']))!=item['bytes']:raise ValueError('Scoped原件长度变化')
            result.add(item['ref'])
    for raw in store.records(task.id,'check'):
        check=CheckResult.model_validate(raw)
        if check.package_evidence is not None:owned(check.subject_id);packet(check.package_evidence)
    with store.connect() as db:
        for table in ('exploration_runs','property_runs','relation_runs','sequence_runs'):
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():continue
            rows=db.execute('SELECT candidate_id,report_ref,report_sha256 FROM '+table+' WHERE task_id=?',(task.id,)).fetchall()
            for candidate,reference,identity in rows:
                if reference is None:continue  # Unfinished attempts have no fabricated report.
                owned(candidate);report=strict_json(read(reference,identity,MAX_CONTROLLER_REPORT))
                if report['candidate_id']!=candidate or report['binding']['task_id']!=task.id:raise ValueError('Scoped验证报告归属变化')
                if type(report['batches']) is not list or len(report['batches'])>3:raise ValueError('Scoped验证批次数量无效')
                for batch in report['batches']:packet(batch['scoped']['package_evidence'])
    return result
