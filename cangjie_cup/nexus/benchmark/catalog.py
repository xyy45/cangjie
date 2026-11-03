"""Authored business rules. Variants are disclosed, not independent semantics."""

VERSION='business-bench-v2-sealed'


def families(variant):
    t=10+variant*3;c=3+variant
    # x/y/z are Int64, v is Bool. Bodies are plain supported Cangjie.
    # Each tuple: family, params, result, goal, buggy body, reference body,
    # independent rule, known defect input. The rule is never inferred by LLM.
    return [
      ('quantity',['x'],'Bool',f'数量x仅在1至{t}（含）有效。',f'return x >= 0 && x <= {t}',f'return x >= 1 && x <= {t}',f'x >= 1 and x <= {t}',[0]),
      ('price',['x'],'Bool',f'单价x必须为正且不超过{t}。',f'return x > 0 && x < {t}',f'return x > 0 && x <= {t}',f'x > 0 and x <= {t}',[t]),
      ('shipping',['x'],'Int64',f'金额x达到{t}免运费，否则运费{c}。',f'if (x > {t}) {{ return 0 }}\nreturn {c}',f'if (x >= {t}) {{ return 0 }}\nreturn {c}',f'0 if x >= {t} else {c}',[t]),
      ('coupon',['x'],'Int64',f'金额x达到{t}减{c}，否则原价。',f'if (x > {t}) {{ return x - {c} }}\nreturn x',f'if (x >= {t}) {{ return x - {c} }}\nreturn x',f'x - {c} if x >= {t} else x',[t]),
      ('stock',['x','y'],'Int64','库存x、请求y：请求须正且不超过库存；非法返回-1，否则返回余额。','if (y < 0 || y > x) { return -1 }\nreturn x - y','if (y <= 0 || y > x) { return -1 }\nreturn x - y','-1 if y <= 0 or y > x else x-y',[5,0]),
      ('refund',['x','y'],'Int64','已付x与请求退款y：退款取两者较小值。','return y','if (y > x) { return x }\nreturn y','min(x,y)',[2,3]),
      ('vip_discount',['x','v'],'Int64','x为金额、v表示会员，会员按九折整数截断，非会员原价。','if (!v) { return x * 9 / 10 }\nreturn x','if (v) { return x * 9 / 10 }\nreturn x','x*9//10 if v else x',[20,True]),
      ('gift',['x'],'Int64',f'每购买{c}件赠一件，返回购买和赠送总件数。',f'return x + x / {c+1}',f'return x + x / {c}',f'x+x//{c}',[c]),
      ('tier_price',['x'],'Int64',f'前{c}件每件10分，超出部分每件8分。',f'return x * 10',f'if (x <= {c}) {{ return x * 10 }}\nreturn {c} * 10 + (x - {c}) * 8',f'x*10 if x <= {c} else {c}*10+(x-{c})*8',[c+1]),
      ('late_fee',['x'],'Int64',f'宽限{c}天，只对超出天数每天收2分。',f'if (x <= {c}) {{ return 0 }}\nreturn x * 2',f'if (x <= {c}) {{ return 0 }}\nreturn (x - {c}) * 2',f'max(0,x-{c})*2',[c+1]),
      ('points_cap',['x','y'],'Int64','x是订单金额、y是积分可抵金额，抵扣不能超过订单金额，返回应付。','return x - y','if (y > x) { return 0 }\nreturn x - y','max(0,x-y)',[2,3]),
      ('expiry',['x','y'],'Bool','x是当前时刻、y是失效时刻，到失效时刻即不可用。','return x <= y','return x < y','x < y',[5,5]),
      ('authorization',['x','y','v'],'Bool','x是当前用户、y是资源所有者，v是管理员标记；管理员或所有者允许访问。','return x == y && v','return x == y || v','x == y or v',[1,2,True]),
      ('transfer',['x','y'],'Int64','余额x转出y，仅允许正数且不超余额，非法返回-1，否则返回余款。','if (y <= 0 || y >= x) { return -1 }\nreturn x-y','if (y <= 0 || y > x) { return -1 }\nreturn x-y','-1 if y <= 0 or y > x else x-y',[5,5]),
      ('daily_limit',['x','y','z'],'Bool','已用x加本次y不能超过限额z，恰好达到可通过。','return x+y < z','return x+y <= z','x+y <= z',[2,3,5]),
      ('page_size',['x'],'Int64',f'分页大小至少1且最多{t}，返回截断后的值。',f'if (x > {t}) {{ return {t} }}\nreturn x',f'if (x < 1) {{ return 1 }}\nif (x > {t}) {{ return {t} }}\nreturn x',f'min({t},max(1,x))',[0]),
      ('packages',['x'],'Int64',f'每箱装{c}件，需要的箱数向上取整，零件数为零箱。',f'return x / {c}',f'return (x + {c-1}) / {c}',f'ceil_div(x,{c})',[1]),
      ('tax',['x'],'Int64','按13%计税并向上取整，金额x非负。','return x * 13 / 100','return (x * 13 + 99) / 100','ceil_div(x*13,100)',[1]),
      ('cancel_state',['x'],'Bool','订单状态0待支付、1已支付可取消，其他状态不可取消。','return x == 0','return x == 0 || x == 1','x == 0 or x == 1',[1]),
      ('retry',['x','y'],'Bool','已尝试次数x小于上限y时允许重试，达到上限停止。','return x <= y','return x < y','x < y',[3,3]),
      ('member_shipping',['x','v'],'Int64',f'会员v或金额x达到{t}时免运费，否则收{c}。',f'if (v && x >= {t}) {{ return 0 }}\nreturn {c}',f'if (v || x >= {t}) {{ return 0 }}\nreturn {c}',f'0 if v or x >= {t} else {c}',[1,True]),
      ('booking_window',['x','y','z'],'Bool','当前时刻x必须在左闭右开区间[y,z)内。','return x >= y && x <= z','return x >= y && x < z','x >= y and x < z',[5,1,5]),
      ('rebate_cap',['x','y'],'Int64','订单金额x，返利y最多抵扣订单的一半（向下取整），返回应付。','return x-y','if (y > x/2) { return x-x/2 }\nreturn x-y','x-min(y,x//2)',[5,4]),
      ('child_ticket',['x'],'Int64',f'年龄x低于{t}时票价50，否则100。',f'if (x <= {t}) {{ return 50 }}\nreturn 100',f'if (x < {t}) {{ return 50 }}\nreturn 100',f'50 if x < {t} else 100',[t]),
      ('installment',['x','y'],'Int64','总额x按正数期数y分期，每期上限向上取整。','return x/y','return (x+y-1)/y','ceil_div(x,y)',[5,2]),
      ('active_account',['x','v'],'Bool','余额x必须为正且账户状态v为启用，才允许消费。','return x > 0 || v','return x > 0 && v','x > 0 and v',[0,True]),
      ('reward',['x'],'Int64',f'消费x达到{t}获得双倍积分，否则积分等于消费额。',f'if (x > {t}) {{ return x*2 }}\nreturn x',f'if (x >= {t}) {{ return x*2 }}\nreturn x',f'x*2 if x >= {t} else x',[t]),
      ('ledger_balance',['x','y'],'Int64','余额x加上带符号变动y，返回不小于零的余额。','return x-y','if (x+y < 0) { return 0 }\nreturn x+y','max(0,x+y)',[5,-2]),
      ('reservation',['x','y','z'],'Bool','已预约x、本次y、总容量z，本次必须为正，合计不超容量。','return y > 0 && x+y < z','return y > 0 && x+y <= z','y > 0 and x+y <= z',[2,3,5]),
      ('cross_file_fee',['x'],'Int64',f'入口调用另一文件的原金额函数后收{c}分服务费；两个文件须协调修复。',f'return helper(x) + {c+1}',f'return helper(x) + {c}',f'x+{c}',[2]),
    ]
