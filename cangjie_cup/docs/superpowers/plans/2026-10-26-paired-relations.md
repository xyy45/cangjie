# 成对调用关系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Reuse the current codex branch; no automatic commits, push, merge, workspace removal or repeated routine approval questions. One fresh whole-stage review at completion.

**Goal:** 用户确认同一函数的输入对关系后，以两个真实SDK观测发现关系反例、驱动下一修复轮次并在交付时重验。

**Architecture:** 独立relations契约／服务，复用原生轴、既有AST和有界副本／CAS模式；从single观测抽取小型primitive_trace，两个业务解释器各自判定。旧检查按原顺序执行，relation加入最后一个必需门禁。

**Tech Stack:** Python3.12、Flask、SQLite、原生JS、现有仓颉1.0.5 SDK／core2；不新增外部依赖或服务。

**Spec:** `docs/superpowers/specs/2026-10-26-paired-relations-design.md`。SDK准备证据：`docs/demo/validation/next-phase-3B-preflight/`。3A验收与旧源码独立封存，不覆盖。

## Global Constraints

- 本阶段真实模型／远程分析MCP预算0；HTTP模型响应及分析资料须标夹具，SDK／原生策略与本地MCP可真实执行。
- Int64／Bool、0..4参数、同包、最多3个允许修改生产文件；不实现3C或语法扩展。
- relations_json16KiB；version1/kind=relation；1..8条关系、表达式1..1024字符；seed0..2^32-1，max_pairs16..64，excluded_inputs0..128。
- 初始最多64对／128调用，最多2批缩减，每批16对／32调用；SDK搜索／缩减执行阶段共享90秒deadline（不含材料绑定／报告重验耗时）、60秒单批、2MiB输出；候选条件检查总8192，结构化／随机各4096。
- single原观测协议／正常harness字节保持；通用层允许不同case重复输入，single外层仍去重。源码／harness／日志／case／native轴绑定，禁止缺一侧仍PASS。
- 仅最多16条保留失败组合成为反馈和必需累计集合；所有原始观测与失败仍归档，披露截断，不承诺全部历史失败已回归。必需集合超预算则UNKNOWN。
- 不修改测试／配置／确认依据以通过门禁；原始键值精确、显示文本不舍入Int64。未知不自动重试，事务不覆盖IPC／SDK／哈希等待。
- 当前工作区有大量历史未提交改动；只扩展本阶段必要文件，逐文件保存修改前副本到本计划工作区。保持主8877加载的3A，3B门禁和页面完整验收前不重启。

## Review Focus

- 相同输入在左右或不同pair中出现，必须有各自真实case观测，不能利用去重缓存伪称双调用；Task1／4验证。
- 只一侧命中封存或缩减破坏固定价格／无优惠前提时，整对不得执行；Task2／4验证。
- 多条关系同一pair失败、展示截断和回归集合去重，不得错配左右或丢失必需保留反例；Task2／4／5验证。
- MCP成功包没有必需relation报告、前置single失败、接受后日志变化，均不得通过交付；Task5验证。
- 大Int64、最小UNKNOWN结构、旧PASS事件、晚到文件／草案响应、跨actor，不得误显示／误确认；Task3／6验证。

---

## Task 1: 抽取原始类型SDK观测协议

**Files:** Create `nexus/repair/primitive_trace.py`, `tests/test_primitive_trace.py`; Modify `nexus/repair/property_trace.py`, `property_service.py`; extend `tests/test_property_trace.py`, `tests/sdk/test_properties_sdk.py`。

**Interfaces:** primitive_trace.case_ids(token,count,kind)；harness(signature,inputs,package,token,kind)->bytes；read(signature,inputs,token,kind,log,exit_code,problem)->dict（PASS／UNKNOWN、counts、observations，每项含test_id/args/actual_return/source）。kind只允许single／relation。property_trace外层原签名与业务判定保持，PropertyService引擎摘要包含primitive_trace源码。

- [x] 写RED：两个kind的固定类名／prefix／nonce，1..128case、0..4参数、Int64／Bool，未知kind／token／包名／类型拒绝；缺失／重复／跨case／跨kind／STDERR／截断为UNKNOWN。
- [x] 先运行`../.venv/bin/python -m pytest tests/test_primitive_trace.py -q --tb=short`，Expected缺失模块FAIL，保存输出。
- [x] 实现只观测不业务裁决的通用层，允许相同输入占不同case；single包装层继续检查适用属性／排除／唯一输入，保留正常固定harness字节和result结构。
- [x] 用Task开始前归档的single固定token/harness作字节对照；测试间接primitive源码摘要变化使旧报告失效，不修改真实产品文件来制造篡改。
- [x] 运行上述专项及`tests/test_property_trace.py tests/test_property_service.py`，Expected全PASS；运行`tests/sdk/test_properties_sdk.py`证明single真实SDK行为仍完整。产品代码改动期间不运行版本绑定SDK套件。

## Task 2: 关系契约、前置条件、采样与缩减候选

**Files:** Create `nexus/repair/relations.py`, `tests/test_relations.py`；必要时在`properties.py`暴露已存在的有界Bool谓词接口，保持single语义。

**Interfaces:** validate_contract(value,signature,examples)->normalized；sampler(contract)->primitive-domain settings(max_cases128)；pair_key(pair)；applicable(contract,pair)->IDs；evaluate_pair(contract,pair,left_result,right_result)->PASS／FAIL／UNKNOWN与typed失败；generate_pairs(contract,axes=None,cumulative=[])->{pairs,candidate_checks,regression_pairs}；shrink_pairs(contract,pair,relation_id,axes=None)->至多16对。pair恰为`{left:[...],right:[...]}`。

- [x] RED 严格8字段、kind、空／重复／错类型关系，非字符串缓存错误、guard引用返回、两个返回的类型、零参数、Bool／Int64下界、未知变量／非法AST／溢出，公开已知expected对冲突；冻结输入不被原始对象后续修改。
- [x] 运行`../.venv/bin/python -m pytest tests/test_relations.py -q --tb=short`，Expected缺失接口FAIL。
- [x] 实现类型精确左右参数／结果环境、公开已知对验证、全guard无覆盖拒绝、双侧保留过滤和可重现有限生成。结构化和固定seed补充各限4096；先保留必需回归、每关系覆盖一对，再填预算。
- [x] RED 非唯一pair拒绝／去重、同输入左右可执行、仅一侧封存、域外保留、公开示例与封存冲突、所有输入封存、多个关系覆盖竞争、回归超过max_pairs时UNKNOWN而非静默丢弃。
- [x] RED 缩减保持原relation前提，支持协调缩减左右相等的参数，typed pair_key区分Bool；严格降分／双侧域与排除，不评估参考代码伪造SDK结论。
- [x] 运行关系、oracle、property_contract及旧corpushash专项，ExpectedPASS；保存真正RED→GREEN和算法边界。

## Task 3: 上传确认、私有冻结及兼容

**Files:** Modify `nexus/uploads/service.py`, `routes.py`, `nexus/execution/workspace.py`; Create `tests/test_relation_uploads.py`。

**Interfaces:** UploadService.confirm增加relations_json=None；保存relations_contract/hash/json/origin；profile精确VERIFICATION_ONLY路径`verification/relations.json`，case提供independent_relations。空字段旧confirmation_hash相同。

- [x] RED UTF-8字节16KiB（包括全空白）、NaN／重复键、错误类型／签名、三契约完整排除集合不等、oracle-v1与非空保留冲突、原文件碰撞、跨actor／CSRF、确认重放不可变。
- [x] 先运行`../.venv/bin/python -m pytest tests/test_relation_uploads.py -q --tb=short`，Expected缺失字段FAIL。
- [x] 校验在SQL写事务前；仅增加精确私有路径白名单，不开放任意JSON。追加材料计入原100文件／2MiB预算；用户确认来源不冒称模型生成，旧草案provenance不包含新关系。
- [x] 验证单文件和同包工程，原始源码／配置／测试／允许路径冻结；空relation字段不改原哈希，single／oracle原行为不变。
- [x] 运行新专项、test_property_uploads、test_upload_routes、test_project_service、test_rule_draft_confirmation，Expected全PASS，无SDK／模型／MCP执行。

## Task 4: 双侧业务判定、SDK搜索与证据重放服务

**Files:** Create `nexus/repair/relation_trace.py`, `relation_service.py`, `tests/test_relation_trace.py`, `tests/test_relation_service.py`, `tests/sdk/test_relations_sdk.py`。

**Interfaces:** relation_trace.harness(contract,pairs,package,token)->bytes；interpret(contract,pairs,token,log,exit_code,problem,*,required_ids=None)->dict。RelationService(store).binding(candidate_id)、async run(candidate_id,deadline_at=None)、verify(candidate_id)。relation_runs CAS；RELATION_STARTED/BATCH_STARTED/FINISHED事件；私有`relations/<uid32>`副本及`src/relation_observations_test.cj`；records中`.relations.json/.log/.cj`。

- [x] RED 左右展开为case2i/2i+1，实际相同输入也各有观测；错侧／缺侧／类型／nonce／summary／SDK异常不能关系PASS，实际900/0的false关系有两个原件坐标且无数值expected。
- [x] RED 先前必需检查的缺失／FAIL／UNKNOWN阻止执行；binding保存其可验证摘要／状态。CAS并发只有一次、STARTED查询不重跑、取消与deadline、间接源码／原生轴／树／日志／harness／左右输入变更拒绝。
- [x] 先运行trace/service纯测试，Expected接口缺失FAIL，然后实现。只继承既有安全记录／生产材料助手，控制循环保持显式可审阅，SQL事务短。
- [x] 搜索／缩减报告全部计数重建；最多16条确定性保留集明确截断，累计仅来自同任务更早attempt。旧报告不受后来候选影响；必需保留pair超过预算则UNKNOWN。
- [x] 真实SDK：计费阈值的公开PASS／关系FAIL与参考PASS、实际协调缩减／累计回归；Bool结果、零参数、Int64边界、相同输入左右两case、64pairs=128调用；两个源文件被实际复制和调用。
- [x] 运行`../.venv/bin/python -m pytest tests/test_relation_trace.py tests/test_relation_service.py -q --tb=short`及`tests/sdk/test_relations_sdk.py`，Expected全部PASS；保存实际原件，不把观测SDK PASS改称关系PASS。

## Task 5: 必需门禁、反馈、定位和交付

**Files:** Modify `cang_sight_server/server.py`, `nexus/repair/cegis_loop.py`, `focus_service.py`, `localization.py`, `nexus/demo/deepseek.py`, `nexus/execution/delivery.py`, `archive.py`; Create `tests/test_relation_gates.py`, `tests/sdk/test_relation_loop_sdk.py`。

**Interfaces:** candidate.test可选relations报告；顺序public→oracle→single→relation。RepairLoop依据配置识别必需关系，未运行前项失败不强索后项；所有必需PASS才能选中。新failure_cases kind=business_relation，两个args／actual_return、relation_id/text、false断言、expected_relation=true及两个真实case/source。FocusService每pair展开左右两个已执行调用目标，保留角色、同一失败树与基线坐标，不填expected。

- [x] RED 单次PASS／关系FAIL不得REVIEW_PENDING；前项失败不执行relation，缺报告OK包仍阻断，UNKNOWN不再调用下一模型；无关系旧流程不变。
- [x] RED 关系反馈带正确候选／契约摘要和两侧原件，私有JSON／封存输入不进模型；多关系同pair定位不冲突，精确输入／返回不丢失，路径建议集合约束不放宽。
- [x] RED Delivery.check_set_hash、accept、export、archive、下载拒绝缺／错／失败／未知关系；接受后日志变更亦拒绝。归档保存relation-report、契约、两侧原件与实际调用关联。
- [x] HTTP模型／分析夹具＋真实SDK／原生策略／本地MCP两轮：首候选公开与single通过但relation失败，第二请求有真实pair反例、正确定位，参考候选通过并归档；真实外部请求0。
- [x] 运行新gates/SDKloop及已有repair_loop、property_gates、deepseek、delivery、localization、审批归档专项，ExpectedPASS。

## Task 6: 页面、读取与类型精确显示

**Files:** Modify `nexus/demo/templates/demo.html`, `static/upload.js`, `demo.js`, `feedback.js`, `localization.js`, `nexus/web/app.py`, `property_view.py`, `nexus/demo/app.py`；Create `static/relations.js`, `tests/relations-ui.test.cjs`, `tests/relation-upload-ui.test.cjs`, `tests/test_relation_web.py`。

**Interfaces:** 上传body可选relations_json；现有GET候选详情返回relations，任务摘要逐候选verify后的关系状态；RelationUI.render／roundState与oracle、single组合。规范left_args_text/right_args_text/left_actual_return_text/right_actual_return_text由服务端生成，typed内部原件不改写。

- [x] Node／Flask先RED：16KiB导入、取消／错编码／大数原文本、晚响应、文件／函数／范围／手动编辑使旧读取失效，草案应用保留手动relations，确认后只读、无配置无空面板。
- [x] 显示左右参数／返回、关系、两侧观测／失败计数和截断；UNKNOWN最小结构无undefined。全部文字textContent，大Int64用规范文本，旧事件PASS不能覆盖当前UNKNOWN。
- [x] actor／CSRF边界沿用，无匿名执行接口，不新增自动模型请求或许可勾选。更新旧可选规则帮助文字，准确表达不同检查可独立启用。
- [x] 运行新UI／web专项与所有Node测试及upload/race/property-web回归，ExpectedPASS。

## Task 7: 验收、审阅、封存及3C衔接

**Files:** Create `docs/demo/next-phase-3B-verification.md`, `docs/demo/validation/next-phase-3B/`（样例、原件、源码／core、重放脚本）；Update总目标与本计划。

- [x] 真实浏览器独立夹具：导入确认、左右关系FAIL／参考PASS、已失效报告UNKNOWN及当前徽标，保存正确媒体格式截图／AX并核对原数据库／SDK原件。模型／远程分析禁用，不伪称现场新模型运行。
- [x] 一次fresh整体审阅，Critical／Important做RED→GREEN集中修复；Minor记录。保留工作区，不自动Git集成或删除证据。
- [x] 最后冻结对应源码，运行完整`../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check`；测试期间不编辑绑定产品源码。仅前端调整时须精确证明Python源码相同并重跑Node，不混淆版本。
- [x] 新关系报告和负控制离线重放，3A及第2项原件继续使用各自封存源码／native核重放；归档不含SDK包、.env、用户真实内容或会话凭据，有限凭据字节扫描不输出秘密。
- [x] 写真实计数、预算与未覆盖边界；只有全部验收才标3B完成，再重读总目标设计3C。对空闲8877激活前检查在途操作，不自动重试旧调用。

## Plan self-review

原始协议／单次兼容、双侧类型／采样／保留、确认冻结、SDK原件／CAS、控制与交付、精确页面及重放各有明确责任和先RED后GREEN任务。没有新增外部服务或付费授权。builder唯一疑问已在spec固定为16条显式保留集合；不以文档或一个样例替代完整3B产品验收。
