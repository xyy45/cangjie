# CangSight-Nexus 源码级开发计划符合性审计

审计日期：2026-10-17（Asia/Shanghai）。被审版本：`f7d6720d60c2277e8f2916dcae87a4ecafd0849a`。工程：`/Users/jadya/Documents/CangSight-Workspace/02-开发工程/CangSight-Nexus`。

## 1. 审计结论与方法

**真实 MCP、仓颉原生 Policy、真实 cjpm、真实 DeepSeek 首轮修复、审阅接受及同版本导出主链有源码和原始记录支持。不能据此判定 Task 1～10 每个细项全部完成。** 九工具全部注册，但成功搜索缺少动态证据；部分防护测试存在断言过弱或用例缺口；源码 ZIP 的默认回归存在 Git 元数据依赖；独立成员复现和赛事提交仍待外部结果。

本次实际读取实现、所有测试文件、历史 RED/GREEN 输出、SDK 原始日志、SQLite 索引对应的 JSON 记录、模型原始请求/响应、归档 manifest 和界面截图。SQLite 用 `mode=ro` 打开，没有调用会建表/写日志的 RunStore。没有启动修复、重跑 pytest、调用付费 API、调用写工具或修改应用代码。唯一新增文件为本报告。因此所有测试通过数均为**历史原始证据复核**，不是本轮重新运行的结果；当前额度、网络和SDK瞬时健康未重新实测。

基准是用户指定附件；已逐字节确认附件与 `docs/delivery-plan.md` 相同。没有以 `delivery-report.md` 或 `test-report.md` 的结论代替实现核查。当前业务源码、Policy、fixtures、锁文件和 pyproject 与 LIVE 前提交 `89e8782` 无差异，之后主要变化为文档、复演脚本和证据。历史输出无签名，作为本地开发证据，不能当独立第三方证明。

状态含义：PASS＝实现与适当证据支持该项；PARTIAL＝实现或验证仅覆盖部分；FAIL＝源码/工件直接与该项冲突；NOT_VERIFIED＝没有足够动态证据。可选和外部事项另外标明，不折算成技术成功。

## 2. 原始证据索引

以下路径相对正式工程根，表中的 E 编号指向本节实际读取的证据。

| 编号 | 原始证据 | 实际内容及证据边界 |
| --- | --- | --- |
| E1 | `docs/evidence/task-01-red.txt`、`task-01-green.txt`、`task-01-sdk-red.txt`、`task-01-sdk-green.txt`；`order-normal-test_normal_and_defective_orde0-pytest-67.txt`、`order-defective-test_normal_and_defective_orde0-pytest-67.txt` | 探针2 passed；早期真实SDK失败/修正记录；正常11测试通过、缺陷zeroQuantity失败。非仅退出码判断。 |
| E2 | `docs/evidence/task-02-red.txt`、`task-02-green.txt` | 缺实现失败及7 passed。 |
| E3 | `docs/evidence/task-03-red.txt`、`task-03-green.txt`、`task-04-green.txt`、`task-04-regression.txt` | MCP/导入阶段5 passed；候选4 passed；回归18 passed、1 deselected。不能由聚合数量推导未写出的搜索成功用例。 |
| E4 | `docs/evidence/task-05-red.txt`、`task-05-compile.txt`、`task-05-green.txt`、`fault-injection.txt` | 原生仓颉Policy实际编译输出（3条Console弃用警告）；7 passed；故障注入5 passed。 |
| E5 | `docs/evidence/task-06-green.txt`、`final-sdk.txt`、`tests/data/cjpm-1.0.5-pass.txt`、`cjpm-1.0.5-fail.txt` | 阶段5 passed；最终SDK+full journey为4 passed/23.70秒；真实SDK格式样本。 |
| E6 | `docs/evidence/task-07-green.txt`、`continuation-reliable-failure-red.txt`、`continuation-reliable-failure-green.txt`、`continuation-cancellation-red.txt`、`continuation-cancellation-green.txt` | 初始循环4 passed；后续可靠失败10 passed、取消竞态13 passed（对应当时组合用例数）。分支测试使用替身。 |
| E7 | `docs/evidence/task-07-live-configured.txt`及 `.runtime/live/f48e2ddc7dce4ec2bc4e9f4ff5d96ed5/` | LIVE 1 passed/9.16秒；已进一步检查数据库、原始模型响应、四次实际检查、接受与导出，不只读取摘要JSON。 |
| E8 | `docs/evidence/task-08-red.txt`、`task-08-green.txt`、`task-09-green.txt`、`task-10-handwritten-journey.txt` | 导出5 passed；页面组合11 passed；完整手写候选SDK链1 passed/8.40秒。手写链不是LIVE模型证明。 |
| E9 | `docs/evidence/final-offline.txt`、`final-sdk.txt` | 53 passed、5 deselected/8.64秒；SDK层4 passed/23.70秒。LIVE另测，不把deselected当通过。 |
| E10 | `docs/evidence/task-10-live-rehearsals.txt`、`task-10-live-rehearsals.json`及 `.runtime/rehearsals/9a04ac31c97d4e55abc56178e845d25b/{1,2,3}/` | 三次实际模型首候选交付，8.981/8.934/8.456秒；本次逐一验证原始模型响应、两个候选检查日志和导出ZIP内容摘要。 |
| E11 | `.runtime/workbench/runs.sqlite3`和对应records；`docs/evidence/workbench-live-delivered.jpg`、`workbench-live-policy.jpg`、`workbench-narrow-final.png`、`recorded-browser-download.json` | 两次真实页面模型任务；原生D拒绝事件；桌面成功和窄屏布局证据。窄屏截图是历史缺配置BLOCKED状态，不是窄屏LIVE成功证明。 |
| E12 | `docs/evidence/original-source-sha256.json`与原目录实际453文件 | 本次重新逐文件SHA256比较：453/453一致，无新增。原目录为 `../../01-原始代码/Sympas-Nexus-GitHub`。证明相对该开工快照未改，不证明上游GitHub版本身份。 |
| E13 | `.runtime/releases/release-manifest.json`、实际source-f7d6720 ZIP、修复ZIP、mp4；`docs/evidence/live-video.json` | 三工件实际摘要与manifest一致；源码ZIP无.git；视频227帧、25.796秒、无音轨、长等待缩短。视频不是未剪辑连续录屏。 |
| E14 | `docs/evidence/optional-analysis-selection.json`、`task-10-sdk-exit9.txt`、`sdk-exit9-system-log.txt` | 可选分析服务不可达，未宣称语义支持；历史SDK exit9失败保留，不能被最新绿色结果抹除。 |

E7 的具体原始锚点（相对该 LIVE 根）：

- `records/4fcbd41e9a714ae6af0f52f992a2cf0d.request.json` 与 `.response.json`：实际响应模型 `deepseek-flash`，finish_reason=stop，prompt 2961/completion 137/total 3098。提案修改quantity.cj为 `quantity >= 1 && quantity <= 1000`。
- 基线build日志 `records/a9f4124f4b104f4aa7c74ff949e6b9dd.log`：真实编译命令与 `cjpm build success`；基线test日志 `records/52517a60da874a328a9755804d793413.log`：11总、10通过、1失败，zeroQuantity，exit1。
- 候选 `c_e94cf28ae55a4c7ca7af3d08a9edf49f`：build日志 `records/2a6b24057e094f49b4cf000f8d1b853b.log`，test日志 `records/1bf9d12285714b8693285ba95cdb5eb2.log`；两者exit0，test为11通过、0失败/跳过/错误。
- `records/c13f0f5df972428db95d6a755bb6eb3a.json` 接受记录绑定同候选、tree `6c7243dd2726411ec419891d926919033b2fcd472b96d3708ddbbd9e25b96584` 和check_set_hash。对应 `exports/f302c29b1ca9434f902a52f93a4f6138.zip` 七项条目，内容SHA与manifest逐项一致。
- 原生Policy事件 `9643a8b4...` / `764fdd43...` / `8895062c...` / `59061069...` / `5c1a40d6...` 分别记录diagnose/apply/build/test/export的Allow。完整文件名保留在records中。

## 3. Task 1～10逐项核查

每任务的序号对应原计划五个checkbox。源码栏写明具体关键函数；“同上”仅引用本任务前行，不借交付报告作证明。

### Task 1：环境与自产基线 — PASS（本机支持范围）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.缺SDK不假PASS；正常/边界回归 | `scripts/doctor.py:inspect_environment`；`fixtures/order-demo/src/order_test.cj:OrderTests` | `tests/test_doctor.py:test_doctor_missing_sdk_is_unavailable_not_pass`；`tests/sdk/test_order_demo.py:test_normal_and_defective_order_demo` | E1；11项含3×100、2×100、1×0、0/-1/1000/1001数量、价格上下界、7×23 | PASS |
| 2.先RED | 探针实施前的缺模块 | tests/test_doctor.py | task-01-red：1 error；Git有T1提交 | PASS |
| 3.真实版本/build/test，配置只探存在 | inspect_environment；`scripts/install_runtime.py:main`；`nexus/adapters/cangjie/sdk.py:sdk_environment` | SDK测试run_sdk | E1、E7；Compiler/Package Manager1.0.5，Python3.12.14、ARM64；doctor本身不调用模型 | PASS |
| 4.正常通过、缺陷断言失败 | 三个production.cj与冻结order_test.cj | 同SDK测试 | E1、E7基线FAIL与候选PASS原始日志 | PASS |
| 5.工具取舍/版本记录/提交 | install_runtime固定SDK/stdx1.0.5.1 URL+SHA；requirements.lock | doctor与SDK测试 | E14明确排除不可达分析；提交914af7e | PASS |

限制：doctor的available只证明可执行版本探针，不证明系统SDK链接兼容；真实构建证据才证明本机可用。未执行可选远端工具的仓颉三样例筛选，因服务不可达而排除，不能宣称其支持仓颉。

### Task 2：契约和记录 — PARTIAL（测试强度不足，不是已发现契约失效）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.权限字段拒绝、重载轮数 | `nexus/contracts.py:Record,CandidateProposal,ModelCall`；`nexus/store.py:get_task,update_task` | tests/test_contracts.py:test_proposal_cannot_set_verified_or_approval；tests/test_store.py:test_task_reloads_without_resetting_attempts | E2；源码extra=forbid/strict=True；但权限字段测试同时传edits=[]，可因空列表而失败，未隔离验证每个字段 | PARTIAL |
| 2.RED | 同上 | tests/test_contracts.py、test_store.py | task-02-red：2 errors | PASS |
| 3.六类记录/日志/完整摘要 | contracts六类模型；store.append_record；source_manifest/tree_hash | test_hash_covers_tests_and_config_but_not_build_products；test_records_are_append_only_and_secrets_not_logged | E2、E7实有model/candidate/check/tool/acceptance/task；摘要含测试配置，排除target/.git | PASS |
| 4.origin/外任务/编号/密钥 | append_record字段模型、owner校验、UNIQUE约束、reject_secrets | test_wrong_origin_rejected；test_foreign_reference_and_duplicate_attempt_rejected | E2；E7模型可信字段由Provider写，不由提案写 | PASS |
| 5.提交/单数据库 | RunStore SQLite+JSON | store测试 | 7f63029；未引入第二数据库系统 | PASS |

“只增”是应用API通过open('x')和唯一键保证，不是文件系统不可篡改保证。日志拒绝敏感字段名，不是任意文本的通用密钥识别器。ToolCall的candidate_id为可选且server当前未填，候选仍可从result_ref追溯，查询便利性弱于计划字段意图。

### Task 3：真实MCP与读取 — PARTIAL

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.独立协议/构建根/路径 | `nexus/mcp/client.py:ToolClient.__aenter__,list_tools,call_tool`；`cang_sight_server/server.py:create_server,main`；WorkspaceStore.import_project/safe_file | tests/integration/test_mcp_protocol.py:test_real_stdio_lists_and_reads_fixture；tests/test_intake.py三用例 | E3；独立stdio和原文相等断言；E7持久读取结果 | PASS |
| 2.RED | 同上 | 上述测试 | task-03-red：2 errors | PASS |
| 3.官方initialize/list/call/close，list/read/search注册 | stdio_client+ClientSession.initialize；Server+stdio_server.run；workspace.search | 协议测试仅断言前三工具是子集 | 源码九路由；E3证明list/read；搜索只有空query拒绝用例，无有效query成功证据 | PARTIAL |
| 4.未知写断连不重放，参数错误/stdout | ToolClient.call_tool将写断连记IN_DOUBT，无重试；server仅TextContent协议 | test_inflight_write_disconnect_is_not_replayed；crash_server.py实际执行marker后断连 | E3、E9；marker一次；普通日志不写stdout | PASS |
| 5.提交/不以handler代协议 | client启动`python -m cang_sight_server.server` | 真实会话测试 | 22c35f9，官方mcp==1.26.0锁定 | PASS |

### Task 4：候选和diff — PARTIAL（主行为通过，细项覆盖有缺口）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.全有或全无/基线不变/重复不增轮 | `nexus/execution/workspace.py:apply_candidate,_diff,diff` | tests/test_workspace.py三个命名用例 | E3；第二文件before_hash错误无candidate发布 | PASS |
| 2.RED | 同上 | workspace+candidate工具测试 | task-04-red：3 failed、1 passed | PASS |
| 3.同基线staging、1～3已有源码、拒绝测试配置链接越界 | apply_candidate；contracts.Edit/editable_path；import_project/source_manifest | test_proposal_requires_existing_cj_paths_and_bounded_edits；intake/workspace测试 | E3、E7实际候选；字段限制、allowlist和before_hash三层 | PASS |
| 4.实际diff/同名不同目录/gate未就绪拒绝 | _diff使用相对路径；server.gated_apply | test_native_gate_allows_real_mcp_candidate断言真实diff；test_writes_denied_until_native_gate_ready | E3；无显式同名不同目录测试；“gate未就绪”测试仅空参数被schema拒绝，不能证明合法请求遇死Policy拒绝（T5另有gate层测试） | PARTIAL |
| 5.提交/物化不假称成功 | CandidateRecord和task状态分离 | workspace/repair测试 | 9617fa4；真实build/test在后续执行 | PASS |

原子性覆盖单次多文件发布和异常清理，不是跨SQLite与文件系统的崩溃恢复事务；计划已排除完整恢复。

### Task 5：原生Policy与gate — PARTIAL（核心控制已证实，限额测试不全）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.Deny零执行/进程不可用/参数绑定 | `nexus/policy/gate.py:gate_and_execute`；`client.py:PolicyClient.decide` | tests/integration/test_policy_gate.py:test_deny_never_calls_action、test_dead_policy_blocks_materialization、test_changed_arguments_rejected | E4；E11原生PROTECTED_PATH事件及截图 | PASS |
| 2.RED | 同上 | policy_gate测试 | task-05-red：1 error | PASS |
| 3.原生编译/三态/64KiB/2秒/协议stdout | `cangjie/policy/src/main.cj:decide,main`；scripts/build_policy.py | test_native_allow_and_need_approval；timeout用例 | E4编译输出；实际二进制IPC；64KiB源码限制存在但无边界测试；2秒分别约束readline及process.wait，并非整个调用严格总计2秒 | PARTIAL |
| 4.超时/坏JSON/错request ID fail closed，执行/导出同gate | PolicyClient.decide；server.gated_apply/gated_check/export_route | test_invalid_json_wrong_request_id_and_timeout_deny；SDK/full journey | E4、E5、E7全部有原生Allow事件；D拒绝未调用action | PASS |
| 5.提交，不冒充OS隔离 | Policy规则与runner分离 | runner测试 | 46814a1；原生Policy控制apply/build/test/diagnose/export，四个只读工具不经过Policy | PASS |

Policy使用通用src/*.cj规则，具体任务allowlist仍由Python物化器校验；这是组合控制，不能宣称Policy本身理解所有业务权限。NeedApproval是原生策略输出，最终接受记录另由Delivery校验。对错误request ID的单个样例也缺arguments_hash，不能独立证明只因request ID而拒绝，但源码同时明确验证二者。

### Task 6：真实执行和诊断 — PASS（有历史环境失败风险）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.零/跳过不PASS、build失败不test、源码失效 | `report_parser.py:parse_test_report`；`verifier.py:identity,_run` | tests/test_report_parser.py全部4用例；tests/sdk/test_verification_tools.py | E5；ERROR/不完整/矛盾footer为UNKNOWN | PASS |
| 2.RED | 同上 | parser+SDK测试 | task-06-red：2 errors | PASS |
| 3.固定argv/最小环境/90秒/2MiB/进程组 | `nexus/execution/runner.py:run_command,sandbox_profile`；sdk_environment | tests/test_runner.py两个用例 | E5、E9；timeout/输出上限使用测试cjpm替身验证runner机制，不作为真实SDK证据；真实SDK另有E7 | PASS |
| 4.真实MCP apply→build→test；坏环境UNKNOWN | verifier._run；server.gated_check | test_real_mcp_apply_build_test；test_build_fail_test_not_run_and_changed_source_invalidates_check | E5、E7四个真实检查日志；argv确为cjpm build -V/cjpm test | PASS |
| 5.提交/可选分析缺失仍诊断 | `nexus/mcp/tools/project.py:diagnose` | SDK/full journey测试 | 2d8614e；analysis=[]与明确未启用限制，非假分析发现 | PASS |

缓存绑定完整tree、test_plan、cjc/cjpm文件摘要、runner/verifier/parser源码摘要；test只复用同身份build PASS。runner允许SDK所需回环TCP及监听，不是完全网络隔离；已限制用户文件读取、外部写和外网连接。SDK exit9曾导致UNKNOWN/失败，后续成功不能保证现场不再出现。该历史问题不是当前已证实持续阻断。

### Task 7：Provider和CEGIS — PASS（首候选LIVE；多轮只做确定性验证）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.反馈/首轮停/三候选/迟到取消 | `nexus/repair/cegis_loop.py:RepairLoop.run,phase,feedback_identity` | tests/test_repair_loop.py七用例 | E6、E9；FAIL诊断进入下一prompt，三候选后UNREPAIRED，CAS保持CANCELLED | PASS |
| 2.RED | 同上 | repair_loop测试 | task-07-red；后续两次RED/GREEN | PASS |
| 3.阶段上下文/480秒/三候选/20k/不重放 | `nexus/llm/provider.py:ModelProvider.propose`；RepairLoop.run；WorkspaceStore.apply_candidate | loop、provider_config测试 | 源码asyncio.timeout(480)、range(...,4)、服务端预算、max_tokens=20000、完整stop响应校验；E7原始请求/响应 | PASS |
| 4.单测与独立LIVE；缺配置明确BLOCKED | provider.propose在缺配置时抛ProviderUnavailable；控制层处理 | tests/live/test_repair_live.py:test_live_main_case | E7原始模型+MCP+检查；live pytest本身只断言REVIEW_PENDING及LIVE SUCCEEDED，额外原始检查补强；历史task-07-live.txt缺配置失败不是成功 | PASS |
| 5.提交/只可靠FAIL反馈，环境故障停 | run对UNKNOWN/NOT_RUN和传输失败停；feedback_identity去ID/时间 | test_not_run_test_blocks_without_requesting_another_candidate；parser错误测试 | 275b80a及89e8782；E6/E7 | PASS |

必须保留的边界：测试名`test_real_fail_feedback_enters_next_prompt`里的Client/Provider是明确替身，不是原生cjpm多轮反馈证据；计划允许确定性分支测试，三次LIVE均首候选成功，不要求强造多轮。重复候选/相同反馈停止代码存在，但相同反馈连续停止的端到端用例不足，当前仅有归一化函数测试。20k上限、HTTP错误/截断和480秒停止也缺独立完整边界测试，不能把源码审阅说成所有故障场景已实测。模型目前返回edits，由控制层预读全部.cj，不提供模型自由选择读取工具的行动接口，是比设计描述更固定的上下文采集方式；主案例要求仍实现。

### Task 8：接受和导出 — PASS

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.改变/并发/包版本/失败对账 | `nexus/execution/delivery.py:accept,acceptance,export,_package,verify_archive` | tests/test_delivery.py七用例 | E8、E9；单元使用明确标注synthetic的check记录，不算真实验证 | PASS |
| 2.RED | 同上 | delivery测试 | task-08-red：1 error | PASS |
| 3.事务占用/唯一exportID/临时包/30分钟 | export BEGIN IMMEDIATE；check_set_hash绑定当前tree/plan/log；临时ZIP核验后replace | concurrent_export/failure_reconcile测试 | E8、E7实际接受记录及manifest | PASS |
| 4.未通过/过期/改变/重复参数/无私有内容 | check_set_hash、acceptance、verify_archive | expired_and_changed_logs；selection_change；changed_archive等 | E8、E9、E7；六次持久MCP export成功记录；包只含候选manifest内文件 | PASS |
| 5.提交/独立工程，不覆原件 | _package只读candidate，写exports；原始文件对比 | full_journey逐文件比对 | 3757464；E7、E12 | PASS |

接受只在用户Web/CLI，不在九工具列表中。默认30分钟过期还影响下载路由（会重新调用acceptance）；历史下载链接不是永久备援，应使用已归档技术包或在有效期内下载。这是演示操作约束。数据文件仍为本机可信控制面，不能抵御具有宿主写权限的人伪造数据库/日志。

### Task 9：页面 — PARTIAL（主链有证据，全部交互边界未覆盖）

| 项 | 对应源码与关键函数 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.刷新不重放/开始幂等/用户接受/可选不阻断 | `nexus/web/app.py:create_app,start,task,accept,export` | tests/test_web.py四个核心用例 | E8、E9；刷新零模型调用、相同start key同任务；恶意Origin拒绝 | PASS |
| 2.RED | 同上 | web测试 | task-09-red：1 error | PASS |
| 3.单页/本机/CSRF/转义/既有循环 | app.local_guard；templates/workbench.html；static/workbench.js:api,refresh | test_accept_requires_user_route；full journey | E11；主机127.0.0.1，源码diff/日志通过textContent显示，无第二套执行器 | PASS |
| 4.真实A+D/桌面窄屏/折叠与按钮 | Web路由、JS、CSS media max-width800px | test_native_policy_probe_denies_and_preserves_frozen_files；SDK full journey | E11成功桌面+原生D；窄屏是BLOCKED历史截图，足以证明布局堆叠，但没有窄屏成功全链操作证据 | PARTIAL |
| 5.提交/不加第二前端 | Flask/Jinja+单JS，无React构建 | web/full journey | bffa94e、1cc7c0b；E8、E11 | PASS |

JS多个refresh请求若迟到，未检查回包taskId是否仍等于当前taskId，也没有取消旧请求/忽略旧请求的测试。当前UI限制运行中开始新任务，但终态刷新与下一任务开始交叠时，旧结果覆盖新显示的风险不能排除；计划Review Focus要求的迟到页面结果保护尚未充分验证。后端接受仍校验当前选择，未发现可绕过验证导出。

### Task 10：复演与材料 — PARTIAL（含一项交付复现缺陷）

| 项 | 对应源码/工件与关键入口 | 对应测试文件/断言 | 实际证据 | 判定 |
| --- | --- | --- | --- | --- |
| 1.包对应检查版/多输入 | full journey；fixtures/order-demo/src/order_test.cj | tests/integration/test_full_journey.py:test_full_journey_matches_exported_candidate | E8、E5；逐文件比较下载工程，不只看成功状态；11种输入排除简单固定返回值 | PASS |
| 2.先验证遗漏会RED | 同测试 | 同上 | 有绿色原始输出，无专属Task10 RED文件或故障变更前失败记录可归因 | NOT_VERIFIED |
| 3.A三次干净真实复演 | `scripts/rehearse.py:rehearse`，新root/import baseline/真实RepairLoop/MCP export | LIVE test+SDK full journey | E10逐一对原始模型/日志/ZIP复核；首候选三次成功，不预设两轮 | PASS |
| 4a.离线/SDK/LIVE分层回归 | pyproject markers；上述测试入口 | tests所有层级 | E9、E7，本机Git工作区实际通过；本轮未重跑 | PASS |
| 4b.源码ZIP按runbook可通过默认回归 | 源码ZIP不含.git；`tests/test_provider_config.py:test_project_dotenv_is_git_ignored`无条件调用git | 该测试不支持无.git源码发布目录 | 本次检查ZIP确实含该测试且无.git；无repo的git check-ignore实测exit128。见F1 | FAIL |
| 4c.另一成员干净环境启动/下载 | docs/runbook.md、independent-reproduction.md为指南与空回执 | 应由外部成员执行 | 尚无执行人/实际日志/签字回执，本机复演不能代替 | NOT_VERIFIED（外部PENDING） |
| 5a.版本/摘要/视频/范围/第三方AI说明 | source-f7d6720 ZIP、mp4、release-manifest；docs/demo-script.md、third-party-and-ai.md | 工件摘要与源码比对 | E13实际哈希一致，业务源码与录制时版本一致；视频为真实帧剪辑 | PASS |
| 5b.10/22中午冻结、10/23提前提交/回下载 | 团队/平台操作 | 外部验收 | 今天10/17，不能倒填未来冻结；平台与准确时刻未知；暂无平台提交和回下载证据 | NOT_VERIFIED（外部PENDING） |

## 4. 九个MCP工具专项核对

`create_server`的routes合并后恰为以下九项，`@server.list_tools`从同一routes生成schema，`@server.call_tool`从同一routes调度。Client通过官方会话真实RPC调用。**注册完整PASS；“九项全部成功实调”整体只能PARTIAL。**

本次读取所有现存 `.runtime/**/runs.sqlite3` 的tool_call及result_ref，成功数如下。这不包含已清理的pytest临时目录；不能因运行根缺记录就断定测试未曾执行。只读工具在测试中不传task_id时不会持久化。

| 工具 | 源码路由/处理函数 | 测试与实际调用证据 | 判定 |
| --- | --- | --- | --- |
| workspace.list_files | routes→workspace.list_files | LIVE等持久成功8次 | PASS |
| workspace.read_file | routes→workspace.read_file | 独立协议测试原文比较；持久成功32次 | PASS |
| workspace.search | routes→workspace.search | 空query拒绝有测试；没有有效查询成功用例/持久成功记录，本轮只读审计不新增调用 | NOT_VERIFIED（注册PASS） |
| project.diagnose | diagnose_route→gated_check→diagnose | 持久成功8次；真实基线build/test日志 | PASS |
| candidate.apply | gated_apply→gate→apply_candidate | 持久成功6次；实际候选记录 | PASS |
| candidate.diff | candidate_diff→WorkspaceStore.diff | test_native_gate_allows_real_mcp_candidate成功调用并断言+//candidate；task-04-green/最终离线聚合通过；无保留的独立tool_call原始响应 | PASS（历史集成测试级证据） |
| candidate.build | build_route→gated_check→verifier.build | 持久成功6次；实际编译日志 | PASS |
| candidate.test | test_route→gated_check→verifier.test | 持久成功6次；实际11项测试日志 | PASS |
| candidate.export | export_route→gate→delivery.export | 持久成功6次；已核验归档 | PASS |

服务端普通日志不写stdout，模型没有accept工具或shell工具。构建/测试FAIL作为operation_status OK的有效检查结果返回，控制器据state决定，不混成传输失败。只读workspace工具和diff没有仓颉gate，不应描述为“九工具全部经过Policy”。计划要求的危险写入和执行路由均经过gate。

## 5. 问题与证据不足清单

### F1：源码ZIP默认回归依赖Git元数据 — FAIL，影响独立复现验收

定位：`tests/test_provider_config.py:42–49`；源码包与 `docs/runbook.md` 的默认pytest入口。

测试无条件执行`git check-ignore --no-index .env`并要求exit0，但`git archive`交付源码无`.git`。在干净、无父级Git仓库的目录中，该命令exit128，断言失败。`git ls-files`非零也不能证明“文件未跟踪”，有可能只是“没有仓库”。本次对指定不存在的git-dir执行同一check-ignore，只读得到exit128，结合ZIP条目证明环境冲突；没有重跑解压工程完整pytest，故完整失败计数不宣称已实测。

上一轮只修正独立指南正文，测试本身仍依赖Git。建议后续在允许改代码时，让发布目录检查`.gitignore`规则/文件包含关系，Git存在时再检查索引，或者明确复现前初始化Git并保证不跟踪.env。本轮不修复。该问题不阻断现有Git开发机A/D演示，但会阻断“按源码ZIP说明默认回归全绿”的验收。

### F2：有效搜索成功路径缺动态证据 — NOT_VERIFIED

定位：`nexus/mcp/tools/workspace.py:search`；`tests/integration/test_mcp_protocol.py`。

实现是有界字面搜索，最多100条，实际注册；现有协议测试只调用空query，正确被schema拒绝。没有非空查询命中/不命中/截断的成功测试；实际修复循环预读文件，不用search。不能把“九工具注册”写成“九工具均成功调用”。不影响已验证A主链。

### F3：若干测试断言未隔离目标条件 — PARTIAL

- 权限字段拒绝测试同时提交非法空edits，可能为错误原因绿灯。
- “gate未就绪拒绝写”集成用例提交空参数，仅证明schema拒绝；真实死Policy的gate级测试另有覆盖，缺少合法MCP提案+死Policy进程的端到端组合。
- Policy错request_id样例同时缺arguments_hash，不单独隔离两种绑定错误。
- 未见同名不同目录、多轮相同反馈提前停止、64KiB边界、HTTP截断/错误及总480秒的完整集成故障用例；有实现不等于每项已动态验证。

这些是覆盖不足，不能据此声称当前实现已发生权限旁路或预算超限。

### F4：页面旧响应保护未充分实现/验证 — PARTIAL

定位：`nexus/web/static/workbench.js:refresh`。异步响应回写DOM前未校验请求所对应的taskId仍是当前任务，也没有对迟到的candidate回包做代次保护。已有取消CAS测试保护后端任务，不等同于保护页面异步显示。未执行浏览器竞态复现，因此不下“现场必现”结论。后端check_set和接受选择校验仍有效，风险主要为展示混淆。

### F5：环境、下载和历史资料的演示限制

- 固定macOS ARM64+Cangjie1.0.5+stdx1.0.5.1+macOS15.4开发SDK。其他系统/默认SDK26.5未验证可用。历史真实exit9需要保留风险说明；本轮未重新执行SDK。
- 接受和下载会检查30分钟有效期；不要把很久以前的页面下载链接作为永久交付入口。材料包中的归档不受该HTTP接受时效影响。
- 本轮不请求模型，当前余额、模型权限和网络连通性NOT_VERIFIED；历史HTTP200及六次成功模型调用不代表现在永远可用。
- `environment-current.json`是早期缺配置时的探针，名字不代表现在实时状态；不能据其api_key_present=false否定后续LIVE原始证据。
- pyproject未直接声明python-dotenv，但requirements.lock固定了该包，mcp依赖链亦包含设置库；按锁文件安装的既定入口有依据，单独包安装的完整性未独立验证。

## 6. Mock、硬编码和伪造成功专项

**未发现产品主链用Mock PASS、固定修复补丁或预置模型响应冒充真实成功的证据。** 本结论来自以下交叉核对，不是搜索关键字后直接保证：

1. Provider实际httpx POST，Authorization只在请求头构造；raw response保存服务模型ID、usage、finish_reason和结构化候选。没有从正常fixture复制参考答案的产品代码。
2. RepairLoop仅从真实检查state判断成功；verifier从真实子进程输出解析；模型提案schema无verified/approval/origin可信字段。
3. 两种实际模型解法出现于证据：E7为`>=1`，录制页面为`>0`，两者有独立候选、检查和导出摘要。相同业务答案不证明硬编码，亦不能用不同答案本身证明真实性，仍以请求/响应和执行链为依据。
4. 单测明确存在Client/Provider替身、synthetic PASS日志、runner假cjpm和手写`.replace`修复。这些只在tests或明确手写SDK集成测试中；它们证明状态机/约束，不用于真实模型成功计数。LIVE测试及rehearse默认连接真实Provider/ToolClient，没有注入这些替身。
5. `.runtime`保留的六次SUCCEEDED模型记录分别来自显式LIVE一次、三次rehearsal、页面两次。检查/工具记录相互对应；三次rehearsal归档和原始候选日志本轮重核通过。

本地日志没有远程签名或不可篡改存储，无法数学证明不存在宿主人工伪造；计划也不要求该能力。可信结论应限定为“当前源码与现存原始证据一致，未发现伪造路径”，而不是不可伪造保证。

## 7. 必须、可选、外部事项

| 类别 | 当前结论 |
| --- | --- |
| 必须：真实MCP/SDK、A修复、Policy D、用户审阅同版导出、原工程不变 | 有源码+测试+原始运行证据支持；A/D受控本机主链可演示 |
| 必须：九工具注册及可用、边界测试、交付复现 | 九注册完整；search成功未验证，部分测试覆盖不足；源码ZIP默认回归有F1缺陷，应在独立验收前处理 |
| 可选：B类型/接口、C跨模块、课题组仓颉语义分析 | 未实现/未准入；按计划不阻断A+D版本；不能宣称已支持 |
| 明确不做：54工具、SMT、多Agent、宏增强、云部署、Docker、签名链、通用恢复、新前端 | 当前未扩展，符合范围限制 |
| 外部必须：另一团队成员干净配置复现 | NOT_VERIFIED / PENDING；本机三次复演不能替代 |
| 外部比赛事项：平台/准确时刻、10/22冻结安排、10/23提前提交和回下载 | NOT_VERIFIED / PENDING。仅截止日期2026-10-23已知，不能自行填写具体时刻或倒填未来操作 |

## 8. 对比赛演示的判断与后续优先级

在已验证的本机环境、有效API配置和接受有效期内，**未发现已证实持续阻断A+D演示的主链源码故障**。真实修复、11项检查、审阅导出和D拒绝均有原始证据。但“无技术问题”和“所有计划项已验收”均不成立。

后续优先处理F1源码包回归问题；补有效search协议测试和权限字段隔离断言，再验证页面迟到回包保护。现场演示前应按既定操作说明确认SDK和API当前可用；历史exit9仍是环境风险。最后由另一成员从干净发布包真实复现，队长确认平台和具体截止时刻并完成正式提交回验。

本轮只新增此报告，不修改源码/测试/交付包、不重新提交Git、不将原blocked开发目标改成完成。报告是对冻结版本的后续审计，现有源码ZIP和技术包不会自动包含它。
