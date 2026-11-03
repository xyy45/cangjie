"""Two team-authored fixtures for the active 4C upload/verification contracts."""
from pathlib import Path
import json
import zipfile

ROOT=Path(__file__).resolve().parent
CONFIG='[package]\nname = "bench"\nversion = "1.0.0"\ncjc-version = "1.0.5"\noutput-type = "static"\n\n[dependencies]\n'
LOCK='version = 0\n[requires]\n'


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def project(folder, sources, fixed, goal, examples, models, function, allowed):
    folder=ROOT/folder;folder.mkdir(exist_ok=False)
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**sources}
    for name,text in files.items():
        p=folder/'工程源码'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    with zipfile.ZipFile(folder/'上传这个工程.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name,text in files.items():z.writestr(name,text)
    (folder/'预期行为.txt').write_text(goal+'\n')
    (folder/'LLM修复提示词.txt').write_text(goal+'\n\n请检查全部相关允许修改文件，修复业务逻辑，保留现有函数签名、对象字段与public可见性。不得修改测试、配置或规则，不得用硬编码样例替代业务实现。请在原有受限仓颉语法内实现。\n')
    dump(folder/'输入与预期输出.json',examples)
    for name,value in models.items():dump(folder/(name+'.json'),value)
    for name,text in fixed.items():
        p=folder/'参考修复_不要上传'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    dump(folder/'案例信息.json',dict(function=function,allowed_paths=allowed,models=list(models),origin='TEAM_AUTHORED_SYNTHETIC'))


sources={'src/amount.cj':'''package bench

public func netRefund(refunds: Array<Int64>): Int64 {
    var total: Int64 = 0
    var index: Int64 = 0
    while (index < refunds.size) {
        let amount = refunds[index]
        if (amount > 0) {
            total = total + amount
        }
        index = index + 1
    }
    return total
}
''','src/refund.cj':'''package bench

public func refundTotal(refunds: Array<Int64>, paid: Int64): Int64 {
    if (paid < 0 || paid > 10000000) { return -1 }
    let total = netRefund(refunds)
    if (total < 0 || total >= paid) { return -1 }
    return total
}
'''}
fixed={'src/amount.cj':sources['src/amount.cj'].replace('if (amount > 0) {\n            total = total + amount\n        }','total = total + amount'),
       'src/refund.cj':sources['src/refund.cj'].replace('total >= paid','total > paid')}
domains=dict(refunds=dict(values=[[],[300,-100],[500,500],[100,-100],[-100],[100],[200,100],[100,200]]),paid=dict(min=0,max=2000,points=[200,500,1000]))
expression='array_sum(refunds) if 0 <= array_sum(refunds) <= paid else -1'
examples=[dict(args=[[300,-100],1000],expected=200,suite='target'),dict(args=[[500,500],1000],expected=1000,suite='target'),dict(args=[[],1000],expected=0,suite='regression'),dict(args=[[],0],expected=0,suite='target')]
models={'独立业务规则':dict(version=4,function='refundTotal',domains=domains,expression=expression,seed=17,max_cases=32,excluded_inputs=[]),
 '业务属性':dict(version=3,kind='single',function='refundTotal',domains=domains,properties=[dict(id='PROP-NET',text='冲正金额参与净退款计算且允许等于实付',precondition='True',assertion='result == (array_sum(arg0) if 0 <= array_sum(arg0) <= arg1 else -1)')],seed=17,max_cases=32,excluded_inputs=[]),
 '成对关系':dict(version=3,kind='relation',function='refundTotal',domains=domains,relations=[dict(id='REL-PAID',text='两份实付金额均足够时同一明细的净退款结果不变',precondition='left_arg0 == right_arg0 and 0 <= array_sum(left_arg0) <= left_arg1 and left_arg1 <= right_arg1',assertion='left_result == right_result')],seed=17,max_pairs=32,excluded_inputs=[])}
project('案例1_数组退款与跨文件',sources,fixed,
 '函数refundTotal(refunds, paid)计算净退款，单位为分。refunds最多16项，测试范围内每项绝对值不超过100000，正数表示退款、负数表示退款冲正，全部项目都必须参与求和。paid为0至10000000；paid非法、净退款为负或超过paid时返回-1，否则返回净退款。净退款恰好等于paid有效；空数组返回0，包括paid=0。检查netRefund与refundTotal两个函数，保持接口不变。',examples,models,'refundTotal',list(sources))


def quota(a,r):return {'$type':'QuotaState','fields':{'available':a,'reserved':r}}


sources={'src/state.cj':'''package bench

public struct QuotaState {
    public let available: Int64
    public let reserved: Int64
    public init(available: Int64, reserved: Int64) {
        this.available = available
        this.reserved = reserved
    }
    public func total(): Int64 { this.available + this.reserved }
}
''','src/quota.cj':'''package bench

public func applyQuota(state: QuotaState, action: String): QuotaState {
    if (action == "reserve") {
        if (state.available <= 10) { return state }
        return QuotaState(state.available - 10, state.reserved + 10)
    }
    if (action == "cancel") {
        if (state.reserved < 10) { return state }
        return QuotaState(state.available + 10, state.reserved)
    }
    return state
}
'''}
fixed={'src/quota.cj':sources['src/quota.cj'].replace('state.available <= 10','state.available < 10').replace('state.available + 10, state.reserved)','state.available + 10, state.reserved - 10)')}
states=[quota(0,0),quota(10,0),quota(20,0),quota(0,10),quota(10,10),quota(0,20)]
domains=dict(state=dict(values=states),action=dict(values=['reserve','cancel','noop']))
reserve='object_with(object_with(state,"available",object_get(state,"available")-10),"reserved",object_get(state,"reserved")+10) if object_get(state,"available") >= 10 else state'
cancel='object_with(object_with(state,"available",object_get(state,"available")+10),"reserved",object_get(state,"reserved")-10) if object_get(state,"reserved") >= 10 else state'
expression='('+reserve+') if action == "reserve" else (('+cancel+') if action == "cancel" else state)'
examples=[dict(args=[quota(20,0),'reserve'],expected=quota(10,10),suite='target'),dict(args=[quota(10,0),'cancel'],expected=quota(10,0),suite='regression')]
models={'独立业务规则':dict(version=5,function='applyQuota',domains=domains,expression=expression,seed=23,max_cases=32,excluded_inputs=[]),
 '业务属性':dict(version=4,kind='single',function='applyQuota',domains=domains,properties=[dict(id='PROP-CONSERVE',text='操作前后总额度守恒且两个字段非负',precondition='True',assertion='object_get(result,"available") >= 0 and object_get(result,"reserved") >= 0 and object_get(result,"available")+object_get(result,"reserved") == object_get(arg0,"available")+object_get(arg0,"reserved")')],seed=23,max_cases=32,excluded_inputs=[]),
 '连续操作状态模型':dict(version=4,kind='sequence',function='applyQuota',state_param='state',domains=domains,initial_states=[quota(20,0),quota(10,0)],initial_precondition='True',context_params=[],operations=[dict(id='OP-RESERVE',text='预留10额度',args=['reserve'],transition=reserve),dict(id='OP-CANCEL',text='取消10预留',args=['cancel'],transition=cancel)],invariants=[dict(id='INV-EXACT',text='每一步遵守参考状态且额度守恒',precondition='True',assertion='result == expected_state and object_get(result,"available") >= 0 and object_get(result,"reserved") >= 0 and object_get(result,"available")+object_get(result,"reserved") == object_get(initial_state,"available")+object_get(initial_state,"reserved")')],seed=23,max_sequences=16,max_steps=4,excluded_inputs=[])}
project('案例2_对象额度与连续操作',sources,fixed,
 'applyQuota(state, action)处理额度预留与取消。state包含非负available和reserved，测试初始总额度不超过20。action="reserve"时，available>=10就将10从available移至reserved；不足10原样返回。action="cancel"时，reserved>=10就将10从reserved移回available；不足10原样返回。其他action不改变状态。每一步两个字段非负、总额度守恒；预留后取消应还原初始状态，连续取消不能凭空增加额度。必须保留QuotaState类型、字段、构造和total方法，只允许修改src/quota.cj。',examples,models,'applyQuota',['src/quota.cj'])

(ROOT/'先看这里.md').write_text('''# 两个新功能测试案例

适用于当前8877的4C稳定版，无跨包导入。每个案例都是有意包含业务缺陷的自建代码。

1. 打开 http://127.0.0.1:8877/ ，点击“上传文件修复”，选择对应案例的“上传这个工程.zip”。不要上传整个案例资料文件夹或参考修复。
2. 导入“预期行为.txt”，读取工程并选择“案例信息.json”中的function；确认允许修改的文件。
3. 输入与预期输出导入“输入与预期输出.json”。所有expected已填写，无null。对象输入必须保留$type与fields，不能只填普通字段字典。
4. 可选“生成草案”体验自然语言辅助：单独同意发送并生成后先检查，不要让草案覆盖已经核对的测试；直接导入本资料也能测试修复闭环。
5. 为了先看清效果，每次仅启用一种附加验证：案例1建议先导入“独立业务规则.json”，也可另开任务试“业务属性.json”或“成对关系.json”；案例2建议只导入“连续操作状态模型.json”，也可另开任务试规则或属性。
6. 在对应“导入规则／导入属性／导入关系／导入状态模型”按钮选择文件，确认冻结后开始修复。模型调用由网页中的发送授权和开始动作触发，产生真实请求；本资料的本地核验不调用模型或远程MCP。
7. 检查反例、失败步骤、两轮差异、真实SDK报告，修复通过后审阅导出。不能保证模型一定修好；有限规则搜索不证明全部输入正确。

案例1：Array<Int64>、同包跨文件、负冲正遗漏与等额边界；两个源码文件都允许修改。

案例2：struct、String操作、纯方法、状态序列。默认两条公开测试刻意都能被缺陷版通过，必须启用状态模型或独立规则／属性，才能检验“普通测试通过但主动验证发现漏洞”的新能力。例：(20,0) reserve→(10,10)，再次reserve应为(0,20)；reserve后cancel应回(20,0)。

参考修复仅用于核对系统产物，不要放入上传ZIP或发送给模型。SDK核验结果会写入“本地验证结果.json”；其验证对象是缺陷及手写参考，不是DeepSeek修复效果。
''')
print(ROOT)
