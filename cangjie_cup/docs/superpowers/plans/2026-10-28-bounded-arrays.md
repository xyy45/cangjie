# 有界Int64数组 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement inline task-by-task. Steps use checkbox (`- [ ]`) syntax. 既有持续授权，不重复阶段确认；保留台账及全部旧原件，不执行Git写入。

**Goal:** 使有界Array<Int64>从上传／确认贯通真实SDK独立验证、反例修复、人工审阅和可追溯交付。

**Architecture:** 扩展现有shared values、受限语法与版本化模型；数组选择只读候选子集／按值验证语义和新V3观测，复用四服务、原生轴、权限及交付。旧活动4A独立快照保持。

**Tech Stack:** 现有Python3.12／Flask／SQLite／原生JS／pytest／Node、固定SDK1.0.5／stdx、仓颉core，无新依赖。

**Spec:** `docs/superpowers/specs/2026-10-28-bounded-arrays-design.md`

## Global Constraints

- Array<Int64> JSON list长度0—16，元素严格Int64／非Bool；String≤256UTF-8字节。Array域values1—16唯一明确数组，无嵌套。
- 候选数组只读：字面量、下标读、size、for遍历、结构比较和返回；拒绝元素赋值／成员方法／构造器。源码与参数／文件／执行预算保持原值。
- 含Array仅Oracle4、property3／relation3／sequence3、V3；String-only维持3／2／V2、numeric旧版本。模型仅预算内预检，新helper checked，无全域枚举。
- 新付费模型／远程分析预算0，HTTP模型／图明确夹具，固定SDK／native／stdio真实调用分别记录。
- 主站独立4A／真实用户数据／session不作fixture、不覆盖；各任务冻结／原件保留，不Git写入或台账清理。

## Review Focus

1. list可变性及Bool混入不能污染key、before_state、左右调用或历史输入；Task1／2／3／4逐层复制及否定控制。
2. 空数组／Int64极值／索引负数／第17项不能静默转义、截断或冒充候选PASS；Task1／2／3真实SDK。
3. 序列Array状态非首参数、固定String上下文与全历史，必须真实前态接续；Task2／4的跨轮SDK。
4. 保留V3协议混入V1/V2、假TCS／CASE／Summary、类型错配均UNKNOWN；Task3协议矩阵与旧golden。
5. 上传／草案／旧响应或篡改不能换冻结测试／规则，摘要PASS不能覆盖详情UNKNOWN；Task4／5审阅／导出及浏览器。

## Task1：数组值、只读语法和公开测试

**Files:** Modify `nexus/repair/values.py`、`nexus/uploads/language.py`、`nexus/projects/index.py`；Create `tests/test_array_values.py`、`tests/test_array_language.py`、`tests/test_array_projects.py`、`tests/sdk/test_array_public_sdk.py`。

**Interfaces:** values.array(value)->新list，has_arrays(signature)->bool，typed_key(array)->('Array<Int64>',tuple(elements))，primitive_weight(array)->len+sumabs，primitive(array,'Array<Int64>')->新list。language.literal(array)->[]／[canonical Int64,...]；Parser.expr／type保持调用接口，type增加规范Array<Int64>，局部for绑定Int64且block后消失。

- [x] 写RED：空／16／17、Bool／float／tuple／嵌套／越界整数、复制／typedkey／weight，字面量往返；Array参数返回／局部／混合／下标读／for与while／size／数组==，错误元素／索引／比较及写入／构造器／方法／嵌套泛型拒绝。工程数组Expect固定原件和跨文件调用保护。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_array_values.py tests/test_array_language.py tests/test_array_projects.py -q --tb=short`；Expected缺失功能FAIL，排除fixture／收集错误后记录真实RED。
- [x] 最小实现上述values／词法[]／精确类型／for局部作用域；TestParser逐数组元素解析及签名typed核对，不允许任意表达式测试。
- [x] 运行新增三文件加 `tests/test_string_values.py tests/test_string_language.py tests/test_string_projects.py tests/test_upload_language.py tests/test_project_index.py tests/test_project_archive.py`；Expected全PASS，原literal数值／String字节不变。
- [x] 真实SDK公开缺陷→修复：漏末项、空／负数／重复／16项／极值；数组返回与两文件原测试。源码先冻结、只改允许生产文件、原测试case完整集核对。运行 `../.venv/bin/python -m pytest tests/sdk/test_array_public_sdk.py -q --tb=short --basetemp=/private/tmp/cangsight-4B-task1-sdk-20261028`；Expected所有测试PASS，业务bad为FAIL、fixed为PASS，原件保存，原4A资产／core不变。

## Task2：Array版本模型、搜索／缩减与原生轴

**Files:** Modify `nexus/repair/oracle.py`、`properties.py`、`relations.py`、`sequences.py`、`cangjie/core/src/main.cj`；Create `tests/test_array_contracts.py`、`tests/test_array_search.py`、`tests/test_array_core.py`。

**Interfaces:** expression_tree(text,names,allow_strings=False,allow_arrays=False)、evaluate(node,env,allow_strings=False,allow_arrays=False)、expression_type(node,names)；新数组helper仅allow_arrays允许。input_key向量保持旧scalar键，数组元素为typed tuple；sampler／checked_axes／generate／shrink输出新独立list。所有模型Array版本由签名has_arrays优先确定，源码依赖后续绑定。

- [x] RED覆盖Oracle4／其余3与wrongversion、结构类型／JSON域／排除输入、全Int64域预算非穷举、array_len／at／sum／append／replace的类型／越界／溢出／长度16；旧版本不能用新helper。Array状态非首参数、String上下文、初态域／后态可达／9条保留历史。
- [x] 运行新增三文件，Expected缺失版本／功能FAIL；实现精确AST白名单／独立allow_arrays、typed domain、确定评分／key／深复制，全部实际计划和缩减前预检。
- [x] 原生增加Array轴分支，实际构建新开发core，记录compiler／source／component。实际合法数组轴、Bool混入／重复／超限拒绝；消费端checked_axes验证嵌套type，不用Python值冒充native。
- [x] 运行新增三文件及 `tests/test_string_contracts.py tests/test_string_search.py tests/test_string_core.py tests/test_oracle.py tests/test_property_contract.py tests/test_relations.py tests/test_sequences.py tests/integration/test_native_core.py tests/integration/test_native_core_policy.py tests/test_native_core_binding.py`；Expected全PASS，新旧源码／核心原件归档，主站4A不变。

## Task3：V3数组可信观测

**Files:** Create `nexus/repair/array_trace.py`、`tests/test_array_trace.py`、`tests/sdk/test_arrays_sdk.py`；Modify `primitive_trace.py`、`property_trace.py`、`relation_trace.py`、`sequence_trace.py`。路径前缀均`nexus/repair/`。

**Interfaces:** array_trace.encode(value,kind)->canonical wire、decode(text,kind)->独立typed值、harness header/guard支持V3和String；primitive_trace.protocol／case_ids／harness／read显式version3，旧default1不变。Array优先协议；全部结果保持typed原值和日志source。

- [x] RED严格a:count:tokens、空／极值／16／17／非规范值／String混合；V1/V2/V3错前缀／kind／case／step／重复／STDERR／summary后／假TCS均UNKNOWN；包级函数引用／命名碰撞与旧V1/V2正常golden。
- [x] 实现V3编码／实际SDK完整case验证；Array返回超16产生VALUE_LIMIT／UNKNOWN，state真实链和未执行尾部计数严格，宿主深复制防alias。
- [x] 运行新协议及全部旧primitive/property/relation/sequence/String trace tests，Expected全PASS。
- [x] `../.venv/bin/python -m pytest tests/sdk/test_arrays_sdk.py -q --tb=short --basetemp=/private/tmp/cangsight-4B-task3-sdk-20261028`；实际Array输入／返回、16与17、极值、独立双调用、状态／String上下文，真实越界／溢出UNKNOWN。ExpectedSDK驱动测试PASS，故意业务FAIL／异常UNKNOWN如实计数；源码先冻结，原日志／输入／结果封存并纯重建一致。

## Task4：冻结、CEGIS、定位和交付门禁

**Files:** Modify `nexus/uploads/service.py`、`rule_contract.py`、`rule_drafts.py`、`nexus/demo/rule_draft_provider.py`、`nexus/demo/deepseek.py`、`nexus/repair/exploration.py`、`property_service.py`、`relation_service.py`、`sequence_service.py`、`cegis_loop.py`、`localization.py`、`nexus/execution/delivery.py`及现有依赖绑定；Create `tests/test_array_uploads.py`、`tests/test_array_services.py`、`tests/test_array_feedback.py`、`tests/test_array_gates.py`、`tests/sdk/test_array_loop_sdk.py`、`tests/sdk/test_array_cegis_loop.py`。只改实际缺口，已泛化门禁不重构。

**Interfaces:** 延用既有prepare／confirm／start／verify／feedback／accept／export协议；新增Arraytyped值及契约版本，Oracle4报告规范JSON text并保留actual_return／expected_value和source。engine binding包括Array codec／values／模型依赖，新core身份不能静默复用旧报告。

- [x] 写RED覆盖schema／提示／确认冻结／跨会话／幂等、list key／排除与history、public原件／模型篡改／数组wire／过期core／先前STARTED、预检失败不得消费SDK／孤立STARTED；Expected真实缺口FAIL。
- [x] 接入四服务实际观测／缩减／全历史、定位与完整反馈，Array模型顺序与权限保持。新生成草案只能预览显式应用，不额外调用付费模型。
- [x] 运行新增上传／服务／反馈／门禁文件以及既有userreview／delivery／artifact／race相关回归，Expected全PASS。
- [x] 两类实际自建漏洞至少覆盖Oracle+property、relation和Array状态。公开PASS→独立FAIL→参考修复PASS；跨轮保留真实更小前缀，所有历史复验。HTTP模型／图夹具、实际SDK/native/stdioMCP；未知首轮后无第二次请求。实际网页接受／导出／下载200，原件篡改400→恢复200。运行新增SDK两文件，Expected驱动测试PASS，原件与冻结执行源均保存。

## Task5：数组页面导入与真实浏览器

**Files:** Modify `nexus/demo/static/upload.js`、`feedback.js`、`exploration.js`、`demo.js`、`templates/demo.html`、`nexus/web/property_view.py`和`nexus/web/app.py`的实际缺口；Create `tests/array-ui.test.cjs`、`tests/test_array_web.py`、`docs/demo/validation/next-phase-4B/browser_fixture.py`。

**Interfaces:** Array参数初值[]，expected仍null；canonical JSON text支持向量中嵌套数组／空数组／大整数，原typed JSON不变。候选当前summary/detail复验冲突UNKNOWN，禁接受且保留合法拒绝。

- [x] Node／Flask RED覆盖[]默认、可读参数／before／return／prefix、当前状态而非历史事件；实现必要显示／帮助及readonly查询。Expected新旧相关测试PASS；不改无关布局。
- [x] `node --test tests/*.test.cjs`和`../.venv/bin/python -m pytest tests/test_array_web.py tests/test_string_web.py tests/test_sequence_web.py tests/test_relation_web.py tests/test_property_web.py tests/test_upload_routes.py tests/test_workbench_race.py -q --tb=short`，Expected全PASS。
- [x] 隔离自建SDK运行副本，所有外部执行禁用；浏览器实际文件导入→确认／只读→FAIL／更小Array反例→PASS→只改副本原件UNKNOWN→恢复PASS。保存截图／AX／零执行审计，关自有tab／服务，主站不作fixture。

## Task6：最终审阅、封存、整体回归与激活

**Files:** Create `docs/demo/next-phase-4B-verification.md`、`docs/demo/validation/next-phase-4B/capture_evidence.py`、`replay_offline.py`；Update本计划、spec、总目标。

- [x] 一次fresh全阶段审阅，对比accepted4A冻结基线；Critical／Important集中RED→GREEN修复，Minor记台账；不二次审阅。每项ruling写清风险。
- [x] 冻结源码／helper／core后运行完整`../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check`；Expected全PASS，期间不编辑冻结源。
- [x] 所有自建SDK／HTTP夹具／native／门禁控制、完整源码／core封存，独立子进程禁止SDK／IPC／网络从ZIP重建；旧2／3A／3B／3C／4A使用各自版本全部重放，ExpectedPASS，不改原件为通过。
- [x] 有限配置凭据／私有成员／路径／嵌套ZIP扫描，显式保留检查过的SDK／自建测试路径，不声称普遍匿名化。
- [x] 独立4B自有core快照就绪，主站当前全部无在途才切换／恢复，保留真实任务／session／记录并比对HTTP资产。只标4B，4C／4D／5仍待实施；重读目标推进4C，预算0。


2026-10-29完成：2240 Python／171 Node，33组独立重建、有限扫描与主站激活PASS；Minor及全部Ruling保留于台账，未Git写入或清理历史原件。
