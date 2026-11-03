# 单次业务属性验证 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, task-by-task. Steps use checkbox (`- [ ]`) syntax. 用户已授权连续开发，保留原方法，不重复八节确认；不自动commit／push。设计builder check已返回nothing important left。

**Goal:** 为上传仓颉函数增加用户确认的单次业务属性，形成冻结→SDK观测→属性判断→反例反馈→审阅／归档闭环；不提前声称3B／3C已实现。

**Architecture:** 独立properties v1 JSON与旧oracle共存；可信SDK观测程序、既有受限表达式解释器与原生参数轴结合。新检查独立报告，接入现有candidate.test、CEGIS、审批和归档，不把SDK调用完成当作属性PASS。

**Tech Stack:** 现有Python／Flask／SQLite／原生JS、仓颉SDK1.0.5及core2，无新增依赖。

**Spec:** ../specs/2026-10-26-single-properties-design.md；../../后续能力提升开发目标.md第3项及../../demo/next-phase-3-preflight.md。

## Global Constraints

- version1、kind single；Int64／Bool、最多4参数、同包最多3个允许修改生产文件；不扩语言／数据库／并发。
- properties_json最多16KiB；属性1..8，id匹配`^PROP-[A-Z][A-Z0-9-]{0,31}$`、text1..500、precondition/assertion各1..1024字符；seed0..2^32-1，max_cases16..128，excluded_inputs0..128项。
- 输入别名arg0…arg3与结果result；前置条件不能引用result。全部表达式静态Bool，运行时Int64严格溢出／截断语义复用oracle，不用eval。
- 契约及原始业务含义由用户确认，模型不能改；无配置时旧确认哈希与oracle v1／v2语义保持不变。
- 生成／累计／缩减都排除保留输入；与oracle v2共存时排除集合完全相同。最少适用1个；缺观测、错树、错误类型及中断不能PASS。
- 初始调用受max_cases限制且≤128；最多2批缩减，每批≤32；单批≤60秒、全部≤传入deadline与90秒的较小值，输出≤2MiB。
- 无新的真实模型／远程MCP预算。上一批6/18已结束，剩余12上限关闭。本阶段HTTP／图响应均用显式夹具，SDK实际执行。
- 保留全部历史改动与codex分支；已封存第2项源码／core／原件及重放，不改旧结果来适配新版本。

## Review Focus

- 空前置条件／漏case／只看到SDK PASS：Task1与3测试确认覆盖、完整观测和属性状态独立，不空通过。
- 属性验证器绕过封存排除：Task1与3覆盖域外保留输入、Bool／Int64精确键、累计及缩减全路径。
- 私有规则混入模型／错用expected数值：Task4断言上下文仅含允许的已执行失败反馈，真实返回与属性真假分字段。
- 审批后报告失效或公开PASS掩盖属性失败：Task4与6覆盖原件变更、错树、缺报告、重复请求与中断门禁。
- 新上传／函数选择／导入的晚响应串到旧属性：Task5覆盖epoch、明确确认、跨actor及原字段／旧流程保持。

## Task 1: 严格契约、属性语义与旧规则兼容

**Files:** Create nexus/repair/properties.py、tests/test_property_contract.py；Modify nexus/repair/oracle.py仅提取domains校验；复用tests/test_oracle.py、test_benchmark_corpus.py。

**Interfaces:** oracle.normalize_domains(domains,params)->dict保持原清理语义。properties.validate_contract(raw,signature,examples)->dict返回附加signature、aliases、algorithm的规范契约；properties.sampler(contract)->dict供既有轴／生成／缩减；properties.applicable(contract,args)->list[str]；properties.evaluate_result(contract,args,result)->dict，含state、适用／通过属性ID与failures。

- [x] RED test_properties_aliases_int_bool_and_refund_invariant：arg0…与result类型正确；两个退款属性可判断真实1100越界，900保持不变通过；Bool不能作整数。
- [x] RED test_properties_reject_bad_schema_types_guards_and_expression：重复键在接入层拒绝；这里拒绝未知字段、版本、名字、输出依赖前置条件、静态非Bool、错误分支类型、溢出、超限、空适用域和与公开expected冲突；域外公开例子不扩大覆盖。
- [x] RED test_reserved_inputs_type_exact_and_outside_domain：排除集合可在域外但类型精确，生成／缩减不触碰保留集合；不混淆true与1。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_property_contract.py -q --tb=short`，观察缺失接口FAIL，保存RED。
- [x] 实现有界AST类型检查与复用解释；只提取旧domains校验，不放宽oracle字段／参数域规则。
- [x] 运行该专项、tests/test_oracle.py、tests/test_upload_oracle.py、tests/test_benchmark_corpus.py；Expected全PASS，旧30／100hash相同。

## Task 2: 属性上传、确认冻结与来源

**Files:** Modify nexus/uploads/service.py、routes.py、nexus/execution/workspace.py；Create tests/test_property_uploads.py。

**Interfaces:** UploadService.confirm增加properties_json=None；stored properties_contract/properties_hash/properties_json/properties_origin；profile注册verification/properties.json为VERIFICATION_ONLY，case提供independent_properties；空字段沿用旧哈希。

- [x] RED 单文件／ZIP、严格16KiB与重复键、规则冲突、签名别名、oracle-v2保留集合不等、保留文件碰撞、跨actor及重复确认不可变；检查旧字段为空确认完全兼容。
- [x] 加入精确路径白名单／原工程碰撞拒绝，规范契约进入树及confirmation_hash；不得发送SDK／模型请求或在冻结后编辑。
- [x] 测试用户属性origin=USER_CONFIRMED，旧草案provenance仍只覆盖原例子／oracle；确认后反向篡改文件和manifest拒绝。
- [x] `../.venv/bin/python -m pytest tests/test_property_uploads.py tests/test_upload_service.py tests/test_upload_routes.py tests/test_project_service.py tests/test_rule_draft_confirmation.py -q --tb=short`。以实际存在旧测试名修订命令并记录，不跳过相应覆盖。

## Task 3: 观测协议、SDK属性搜索及重放

**Files:** Create nexus/repair/property_trace.py、property_service.py、tests/test_property_trace.py、tests/test_property_service.py、tests/sdk/test_properties_sdk.py；Modify nexus/execution/runner.py。

**Interfaces:** runner.run_command增加可信关键字test_output='failures'，只允许failures/all且all仅用于test，执行argv绑定show-all选项；默认字节语义不变。property_trace.harness(contract,cases,package,token)->bytes；property_trace.interpret(contract,cases,token,log,exit_code,problem,*,required_ids=None)->dict。PropertyService(store).binding(candidate_id)、async run(candidate_id,deadline_at=None)、verify(candidate_id)。

- [x] RED SDK summary／case／STDOUT标记完整校验：一个正确case一条token／类型匹配的返回，拒绝缺失／重复／wrong-case／错token／溢出／截断；SDK执行PASS而属性FAIL必须可区分。
- [x] RED runner输出参数封闭、默认argv不变、all透传到受限测试阶段；不允许任意命令参数。
- [x] RED 唯一CAS、错候选／树／计划／属性／日志、全guard不适用、原生轴变化、保留输入生成／累计／缩减、STARTED不重跑及取消未知；实现绑定报告与受限批次。
- [x] SDK退款用例：公开[1000,800,100]→900与[1000,800,200]→1000均通过；域paid900..1000/refunded800..900/requested100..200，基线漏扣历史额度应被范围／非法保持属性击穿；参考修复PASS。
- [x] 真实SDK Bool与Int64极值、128输入上限、缩减仍适用且失败；完整日志／harness／manifest重放一致，源码和编译产物不被改写。
- [x] `../.venv/bin/python -m pytest tests/test_property_trace.py tests/test_property_service.py -q --tb=short`与`../.venv/bin/python -m pytest tests/sdk/test_properties_sdk.py -q --tb=short`。Expected纯测试先RED再GREEN；SDK真实击穿／参考PASS，不伪造失败。

## Task 4: 策略测试、反馈、审阅与归档门禁

**Files:** Modify cang_sight_server/server.py、nexus/repair/cegis_loop.py、focus_service.py、localization.py、nexus/demo/deepseek.py、nexus/execution/delivery.py、archive.py；Create tests/test_property_gates.py、tests/sdk/test_property_loop_sdk.py。

**Interfaces:** candidate.test返回可选properties报告，旧oracle FAIL／UNKNOWN不启动新检查；RepairLoop只在所有必需检查PASS时选中候选。业务属性failure_cases使用kind business_property、actual_return、assertion_value、expected_property和绑定来源，不用伪数值expected。check_set_hash／EvidenceArchive消费PropertyService.verify。

- [x] RED 公开PASS／属性FAIL不得REVIEW_PENDING或接受／归档；属性UNKNOWN阻断；无属性旧流程不变；属性被改、缺失、错树、审批后失效不能交付。
- [x] RED model上下文／私有输入不泄漏、定位expected缺失不造答案、建议路径集合指令明确且旧校验不放宽。仅新提示版本使用新证据，旧评测结果保持原样。
- [x] SDK+HTTP／MCP夹具两轮：保留缺陷首候选公开PASS／属性FAIL，下一保存请求有实际反例，参考候选PASS；actual_return与SDK日志一致；模型／远程MCP真实调用0。
- [x] 运行新gates／loop专项与既有CEGIS、审批、归档、定位、DeepSeek协议覆盖，Expected全部PASS；实际命令与结果记录进ledger。

## Task 5: 可用页面、导入与可见结果

**Files:** Modify nexus/demo/templates/demo.html、static/upload.js、demo.js、feedback.js、localization.js、nexus/web/app.py；Create static/properties.js、tests/properties-ui.test.cjs、tests/property-upload-ui.test.cjs、tests/test_property_web.py；Reuse现有浅色样式。

**Interfaces:** 上传确认body可选properties_json；现有/api/candidates/<candidate_id>返回只读properties结果，既有任务／候选归属中间件生效；PropertyUI.render／roundState与旧ExplorationUI组合，不靠前端决定审批。

- [x] RED 导入UTF-8／16KiB、取消导入、源码／函数／范围变化、晚响应、草案应用不覆盖属性、重复确认及无属性旧路径；private数据只发给所属会话。
- [x] 展示输入别名、用户确认字段及报告每属性适用数、实际返回、失败约束、PASS／FAIL／UNKNOWN。描述textContent渲染，错树报告不显示为通过。
- [x] Node与Flask路由测试先FAIL再实现PASS；不自动勾选许可／触发模型，不新增执行端点或无关布局。

## Task 6: 收尾、独立审阅与3B衔接

**Files:** Create docs/demo/next-phase-3A-verification.md、docs/demo/validation/next-phase-3A/及示例；Update总目标与本计划；不覆盖第2项原件。

- [x] 真实浏览器HTTP夹具完成属性JSON导入／确认／结果，保存截图和数据库／SDK对照；各类来源分别标识。
- [x] 一次fresh-context整体审阅，Critical／Important按RED→GREEN修复，Minor记录不假装已完成；不按任务反复派评审。
- [x] 源码冻结后完整 `../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check`；不在版本绑定测试期间修改产品源码。
- [x] 第2项归档源码重放仍PASS；新属性契约／原件／源码／core归档与验证，排除密钥与真实会话。无需额外重复执行已通过的旧SDK测试以充数。
- [x] 写真实验收与未覆盖边界，只将3A标已验收；重读总目标后编写3B计划。3B／3C及整个目标保持未完成。

## Plan self-review

契约、确认、采样／保留输入、严格观测、真实SDK、CAS恢复、属性与工具状态区别、反馈／定位、交付门禁、页面和归档各有对应任务。无新依赖、付费预算或语言扩展。用户连续授权保留，实施方逐项执行；现有未提交基线与阶段2封存保护历史，最终一次独立审阅，不自动Git操作。
