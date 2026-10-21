"""Fixed replay evidence and explicitly synthetic presentation cases."""
from copy import deepcopy
import difflib
import hashlib
import io
import json
from pathlib import Path
import zipfile
from nexus.scenarios import scenarios

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / 'data'
STAGES = ['需求确认', '工程检索', '候选生成', '策略检查', '工程验证', '人工审阅', '交付归档']


def changed(path, before, after):
    return dict(path=path, before=before, after=after, diff=''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True), fromfile='a/'+path, tofile='b/'+path)))


def load_cases():
    archive = (DATA/'order-live.zip').read_bytes()
    if hashlib.sha256(archive).hexdigest() != 'c109f3ab1ab63b322b9a172626853ae9b9437bc7b29c9b2d24df809b70806a22':
        raise ValueError('Historical artifact identity changed')
    summary = json.loads((DATA/'order-live-summary.json').read_text())
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest = json.loads(z.read('manifest.json'))
        if any(hashlib.sha256(z.read(n)).hexdigest() != h for n,h in manifest['files'].items()):
            raise ValueError('Historical evidence changed')
        after = z.read('project/src/quantity.cj').decode()
    before = (ROOT/'fixtures/order-demo-bug/src/quantity.cj').read_text()
    tests = next(c for c in summary['checks'] if c['kind']=='test')
    order = dict(id='order', title='订单边界修复', category='边界逻辑', origin='LIVE_REPLAY',
        source_label='回放', provider='AI', language='Cangjie', verdict='ALLOW', stages=STAGES,
        requirement='数量 1–1000；单价 0–1000000；非法订单返回 -1；合法订单总额为数量乘单价。',
        requirements=['数量边界', '单价范围', '总额计算'],
        files=[changed('src/quantity.cj', before, after)],
        metrics=dict(files=1, tests=11, tokens=4529, seconds=summary['elapsed_seconds'], candidates=1),
        checks=[dict(name='工程构建',state='RECORDED_PASS'),
                dict(name='目标行为',state='RECORDED_PASS'),dict(name='回归测试',state='RECORDED_PASS')],
        tests=[dict(name=k.split('.')[-1],state='RECORDED_'+v) for k,v in tests['case_results'].items()],
        approval_origin=summary['approval_origin'],
        identity=manifest['project_tree_hash'],
        logs=['LIVE · 2026-10-18', 'DeepSeek · 4529 tokens', 'MCP · stdio',
              'Policy · Allow', 'cjpm build -V · PASS', 'cjpm test · 11/11',
              '目标与回归共用冻结测试集'],
        limitations=['历史执行', '公开测试', '单平台'])
    fee_before=(ROOT/'fixtures/order-demo-bug/src/fee.cj').read_text()
    fee_after=fee_before.replace('quantity * unitPrice', 'unitPrice * quantity')
    if fee_after == fee_before:
        fee_after=fee_before.replace('public func', '// 演示：费用计算保持接口一致\npublic func', 1)
    multi=dict(id='multifile',title='跨文件协同修复',category='多文件',origin='SIMULATED',source_label='模拟',
        provider='预置',language='Cangjie',verdict='ALLOW',stages=STAGES,
        requirement='联动数量校验与费用计算，保留接口及已有行为。',
        requirements=['数量校验', '费用计算', '接口兼容'],
        files=[changed('src/quantity.cj',before,after),changed('src/fee.cj',fee_before,fee_after)],
        metrics=dict(files=2,tests=11,tokens=None,seconds=None,candidates=2),
        checks=[dict(name=n,state='SIMULATED_PASS') for n in ['工程构建','目标行为','回归测试']],
        tests=[dict(name=k.split('.')[-1],state='SIMULATED_PASS') for k in tests['case_results']],
        approval_origin='SIMULATED_UI_REVIEW',identity=None,
        logs=['SIMULATED · 跨文件流程', '候选 1 · 模拟失败', '反馈 · 边界诊断', '候选 2 · 预置修改',
              'Policy · 模拟 Allow', '构建与测试 · 未执行'],limitations=['预置案例','未运行'])
    deny=json.loads((DATA/'policy-deny.json').read_text())
    policy=dict(id='policy',title='越权操作拦截',category='策略防护',origin='NATIVE_REPLAY',source_label='回放',
        provider='手写探针',language='Cangjie',verdict='DENY',stages=STAGES,
        requirement='尝试改写受保护测试；策略应拒绝，原始工程保持不变。',
        requirements=['测试保护','范围约束','基线不变'],
        files=[dict(path='src/order_test.cj',
            before=(ROOT/'fixtures/order-demo-bug/src/order_test.cj').read_text(),
            after=(ROOT/'fixtures/order-demo-bug/src/order_test.cj').read_text(),diff='')],
        metrics=dict(files=0,tests=None,tokens=0,seconds=None,candidates=0),checks=[],tests=[],
        approval_origin='NONE',identity=None,logs=['NATIVE_REPLAY · 手写探针',
            'candidate.apply · ERROR','Policy · Deny','PROTECTED_PATH','基线未变 · 写入 0'],
        limitations=['历史探针'],native_evidence=deny)
    historical={c['id']:c for c in (order,multi,policy)}
    labels={'REQ-QTY':'数量边界','REQ-PRICE':'单价范围','REQ-TOTAL':'总额计算',
            'REQ-DISCOUNT':'优惠门槛','REQ-QUANTITY':'数量校验','REQ-FEE':'费用计算',
            'REQ-CHECKOUT':'结算金额','REQ-STOCK':'申请范围','REQ-REMAINING':'库存余量','REQ-SCOPE':'范围保护'}
    result={}
    for entry in scenarios():
        source=ROOT/entry['source']
        real_files=[dict(path=name,before=(source/name).read_text(),after='',diff='') for name in entry['allowed_paths']]
        case=deepcopy(historical.get(entry['id'],dict(
            id=entry['id'],origin='SAMPLE',source_label='样例',provider='待生成',language='Cangjie',
            verdict='DENY' if entry['kind']=='probe' else 'ALLOW',stages=STAGES,
            files=deepcopy(real_files),checks=[],tests=[],approval_origin='NONE',identity=None,
            metrics=dict(files=None,tests=None,tokens=None,seconds=None,candidates=None),logs=[])))
        case.update(title=entry['title'],category=entry['category'],group=entry['group'],kind=entry['kind'],
            project_id=entry['project_id'],real_files=real_files,can_replay=entry['id'] in historical,
            requirement='；'.join(r['text']+'：'+r['observable_behavior'] for r in entry['requirements']),
            requirements=[labels[r['id']] for r in entry['requirements']],
            requirement_ids=[r['id'] for r in entry['requirements']],limitations=entry['limitations'])
        if entry['kind']=='probe':case['probe_target']=entry['probe_target']
        result[case['id']]=case
    return result


def case_catalog(cases):
    return [{k:deepcopy(c[k]) for k in ('id','title','category','origin','source_label','group','kind','can_replay')} for c in cases.values()]


def download_case(case):
    origin=case['origin']
    out=io.BytesIO()
    provenance=dict(schema_version=1,origin=origin,current_execution=False,
        current_model_call=False,current_human_approval=False,case_id=case['id'],
        historical_approval_origin=case['approval_origin'])
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('demo-provenance.json',json.dumps(provenance,ensure_ascii=False,indent=2))
        if origin=='LIVE_REPLAY':
            z.writestr('original-export.zip',(DATA/'order-live.zip').read_bytes())
            z.writestr('README.md','# 历史回放\n\n2026-10-18 历史导出；当前未执行修复或重新审批。\n')
        else:
            for f in case['files']:z.writestr('project/'+f['path'],f['after'])
            z.writestr('report.json',json.dumps(case,ensure_ascii=False,indent=2))
            z.writestr('README.md','# 模拟演示\n\n预置代码与界面流程；构建和测试未运行，不是已验证交付。\n')
    out.seek(0)
    return out
