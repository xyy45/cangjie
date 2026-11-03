# 实施记录

**最新状态（2026-10-17）：真实LIVE修复与三次完整复演、浏览器A+D和实际下载核对均通过；下文保留历史BLOCKED与故障记录，不能作为当前状态。最终回归离线53 passed、SDK层4 passed；外部独立复现和赛事提交仍待完成。**

正式目录为当前仓库。原始 Sympas-Nexus 只读，未复制密钥、缓存和数据库。
当前新实现尚未复用原框架产品源码：原有 Server 依赖全工具注册、旧网关和 HITL；为满足九工具与原生 Policy 边界，使用独立实现。原副本无 Git 元数据，不能采信工作区 README 的提交身份为当前可核实提交。已保存源文件 SHA-256 清单供后续比对。

## Task 1

- Python 3.12.14 独立虚拟环境；固定依赖见 pyproject.toml / requirements.lock。
- 官方 Cangjie 1.0.5 LTS macOS ARM64：SHA256 e07d22584237f065b30a771b7110a87a8931334c40be3a148090944ae916ed1f，与官方页面数据一致。SDK 仅放 .runtime/sdk，排除版本库与交付包。
- 系统默认 macOS26.5 SDK 与该版链接器不兼容；本机已有 MacOSX15.4.sdk 可用。环境传入最小白名单，避免宿主环境中的非法 UTF8 造成 cjpm 启动异常。
- tests/test_doctor.py：RED 缺模块；GREEN 2 passed。
- tests/sdk/test_order_demo.py：正常版真实 build/test；11 用例通过；缺陷版 zeroQuantity 真实失败（10 passed / 1 failed）。SDK 早期环境失败亦保存，不能计为业务测试失败。
- fixture 为正常参考基线；后续 A 场景从其数量下界缺陷版生成冻结工程，不向模型提供参考修复。
- 课题组分析当前排除：原清单 sympas_slice 明示 C/C++；code_scan / ast_symbol_extractor / dep_graph 尚无可访问已确认的仓颉语义后端，不把工具声明当通过。待有端点后补正常/缺陷/非法语法探针，当前不提供确定性分析结论。
- Task 1 环境与自产基线已验证；可选工具实际服务筛选待配置。T2 接续。

## 后续验收

Task 2–10 未完成。LIVE 模型、真实 MCP、原生 Policy、受限 runner、接受导出、浏览器与三次复演均未验证。视频、第三人复现和实际比赛提交需要外部配合，不能以自动测试替代。

## Task 2

严格 Pydantic 数据对象（拒绝额外权限字段、非法修改路径与 origin）、完整树摘要、SQLite 任务与六类只增 JSON 记录已实现。轮数只增且重载保留；同任务候选编号唯一；跨任务引用和凭据字段拒绝。RED 缺实现，GREEN 7 passed，证据见 task-02-*.txt。后续接受与导出事务由 T8 增补，当前无完整事件溯源。

## Task 3

官方 MCP SDK 1.26.0 的独立 stdio Server 与 Client 已实现；initialize/list_tools/call_tool/关闭经真实进程验证。读取源码内容与 fixture 相同；路径越界与空搜索错误准确返回。写请求连接不可用为 IN_DOUBT，无自动重放。登记工程导入冻结摘要，符号链接、未登记工程、模糊构建根均拒绝。5 passed，证据 task-03-*.txt。当前仅三个只读工具，写工具在 T5 前关闭。尚需补充“在途写请求断连”故障进程测试（当前断连用例为未连接会话）。

## Task 4

独立 staging 校验 1–3 既有允许源码、before_hash 后整体发布；每次来自冻结基线；实际文件计算 diff。重复候选不增加轮数。当前 Server apply 明确拒绝（待 T5 原生 gate），diff 可经 MCP 调用。Task 4 测试 4 passed；默认回归见 task-04-regression.txt。T4 不声称修复成功。

## Task 5

原生 policy 已经官方 SDK 1.0.5 编译，使用官方 stdx 1.0.5.1（GitCode release，下载文件 SHA256 202b91110996c60de35f2dc07c278bc19a08df2029dc3376710c9f3e84121e7b；此为本地下载摘要，未声称官方签名）。固定编译命令 scripts/build_policy.py。三态规则与 JSONL IPC、64 KiB／2 秒限制、故障关闭均有测试；真实 MCP apply→diff 通过。build/test/export 将随 T6/T8 工具注册走同一 gate，当前无这些可旁路入口。7 项 gate/候选集成通过。Policy 应用层许可不构成 OS 沙箱；T6 尚须验证受限 runner。

## Task 6

实际 SDK 输出解析、固定 build/test argv、90 秒／2 MiB 限制、进程组收尾、编译失败不运行测试、源码变化失效已实现。诊断与 build/test 通过同一 native gate；真实 MCP apply→build→test（11 非零测试 PASS）有 SDK 集成证据。缺失／零测试／跳过／不完整输出 UNKNOWN，负进程退出与无法归因环境错误不作为模型修复反馈。

macOS sandbox-exec 为本机受控演示 runner：限制工程外写入、用户目录数据读取及外网连接，实测合成哨兵读写与外网连接拒绝。cjpm 打开 toml/lock 需要写权限，允许这两文件但运行后完整摘要必须不变；target 与临时目录可写。SDK unittest 内部 bind 动态端口，需要本机网络连接及监听；故不是全禁网环境，也不宣称通用恶意代码隔离。当前默认注册自产工程，禁止任意上传。后续发布仍须明确此边界。

测试 task-06-green.txt 5 passed（含真实 MCP/SDK）；默认回归见 task-06-regression.txt。尚须补充超量输出／超时故障进程测试、在途 MCP 写断连测试和检查缓存配置版本绑定后再做最终验收。

## Task 7（实现中，LIVE 未通过）

Provider 使用一次真实 HTTP JSON 请求，保留请求/原始响应、actual model ID/origin/usage；未知付费调用不重试，截断提案不应用。单循环经 MCP 诊断/读取/apply/build/test，480 秒、最多三候选、重复或两轮无新反馈停止，取消后迟到响应不物化。确定性分支 4 passed，仅测试替身，不作 LIVE 证据。

显式执行 tests/live/test_repair_live.py，真实基线经过 SDK 诊断，因未配置 DeepSeek 进入 BLOCKED，测试 FAILED（见 task-07-live.txt），没有 skip 或模拟成功。LIVE A 及三次复演仍未完成。已通过异步问题请求配置路径，继续独立实现 T8/T9，不声称 T7 验收完成。

官方 Provider 请求合同参考 https://api-docs.deepseek.com/api/create-chat-completion/ ，max_tokens=20000，服务不支持即明确错误。模型设置必须用户配置，不臆造当前模型名。

## Task 8

用户接受绑定当前选择、树摘要、真实日志与必需检查集合，30 分钟过期；accept 不注册为 MCP Tool。原生 gate 保护 candidate.export，第九工具已注册。SQLite 事务先保留唯一 export_id 再打包与核对 manifest，重复并发请求共享导出 ID，故障保留 FAILED 可按同 ID 再核对生成。候选变化、过期、日志改变阻止旧接受导出。5 单元测试通过；这些使用明确标注的合成检查记录，不替代 SDK/LIVE 端到端交付验证。T10 需真实主链导出复核。

## Task 9（页面已实现，LIVE A 页面验收待配置）

Flask 单页、开始幂等、进度轮询、实际 diff/检查、用户接受、MCP 导出和下载已接通；只监听本机，POST 验证 Origin + 本地会话 CSRF。源码仅 textContent 输出。页面默认仅登记边界缺陷案例，不接收宿主任意上传。

浏览器实际点击开始，真实基线诊断后显示 BLOCKED（缺模型配置），刷新保留同一任务且未创建新模型调用。桌面双栏／390px 窄屏堆叠截图在 evidence/workbench-*.png；截图为当时实际受阻状态，不冒充成功。成功 A 浏览器全流程与 D 页面演示尚待 T10。

## Task 10（进行中）

真实 SDK/MCP/原生 Policy/HTTP 接受导出主链的手写候选集成通过，导出源码逐文件核对。这是无模型集成证据（task-10-handwritten-journey.txt），不是 LIVE 修复。三次 LIVE A、第三人成员复现、版本对应录像、正式冻结及比赛提交/回下载均未完成。

## 加固与当前待办

已补真实MCP在途写断连（一次写、响应丢失、不重放）；受限runner超时、输出上限和子进程收尾；验证计划绑定固定编译器/cjpm二进制及runner/verifier版本；policy决定与工具结果落盘；旧计划检查在页面显示UNKNOWN；接受绑定当前候选选择；下载前再次校验归档。原始目录453文件重新SHA256核对完全一致。

浏览器已实点“检查测试保护”，原生Deny，写动作执行数0，冻结文件不变。此为独立保护探针，非LIVE A成功。课题组默认本机服务127.0.0.1:2266/health实际连接失败（HTTP000），当前无法做正常/缺陷/非法仓颉样例准入，继续排除，不假定支持。

## 最新验证与环境异常

最后一轮显式SDK/交付集成 4 passed（task-10-sdk.txt），默认离线回归见task-10-offline.txt。此前一轮正常样例曾被系统以exit9终止（task-10-sdk-exit9.txt），同期AppleSystemPolicy有拒绝记录（sdk-exit9-system-log.txt）。独立复核正常/缺陷再次通过（task-01-sdk-recheck.txt）。尚未根治该偶发主机策略异常，不能称稳定性完成；运行时ERROR已修正为UNKNOWN，阻断模型自动修复反馈。没有禁用Gatekeeper/AMFI或降低宿主安全设置。

原始SDK报告样本冻结在tests/data，后续SDK测试使用带运行目录标识的新日志，不覆盖解析样本。无新反馈比较会规范化候选ID和耗时，避免相同失败被变化的日志路径/时间误当新证据。

当前首要外部阻塞仍是DeepSeek配置；目标保持active。尚无一次LIVE模型成功、连续三次LIVE复演、第三人复现、对应视频和正式提交回验。不以已实现文件数量替代这些验收。

最终页面回验：当前版本真实基线 build PASS / test 11项中10通过1失败；模型缺配置保持BLOCKED；原生保护探针Deny、写动作0、文件不变。最新桌面/窄屏/策略截图为workbench-*-final.png。刷新后下载链接恢复的API+真实SDK交付回归6 passed（refresh-delivery-recheck.txt）。环境探针修复cjpm内层调用cjc所需HOME/PATH，实际doctor返回SDK available，模型配置缺失；未发出付费请求。


## 配置等待期间的续轮（用户明确要求不运行LIVE）

已核查并测试从工程根自动加载.env、启动目录独立性、现有环境变量优先级、Git忽略及未跟踪；测试只使用临时合成配置，无HTTP请求、无ModelCall。用户将自行在正式目录填写.env，不创建或覆盖其配置文件。Task 7 LIVE继续BLOCKED，待用户告知配置就绪后再验收。

补充RED→GREEN修复：测试NOT_RUN不能作为可靠失败继续模型生成；通过计数与失败结尾矛盾的日志判UNKNOWN；阶段读写之间发生取消时使用SQLite条件更新，避免迟到阶段覆盖CANCELLED。证据continuation-reliable-failure-*.txt、continuation-cancellation-*.txt、dotenv-verification.txt。SDK/MCP/HTTP交付回归本轮3 passed（continuation-sdk.txt）；完整默认离线结果见continuation-offline.txt。最终验收仍缺LIVE A、连续三次复演、外部成员复现、录像、冻结与提交回验，不以配置单测替代。


## 配置就绪后的真实验收

用户配置.env后，最小真实API调用HTTP200，服务报告deepseek-flash，用量9tokens。Task7真实LIVE测试1 passed，首候选通过构建与11测试，再由CLI测试操作者接受并经MCP导出（task-07-live-delivered.json）。没有用参考修复答案替代模型输出。

scripts/rehearse.py从三份独立干净基线连续真实执行，均首候选DELIVERED；耗时8.981/8.934/8.456秒，每次都有LIVE ModelCall、原生Policy、真实build/test和独立导出摘要。浏览器另实际运行两次LIVE任务，其中录制任务产生quantity > 0的独立模型修改，同样11测试通过并下载核对。D保护探针原生Deny、执行数0、文件不变。

权限配置切换导致工作台服务停止，已通过端口无监听及SQLite REVIEW_PENDING核查后恢复；仅重新读取原任务，未重放模型调用。录制采集227个实际页面帧，编码视频25.796秒；长等待缩短，非连续未剪辑录屏，元数据和帧摘要见live-video.json。最终回归离线53 passed、真实SDK/交付4 passed。

下一步外部验收：另一成员按runbook独立复现；队长核对赛事入口/截止时间并正式提交回下载。已向用户请求执行人和平台信息。B/C及可选课题组分析仍未纳入本有限范围版本。
