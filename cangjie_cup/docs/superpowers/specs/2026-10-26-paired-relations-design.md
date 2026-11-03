# 3B 成对调用关系设计

2026-10-26。状态：设计准备，产品未实现。依据`docs/后续能力提升开发目标.md`与已验收3A；持续授权覆盖常规实现和设计选择，新付费预算仍须独立批准。本阶段实际模型／远程分析调用预算0。

## 目的与范围

在同一仓颉函数的两个真实调用之间，验证用户确认的业务关系。例如只在价格固定、正价格、无优惠的有限区间内，数量增加时总金额不得下降。用户可表达其他有界关系；系统不自动推断关系成立的业务前提。

保持Int64／Bool、0至4参数、受限同包与最多3个允许修改生产文件。关系与单次属性／旧oracle可以同时启用。没有字符串／数组／对象、跨包、外部状态、并发或操作序列；3B不代替3C。

## 方案与实现方决定

采用**输入对＋有界条件／断言**，独立版本化JSON及报告，复用原生轴、白名单AST、固定SDK观测和已有门禁。任意变换源码会扩大执行面；固定关系模板会限制用户表达，均不采用。暂不增加变换DSL或新依赖。

抽出小型通用`primitive_trace.py`，只负责原始类型、固定测试程序、nonce/case匹配与完整SDK观测；single与relation各自解释自己的业务条件。PropertyService保持单次语义，RelationService按相同记录／CAS模式独立实现成对重放，复用既有记录读写／生产材料选择，不为两个引擎重构大型通用状态框架。

以上为实现方的选择，不冒称用户逐项确认。继续保留当前codex分支和未提交工作区，不自动commit、push或清理。

## 确认契约

新增可选`relations_json`，UTF-8最多16KiB，严格对象，无重复键／NaN。空／未提供与旧确认完全兼容。原始字段恰为：

`version=1, kind="relation", function, domains, relations, seed, max_pairs, excluded_inputs`。

- function为当前选择函数；domains为实际参数名的既有Int64 min/max/points和Bool空对象域，左右共享同一函数域。
- relations为1至8项，每项恰为`id,text,precondition,assertion`；id唯一、匹配`REL-[A-Z][A-Z0-9-]{0,31}`，text1至500字符，表达式1至1024字符。
- 别名为`left_arg0…left_arg3`、`right_arg0…right_arg3`，按签名排序；返回为`left_result`／`right_result`。precondition不引用返回；precondition与assertion均静态检查为Bool。
- 继续使用既有白名单AST、Int64溢出／截断除法语义。非字符串在进入缓存前拒绝；禁止eval、成员访问、任意调用、源码插入和不受限运算。
- seed为0..2^32-1；max_pairs为16..64，是上限而非承诺生成数；0参数或Bool有限域可少于16对。
- excluded_inputs为0至128个类型精确且不重复的函数参数数组，可记录域外保留输入。任一侧命中就过滤整对。新关系契约不得把已确认公开示例同时列为保留输入。
- 三种检查共存时完整排除集合必须相同；oracle v1仅能与空排除集合共存。这个约束只在新关系配置时加入，不改已冻结旧契约。
- 从公开示例的已确认expected构造已知输入对：两侧在关系域内且满足前提时，若这两个expected违反关系则拒绝确认；缺少一侧已知expected不推断答案。
- 确认前，有限采样必须为每条关系找到至少一个适用输入对；否则拒绝覆盖不足。运行时仍需全部关系至少有一个完整双侧观测，不能空通过。

标准化附加signature、aliases、algorithm=`paired-relations-v1`，冻结为`verification/relations.json`，独立relations_hash与origin=`USER_CONFIRMED`进入confirmation_hash／树／计划。保留文件精确白名单，不能覆盖原工程同名路径；仍遵守追加验证材料后的100文件／2MiB限制。原模型草案仅负责原examples/oracle，不悄悄覆盖relations。

## 有限输入对算法

`RelationContract`的采样器使用同一个函数的原生`boundary.axes`证明；不将8个左右别名伪装成新8参数函数，也不改变原生核。

1. 通过原有算法产生最多128个基输入，保持域、类型与排除约束。
2. 在总计最多8192个候选对预算内，先枚举结构化候选：同输入对、基输入的一维轴替换及相反方向；再使用固定seed的基输入组合补充。前半／后半各至多4096次候选检查，重复有类型精确的pair_key去重。
3. 对候选计算全部关系的前置条件，任何解释错误拒绝／UNKNOWN，不能当false跳过。仅保留至少一条关系适用且双侧都可执行的输入对。
4. 优先保留已验证的先前候选反例，再为尚未覆盖的每条关系选一对，最后按固定生成顺序填满max_pairs。不得静默丢弃必需累计反例；累计超过预算或无法满足剩余覆盖则UNKNOWN。

候选检查是Python中的纯条件解释，实际仓颉调用仅针对最终选中输入对。记录生成检查数、选中对数、每关系适用／双侧观测／失败数。8192候选及有限参数域不构成完备性或性能容量承诺。

## 双侧观测与判定

每个pair按顺序展开为两个独立SDK case，索引为2i和2i+1；即使输入相同也执行两次。初始最多64对／128调用。

通用观测器使用固定kind枚举single／relation；single保持原`NEXUS_PROPERTY_V1`、`NexusProperties`及原harness字节语义，relation使用`NEXUS_RELATION_V1`、`NexusRelations`。函数引用／标准输出别名沿用真实SDK验证的实现。通用层允许重复输入的不同case；single外层继续拒绝重复输入。

完整SDK summary、预期全部case PASS、exit0和每case恰好一条类型精确／token正确的STDOUT标记缺一不可。随后以两个真实返回计算关系；观测case PASS只证明调用完成，关系断言false为业务FAIL。缺任一侧、跨case／token借值、截断、类型错误、域／排除错误、所有guard不适用或解释错误均UNKNOWN。

关系反例字段包含`kind=business_relation, relation_id, relation_text, left_args, right_args, left_actual_return, right_actual_return, assertion_value=false, expected_relation=true`，并关联两侧实际caseID、日志区间、同一候选／树／契约摘要。pair_id为派生分组，不冒充SDK单个case。没有单一数值expected，不调用模型裁决。

## 执行、缩减、CAS与重放

RelationService的binding/run/verify与现有风格一致，relation_runs按candidate_id唯一CAS登记STARTED；SQL写事务不包含原生IPC、文件散列、SDK或网络等待。绑定候选／树／公共测试、冻结计划、契约、旧检查排除集合、引擎源码、固定SDK与native core。

初始最多64对；随后最多2批缩减，每批16对／32调用；总deadline不超过调用方剩余时间与90秒较小值，单批60秒、输出2MiB。缩减保持原失败关系ID及前提，双侧域／排除约束；可单侧缩小，也可协调缩小原本相等的参数，候选分数严格下降。每个接受的缩减结果都由SDK重跑两侧确认；不承诺全局最小。

报告、模型反馈和后续必需累计回归使用同一份最多16条保留失败输入对／关系组合，按评分和确定性顺序选取。批次原件仍保留所有实际观测／失败、真实总数和截断标记；报告明确说明累计回归限定该保留集合，不声称未保留失败也已全部回归。累计仅来自同任务更早attempt且已经verify的报告；同一输入对触犯多条关系时，实际回归按类型精确的输入对去重。STARTED、取消或先前UNKNOWN不得自动重放新执行。verify不执行SDK／模型／MCP，只重建输入对、材料、两侧观测、判定、缩减轨迹、计数与汇总；缺失／变更使报告失效。

公共观测层抽取后，其文件摘要必须加入single和relation两种引擎身份，不能遗漏间接依赖；旧3A封存源码仍独立可重放。

## 必需检查、反馈与交付

candidate.test顺序为公开→oracle（若有）→single（若有）→relation（若有）。前项FAIL／UNKNOWN不启动后项。控制器依据冻结上传配置识别必需项；所有前项通过却缺少关系报告，即使MCP envelope为OK也阻断。

关系FAIL反馈有两组实际参数／返回、违反关系摘要、case/log引用及正确候选树；不发送完整私有契约、保留输入或未执行答案。UNKNOWN停止进一步模型轮次。原3轮／480秒修复预算不扩充；本阶段只使用HTTP模型夹具。

FocusService将一对失败展开成两个真实调用的基线定位目标，保留左右角色与真实caseID；不编造expected或把静态依赖当因果。DeepSeek提示说明新反馈含义，原建议路径集合约束保持。

DeliveryService、EvidenceArchive、审批／下载／导出重验关系PASS并绑定报告；新增relation-report与契约原件。未配置时沿用旧行为，不能用单次属性PASS替代关系PASS。

## 页面与精确展示

上传窗口添加可选关系JSON编辑／导入及左右别名，复用当前浅色样式、16KiB、读取epoch与确认流程。文件／函数／范围改变使晚到读取失效，确认许可复位；草案应用不覆盖relations。

RelationUI展示左右输入／实际返回、违反的关系、覆盖计数与PASS／FAIL／UNKNOWN。规范文本由服务端从原始Int64／Bool生成，不使用Number舍入值。任务候选摘要和当前详情只使用verify后的状态；历史事件不能单独成为当前PASS。沿用现有所有权GET接口，不新增匿名执行端点。修复窗口同时考虑oracle、single、relation，未启用关系则不出现空面板。更新可选规则帮助文字，避免在启用另一种检查时仍说留空只验证公开示例。

## 验收与后续

1. 带明确固定价格／无优惠前提的计费缺陷：公开示例PASS、关系FAIL，参考修复PASS；证明实际执行两侧而非只查模型答案。
2. 同包跨文件关系、Bool返回、零参数与Int64边界真实SDK通过；相同输入两侧有独立case原件。
3. 双侧保留过滤、前提保持的实际缩减、累计回归、缺／错单侧观测、CAS／取消／篡改和未知门禁全部测试。
4. 与旧oracle／single共存顺序正确；两轮HTTP模型夹具收到真实关系反例；定位、审阅、归档与重放闭环。
5. 浏览器导入／冻结／关系FAIL与PASS／证据失效UNKNOWN，精确大整数与跨actor、晚到响应覆盖；无真实模型／远程MCP调用。
6. 完整非live Python／Node／diff检查、一次fresh整体审阅、源码与SDK原件归档及3A／第2项历史重放；再标3B已验收。

3C状态序列与第4、5项仍保持未完成。关系不等于事务、幂等或并发证明，不在本增量中扩大这些声明。

## Builder check结论

一次fresh builder check提出累计回归集合歧义，已由实现方在上述“执行、缩减、CAS与重放”明确：最多16条保留集为必需回归集，其余全部原始失败仍归档并披露截断。选择沿用3A的有界保留策略，以免未声明地扩充SDK调用预算；代价是不能宣称所有历史失败均已回归。没有待用户回答的需求问题，常规持续授权保持。
