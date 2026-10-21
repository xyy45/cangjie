# V1.1 增量开发进度与验收账本

2026-10-17。正式工程仍为现有 CangSight-Nexus；实施前基线7e29bd5，未重建/覆盖工程。用户指定的两个文档原文复制在本目录；其中关于另一主机预览缺环境的事实不当作当前本机状态。旧源码ZIP、技术包和LIVE证据保持历史版本，不将正在开发的V1.1冒充可交付完成版。

## 执行顺序

1. R0：固定基线、只读核查Sympas参考、记录真实复用/未确认项。
2. R1：需求/版本/验证计划契约与冻结服务；完整失败反馈与上下文预算。
3. R2：任务绑定需求和计划、版本化MCP/原生Policy、目标/回归投影；保持九工具和真实SDK。
4. R3：用户拒绝/取消、接受身份与动作绑定、完整证据归档、事件与启动中断核查。
5. R4：预检、需求确认页、历史与候选切换、审阅/拒绝；继续验证迟到响应保护。
6. R5：完整回归和新版本实际A/D；付费LIVE需要先说明原因并取得授权。外部独立成员验收与比赛提交另保留PENDING。

## 当前实现

| 模块/AC | 状态 | 实际证据与待做 |
| --- | --- | --- |
| R0 / M1 | 已检查；集成未确认 | m1-reference-inspection.json及m1-reuse-review.md；原参考453文件不变、无Git元数据，plugin声明1.0.0/MIT但无LICENSE文本；没有直接源码复用或实际原框架网关集成测试 |
| M2 / AC02 | 已接需求API、任务与页面 | RequirementItem/Confirmation/Spec/VerificationPlan，RequirementService使用同一RunStore SQLite；空目标、未知工程/路径、重复ID、未映射业务、未知版本、过期确认、版本修订、摘要篡改测试。POST /api/tasks只接受project/spec_id/幂等键，goal来自确认原文，身份来自本地会话；页面显式确认后再启动。任务/候选/检查绑定需求和冻结计划 |
| M3 / AC05 | 反馈增强已接现有循环 | 真实MCP candidate.diff＋服务端候选内容、基线before_hash、可归因失败、诊断片段范围、剩余预算；反馈落事件。SDK手写失败候选证明真实工具失败可构造完整反馈，不等于真实模型多轮成功 |
| M3 上下文预算 | 已实现 | 256KiB按UTF-8字节计数；超限在HTTP/付费调用记录前停止，不暗删必需内容。单测确认不初始化HTTP、无模型请求记录 |
| M4/M5 版本协议 | 已接真实协议并回归 | 九工具强制schema_version=1/tool_version=1.1、deadline和输入树；原生Policy严格12字段请求/8字段响应，核对实际源码/二进制/编译器摘要；SQLite写请求去重，在途/证据缺失IN_DOUBT，不自动重放 |
| M6 / AC08 | 固定案例投影已接通 | 解析原生SDK的OrderTests用例项，按冻结集合投影目标/回归；仅总数或缺用例为UNKNOWN。V1.1接受前重新解析日志、核对JSON报告/绑定并要求所有需求SATISFIED_BY_TESTS；不宣称通用用例发现 |
| M7 / AC09、AC11 | 已接核心、真实SDK与一次授权LIVE回归 | 审批绑定会话/动作/需求/计划/检查/审阅；原子导出预约与外部摘要回执，project/evidence完整归档；OS控制器锁、MCP所有权复核及启动保守中断核查，不自动续跑 |
| M8 / AC01、AC10 | 已接审阅/历史/取消并回归 | 预检不探测付费API；需求确认、用户拒绝/取消、历史任务及候选只读浏览、顺序事件接口、12项Node竞态；实际浏览器核对历史证据失效提示和下载保护 |
| AC04 新V1.1 LIVE、AC12 外部复现 | LIVE一次PASS；外部PENDING | 当前版真实请求1次/首候选/11测试/测试操作者批准导出，记录见R5；旧LIVE仍只作旧版历史证明，不能替代成员独立复现 |

需求服务当前只支持订单登记模板，允许确认既有规则、缩小已登记源码范围和从旧spec新建内容版本。业务条目语义变化如果没有维护者验证映射会明确拒绝，不把任意新规则关联旧测试。需求原文逐字保留。两个逻辑套件目前复用同一11项冻结OrderTests，映射写明此限制，不宣称独立保留测试评估。

当前唯一登记案例的测试均公开，RepairLoop增强反馈明确沿用该公开测试前提；隐藏测试没有启用。读/搜/上下文的冻结可见性已接并由维护者配置测试证明；没有实际隐藏保留测试评估，不能据此宣称通用隐藏测试隔离或独立泛化评估完成。

## 本轮实际验证

- feedback-red.txt：新反馈模块缺失时失败；feedback-green.txt：初始反馈/循环10通过。
- context-limit-red.txt：缺门禁时触发禁止的HTTP夹具并失败；feedback-context-green.txt：12通过（反馈、循环、相同失败两次停止、上下文字节门禁）。夹具不调用网络，不作LIVE证据。
- requirements-red.txt：服务缺失失败；requirements-green.txt：最初4通过；随后增加存储摘要篡改测试，纳入总回归。
- feedback-real-sdk.txt：1 passed，4.71秒。真实MCP/Policy/cjpm，手写错误数量候选build PASS/test FAIL，反馈diff和内容逐字对应真实候选，基线未变。
- r1-offline.txt：`python -m pytest tests -m 'not sdk and not live' -q`，**70 passed、6 deselected，11.68秒**。
- r1-sdk.txt：`python -m pytest tests/sdk tests/integration/test_full_journey.py -q`，**5 passed，27.91秒**。正常/缺陷基线、真实反馈、检查失效及完整接受导出回归均通过。
- 本轮实际DeepSeek API调用0；未新生成LIVE或宣传三轮真实成功。

原始输出均在docs/evidence/v1.1/。完整SDK正常/缺陷日志另为docs/evidence/order-{normal,defective}-test_normal_and_defective_orde0-pytest-81.txt。原始参考清单453文件重新比较一致。本轮仅为V1.1首个增量，后续按账本继续开发，不宣告总目标完成。


## R2增量：需求—任务—验证绑定（2026-10-17）

- 新任务schema_version=2；旧V1无版本记录由明确兼容读取器识别为version1，不补造确认需求；未知版本拒绝。Task增加revision并在状态更新递增。候选记录绑定spec_hash、verification_plan_hash与可获得的成功model_call_id，手写SDK候选保持无模型调用引用，不冒充LIVE。
- RequirementService.prepare_task/task_context核对原文、允许范围、固定预算、基线及计划；原生工具链摘要写入计划，验证时核对。错误/重复需求引用在候选物化前拒绝。检查缓存加入需求与计划身份。
- 读/搜以可信任务计划筛选PRODUCTION/PUBLIC_TEST；VERIFICATION_ONLY不可读/搜，省略task_id不能绕过绑定工作区可见性。以维护者测试profile证明该控制；尚未开展隐藏保留测试评估。控制器对存在保留测试的诊断只保留获准的状态/计数，反馈不包含用例名/完整报告。
- CheckResult增加实际argv、工程相对根、工具链摘要、毫秒耗时、JSON报告引用、用例项、套件投影、需求/计划绑定与范围说明；通过仍只表示所测冻结约定。接受时重新验证日志用例和JSON报告，报告篡改阻止旧接受继续导出。
- GET /api/environment、需求草稿/确认入口已接。POST /api/tasks不再接收客户端goal/身份；确认的source_text是唯一原文。页面先准备三条验收卡，用户再确认启动；配置检查不等于模型连接成功。
- 显式LIVE测试和三次rehearse脚本已改为创建确认需求与version2任务，但本轮没有执行它们，费用为0。

### R2实际证据

- task-binding-red.txt / task-binding-green.txt；requirements-api-red.txt / requirements-api-green.txt；suites-red.txt / suites-green.txt保留先失败再通过记录。
- binding-visibility-green.txt：21 passed，1.25秒（任务绑定、原生MCP读取/搜索拒绝、反馈、API、解析和前端wrapper）。
- requirements-ui-races.txt：7个Node原生异步测试通过，含准备需求不会自动启动和原六类迟到响应。
- r2-offline.txt：完整离线 **78 passed、8 deselected，11.19秒**。
- r2-sdk.txt：真实SDK/集成 **7 passed，46.95秒**，包括新V1.1任务完整绑定与报告篡改拒绝，以及真实失败反馈进入下一提案的两候选链。
- v11-binding-real-sdk.txt：最初同版绑定工具链专项1 passed/8.38秒。新SDK测试的候选生成明确手写/确定性替身；实际MCP、原生Policy、cjpm和报告均真实执行，模型调用记录为空，不能称真实模型多轮成功。
- r2-final-targeted.txt：最后提示词/前端改动后针对性 **17 passed，0.82秒**。核心SDK执行代码未再变化；未重复付费LIVE。
- requirement-draft-desktop.jpg：真实浏览器只点击准备需求，三个需求完整显示；独立预览禁用worker，SQLite核查tasks=0/specs=0、仅3个草稿；没有确认或模型请求。首次预览遇到Flask旧模板缓存，重启预览加载当前模板后重新截图，未保留旧画面作当前证据。
- r2-integrity.json：原参考453文件再次一致；运行服务重启前已查无执行中任务并备份SQLite到.runtime/backups/workbench-before-v11-bindings.sqlite3；没有启动自动恢复或重放任务。

剩余P0：M4/M5跨进程版本契约和策略组件身份、M7审阅拒绝/取消/审批身份动作及完整证据导出、启动所有权/中断事件；M8历史/候选切换和友好失败细节；最后当前版本LIVE授权与外部验收。M1仍保留未确认，不让它阻塞上述开发，不宣告V1.1完成。


## R3增量：版本化真实MCP与原生Policy（2026-10-17）

- 九工具入口必须提供整数schema_version=1、tool_version=1.1、request_id和期限；旧版本/未知字段/错误输入树明确拒绝。ToolClient负责默认封装，不直接调用handler代替协议。响应缺版本时，写操作视为IN_DOUBT。
- 原生仓颉Policy请求/响应同时携带schema_version、policy_version、request_id、输入树、参数摘要与审批摘要；响应逐项核对。UTF-8消息含换行不超过65536字节，IPC启动/I/O/退出共用两秒预算。期限由可信Python入口与执行门禁核对，未声称原生程序自身实现墙钟检查。
- build_policy.py实际编译并写本机构建记录；调用前后及执行前核对源码/程序/编译器摘要。旧程序、构建记录不符、缺程序均拒绝；本机预检也检查这些身份。SDK版本仍固定1.0.5。
- 同一SQLite新增tool_requests操作账本，五类执行/写工具绑定任务、请求、输入、参数、需求/计划、Policy组件和执行计划。完成请求核对真实产物及原始请求摘要后返回同结果；相同ID改参数拒绝，在途或缺失证据IN_DOUBT；不承诺未经证明的exactly-once。
- 新增真实stdio跨Server重试、双Client并发、原始请求/产物缺失、丢失完成状态测试；不会生成第二候选。测试故障注入只用于边界验证，不充当LIVE模型成功。

### R3实际证据

命令均从正式工程运行，原始输出位于docs/evidence/v1.1/protocol/：

- `python scripts/build_policy.py`：policy-compile.txt，实际cjc编译成功（保留编译警告）。
- `python -m pytest tests/integration/test_request_replay.py tests/integration/test_protocol_versions.py tests/integration/test_policy_gate.py tests/test_web.py -q`：final-targeted.txt，29 passed/9.52秒；之后另补中断账本专项纳入完整回归。
- `python -m pytest tests/sdk tests/integration/test_full_journey.py -q`：r3-sdk.txt，7 passed/58.60秒，真实MCP/Policy/cjpm与V1.1失败反馈、同版接受导出回归。
- 并行运行离线与SDK的首次离线结果r3-offline.txt：1 failed、92 passed、8 deselected/17.52秒。进程超时夹具未能在两秒内写出子PID；没有删除失败证据或放宽断言。随后单独复测runner-isolated.txt：1 passed/2.23秒。
- `python -m pytest tests -m 'not sdk and not live' -q`顺序完整重跑：r3-offline-sequential.txt，94 passed、8 deselected/16.29秒。没有修改该超时测试或产品runner来掩盖失败。
- integrity.json：原参考453文件摘要一致、主服务无活动任务。本轮付费API调用0。服务重启前已备份.runtime/backups/workbench-before-v11-protocol.sqlite3，不自动恢复任务。
- replay-red.txt与versions-red.txt保留新增约束未实现时的实际失败；当前通过证据单独保存。

本阶段没有完成M7/M8剩余审批身份/拒绝/取消/完整归档/启动所有权与历史切换；V1.1 LIVE和独立成员复现仍未运行，M1新框架身份仍未确认。不发布本阶段为比赛最终完成版。


## R4增量：审阅、完整交付、中断与历史（2026-10-17）

### 源码和行为

- `nexus/execution/review.py`：用户拒绝核对当前候选及task_revision，记录USER来源、服务端会话actor和原因，转REJECTED；取消使用同一SQLite事务写状态/事件，区分已完成模型请求与真正未决请求，阻止后续步骤而不承诺撤销在途费用。两者都不调用模型。
- `nexus/store.py`：状态比较增加expected_revision；状态与TASK_STATE_CHANGED事件同事务。新RunEvent严格版本化，按任务写入递增sequence；旧V1事件只经显式读取视图保留，顺序事件接口单独报告legacy_event_count，不伪造历史时间。ReviewRecord及ModelCall也有明确schema版本。
- `nexus/execution/delivery.py`：新V1.1批准包含actor、candidate.export、需求/计划、审阅和检查集，接受与原生审阅记录同事务写入。导出预约唯一export_id；取消与发布状态提交相互比较，迟到导出不能覆盖CANCELLED。外部export_artifacts记录最终ZIP及manifest SHA256，读取再次核对。
- `nexus/execution/archive.py`：V1.1 ZIP使用project/与evidence/分区，逐字复制实际记录和日志，保存真实diff、冻结需求/计划、套件与需求结果、模型/工具及MCP操作索引、审阅/批准预约。缺原始记录停止；没有模型调用的SDK候选明确NO_MODEL_CALL_RECORDED。归档冻结于导出完成前，最终状态在外部回执，不回写ZIP制造循环摘要。V1历史ZIP继续显式使用原布局。
- `nexus/execution/ownership.py`：OS flock确认控制器，PID仅供记录；持久化本机session key为0600，不分享运行库。无法确认所有权的工作台只读；受管理运行库的真实MCP执行也核对控制器传递的租约及实际锁，旧元数据或已释放锁不足以写入。独立SDK/CLI运行库属于明确的隔离测试配置，不伪装为工作台所有者。
- 启动核查仅将旧READY置BLOCKED、活动阶段保守置IN_DOUBT，保留原请求/候选/检查并记录CONTROLLER_RESTARTED，不重放模型、补丁、验证或导出，不盲杀旧PID。仍在执行的真实控制器不能被第二实例误判为中断。
- `nexus/execution/workspace.py`：只规范导入副本的源码文件0644/目录0755，读取、候选和验证入口单独核对权限；内容SHA并不包含权限。归档project文件同为0644。测试证明原登记输入不被改写、内容相同但权限改变仍被拒绝。
- `nexus/web/app.py`和workbench.js：拒绝/取消API身份从服务端会话取，拒绝客户端伪造actor或旧revision；历史和候选浏览不改变服务端待审阅对象。旧候选不能批准，异步结果有代次隔离。已交付历史证据失效时保留历史状态，隐藏下载并提示新建任务，不自动付费重跑。

### 实际测试证据

目录：`docs/evidence/v1.1/review/`。

- review-red.txt：新审阅模块未实现时的实际收集失败；review-green.txt保留初次发现旧批准缺task_id的问题，随后修复并回归，未覆盖旧失败。
- review-delivery-green.txt：22 passed/2.86秒；review-api-races-green.txt：32 passed/3.88秒，含取消发生于真实打包过程后的发布阻止。
- archive-real-sdk.txt：1 passed/9.92秒，真实MCP/Policy/cjpm通过后实际打包project/evidence、逐文件及外部摘要核对、异会话拒绝。完整回归版本另增加原生证据缺失阻止、归档篡改拒绝与原字节恢复核查。
- ownership-green.txt：2 passed；review-owner-green.txt：36 passed/4.25秒；owner-protocol-green.txt：27 passed/11.93秒，包含真实另进程持锁及真实MCP受管理写入租约测试。
- ui-history-final.txt：Node原生异步测试12 passed，无npm依赖、无模型请求；覆盖旧任务/候选迟到、拒绝/取消、版本化批准和历史切换。
- r4-offline.txt：1 failed、104 passed、8 deselected/19.91秒；再次出现进程夹具在两秒内未写子PID。runner-isolated-repeat.txt：1 passed/2.20秒。为稳定验证真实超时后清理，夹具改为五秒等待并新增总耗时<10秒断言，子进程仍睡30秒；产品runner的90秒上限和原生Policy的两秒限制未改。
- r4-complete-offline-final.txt：`python -m pytest tests -m 'not sdk and not live' -q`，**108 passed、8 deselected/24.62秒**。包含实际Policy/MCP、审阅、所有权、历史保护及前端wrapper；不是LIVE证明。
- r4-complete-sdk.txt：`python -m pytest tests/sdk tests/integration/test_full_journey.py -q`，**7 passed/56.84秒**。当前同版真实构建、11用例投影、失败反馈、完整归档、原始证据缺失/报告篡改拒绝及HTTP交付回归。候选生成器为明确手写/确定性测试，不当作模型修复。
- live-collection-only.txt：仅`pytest tests/live/test_repair_live.py --collect-only -q`，1 test collected；**尚未执行**。新LIVE入口已准备为一个A任务、独立标注手写D探针、测试操作者批准、真实MCP导出和摘要汇总，不能将收集结果计作LIVE成功。
- workbench-history-protection.png：主服务真实页面，只读取旧任务；历史状态保留，构建/测试显示UNKNOWN、失效提示和禁用审批按钮可见、下载隐藏。没有点击确认/开始/接受。
- integrity.json：原参考453文件摘要一致；重启前无活动任务并备份运行库。重启后本机预检ready、模型连通未探测、session key0600；浏览器检查后任务9个，本阶段付费调用0。

### 剩余边界

M1仍PARTIAL：原始参考身份/许可证文本及“新Sympas-Nexus”对应关系未确认，没有假称直接复用源码或基座网关集成。当前V1.1 LIVE A尚待单独费用授权，旧V1三次成功不迁移为新版证明；新版实际操作视频待这次验收后制作。独立组员复现、赛事平台/截止时刻核实和正式提交为外部PENDING。可选B/C和通用分析不开发。尚未宣告技术总验收或比赛全部完成。


## R4发布自检补充（2026-10-18）

- 提交948e96e的源码ZIP在无.git、无.env、无旧任务记录的临时解压目录运行默认离线回归：`zip-no-git-offline.txt`，108 passed、8 deselected/26.22秒。只复用固定SDK/stdx，重新编译原生Policy；第一次自检漏接stdx目录导致真实编译失败，保留zip-policy-build-missing-stdx.txt，补齐工具链链接后zip-policy-build.txt成功。没有用原运行库或旧策略程序代替干净构建。
- `v11-mcp-export-real-sdk.txt`：新增真实stdio V1.1导出与重复请求专项，1 passed/12.08秒；经原生Policy，返回同一export_id、同版project/evidence及有效外部回执。此前归档专项直接调用交付服务，现补足这一新版跨进程导出覆盖。此补充只增强SDK测试及文档，不改变948e96e应用行为。
- 新版A LIVE费用授权仍待用户答复，没有执行LIVE测试。源码发布清单使用明确提交号；同机无Git自检不等于另一成员独立复现。最新开发验证快照与摘要由.runtime/releases/CangSight-Nexus-v1.1-development-manifest.json记录，未标记比赛正式提交完成。


## R5：一次授权的当前版LIVE验收（2026-10-18）

用户明确授权一次任务后，仅执行`pytest tests/live/test_repair_live.py::test_live_main_case -q -s`一次：1 passed/12.33秒。实际API模型deepseek-flash，请求1次、候选1个；prompt4210/completion103/total4313 tokens，金额未提供不按零估算。实际基线build PASS/test 10通过1失败；候选build PASS/test11通过0失败、三条需求均SATISFIED_BY_TESTS，测试操作者LIVE_TEST_OPERATOR批准，经真实MCP/原生Policy完整导出并核对ZIP。D为额外标注的手写保护探针，无额外模型请求，MCP与原生Policy分别拒绝，基线不变。不能称模型多轮LIVE失败反馈已发生，机制仍由真实SDK确定性两候选试验证明。

实际记录：docs/evidence/v1.1/live/current-a-live.txt、current-live-summary.json；导出ID58193371f19d419fa05c7ab80ad58ec4，ZIP SHA256为20f50e30eb0e587028d3e29ac571580f21668b5fa291252cc09595e2d3eb0765。视频为实际LIVE记录的26秒只读浏览器帧回放，非实时修复录屏；采集禁止POST、worker禁用、无新模型调用，预览已停止；来源与解码/目视检查见video-provenance.json。实际浏览器显示候选PASS和冻结需求结果，原批准者不同于回放会话，下载不能跨身份复用。

本轮可自主完成的实现、真实内核测试、一次授权LIVE、源码固定与敏感检查已做；M1原基座身份/许可证未确认部分仍PARTIAL。另一成员独立复现、赛事入口和正式提交PENDING，具体截止时刻未知。技术验收包可供团队开始独立复现，不宣告比赛整体验收完成。

补充：`docs/evidence/v1.1/live/v11-http-mcp-sdk.txt`，1 passed/13.00秒，使用真实SDK候选，经V1.1 HTTP会话批准、真实MCP完整导出、重复导出同ID及HTTP下载逐字节核对；worker禁用，无新增模型请求。


## 完成条件复核补充（2026-10-18）

此前阶段记录按当时版本保留，最新状态以 completion-audit.md 为准。补齐范围选择冻结、错误业务码、失败/未知状态及输出目录符号链接保护；未追加付费模型请求。历史 LIVE 的模型提案可重用作明确标注的执行器重验证，旧批准必须失效。网络端口隔离试验没有全部通过，规则已撤回并记录限制。M1 指定基座、另一成员复现仍未完成，不宣告总验收通过。


## 用户范围决定：暂缓 Docker 集成（2026-10-18）

用户明确：“本次 CangSight-Nexus V1.1 暂缓 Docker 集成。”调查报告和实际审批边界探针已保存至 docs/docker-feasibility-assessment.md、docs/evidence/docker-feasibility/；仅保留为调查材料，不安装运行时、不构建镜像、不修改稳定主链。后续恢复 Docker 实施需用户重新明确授权，本次没有新增模型调用。

审批接口隔离仍未满足：隔离副本中的新本机会话可创建批准，不能将会话/CSRF验证当作真人授权证明。要求容器隔离的验收不能以native执行替代。该要求尚未以Docker后端契约落地，不宣称已实现自动门禁。

剩余P0：可信人工审批边界、M1实际指定基座入口与来源/许可核实、AC-12另一成员干净环境运行和下载回执。原生MCP/Policy/cjpm技术回归与一次历史LIVE证据继续保留，不能据此判定上述缺口完成。平台确认和比赛正式提交保持外部PENDING。


## Native审批与执行修复（2026-10-18，用户再次确认范围）

V1.1不引入Docker，Native继续开发；Docker不作为前提。实际补上本机操作者凭据配对、全API审批/读取/导出门禁、重启失效；Native保护运行库控制数据（含/tmp运行库）、断开候选stdin/额外FD，并限制对无关进程发信号。原工作台JS主链不重写，原生Policy和真实MCP/cjpm保留。

完整离线133 passed/9 deselected（25.77秒），真实SDK/HTTP 8 passed（61.02秒）。真实仓颉手写安全候选11次验证凭据读拒绝、stdin EOF、审批数据403；非LIVE、无模型请求。既有真实模型提案在当前执行器重新验证并以新测试操作者批准导出（11.052秒、模型请求0），不是新LIVE。正式服务无活动任务时已备份重启，用户需在本机授权页自行配对。

实测、原始记录和剩余安全范围见native-security-fix-report.md。一般IPC/调试/资源耗尽的完整隔离不宣称已证明，强制要求超出已测边界时仍BLOCKED/NOT_VERIFIED。M1与外部复现/比赛正式提交未完成。原生候选目录不是安全沙箱，不将Docker缺席列为验收阻塞理由。


## 2026-10-18 指定 M1 来源核查

已固定 nuptpisa/CangSight@5db0c7eeeb6a62812fc04e9e88497339fed5e11f 的 Sympas-Nexus 子目录；447份上游文件与本地相同，本地另6份交付资料；原始453文件未变。根Apache-2.0与插件MIT声明差异已记录。真实网关静态接口及实际import探针已核查，缺flask_cors，未启动旧领域服务、未安装整库依赖。当前未实施基座适配，M1/AC03 BLOCKED，不能把来源核实和独立工程回归称为集成完成。离线133通过/9排除，tests/sdk真实Native7通过，原始证据位于 docs/evidence/v1.1/m1-upstream。详见 m1-reuse-review.md 新增补充。不接Docker、不新增付费调用。


## 最小派生网关实施补充（2026-10-18）

已按用户许可处理指令保留根Apache-2.0，检查网关无单独许可/版权例外。新增真实复用上游函数与查询路由结构的sympas_runtime模块，仅挂仓颉创建/查询/事件入口，复用当前控制层事务、运行库、审批门禁。真实SDK手写探针与重开库验证通过；最终离线141/10排除，SDK/HTTP9通过、最终查询字段另1项SDK复测通过，Node15通过。详情m1-integration-report.md；M1仍PARTIAL，原始完整基座入口未启动，Native子进程强制边界未完成。不是新版LIVE或比赛完成。


## Native测试编译/运行拆分（2026-10-18）

runner保持固定MCP命令入口，内部将测试拆为真实cjpm test --no-run及--skip-build，共享原时限/输出预算；冻结具体可执行文件路径/内容，禁止执行复制程序及SDK调试器。CheckResult.execution_argv保存实际发起步骤。真实仓颉shell拒绝和原生文件/硬链接/复制执行探针通过，离线141/11排除、SDK/HTTP10通过。失败定位与最终范围见native-execution-staging.md。无Docker、无新增模型调用、原Sympas453文件不变。旧验证计划/批准不复用。仍不宣告M1完整或一般Native隔离、外部验收完成。


## M1真实基座分派核心更新（2026-10-18）

已提取固定上游_execute_run及create_run入队/线程流程，注入既有RepairLoop/真实RunStore投影，主页面新任务通过基座入口。自动实测9次真实MCP、4项检查，基线FAIL到候选11项PASS，最终REVIEW_PENDING；生成阶段明确脚本化，非LIVE且无自动接受/导出。离线144通过/12排除，SDK/HTTP11通过（73秒），Node15通过。按设计最小适配范围M1/AC03通过；未引入整份旧平台、不伪造全量复用。完整范围及证据见m1-dispatch-acceptance.md。总目标、当前新版LIVE、一般Native未覆盖安全边界和外部成员验收仍未完成。
