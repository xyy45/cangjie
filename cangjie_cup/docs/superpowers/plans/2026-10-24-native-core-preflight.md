# 第5阶段代码入口核对（预研，未开始实现）

执行前提：按总计划先完成阶段4数据／工具子项验收并重新读取升级文档；真实模型比较等待预算时可推进不依赖其成绩的原生核心开发，保留阶段4整体未完成。本文只记录当前源码事实和下一阶段需要决定／验证的接口，不代表仓颉强化已经实现。

## 当前原生能力

`cangjie/policy/src/main.cj`通过JSON行IPC返回Allow／Deny／NeedApproval；参与candidate.apply／build／test／export和project.diagnose。当前schema1、policy1.1、12字段，原生核检查版本、请求／树／参数摘要形式、动作白名单、1至3文件数量、受保护路径、候选预算及导出接受标记／摘要形式。

`nexus/policy/client.py`使用固定二进制和源／编译器摘要校验；Python侧执行2秒IPC预算、deadline检查、响应绑定和组件变化复查。`nexus/policy/gate.py`复查请求未变、决策Allow、响应字段一致、期限及组件一致后才调用动作，并保存决策／执行后果。当前不是Python模拟仓颉结果。

## 应强化的边界

| 主题 | 当前实现依据 | 下一阶段方向与必要证据 |
|---|---|---|
| 任务范围 | 原生核只认识src生产路径形态；具体allowed_paths由WorkspaceStore.apply_candidate检查 | 将已确认范围作为服务持有事实加入版本化IPC；原生核独立拒绝范围外、重复路径和保护文件；不能由模型传入或扩大范围 |
| 任务状态 | PolicyRequest没有status／revision；应用检查当前READY／APPLYING，验证器检查终态 | 新原生契约检查动作与任务状态；明确旧任务读取及新运行协议，不允许新决策失败后退回旧协议绕过 |
| 决策后变化 | 门禁核对请求和组件，动作侧各自复查；候选复制与登记不是同一事务 | 原生决策绑定任务revision／基线／需求版本；动作登记前以短事务CAS复核，不在编译／网络等待期间占数据库事务 |
| 审批绑定 | DeliveryService以当前候选／check_set／版本／用户／过期状态核验；原生核只看accepted和64位摘要形式 | 把审批所覆盖版本／树／校验集合与当前事实分别传入原生核比对；Python保留持久化和原件核验，模型不能签发审批 |
| 确定性边界 | oracle.py的axis_values／generate_inputs／shrink_inputs是Python；真实被测函数由仓颉执行 | 先迁移适合的单参数Int64／Bool边界轴到仓颉IPC；测试min／max溢出边缘、顺序和去重。多参数组合／随机／保留输入过滤继续显式标明语言归属，不把部分迁移称为全部原生 |
| 原生组件身份 | build_policy.py直接编译单个main.cj，身份仅覆盖该源文件及二进制／cjc | 若拆多个.cj，构建与身份必须覆盖完整源集合，保留发布切换的临时文件与原子替换；不能只给主文件计算摘要 |

## 接口与验证准备

下一阶段从`nexus/contracts.py:PolicyRequest／PolicyResponse`、`cang_sight_server/server.py:gated_apply／gated_check／export_route`接入。变更须先写原生拒绝测试，编译真实仓颉组件，再用门禁验证拒绝时动作计数为0。现有SDK上传／CEGIS／交付链必须保持，旧证据按原版本读取，不把新组件与旧审批混用。

现有回归入口：`tests/integration/test_policy_gate.py`、`tests/test_policy_presentation.py`、`tests/test_contracts.py`和真实SDK修复／交付测试。需要补：状态不匹配、决策后revision变化、确认范围变化、审批旧树／旧需求、组件多文件变更、原生边界与现算法的逐项对照。不得只用常量fixture证明新原生能力。

上述为源码核对与拟验证事项；尚未修改原生协议、仓颉源文件或二进制，未证明其中拟议的并发／版本行为。
