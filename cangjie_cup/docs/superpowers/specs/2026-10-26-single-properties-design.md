# 3A 单次业务属性验证设计

2026-10-26。实现前设计；当前产品尚未具备该能力。依据总目标第3项与next-phase-3-preflight.md，承接第2项已完成的真实批次与归档证据。用户已授权按路线连续开发，常规实现选择不重复八节确认；新付费预算仍独立，本阶段只用离线／SDK／HTTP夹具，不调用真实模型或远程MCP。

## 目的与边界

让用户为上传的仓颉函数确认“返回值必须满足什么”，不必为每个输入写唯一标准答案。保留现有公开例子／oracle，真实SDK运行目标函数，严格采集返回值，固定解释器判定属性；不由模型自评或修改验证依据。

仍是Int64／Bool、每函数最多4参数、同包最多3个允许修改的生产文件。只做3A单次调用；关系／序列、字符串／数组／对象、数据库／网络／并发不在本增量。不自动生成属性草案，不新增依赖或服务。

## 方案选择

比较见preflight：统一改造oracle会使旧答案语义与证据变化；外部性质框架没有当前必要性。采用**独立版本properties契约**，复用现有类型／算术解释、参数轴、受限副本、策略测试入口与归档。该选择由实现方作出，未声称用户逐字段选定设计。

SDK已实际验证`--show-all-output`可在原沙箱中获取通过／失败用例的Int64／Bool输出；默认仅显示失败用例输出。使用可信观测测试程序加新输出模式，SDK完成与属性通过独立记录：无断言的观测case PASS只证明调用完成，不直接等于属性PASS。

## 契约与确认

新增可选`properties_json`，UTF-8最多16KiB；空字符串等同未启用，非空必须严格JSON对象，无重复键。用户导入／编辑、预览、确认后冻结为`verification/properties.json`，不覆盖原工程同名保留文件。

原始字段恰为：`version=1`、`kind="single"`、`function`、`domains`、`properties`、`seed`、`max_cases`、`excluded_inputs`。

- function匹配选择的签名；domains使用实际参数名及既有Int64 min/max/points、Bool空对象语义。
- properties为1至8项；每项恰为id、text、precondition、assertion。id匹配`^PROP-[A-Z][A-Z0-9-]{0,31}$`且唯一，text为1至500字符；两表达式各1至1024字符。
- 输入表达式别名固定为arg0…arg3，按签名顺序；实际返回值别名result。原函数参数即使名为result也不冲突。前置条件不允许引用result，断言允许；类型均静态检查为Bool。
- 复用oracle白名单AST、短路、Int64溢出／截断除法语义；禁止eval、属性访问、任意调用或源码拼接。未知名字、Bool作整数、错误分支类型及危险语法在确认前拒绝。
- seed为0..2^32-1，max_cases为16..128；excluded_inputs为0至128个类型精确且不重复的参数数组。排除集合可含域外保留输入，但必须符合函数参数类型。属性和oracle同时启用时，若oracle为v2，两者的完整排除集合必须相同；v1不得另外伪称封存保护。
- 每条属性必须在有限生成输入中至少有1个前置条件适用输入，否则确认拒绝为覆盖不足；执行时仍重新核对实际适用／观测数，不能空通过。
- 公开示例在属性域内且满足前置条件时，其已确认expected也必须满足断言；冲突拒绝。域外例子仍由公开测试验证，不扩大属性覆盖声明。
- 标准化附加signature、algorithm=`single-properties-v1`；保存独立properties_hash及origin=`USER_CONFIRMED`。包括在最终confirmation_hash与不可变树中。旧调用未提供字段时，旧确认内容与哈希行为不变。

oracle v1／v2不新增字段、不改解释语义。可从旧校验中提取公共domains规范化函数，须用旧契约与旧语料hash快照证明字节语义相同。旧模型草案仍只负责其原有例子／oracle，用户新增属性不冒称由模型生成。

## 观测协议与解释

可信测试程序只复制冻结配置及生产.cj文件，独立创建测试，不修改候选。函数名和字面量来自已校验签名／输入；属性文字不拼入仓颉源码。使用带精确签名的本地函数引用消除与标准库函数的同名歧义，标准输出使用显式导入别名；不导入自身包。

每个输入调用目标一次，打印固定行`NEXUS_PROPERTY_V1|<token>|case<index>|<Int64或Bool>|<实际值>`。token由候选／契约／批输入摘要产生；测试类名固定前缀加摘要，caseID与输入清单一一绑定。Int64要求规范十进制且在范围内，Bool只接受true／false，不接受null／浮点／字符串。

先核验完整SDK最终summary、预期caseID、全部case PASS及exit0，再在首个summary之前的对应case STDOUT段解析标记；可忽略ANSI／固定缩进，不允许跨用例借用。每case恰好1条正确token／类型观测。缺失、重复、错token、错误case、溢出、截断或不完整日志为UNKNOWN，不凭字符串匹配判成功。

使用受限解释器，以实际观测结果计算已确认属性。报告分别保存execution_state与property_state、每属性生成／适用／观测／失败数。属性PASS需要完整且每条至少一个实际适用输入、所有断言true；实际断言false为FAIL；解释／执行异常为UNKNOWN。

## 执行、恢复与重放

新增PropertyService的binding/run/verify，模式与既有ExplorationService一致；复用其生产材料选择与记录读写，不复制或放宽沙箱。新property_runs按candidate_id唯一CAS登记STARTED；网络、原生IPC、SDK和文件验证不置于SQLite写事务内。

binding包含候选／树、冻结测试计划、properties_hash、必要的旧oracle排除绑定、解释器／观测解析器／执行器／SDK报告解析器源码摘要、SDK及native core身份。原生boundary.axes产生输入轴并严格核对类型、顺序、域；生成／缩减保留现有有限采样，不冒称完备。

总体执行不超过传入deadline与90秒较小值，每次SDK批次不超过60秒；初始最多128调用，随后最多2批缩减，各不超过32调用。输出最多2MiB。每条记录保存实际执行argv、工程manifest、可信harness、完整日志及hash。

缩减以真实失败为依据，保持原失败属性的前置条件及域／排除约束；用SDK重跑确认后才收下。不能用Python参考实现代替目标函数。初始搜索要求全部属性覆盖；缩减解释仅要求原失败属性的实际适用覆盖，required_ids作为批次事实绑定并由verify重建，不能借此宣称整个候选通过。失败列表最多16条且明确截断标记，真实失败总数独立保存；缩减未知使报告UNKNOWN并保留已有诊断，不承诺全局最小。

STARTED或中断请求不自动执行第二遍；查询为UNKNOWN，需新候选／新任务。verify只重建材料、观测与解释结论，不执行SDK／模型／MCP。报告或源文件／工具版本改变会失效，不能沿用旧PASS。

## 进入既有修复与交付门禁

candidate.test在公开测试PASS后先执行旧oracle探索；旧探索FAIL／UNKNOWN时不追加属性执行，先按原语义处理。旧探索无配置或PASS时运行必要属性检查。仅当公开测试、旧探索（若有）和属性（若有）全PASS才能REVIEW_PENDING。

属性FAIL构造新的`business_property`反馈，包含实际输入、actual_return、assertion_value=false、expected_property=true、属性ID／已确认约束摘要、候选／树／契约及日志引用；不伪造唯一expected数值，不发送完整契约、保留输入或未执行测试。属性UNKNOWN阻断，不能让原test PASS吞掉新结果。

既有FocusService对属性反例只做函数／参数与基线静态定位，标明失败树与基线坐标；expected数值不存在时保留缺失，不用oracle猜出答案。DeepSeek提示补充新反馈含义，以及suggestions.path必须与proposal.edits.path完全一致；保留原严格校验器，旧真实失败不改写，新提示不借用旧成绩。

DeliveryService.check_set_hash加入当前属性报告，审批／导出／重试／下载和EvidenceArchive均重新核验。缺失、未知、失败、错树或审批后变化均不能交付。归档保存契约、报告、harness、日志、缩减记录及来源；不存在属性配置时保持旧路径。

## 页面与访问边界

上传窗口增加“业务属性（可选）”JSON编辑／导入与签名别名预览；复用既有浅色样式、UTF-8大小检查、读取epoch及确认流程。模型草案应用只覆盖其原字段，不悄悄覆盖新属性；函数／文件／范围改变时失效旧输入读取与确认许可，不能错用晚到结果。

新增PropertyUI展示属性执行中／PASS／FAIL／UNKNOWN、每项适用数与真实反例；轮次完成状态同时考虑新检查。通过现有受任务／candidate归属校验的GET接口及事件提供只读报告，不另开匿名执行端点。描述按textContent渲染。没有新属性时不出现空面板。

## 验收条件

1. 单文件退款：公开示例通过，但属性击穿累积越界；参考修复通过；适用数、actual_return与SDK原件一致。
2. 同包多文件：只改允许生产文件，配置／公开测试／属性及签名冻结；Bool返回值和Int64极值类型精确。
3. 全guard为false、规则冲突、未知变量、类型错配、溢出、缺／重复观测、错误树／契约／日志及中断均不能PASS；旧oracle／确认兼容快照不变。
4. 明确HTTP／MCP夹具，真实SDK两轮：首轮公开PASS／属性FAIL，实际属性反例进入下一模型请求，参考候选PASS；不称真实模型收益，不新花付费预算。
5. 属性未通过无法接受／导出；批准后报告被替换或失效仍不能交付；既有审批和隔离测试继续通过。
6. 浏览器fixture完成导入／确认／属性展示与新反例查看；跨actor、晚响应、重复点击和无属性旧流程覆盖。
7. 端到端原件归档／重放、完整非live Python／Node／diff检查通过，旧阶段源码重放仍可用；真实调用为0，状态与局限写入验收文档。

## 后续

3A验收后再设计3B成对调用与3C显式标量序列，分别定义前置条件、两侧保留输入排除、状态转移、逐步实际观测与序列缩减。本设计不把3A完成视为整个第3项或总目标完成。保留未提交工作区，不自动commit／push／部署。
