"""Team-authored compound rules; difficulty awaits actual repair measurements."""
from copy import deepcopy

VERSION='business-hard-bench-v1-sealed'
HIGH=2**63-1


def domain(low,high,*points):return dict(min=low,max=high,points=list(points))


def function(name,domains,body,kind='Int64'):
    params=', '.join(name+': '+('Int64' if value else 'Bool') for name,value in domains.items())
    return ('package bench\n\npublic func '+name+'('+params+'): '+kind+' {\n    '+body.replace('\n','\n    ')+'\n}\n').encode()


def row(number,family,goal,defect,bad,good,domains,expression,public,witnesses):
    name=f'hard{number:03}'
    return dict(id=f'business_hard_{number:03}',family=family,variant=1,function=name,goal=goal,defect=defect,
                source={'src/logic.cj':function(name,domains,bad)},reference={'src/logic.cj':function(name,domains,good)},
                domains=domains,expression=expression,public_inputs=public,holdout_witnesses=witnesses)


def tasks(count=10):
    if type(count) is not int or count not in (10,30):raise ValueError('组合规则数据支持10或30项')
    result=[]
    result.append(row(1,'cumulative_refund',
        'paid为实付、refunded为已累计退款、requested为本次申请，均为整数分；paid在0..10000、refunded在0..10000、requested在-1..2000。历史累计必须在0..paid，本次必须为正且不超过剩余实付；合法返回新的累计退款，非法返回-1。',
        '只对本次申请与实付比较，漏掉历史累计占用额度。',
        'if (refunded > paid) { return -1 }\nif (requested <= 0 || requested > paid) { return -1 }\nreturn refunded + requested',
        'if (refunded > paid) { return -1 }\nif (requested <= 0 || requested > paid - refunded) { return -1 }\nreturn refunded + requested',
        dict(paid=domain(0,10000,0,100,1000,10000),refunded=domain(0,10000,0,100,900,1000),requested=domain(-1,2000,-1,0,1,100,200,2000)),
        '-1 if refunded > paid or requested <= 0 or requested > paid-refunded else refunded+requested',
        [[1000,0,100],[1000,100,0]],[[1000,900,200],[100,100,1]]))
    result.append(row(2,'discount_order',
        'amount在0..10000分，percent在50..100，threshold在0..10000分，coupon在0..1000分。先按percent百分比折扣并整数截断；以折后金额达到threshold（含等号）判断满减，符合时减coupon，最终最低0。',
        '把满减资格判断及减券放在折扣之前。',
        'var value = amount\nif (value >= threshold) { value = value - coupon }\nif (value < 0) { value = 0 }\nreturn value * percent / 100',
        'var value = amount * percent / 100\nif (value >= threshold) { value = value - coupon }\nif (value < 0) { value = 0 }\nreturn value',
        dict(amount=domain(0,10000,0,100,1000,10000),percent=domain(50,100,50,80,100),threshold=domain(0,10000,0,500,900,10000),coupon=domain(0,1000,0,50,100,1000)),
        'max(0,amount*percent//100-coupon) if amount*percent//100 >= threshold else amount*percent//100',
        [[1000,100,500,100],[100,80,500,50]],[[1000,80,900,100],[1000,80,500,100]]))
    result.append(row(3,'rounded_fee_bounds',
        'amount为0..1000000分，rate为0..1000基点（万分比），floor为0..100分，ceiling为100..500分。金额0不收费；正金额手续费为amount*rate/10000向上取整，再限制在floor至ceiling闭区间。',
        '万分比计算向下截断，非整除的正金额少收费。',
        'if (amount == 0) { return 0 }\nvar fee = amount * rate / 10000\nif (fee < floor) { fee = floor }\nif (fee > ceiling) { fee = ceiling }\nreturn fee',
        'if (amount == 0) { return 0 }\nvar fee = (amount * rate + 9999) / 10000\nif (fee < floor) { fee = floor }\nif (fee > ceiling) { fee = ceiling }\nreturn fee',
        dict(amount=domain(0,1000000,0,1,101,10000,1000000),rate=domain(0,1000,0,1,100,1000),floor=domain(0,100,0,1,100),ceiling=domain(100,500,100,500)),
        '0 if amount == 0 else min(ceiling,max(floor,ceil_div(amount*rate,10000)))',
        [[0,100,1,500],[10000,100,1,500]],[[101,100,1,500],[1,1,0,100]]))
    result.append(row(4,'reservation_release',
        'stock为可用库存、reserved为已预留库存，二者在0..1000；quantity在-2..2000，release为Bool。预留时quantity须正且不超过stock，返回stock-quantity；释放时quantity须正且不超过reserved，返回stock+quantity。任何非法操作返回原stock；函数只返回新的可用库存，不代表数据库或并发操作。',
        '释放库存时误用可用库存代替已预留数量作上限。',
        'if (quantity <= 0) { return stock }\nif (release) {\n    if (quantity > stock) { return stock }\n    return stock + quantity\n}\nif (quantity > stock) { return stock }\nreturn stock - quantity',
        'if (quantity <= 0) { return stock }\nif (release) {\n    if (quantity > reserved) { return stock }\n    return stock + quantity\n}\nif (quantity > stock) { return stock }\nreturn stock - quantity',
        dict(stock=domain(0,1000,0,1,10,1000),reserved=domain(0,1000,0,1,5,10,1000),quantity=domain(-2,2000,-2,0,1,2,1000,2000),release={}),
        'stock+quantity if release and 0 < quantity <= reserved else (stock-quantity if not release and 0 < quantity <= stock else stock)',
        [[10,0,2,False],[10,5,0,True]],[[10,0,1,True],[0,10,1,True]]))
    result.append(row(5,'installment_remainder',
        'total为0..10000分，periods和index在0..12。periods至少1、index从1到periods，否则返回-1。前periods-1期每期为total/periods整数截断，最后一期为剩余金额，所有期数总和须等于total。',
        '最后一期仍只取平均整数，丢失分摊余数。',
        'if (periods < 1 || index < 1 || index > periods) { return -1 }\nreturn total / periods',
        'if (periods < 1 || index < 1 || index > periods) { return -1 }\nlet base = total / periods\nif (index == periods) { return total - base * (periods - 1) }\nreturn base',
        dict(total=domain(0,10000,0,1,100,1200,10000),periods=domain(0,12,0,1,3,12),index=domain(0,12,0,1,3,12)),
        '-1 if periods < 1 or index < 1 or index > periods else (total-(total//periods)*(periods-1) if index == periods else total//periods)',
        [[1200,12,1],[1200,0,1]],[[100,3,3],[1,12,12]]))
    result.append(row(6,'discount_shipping',
        'amount在0..20000分、coupon在0..5000分、threshold在5000..15000分、vip为Bool。折后商品金额为max(0,amount-coupon)；会员或折后金额达到threshold（含）免运费，其余收800分运费。返回折后商品金额加运费。',
        '普通用户的免运费资格使用折前金额，忽略优惠后的门槛。',
        'var net = amount - coupon\nif (net < 0) { net = 0 }\nif (vip || amount >= threshold) { return net }\nreturn net + 800',
        'var net = amount - coupon\nif (net < 0) { net = 0 }\nif (vip || net >= threshold) { return net }\nreturn net + 800',
        dict(amount=domain(0,20000,0,5000,10000,20000),coupon=domain(0,5000,0,1000,2000,5000),threshold=domain(5000,15000,5000,9900,10000,15000),vip={}),
        'max(0,amount-coupon) if vip or max(0,amount-coupon) >= threshold else max(0,amount-coupon)+800',
        [[10000,0,9900,False],[5000,0,9900,True]],[[10000,2000,9900,False],[10000,1000,10000,False]]))
    result.append(row(7,'points_dual_cap',
        'points在0..100000、amount在0..10000分、requested在0..1000分、percent在0..50。每100积分可抵1分，余数积分不可折算；订单抵扣上限为amount*percent/100整数截断。返回requested、积分可抵金额、订单抵扣上限三者的最小值。',
        '只限制积分余额与申请金额，遗漏订单比例抵扣上限。',
        'let balance = points / 100\nvar used = requested\nif (used > balance) { used = balance }\nreturn used',
        'let balance = points / 100\nlet cap = amount * percent / 100\nvar used = requested\nif (used > balance) { used = balance }\nif (used > cap) { used = cap }\nreturn used',
        dict(points=domain(0,100000,0,99,100,10000,100000),amount=domain(0,10000,0,100,1000,10000),requested=domain(0,1000,0,1,10,1000),percent=domain(0,50,0,1,20,50)),
        'min(requested,points//100,amount*percent//100)',
        [[10000,1000,10,50],[0,1000,5,50]],[[100000,100,1000,20],[10000,0,10,50]]))
    result.append(row(8,'safe_product_extreme',
        f'quantity在-1..{HIGH}、price在-1..1000。负数非法返回-1；非负输入在乘积可用Int64表示时返回quantity*price，超过Int64最大值{HIGH}则返回-1。等于最大值仍合法；零价格不除零，非法输入不能先计算溢出的乘积。',
        '安全乘法上界使用大于等于，错误拒绝仍在Int64范围内的整除临界值。',
        f'if (quantity < 0 || price < 0) {{ return -1 }}\nif (price > 0 && quantity >= {HIGH} / price) {{ return -1 }}\nreturn quantity * price',
        f'if (quantity < 0 || price < 0) {{ return -1 }}\nif (price > 0 && quantity > {HIGH} / price) {{ return -1 }}\nreturn quantity * price',
        dict(quantity=domain(-1,HIGH,-1,0,1,2,HIGH//2,HIGH-1,HIGH),price=domain(-1,1000,-1,0,1,2,3,1000)),
        f'-1 if quantity < 0 or price < 0 or (price > 0 and quantity > {HIGH}//price) else quantity*price',
        [[2,3],[-1,1]],[[HIGH,1],[HIGH//2,2]]))
    target=row(9,'cross_file_member_gate',
        'quantity在-2..1000、price在0..10000分、member为Bool。合法数量为1..1000，合法单价为1..10000；任何用户非法输入均返回-1。合法时商品金额为quantity*price，会员免20分服务费，非会员另加20分；会员不得绕过输入校验。检查同包三个文件中的校验、计价和结算函数。',
        '结算入口把非会员作为非法输入拒绝条件，导致会员绕过跨文件校验。',
        'if (!valid009(quantity, price) && !member) { return -1 }\nlet amount = amount009(quantity, price)\nif (member) { return amount }\nreturn amount + 20',
        'if (!valid009(quantity, price)) { return -1 }\nlet amount = amount009(quantity, price)\nif (member) { return amount }\nreturn amount + 20',
        dict(quantity=domain(-2,1000,-2,0,1,2,1000),price=domain(0,10000,0,1,100,10000),member={}),
        '-1 if quantity < 1 or quantity > 1000 or price < 1 or price > 10000 else (quantity*price if member else quantity*price+20)',
        [[1,100,False],[2,100,True]],[[0,100,True],[-1,100,True]])
    helper_domains={k:v for k,v in target['domains'].items() if k!='member'}
    validation=function('valid009',helper_domains,'return quantity >= 1 && quantity <= 1000 && price >= 1 && price <= 10000','Bool')
    amount=function('amount009',helper_domains,'return quantity * price')
    for kind in ('source','reference'):
        target[kind]={'src/order.cj':target[kind]['src/logic.cj'],'src/validation.cj':validation,'src/amount.cj':amount}
    result.append(target)
    result.append(row(10,'incremental_tiers_cap',
        'quantity在0..500，cap在300..1000分。前100件每件1分，第101至200件每件2分，第201件起每件3分；各段分别计费相加，最终不超过cap，零件数费用为0。',
        '把全部数量按最高已达到档位单价收费，遗漏分段增量计费。',
        'var total = quantity\nif (quantity > 100) { total = quantity * 2 }\nif (quantity > 200) { total = quantity * 3 }\nif (total > cap) { return cap }\nreturn total',
        'var total = quantity\nif (quantity > 100) { total = 100 + (quantity - 100) * 2 }\nif (quantity > 200) { total = 300 + (quantity - 200) * 3 }\nif (total > cap) { return cap }\nreturn total',
        dict(quantity=domain(0,500,0,1,100,101,200,201,500),cap=domain(300,1000,300,500,1000)),
        'min(cap,min(quantity,100)+2*min(max(quantity-100,0),100)+3*max(quantity-200,0))',
        [[50,500],[500,300]],[[101,1000],[201,1000]]))
    return result if count==10 else expand(result)


def expand(first):
    """Three logically different defects per rule, not threshold substitutions.

    First ten stay byte-for-byte stable. The variant matrix documents authored
    intent; actual SDK holdout failures establish each executable defect.
    """
    result=list(first)

    def add(base,variant,defect,bad,witnesses,public=None,patches=None):
        task=deepcopy(first[base-1]);number=base+10*(variant-1)
        old=f'{base:03}';new=f'{number:03}'
        task.update(id=f'business_hard_{new}',function='hard'+new,variant=variant,defect=defect,
                    holdout_witnesses=witnesses)
        if public is not None:task['public_inputs']=public
        for kind in ('source','reference'):
            task[kind]={p:raw.replace(('hard'+old).encode(),('hard'+new).encode())
                        .replace(('valid'+old).encode(),('valid'+new).encode())
                        .replace(('amount'+old).encode(),('amount'+new).encode()) for p,raw in task[kind].items()}
        if patches:
            # Cross-file variants start from the correct entry and helpers.
            task['source']=deepcopy(task['reference'])
            for path,(before,after) in patches.items():
                assert before in task['source'][path]
                task['source'][path]=task['source'][path].replace(before,after)
        else:task['source']={'src/logic.cj':function(task['function'],task['domains'],bad)}
        result.append(task)

    add(1,2,'把可退剩余额度的闭区间写成开区间，拒绝全额退清。',
        'if (refunded > paid) { return -1 }\nif (requested <= 0 || requested >= paid - refunded) { return -1 }\nreturn refunded + requested',
        [[1000,900,100],[100,0,100]])
    add(2,2,'满减门槛使用严格大于，恰好达到折后门槛时不减券。',
        'var value = amount * percent / 100\nif (value > threshold) { value = value - coupon }\nif (value < 0) { value = 0 }\nreturn value',
        [[1000,80,800,100],[100,100,100,50]])
    add(3,2,'零金额也收取最低手续费，遗漏零金额优先规则。',
        'var fee = (amount * rate + 9999) / 10000\nif (fee < floor) { fee = floor }\nif (fee > ceiling) { fee = ceiling }\nreturn fee',
        [[0,100,1,500],[0,0,100,100]],[[10000,100,1,500],[20000,100,1,500]])
    add(4,2,'预留条件拒绝等于可用库存的申请，不能预留最后一件。',
        'if (quantity <= 0) { return stock }\nif (release) {\n    if (quantity > reserved) { return stock }\n    return stock + quantity\n}\nif (quantity >= stock) { return stock }\nreturn stock - quantity',
        [[10,0,10,False],[1,0,1,False]])
    add(5,2,'把尾期余数加在首期，破坏各期应付金额的业务约定。',
        'if (periods < 1 || index < 1 || index > periods) { return -1 }\nlet base = total / periods\nif (index == 1) { return total - base * (periods - 1) }\nreturn base',
        [[100,3,1],[100,3,3]])
    add(6,2,'免运资格遗漏会员分支，低于门槛的会员被收运费。',
        'var net = amount - coupon\nif (net < 0) { net = 0 }\nif (net >= threshold) { return net }\nreturn net + 800',
        [[5000,0,9900,True],[0,0,5000,True]],[[10000,0,9900,False],[10000,0,9900,True]])
    add(7,2,'不足100的剩余积分向上折算，凭空增加可抵余额。',
        'let balance = (points + 99) / 100\nlet cap = amount * percent / 100\nvar used = requested\nif (used > balance) { used = balance }\nif (used > cap) { used = cap }\nreturn used',
        [[99,1000,10,50],[1,100,1,50]])
    add(8,2,'把零价格误判成非法，安全乘法的零元订单被拒绝。',
        f'if (quantity < 0 || price <= 0) {{ return -1 }}\nif (quantity > {HIGH} / price) {{ return -1 }}\nreturn quantity * price',
        [[HIGH,0],[0,0]])
    add(9,2,'跨文件校验助手允许数量0，非会员也能通过零数量订单。','',
        [[0,100,False],[0,1,False]],patches={'src/validation.cj':(b'quantity >= 1',b'quantity >= 0')})
    add(10,2,'第三档计费丢失完整第二档的累计200分。',
        'var total = quantity\nif (quantity > 100) { total = 100 + (quantity - 100) * 2 }\nif (quantity > 200) { total = 100 + (quantity - 200) * 3 }\nif (total > cap) { return cap }\nreturn total',
        [[201,1000],[250,1000]])
    add(1,3,'只拒绝零退款，负数申请反向减少历史退款。',
        'if (refunded > paid) { return -1 }\nif (requested == 0 || requested > paid - refunded) { return -1 }\nreturn refunded + requested',
        [[1000,100,-1],[100,0,-1]])
    add(2,3,'减券后遗漏最低0的约束，产生负应付金额。',
        'var value = amount * percent / 100\nif (value >= threshold) { value = value - coupon }\nreturn value',
        [[100,100,0,500],[0,50,0,100]])
    add(3,3,'向上取整后遗漏最高手续费约束，超限收费。',
        'if (amount == 0) { return 0 }\nvar fee = (amount * rate + 9999) / 10000\nif (fee < floor) { fee = floor }\nreturn fee',
        [[1000000,1000,1,500],[10000,1000,0,100]])
    add(4,3,'释放分支错误扣减可用库存，操作方向反转。',
        'if (quantity <= 0) { return stock }\nif (release) {\n    if (quantity > reserved) { return stock }\n    return stock - quantity\n}\nif (quantity > stock) { return stock }\nreturn stock - quantity',
        [[10,5,2,True],[0,10,1,True]])
    add(5,3,'合法性检查允许第0期，返回一个实际不存在的账单。',
        'if (periods < 1 || index < 0 || index > periods) { return -1 }\nlet base = total / periods\nif (index == periods) { return total - base * (periods - 1) }\nreturn base',
        [[100,3,0],[1200,12,0]])
    add(6,3,'优惠超过原价时未归零，负商品金额抵扣了运费。',
        'let net = amount - coupon\nif (vip || net >= threshold) { return net }\nreturn net + 800',
        [[0,1000,9900,False],[0,1000,9900,True]])
    add(7,3,'比例计算先除后乘，整数截断过早降低订单上限。',
        'let balance = points / 100\nlet cap = amount / 100 * percent\nvar used = requested\nif (used > balance) { used = balance }\nif (used > cap) { used = cap }\nreturn used',
        [[100000,199,1000,50],[10000,99,100,50]])
    add(8,3,'负数量被取反后按正数计价，非法输入没有返回错误码。',
        f'if (price < 0) {{ return -1 }}\nif (quantity < 0) {{ return -quantity * price }}\nif (price > 0 && quantity > {HIGH} / price) {{ return -1 }}\nreturn quantity * price',
        [[-1,2],[-1,1000]],[[2,3],[1,-1]])
    add(9,3,'跨文件金额助手把数量乘单价写成相加，入口校验正确但结算错误。','',
        [[3,100,False],[1,100,True]],[[2,2,False],[2,2,True]],
        patches={'src/amount.cj':(b'return quantity * price',b'return quantity + price')})
    add(10,3,'分段计费正确但遗漏最终封顶，超出费用上限。',
        'var total = quantity\nif (quantity > 100) { total = 100 + (quantity - 100) * 2 }\nif (quantity > 200) { total = 300 + (quantity - 200) * 3 }\nreturn total',
        [[500,300],[201,300]],[[50,500],[100,300]])
    return result
