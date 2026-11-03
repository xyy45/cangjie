# Bounded Strings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in this session. No per-task implementation or review agents. One fresh whole-stage review at the end.

**Goal:** 在仓颉受限修复流程中支持有界String，覆盖公开测试、四种独立验证、反例迭代与交付。

**Architecture:** 复用现有解析、服务和门禁，新增共享值语义和V2观测，String契约显式新版本。原numeric协议与算法保持，原生仓颉核提供String有限域轴，8877在验收前继续独立3C快照。

**Tech Stack:** Python3.12／Flask／SQLite／vanilla JS／Node test／pytest／固定仓颉SDK1.0.5及stdx；不增依赖。

**Spec:** `docs/superpowers/specs/2026-10-27-bounded-strings-design.md`

## Global Constraints

- 真实模型／远程分析新预算0；任何HTTP模型或分析图均明确夹具，实际SDK／原生IPC另记。
- String值／源字面量／表达式中间值最多256 UTF-8字节，合法Unicode标量，无规范化；byte_len和rune_len语义分别明确。
- String域values1—16；同包最多3允许生产文件、普通函数最多4参数，既有文件／契约／执行／保留输入预算不变。拒绝数组值、对象、跨包、导入或一般成员访问。
- 含String仅oracle3、property2、relation2、sequence2；纯numeric继续旧版本；V1正常harness与数值采样／缩减golden不变。
- 只预检预算内实际计划／缩减／历史回归和既定公开示例，不枚举完整Int64域，矛盾模型和超限在SDK前拒绝，不报告未采样语义已证。
- 原生boundary.axes含String分支；Python完整typed重建证明，不用Python结果冒充仓颉返回。
- 主站独立3C快照／原用户数据／会话不改，最终闲置审计后另建4A快照切换；不重试未知请求。
- 复用已授权历史dirty工作区；不修改.git、不commit／push／reset／clean／删除台账。按任务保存精确源码和原件，禁止跨运行复制参考修复充当模型候选。

## Review Focus

1. 字符串里的伪CASE／Summary／协议／引号／注释不能控制解析、测试harness或日志归属；覆盖Task1和Task3。
2. 未规范化Unicode的字节数／码点数、控制字符显示及256边界跨层相同；覆盖Task1／2／3／5。
3. 历史numeric结果、harness、得分与旧档案继续准确复验，不能悄悄迁移；每任务兼容及Task6。
4. 混合String状态／上下文的缩减保持原初态可达和全历史前缀，不比较不相容Python类型或静默漏回归；Task2／4。
5. 用户确认后模型不能修改String测试／规则／范围；未知与篡改禁接受和交付但保留合法拒绝；Task4／5。

## Task 1: 有界值、受限String语法与公开测试

**Files:** Create `nexus/repair/values.py`, `tests/test_string_values.py`, `tests/test_string_language.py`, `tests/test_string_projects.py`, `tests/sdk/test_string_public_sdk.py`; Modify `nexus/uploads/language.py`, `nexus/projects/index.py`, only necessary existing public-test producers.

**Interfaces:** values.string(value)->str严格检查；primitive(value,kind)->原typed值；byte_len(str),rune_len(str)->int；typed_key(value),primitive_weight(value)；string_literal(value)->CjUnicode转义字面量。values模块不导入oracle／language，不造成环依赖。旧language.literal数值返回字节不变；String用string_literal。inspect_source／inspect_project返回既有结构含String类型，不增加任意AST执行。

- [x] 编写RED：空／Unicode／代理字符／256与257、NUL、美元插值形状安全字面量；注释和引号中的括号不影响函数索引；String参数/返回/混合调用、size/专用toRuneArray().size；错误算术／一般成员／插值／I/O仍拒绝。@Expect String字面量项目解析及保护原测试；普通函数重载、范围与包不放宽。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_string_values.py tests/test_string_language.py tests/test_string_projects.py -q --tb=short`，观察真实缺失功能RED。
- [x] 最小实现独立值语义、完整String词法和精确类型推导；逐码点转义不把JSON变可执行源码。项目测试复用同一解码器，String+String和==/!=限定，长度链只接String，无String排序。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_string_values.py tests/test_string_language.py tests/test_string_projects.py tests/test_upload_language.py tests/test_project_index.py tests/test_project_archive.py -q --tb=short`；这些既有文件均已实际定位。
- [x] 写并真实运行 `tests/sdk/test_string_public_sdk.py`：ASCII和中文byte/rune边界、String返回quote/control/empty、两文件helper、256边界；公开缺陷FAIL与参考修复PASS，真实固定SDK argv／日志／源／config／manifest保留。只自建样例，无模型或分析。
- [x] 保存任务证据及精确退出状态，task-done只运行实际发现的对应测试命令；不Git提交。

## Task 2: String契约、类型表达式、有限搜索／缩减与原生轴

**Files:** Create `tests/test_string_contracts.py`, `tests/test_string_search.py`, `tests/test_string_core.py`; Modify `nexus/repair/oracle.py`, `properties.py`, `relations.py`, `sequences.py`, `cangjie/core/src/main.cj`, necessary native binding modules. Sharedvalues来自Task1。

**Interfaces:** oracle.expression_tree/evaluate保留旧调用默认语义；String版本显式传入类型/版本上下文（具体可选参数名由实现者在首个brief定下）。String normalize_domains→{values:[...]}；所有类型检查共享values。axis_values、generate_inputs、shrink_inputs对新版本支持String；原native boundary_payload结构保持。core boundary.axes验证并返回JsonString轴，与Python checked_axes全值/类型/顺序对比。

- [x] RED：四种版本拒绝String旧版／numeric乱新版；String常量/拼接/等值/长度helper/类型分支，旧版本拒新语义；非法UTF-8／溢出中间值／重复域/过多值／保留冲突；公开例子与模型不一致。完整域不穷举，计划输入可检测矛盾，超预算安全失败。
- [x] RED：确定seed排序、String严格typedkey、混合值权重、仅域内变短缩减；关系两侧String返回；String状态／String固定上下文和非首槽状态、同完整输入操作一致、初态可达、历史9前缀不按8截断。
- [x] 实现新契约的显式版本和安全类型表达式；数值旧函数默认行为与golden保持。新状态/关系沿已有接口，不能落入else整数转换。
- [x] 增加原生String轴分支，按values顺序去重检查而不是偷偷去重；运行 `../.venv/bin/python scripts/build_core.py`（先读脚本实际CLI），保留旧3C核心不覆盖快照。真实原生good/empty/control/256和invalid字段/重复/过长返回及proof篡改控制。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_string_contracts.py tests/test_string_search.py tests/test_string_core.py tests/test_oracle.py tests/test_property_contract.py tests/test_relations.py tests/test_sequences.py -q --tb=short`。旧边界轴golden、core policy/transition原有检查加入实际测试集合；来源和命令均记台账。
- [x] 记录核心源/二进制/compiler/stdx身份及契约纯数据测试结果，无真实模型/远程MCP调用。

## Task 3: V2有界String观测、Oracle观测与可信逐步链

**Files:** Create `nexus/repair/string_trace.py`（只共享编码/解码/可信代码片段，名称可在brief合理调整）, `tests/test_string_trace.py`, `tests/sdk/test_strings_sdk.py`; Modify `primitive_trace.py`, `property_trace.py`, `relation_trace.py`, `sequence_trace.py`。

**Interfaces:** primitive_trace.harness／interpret新增显式version可选参数默认1；oracle-kind仅version2允许，类NexusOracleV2+token。新prefix ORACLE_V2／PROPERTY_V2／RELATION_V2／SEQUENCE_V2／SEQUENCE_END_V2和VALUE_ERROR_V2全部纳入跨kind保留识别。String token `s:`+小写UTF-8hex，最多512hex字符；Int64/Bool canonical旧表示。输出含actual_return原typed值和原日志source坐标。序列before/after String同样编码。

- [x] RED：空串、分隔符/换行/伪Summary/保留前缀、Unicodecombining/emoji、NUL、256/257，非法/奇数/大写hex、非法UTF-8和过长编码；跨kind、重复、stderr、汇总后、missing case/token/end、错误actual前态均UNKNOWN。完整SDK检查先于业务解释。
- [x] 实现受信任编码辅助函数与名字避让，返回超限发VALUE_LIMIT，整批UNKNOWN；不能截断值。Oracle3获取actual观测后Python比较expected，不解析String断言失败文本。V1正常harness字节不变。
- [x] 真实SDK：String原样返回与混合Bool/Int64输出、函数/变量名碰撞、String状态与String上下文、首次实际偏离早停、UTF8完整边界；SDKcase/实际step/source完整，保留argv和所有原件。public/SDK malformed-fixture只用于否定控制，不能把夹具日志说成SDK输出。
- [x] 运行 `../.venv/bin/python -m pytest tests/test_string_trace.py tests/test_primitive_trace.py tests/test_property_trace.py tests/test_relation_trace.py tests/test_sequence_trace.py -q --tb=short` 及 `../.venv/bin/python -m pytest tests/sdk/test_strings_sdk.py -q --tb=short`，ExpectedPASS；保存sourcefreeze和原件hash。

## Task 4: 冻结、服务绑定、CEGIS反馈和交付全链

**Files:** Create `tests/test_string_uploads.py`, `tests/test_string_services.py`, `tests/test_string_gates.py`, `tests/sdk/test_string_loop_sdk.py`; Modify `nexus/uploads/service.py`, `rule_contract.py`, `rule_drafts.py`, `nexus/repair/exploration.py`, `property_service.py`, `relation_service.py`, `sequence_service.py`, `verification_evidence.py`, `cegis_loop.py`, `focus_service.py`, `localization.py`, `nexus/demo/deepseek.py`, only necessary workspace/delivery/archive modules.

**Interfaces:** upload确认保留原String JSON、typed样例、版本/algorithm/hash。服务依赖清单覆盖values、string_trace、新表达式/采样和nativeidentity。Oracle3 batch含token/observations，失败含actual SDK test_id、args、expected/actual规范JSON文本、expected_value/actual_return typed、source/oracle_hash；旧oracle字段和harness不改。其余服务既有report接口接新typed值，不加新的执行通道。

- [x] RED：String版本与公开示例冻结、CSRF/actor/范围/重复确认、draft JSON类型拒绝与显式应用。草案提示根据签名给新版String域/表达式，旧fixture不改成假通过。
- [x] RED：四种服务真实String报告绑定、篡改hex/log/model/公测/core/source UNKNOWN，当前FAIL/UNKNOWN阻接受/导出/下载、历史保留全部回归；同请求恢复不重复执行。模型/规则测试越权拒绝。
- [x] 实现各服务新版分支与依赖绑定，反馈不丢空串/control/String状态前缀，case/step映射保留实际id；source静态定位仅线索，不称动态证明。
- [x] 真实SDK集成自建三例：byte/rune边界规则/属性；两文件票据关系；String显式状态序列，初轮公开测试PASS而独立验证FAIL，参考修复PASS，至少一份真实更小失败，历史回归有效。
- [x] `tests/sdk/test_string_loop_sdk.py`两轮显式HTTP模型+分析夹具，真实本地SDK/native/stdioMCP，UNKNOWN不触发第二次请求；人工测试审批/导出正常200，原件改动实际下载400后恢复。禁止接真实DeepSeek/6240，夹具origin清楚。
- [x] 运行新增上传/服务/门禁及既有 `test_workbench_race.py`、`test_user_review.py`、交付/归档/DeepSeek直接相关测试；每个brief先rg确定真实文件名和最终命令，运行终态后记录，不凭测试数量猜成功。

## Task 5: String导入、草案提示和精确值展示

**Files:** Create `tests/strings-ui.test.cjs`, `tests/test_string_web.py`; Modify `nexus/demo/static/upload.js`, `properties.js`, `relations.js`, `sequences.js`, `feedback.js`, `localization.js`, `nexus/web/property_view.py`, necessary template/help text, corresponding existing UI tests.

**Interfaces:** primitive_text新增String canonical JSON text（带引号和控制字符转义），内部typed值不改，vector涵盖String。UploadUI String默认args=""，expected仍null待用户核对；导入/epoch/confirm只读复用；无需新layout或依赖。

- [x] Node/Flask RED：空串可见与null区别、引号/control/伪HTML textContent安全、Unicode/Int64并列不丢精度、参数类型默认正确，JSON导入后旧响应不能覆盖，草案不静默替换手工验证契约；当前摘要/详情冲突与失败刷新禁接受但可合法拒绝。
- [x] 实现必要UI范围说明和canonical显示，保留浅色样式，未配置验证项不显示空面板。不加入无关解释性徽标／布局改造，不假装所有字符串语法均支持。
- [x] 运行 `node --test tests/*.test.cjs` 与 `../.venv/bin/python -m pytest tests/test_string_web.py tests/test_sequence_web.py tests/test_relation_web.py tests/test_property_web.py tests/test_upload_routes.py tests/test_workbench_race.py -q --tb=short`。
- [x] 显式禁执行的隔离浏览器夹具实际导入String源码/例子/模型、确认/只读回载，核对SDK FAIL/PASS与篡改UNKNOWN、quoted empty/Unicode值。保存真实JPEG/AX及来源审计；不调用真实模型/分析，不改主站数据。

## Task 6: 一次审阅、最终验收、封存和激活

**Files:** Create `docs/demo/next-phase-4A-verification.md`, `docs/demo/validation/next-phase-4A/`; Update本计划、总目标。

- [x] 一次fresh全阶段审阅，检查本spec与accepted3C基线完整diff；Critical/Important集中真实RED→GREEN，Minor台账暂缓，不二次审阅。既有dirtytree不清理、不Git变更。
- [x] 冻结准确source/helper/core身份后 `../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check` 全部通过；执行期间不并行编辑冻结源。
- [x] 封存所有自建真实SDK成功/失败/缩减/累计回归、HTTP模型与分析夹具原件、审批/交付否定控制。禁止SDK/nativeIPC/网络的独立子进程重放；旧2/3A/3B/3C均按各自源码/core复验。不改原件和报告以便通过。
- [x] 有限配置凭据/路径/嵌套ZIP检查，排除.env/会话/真实用户上传/SDK安装包，保留并明确说明已检查工具链路径，不能假称全脱敏。
- [x] 独立4A快照就绪，主站当前任务/模型/工具/分析无在途时切换，原数据/session保持；HTTP资产hash和任务数量复核。只标4A验收，4B/4C/4D/5未完成；重读目标推进4B，预算仍0。

## 计划审查

共享值/解析公开测试、版本模型/搜索/native、可信观测、服务/门禁、页面、最终封存分别独立可验证。接口由前任务提供，后续不猜typed类型和版本；包含Stringoracle不依赖失败消息、全部保留prefix、有限预检与序列实际可达。新阶段不复用已耗尽付费额度或覆盖已激活3C快照。
