# 4C 有限结构体／类验收记录

状态：4C有限结构体／类已验收并激活。主站8877运行独立4C快照；4B快照保留可回退。后续4D跨包与第5项部署仍未完成。

## 能力边界

支持最多4种具名扁平struct／class，每类1—4个只读public let普通值字段和最多4个受限纯方法；字段为Int64、Bool、有界String或Array<Int64>。JSON通过显式$type与冻结字段注册表绑定名义类型。暂不支持可变对象身份、继承、嵌套对象或对象数组，不宣称一般仓颉工程语义已覆盖。

Oracle5／属性4／关系4／状态序列4使用冻结注册表、有限对象域及闭合object_get／object_with／object_new表达式。V4独立仓颉观测读取真实返回字段，状态序列链使用实际返回的下一状态。公开测试仅观测失败字段；String差异保持TEXT_ONLY，不把差异文本推断成完整实际String。

## 已有真实验证

- 真实本地SDK四服务：公开PASS→独立FAIL→参考修复PASS，4项通过，8份报告；覆盖非首对象状态、固定Array上下文、真实缩减与跨候选历史。
- CEGIS：两个自建两轮场景可进入人工审阅及交付，一个真实SDK溢出场景停止为UNKNOWN。模型HTTP与图均为显式夹具；本阶段新增真实付费模型与远程6240请求为0，不代表新增模型修复质量评测。
- 最终一次独立审阅的三个Important已在同一修复阶段处理：混合工程普通断言映射、String差异中的日志控制样式文本、嵌套对象大整数精确展示兜底。
- 追加的合法case0类型名在实际SDK中复现构造器被测试方法遮蔽，已用包级构造辅助函数修复。3个名称冲突场景及1个真实控制样式String差异场景共4项通过；原始编译失败和一次测试样例类型不一致均完整保留。
- 定向协议／日志448项通过，关联134项通过，前端181项通过；这些集合有重叠，不相加宣称独立测试总数。
- 日志头兼容修复后56项定位／反馈／解析定向测试通过。被中断的首轮完整回归为8失败、267通过、1项live未选，110.21秒，退出2；因已知旧TCS简化日志头回归而中断，不计作完整验收。

## 当前冻结与待验收

重启完整回归冻结执行源342文件，摘要`e1beacacc504a55946221136673085ad0baa908371cc0889f615a032b8600a04`。原生core摘要`2be34e85f5fdecdd661a9ef292ca0ea16229a1cb2c84e6dbe23b1c8c6fc8e62a`，源码与编译器身份已比对。

完整not-live测试、当前版原件封存与禁止执行的重建、归档有限检查、历史阶段重放、浏览器验收及空闲主站切换均已完成，详见下文。结论仅覆盖本文声明的有界语言和自建验证场景，不扩大为一般仓颉语义或真实模型质量评测。

执行计划：[4C实施计划](../superpowers/plans/2026-10-29-bounded-objects.md)。

## 隔离浏览器与历史重建

浏览器使用本次冻结e1beac版本中已经完成的真实SDK对象CEGIS运行的独立副本；完整测试继续运行时，副本验收与之隔离。为检查待审阅按钮，仅副本任务从DELIVERED显示为REVIEW_PENDING，明确记录为UI状态夹具；没有改写真实运行或执行实际审批。

- 对象脚手架、源码／预期行为／测试JSON／属性JSON文件导入、显式核对与确认、重新打开后只读通过；测试与属性原文保持字节一致，包含Int64最大／最小值。
- 展示首轮真实失败的完整对象状态前缀与首次偏离，再切换修复后通过。对副本日志做篡改，最新结果变为UNKNOWN，禁止接受且拒绝按钮可用；恢复日志后回到PASS。
- 查看了导入、极值对象JSON、失败轨迹、首次偏离和UNKNOWN门禁五种截图；没有观察到字段遮挡或数字舍入。
- 自有无头Edge临时上下文已关闭，8898服务已终止。后端审计SDK／native／模型／远程分析执行均为0、denied为空；脚本同时阻断并检查页面外网请求。初次浏览器样例错误地用max_cases=8，按既有16..128范围被400拒绝，原失败保留；只把自建样例改为16，没有修改产品约束。

[浏览器审计](validation/next-phase-4C/browser-audit.json)、[首次对象状态偏离](validation/next-phase-4C/browser-final-object-first-mismatch.png)、[精确对象JSON](validation/next-phase-4C/browser-final-exact-object-json.png)、[UNKNOWN拦截](validation/next-phase-4C/browser-final-unknown-gate.png)。

第2、3A、3B、3C、4A、4B及3C补充缩减均按各自旧源码／core重建通过；本阶段各任务的七个旧版重建脚本也均通过。当前版本7个已完成运行和6组公开SDK原件的初步纯重建通过，不替代最终完整回归与封存验收。

## 最终冻结回归与封存（切换前）

完整not-live测试2720通过／1项live按预算未运行，4306.91秒，退出码0；没有修改冻结源码或放宽超时／断言。前端181通过，45个Node测试／脚本／模板／样式输入的字节与记录该Node结果时完全一致，另存输入绑定证明。最终git diff --check通过。

当前冻结源342文件e1beac...、自有core2be34...：封存7个服务／闭环运行、23组V4观测、6组公开SDK测试、27组native边界原件，共1286文件。按提取出的同版源码与core独立重建63组全部通过，SDK／native IPC／模型／远程分析执行均为0。这里包含业务FAIL、执行UNKNOWN和非法输入REJECTED的预期结果，不是声称所有业务都通过。模型HTTP与图仍为显式夹具。

有限扫描36个归档、11131个成员、5个嵌套归档，按已列私有文件名／ZIP路径与符号链接／三类密钥模式检查，发现0项；保留已检查的自建SDK／运行路径，不宣称普遍匿名化或干净机器部署。

[完整Python结果](validation/next-phase-4C/full-python.txt)、[Node结果与输入绑定](validation/next-phase-4C/node-input-binding.json)、[封存摘要](validation/next-phase-4C/capture-final.txt)、[独立重建](validation/next-phase-4C/replay-final.json)、[有限检查](validation/next-phase-4C/finite-artifact-scan.json)。

## 主站激活与数据保持

2026-10-30主站空闲复核后，优雅停止自有4B进程17930，启动独立4C快照`.runtime/active-stage-4C`，PID33505，8877监听与工作目录已确认，控制器OS flock已核实。新快照使用自有2be34...核心，原SDK／stdx只读共享，沿用原会话与配置；没有新模型或远程分析请求。

切换前、旧进程停止后及新进程启动后的17张数据库表、3959份记录、会话摘要全部相同：31个待审阅、10个已交付、3个已拒绝任务保持，176个工具请求和39个模型调用仍为原完成状态。首页、案例目录及15个脚本／样式资产均200且资产字节匹配。4B快照保留回退。

[激活记录](validation/next-phase-4C/activation.json)、[切换前](validation/next-phase-4C/activation-before.json)、[切换后](validation/next-phase-4C/activation-after.json)。后续按总目标推进4D跨包与第5项部署；本阶段不宣称干净机器部署已完成。
