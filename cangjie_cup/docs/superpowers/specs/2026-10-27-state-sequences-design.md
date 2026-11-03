# 3C：受限操作序列设计

日期：2026-10-27。状态：builder检查通过，产品尚未实现。沿用用户已确认《后续能力提升开发目标.md》的持续实施授权，常规阶段与技术选择不重复请求批准；以下具体取舍为实施者判断，不冒称用户逐项选定。真实模型／远程分析新预算0。

## 意图、现状与范围

3A验证一次返回，3B验证两个独立输入的关系。3C从用户确认的初始状态出发，将上一步仓颉函数的实际返回作为下一步状态，找出“扣减→取消”“累计退款再次请求”中只有特定可达路径才出现的错误。参考状态转移和不变量由用户确认冻结，模型不能修改，也不能自行裁决通过。

技术栈保持Python3.12／Flask／SQLite／原生JS、固定仓颉1.0.5 SDK与core2。本阶段仍为同包、最多3个允许修改生产文件，函数1..4个Int64／Bool参数。一个选定参数是状态，返回类型必须与该参数相同。多个操作是同一个被选函数的不同参数模板；不增加多函数状态机入口、对象／多字段状态、数据库、网络、并发或事务语义。

项目现位于 /Users/jxy/Desktop/mass/CangSight-main。迁移恢复6个内部相对软链接后，3B冻结244份源码未变、归档重放PASS、主8877及44任务／176已完成请求保持。3B主站运行独立冻结快照，3C开发期间不直接加载开发目录。真实SDK探针已证明同case连续调用、提前Unit return、Bool和Int64下界可行，详见next-phase-3C-preflight.md；探针不是产品验收。

## Approaches

A. 在可信SDK观察harness的同一case中串接原始类型状态，Python根据冻结模型独立解释：符合现有语法与上传入口，原件可逐步重放，选择本方案。

B. Python每步启动一个SDK进程、把返回拼成下一步输入：副本与编译开销过大，有限预算内难以形成有意义路径，且增加进程间状态与失败处理；不采用。

C. 直接支持仓颉对象及任意多函数状态机：需要对象构造／序列化／别名语义，属于第4项，当前语法门禁不能提供可信支持；本阶段不采用。

选择A是对已确认路线的实现判断。缺少配置或不适用函数仍保留原手动修复路径，不自动生成或勾选序列模型。

## 用户契约 sequence-v1

新增可选sequences_json，UTF-8原始文本包括空白最多16KiB。严格拒绝重复字段、NaN／Infinity、未知字段和错误类型。原始必需字段恰为：

version、kind、function、state_param、domains、initial_states、initial_precondition、context_params、operations、invariants、seed、max_sequences、max_steps、excluded_inputs。

- version整数1，kind字符串sequence，function为当前选定函数名；state_param是其一个参数名。1..4参数，状态与返回同为Int64或同为Bool。
- domains沿用已验证的原始类型域格式，包含所有参数。状态域描述模型可达状态的允许范围，不等于仅允许初始输入；Int64有min／max／points，Bool为{}。
- initial_states为1..16个类型精确、去重的显式初始状态，须在状态域内；Bool可仅选true或false。
- context_params为0..3个非状态参数名，无重复，规范化按原函数参数顺序排列；每个轨迹开始采样一次并在该轨迹全部步骤保持。
- initial_precondition是1..1024字符的Bool安全AST表达式，变量只有initial_state和ctx<i>（i为上下文参数在原签名的索引）。没有适用初始／上下文组合时拒绝确认或运行UNKNOWN。
- operations为1..4项，每项恰为{id,text,args,transition}。ID匹配OP-[A-Z][A-Z0-9-]{0,31}且唯一，text1..500字符。args按原签名去除状态参数后的顺序排列；每项只能是类型正确且域内的常量，或恰为{domain:当前参数名}，或恰为{context:当前参数名}。context参数的槽位必须使用context引用，非context槽只能常量或同名domain引用，禁止跨槽别名与脚本。
- transition是1..1024字符、类型等于状态类型的安全AST表达式；复用现有oracle.expression_tree／类型检查和有界整数语义，禁eval。别名state是参考前态，arg<i>是完整参考调用参数（含参考状态）。转移只允许函数可见的当前状态及参数；禁止initial_state和step_index等隐藏历史变量。需要计数或原始容量时必须通过真实参数或状态显式传入。
- invariants为1..8项，每项{id,text,precondition,assertion}；ID匹配INV-[A-Z][A-Z0-9-]{0,31}且唯一，text1..500。前置条件Bool只引用initial_state、before_state、arg<i>、step_index；断言再增加result和expected_state，均为状态类型。result是SDK实际后态，expected_state是参考后态，不暗示独立于用户模型的第二正确性来源。
- seed整数0..2^32-1，max_sequences整数8..16，max_steps整数2..8。搜索中的每个初始轨迹2..max_steps步；经真实缩减允许1步反例。最多16轨迹／128计划调用。
- excluded_inputs为0..128个完整参数数组，类型精确，允许域外保留值；与启用的oracle／single／relation完整保留集合相同，旧oracle-v1只能与空集合共存。不得保留公开示例。

规范化契约增加冻结signature、state_index、aliases和algorithm=state-sequences-v1，原对象不能经后续修改影响契约。初始、上下文和每步非状态参数域均冻结。JSON是验证数据，不是可修改生产路径。

公开例子检查：对域内完整输入，找出所有匹配的操作模板（context槽以该公开输入自身值作为context）；逐项计算参考transition，与已确认expected不一致则拒绝。initial_states不限制公开例子中的状态。没有匹配操作模板或位于模型域外的例子仍独立执行公开测试，不冒称已校验模型覆盖。转移不能依赖隐藏历史，因此无需猜测单调用的初始状态或步数。

## 路径计划、执行与保留输入

每个具体轨迹恰为{initial_state,context,steps}。context是按冻结context_params排列的原始值数组，steps为1..8项{operation_id,args}，args是去掉状态参数的完整、已具体化非状态数组。轨迹身份来自类型精确的规范化数据，Bool与Int64不混淆。参考模型是冻结契约的一部分，不使用候选返回来生成“预期”。

生成从原生boundary.axes＋现有参数域采样构造有限原始值池；纯数据确认阶段使用相同原生轴等价算法，不执行SDK／MCP／模型。候选条件检查总数上限8192，结构化和固定seed补充分别最多4096，不先展开无界笛卡尔积。

先放同任务更早attempt已验证的必需失败前缀，再覆盖操作／不变量的模型适用路径，再填有限预算。每份历史报告最多保留8条，但必需集合是此前全部有效保留前缀的去重并集，不按8再次截断；并集超过max_sequences／128计划调用／max_steps时UNKNOWN。结构化优先包含同一操作同一具体非状态参数连续重复、每个有序操作对、交替操作和短／长路径；其余用固定seed生成。不能从任意中间状态直接回归旧反例，必须重放其初始状态与完整前缀。

计划预先计算独立参考状态链。任一步参考表达式溢出／类型错误、参考后态出状态域、适用参考不变量为false，属于用户模型无法验证／矛盾，确认拒绝或运行UNKNOWN，不算候选缺陷，也不静默删去问题轨迹。初始前提不满足、某一步完整参考调用命中保留输入的轨迹允许整体过滤；所有路径被过滤或覆盖不足时UNKNOWN。

可信harness把实际返回传给下一步，只在实际后态与该步参考后态首次不同后输出结束标记并立即return该case；不再执行尾部步骤。它不使用@Assert宣告业务通过，仅完成原始观测。原因是：直到首次不同前实际链与模型链相同，因此所有实际调用参数均等于预检的参考输入；若继续执行已偏离状态，可能命中保留输入。提前结束同时避免对无效状态继续调用。

这不是完整执行失败后的尾部业务效果；每个报告明确计划步数、实际观测步数、未执行尾部及提前结束原因。PASS必须每条轨迹完整执行并全部符合模型和适用不变量。完整且合法的首次偏离前缀可判FAIL，不需要伪造尾部观测。只有SDK完整成功、全部case和协议完整时才解释业务；进程异常、取消、缺结束标记或其它case不完整使整批UNKNOWN，保留可用原始材料但不作为自动反馈继续修复。

## SDK观测协议与解释

每条轨迹一个NexusSequences<16位nonce>.case<i> SDK测试case；每步是该case中的一次实际目标函数调用，不冒称每步一个独立SDK case。可信harness逐步使用唯一局部变量和函数类型别名，避免候选函数同名冲突；包名、函数名、原始类型及literal沿用安全门禁。

观测行：NEXUS_SEQUENCE_V1|<token>|case<i>|step<j>|<Int64或Bool>|<before_state>|<after_state>。
结束行：NEXUS_SEQUENCE_END_V1|<token>|case<i>|<observed_steps>|COMPLETE或MODEL_MISMATCH。

sequence_trace独立解释器复用SDK报告解析器、CASE识别和原始类型校验；不把旧single／relation一次调用解释器错误套到多步case。旧primitive_trace只增加保留前缀识别，遇到序列协议混入旧协议必须UNKNOWN；旧正常harness字节、single唯一输入约束和relation双case语义保持。

必须验证nonce、完整SDK summary／case集合、STDOUT归属、唯一连续step从0开始、类型和Int64／Bool规范文本、before等于初始或前一步actual、实际参数等于冻结harness／参考前缀。COMPLETE恰有全部步骤且每步符合模型；MODEL_MISMATCH恰止于第一次不等，不能提前／延后，不能有后续观测、重复结束或缺行。错误case／kind／STDERR、重复、交错、截断、错误类型、异常、伪造计数均UNKNOWN。

每步记录共享SDK test_id＋独立step_index、完整实际args、before_state、actual_return、reference_before、expected_state、operation_id/text、适用和违反不变量ID、ANSI_STRIPPED_FULL_LOG坐标；结束行另有source。SDK case通过只表示观察完整，业务PASS／FAIL由Python对原件重建决定。

## 反例、缩减与累计

失败kind=business_sequence。保留初始状态、上下文、到首次失败为止的全部真实步骤、失败step_index、operation_id、model_mismatch及违反不变量；failure_ids可包含MODEL-<operation_id>和INV-...。模型预期是用户确认状态模型的计算结果，允许作为typed expected_state反馈；不发送完整私有契约、封存输入、参考修复或未执行尾部。

每份报告确定性保留最多8条不同失败前缀作为反馈及未来必需回归；同一前缀的多个failure_ids归组，保留全部raw失败／步骤并披露截断。不能声称全部原始失败都进入累计回归。必需集合超max_sequences、步数上限或总计划调用预算则UNKNOWN，不丢弃或截断必需前缀。

最多2个缩减批次，每批最多8条轨迹且每条最多8步（最多64计划调用）。尝试删连续操作／保留子序列、减少初始状态／上下文／非状态值；修改context须在整条轨迹一致，model链、初始前提、域、保留过滤及原始目标failure_id必须保持可适用。候选评分按步数优先、再原始值绝对值与类型精确序列键，严格下降；失败只能通过新真实SDK观测确认，不能用模型或模拟执行代替。没有全局最小承诺。

## 执行服务、证据与恢复

新增sequences.py、sequence_trace.py、SequenceService(ExplorationService)。复用已有记录读写／生产材料副本助手，不新增通用框架。将RelationService已有的公开原件核验提取为小型verification_evidence.py供两个服务使用；旧RelationService方法委托并保持相同证据结果，引擎摘要纳入新助手，正常旧语义不变。

sequence_runs以candidate_id唯一CAS保存STARTED／PASS／FAIL／UNKNOWN、报告ref／sha；事务短，不跨原生IPC、SDK、文件哈希或网络。每个搜索／缩减副本位于sequences/<uid32>，使用src/sequence_observations_test.cj，records后缀.sequences.json／.log／.cj。只读verify不执行SDK／模型／远程分析或原生IPC。

绑定候选树、需求／验证计划、序列契约／来源、全部已配置前置检查的当前可验证摘要／状态、公开测试原件、工具链和原生核身份、输入计划／原生轴证明、harness、复制生产材料、完整日志、case／step坐标、搜索／缩减计数与结论；引擎摘要包括实际使用的契约／AST／协议／报告／runner／前置报告核验／共享原件助手源码依赖。

顺序public→oracle→single→relation→sequence。每个已配置前项必须当前PASS且原件有效，才执行sequence。缺失、未知、变化或未启用的必需报告不能靠MCP成功包绕过。无sequence配置保持旧流程。SDK搜索与缩减执行阶段共享90秒deadline，单批最多60秒，输出2MiB；不是含材料绑定／重验的端到端延迟保证。取消、STARTED重放、不确定执行均不自动重跑。

## 上传、修复、定位与交付

确认时可选sequences_json；没有字段时旧confirmation_hash不变。规范化私有verification/sequences.json和原始文本、digest、USER_CONFIRMED来源绑定；仅新增精确VERIFICATION_ONLY白名单，预算继续100文件／2MiB。与前三种验证契约的保留集合统一；源码／测试／规则／配置／允许路径不能被模型修改。

candidate.test和RepairLoop识别sequence为配置后必需门禁。FAIL反馈真实前缀进入下一轮；UNKNOWN停止、不自动重试。FocusService使用真实步骤完整args定位同一失败树／基线，保留sequence_id、step_index、operation、before／actual／expected及source；实际SDK test_id保持不变，另以call_id区分同case不同step，不能捏造SDK caseID。映射键扩展可选call_id，旧调用语义不变；多个failure_id共用一步时合并事实保留全部标签。沿用最多8个定位目标，优先各保留轨迹的失败步骤，再补其前置步骤；超过8明确truncated，完整真实前缀仍保留在序列报告和反馈。

Delivery.check_set_hash、人工接受、export、archive、下载均重验当前sequence PASS与全部前置原件。归档包含冻结契约、报告、所有实际步骤／harness／日志／模型链，接受后改任一原件或模型均拒绝交付。

## 页面

沿用浅色样式与现有导入／冻结交互，新增可选序列JSON导入，原文本保持Int64精度，16KiB、异步epoch／关闭／函数或源码切换、草案应用不覆盖手动序列。确认后只读，模型许可仍是开始修复时发送，不能自动勾选或自动执行。

读取API沿用候选详情及任务当前摘要的verify，不新增执行接口；服务端生成initial_state_text、before_state_text、actual_return_text、expected_state_text及args_text等规范文本。UI展示轨迹→逐步操作→实际／参考状态、真实case＋step与原件位置、提前结束和未执行步、缩减／累计／截断。无配置不显示空面板。

当前摘要与详情有任一状态／binding／候选树冲突时保守UNKNOWN，沿用3B双向新鲜度和接受按钮保护；旧事件PASS不得盖过当前未知。textContent、actor／CSRF及只读所有权保持。

## 验收

1. 真实SDK库存扣减→取消与累计退款：公开少量测试通过，但真实可达序列击穿缺陷；参考修复通过，旧失败前缀在下一候选完整回归。至少一条两文件生产工程。
2. Bool状态、状态参数非首位、Int64下界、16轨迹×8步=128计划调用；不把重复步骤去重成一次观测。
3. 第一次偏离后正确停止，不执行尾部或可能保留输入；完整日志证明实际链／步骤计数，缺行／结束／错误before／跨case／截断等UNKNOWN。
4. 模型矛盾／溢出、不适用初始／不变量、保留集合冲突、累积超预算、真实缩减后前提失效均有明确拒绝／UNKNOWN。
5. HTTP模型／分析夹具＋真实SDK／原生策略／本地MCP两轮：公开和已配前项PASS，sequenceFAIL反馈完整真实前缀，下一候选PASS进入审阅／归档。真实外部请求0；夹具不作模型修复质量或6240准确率成绩。
6. 接受后改步骤日志／结束标记／harness／参考模型／前置公开原件／引擎助手，交付或下载拒绝。
7. 浏览器导入／冻结、真实序列FAIL／PASS／UNKNOWN与当前徽标，原始typed值与规范文本、迟到响应、跨actor／CSRF测试；保留正确媒体格式和原件。
8. 一次fresh整体审阅、重要问题集中RED→GREEN、最终冻结全量Python／Node与diffcheck、源码／core／SDK封存及禁执行的归档重放、有限凭据检查；旧3A／3B／第2项按各自源码重放。普通阶段不再重复审批。

## 留给builder的判断

安全AST小接口命名、内部已解析树是否缓存（不可改语义／哈希）、具体采样和缩减候选顺序、低层UI DOM布局和小规模重复代码取舍可自行确定，记录在计划／ledger。不得扩大支持范围、增加付费请求、放宽必须PASS的门禁或改变保留集合承诺。项目工作区与历史脏改动保留，不自动Git提交／推送／合并／清理。

## Builder检查及实施者补充判断

fresh builder返回nothing important left。之后自检作两项收紧：转移禁止函数不可见的initial_state／step_index，消除不可实现或单调用模型歧义；沿用8个定位目标上限并优先失败步，完整前缀不截断原件。这些是实施者取舍，不冒称用户另行选择；无需扩展语法、引入服务或新增付费授权。
