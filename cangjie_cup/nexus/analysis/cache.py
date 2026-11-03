"""Short-lived reuse of verified observations, scoped to actor and tool identity."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time

from nexus.analysis.normalize import TOOLS,normalize

PROFILE=6
CACHE_SECONDS=300


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def arguments(tool,source,criterion):
    args=dict(code=source['code'],filename=source['filename'],lang='cangjie')
    if tool=='sympas_slice_table':args.update(direction='Bwd',method='SymPas',table_formats=['json'],timeout_sec=40)
    if tool=='sympas_slice':args.update(**criterion,format='json')
    if tool=='sympas_dep_graph':args.update(graph_types='Ddg,Cg,Pdg',formats=['dot','svg'])
    return args


def key(source,origin,criterion,scope):
    if not isinstance(scope,str) or not re.fullmatch('[0-9a-f]{64}',scope):return None
    root=Path(__file__).parent
    pipeline={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in ('cache.py','client.py','service.py','normalize.py','recovery.py','point.py')}
    return digest(dict(profile=PROFILE,pipeline=pipeline,scope=scope,source=source['source_sha256'],
                       filename=source['filename'],origin=origin,criterion=criterion))


def verified(service,identity,actor_id,expected_key):
    """Return the original timestamp, never a new execution time or fabricated data."""
    report=service.get(identity,actor_id=actor_id)
    root=service.directory(identity)
    if not report.get('result_sha256'):raise ValueError('缓存缺少封存原件')
    original=json.loads((root/'result.json').read_bytes())
    for field in ('id','status','source','analysis_profile','cache_key','completed_at','observations','slice_criterion','origin'):
        if original.get(field)!=report.get(field):raise ValueError('缓存元数据与封存原件不符')
    if (report['status']!='COMPLETE' or report.get('analysis_profile')!=PROFILE or
            report.get('cache_key')!=expected_key):raise ValueError('缓存执行绑定不符')
    observations=report['observations']
    if len(observations)!=len(TOOLS) or {o['tool'] for o in observations}!=set(TOOLS):raise ValueError('缓存工具证据不完整')
    for o in observations:
        raw=json.loads((root/o['raw_ref']).read_bytes())
        if (raw.get('tool')!=o['tool'] or raw.get('source_sha256')!=report['source']['source_sha256'] or
                raw.get('input')!=arguments(o['tool'],report['source'],report['slice_criterion']) or
                raw.get('request_id')!=o['request_id'] or raw.get('http_status')!=200 or o.get('http_status')!=200):
            raise ValueError('缓存工具输入绑定不符')
        checked=normalize(o['tool'],raw.get('response'),report['source']['filename'],report['source']['line_count'])
        if checked['status']!='VALID' or o['status']!='VALID' or checked['data']!=o['data']:
            raise ValueError('缓存工具结果不符')
    try:
        stamp=datetime.fromisoformat(report['completed_at'])
        if stamp.tzinfo is None:raise ValueError('缓存时间无时区')
        age=time.time()-stamp.timestamp()
    except (ValueError,KeyError,TypeError) as exc:raise ValueError('缓存完成时间无效') from exc
    return report['completed_at'] if 0<=age<=CACHE_SECONDS else None
