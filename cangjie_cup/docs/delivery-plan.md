# CangSight-Nexus：MCP 驱动仓颉工程修复开发计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本文件不要求派生子智能体；任何并行代理执行另按用户授权。

**Goal:** 在 2026-10-23 截止前，交付一条能稳定演示的“导入仓颉工程—MCP 诊断—AI 候选—真实构建测试—反馈修复—审阅导出”主线。

**Architecture:** 在独立新工程中选择性复用新的 Sympas-Nexus 框架；Python 单编排器通过真实 MCP Client/stdio Server 执行工程工具。Server 侧统一经过仓颉 Policy 决策，再进行候选物化与 `cjpm` 验证；SQLite 与文件日志保存最少运行记录，Flask 服务端页面提供统一入口。

**Tech Stack:** Python、Flask/Jinja、官方 MCP Python SDK、仓颉 SDK、JSONL IPC、SQLite、pytest。准确依赖和 SDK 版本在阶段 S0 验证后固定，不把旧框架宽版本依赖直接作为新锁文件。

**Spec:** 本文件第 1—5 节固化用户于 2026-10-17 确认的范围；参考[新的 MCP-CEGIS 规划与代码审计](</Users/jxy/Desktop/CangSight-Nexus_MCP-CEGIS开发规划与代码审计.md>)与[比赛参考文档 6.1](</Users/jxy/Desktop/ChinaSoft_2026_双大赛_仓颉杯与鸿蒙AI杯_参考文档.md:1694>)。不是照搬旧文档的全部功能门槛。

**状态：开发计划已编写，产品实施未在本轮开始。** 下文的目录、接口、命令和测试均为后续目标，不是已存在或已通过的声明。

## Global Constraints

- 主语言是仓颉；主线必须保留真实 MCP，不采用此前“MCP 全部移除”的 MVP。
- 只接入实际支持仓颉且对案例有帮助的课题组分析工具；不支持的直接排除，不阻塞本地工程验证修复。
- 第一个版本先支持小型、明确构建根的工程，候选每次修改 1—3 个已有 `.cj` 文件；最多 3 个候选。
- 原始工程不改写，每次候选从同一基线创建；测试、依赖配置、平台和 SDK 不属于模型可修改范围。
- 构建与测试真实调用固定 SDK 的 `cjpm build -V`、`cjpm test`，不能由模型生成任意 shell 命令。
- 失败、未知、未运行与通过分开；模型不能自行把检查改成通过。
- 截止前默认只执行登记的自产演示工程；不开放“任意上传代码在宿主执行”。候选仍是不可信代码，执行需受限环境和进程生命周期控制，独立目录不冒充沙箱。
- 不做 54 工具全量接入、SMT、多 Agent、宏增强、云部署、Docker 镜像、签名链、完整自动恢复或新前端框架迁移。
- 2026-10-22 中午冻结主要功能，23 日提前提交。截止日期按用户给定约束；具体时刻、平台要求由队长核对，不以本文代替赛事通知。
- 新工程与原始代码副本分离；密钥、`.env`、旧数据库、缓存和历史用户源码不复制到新仓库或发布包。

## Review Focus

1. MCP 连接中途丢失：只读可显式重试，未知在途的写入／付费调用不自动重放；Task 3、7 验证。
2. 演示目录存在额外构建根或路径冲突：不猜工程根，不写越界路径；Task 3、4 验证。
3. 零测试／跳过／日志不完整：不得以退出码 0 标绿；Task 6 验证。
4. 审批时或导出前候选改变：旧检查和接受失效；并发导出不能多次消费；Task 8 验证。
5. 刷新页面或模型响应迟到：不重复创建任务、不重新调用付费请求、旧结果不覆盖当前选择；Task 7、9 验证。

---

## 1. 本次范围与文档优先级

本次选择“**主线完整、支持范围有限、演示场景稳定**”，不是“所有能力都完善”。目标是完成软件系统的实际操作流程，不是先做大规模工具验收和审计平台。

### 1.1 必须有的功能

1. 选择／导入小型仓颉工程和输入修复目标。
2. 经 MCP 读取工程、取得基线诊断；有适用的课题组分析工具时增加辅助定位。
3. DeepSeek 基于真实源码、诊断和需求生成结构化候选。
4. 仓颉 Policy 决定候选、执行和导出动作能否继续。
5. 经 MCP 在独立副本应用修改，运行完整工程构建、目标与回归测试。
6. 可靠失败反馈给模型，在三候选预算内修正；环境错误立即停止。
7. 页面查看修改和验证，用户接受后导出同一版本工程。

### 1.2 可以不完备的能力

任意规模工程、所有仓颉特性、完整调用图、通用 AST、全工具目录、多个模型、自动重启恢复、批量任务和复杂设置均不列为发布前置条件。工具不支持仓颉时不要求现场开发新编译前端。

第一条主链只需一个案例。第二、第三案例和更深分析只在主案例已经走通后增加。若最后只交付主案例，也要说明是受控工程范围，不宣称通用全工程分析。

### 1.3 替代旧门槛

| 旧要求 | 本次决定 |
| --- | --- |
| 课题组诊断、定位、候选重分析三环节全部准入才能完成主链 | 取消硬前置；支持的接入，不支持的记录不适用；真实 `cjpm` 诊断／测试维持闭环 |
| 第一轮实现十二个工程工具 | 合并候选创建和应用，证据查询走普通后端 API；首版九个 MCP 工具 |
| 全 54 项清点和逐项资格作为开发任务 | 不做全量工程；只保留候选工具清单，首日小样例筛选后定名单 |
| 十二个评测任务作为完成线 | 改为一个必需主案例、两个可选案例和一个拒绝场景；不凑数量 |
| 独立证据平台、复杂恢复／审计链 | 日志和 diff 自动落盘、SQLite 关联；重启后人工处置 |
| React/Vite 新前端与 FastAPI 迁移 | 沿用新 Sympas-Nexus 已有 Flask 机制，先做一个服务端页面 |

本文是当前截止前范围，优先于[历史重新开发说明](../../redesign.md)中冲突的发布门槛；历史说明保留为长期设计参考，不再要求逐条在本次实现。本文也不采纳外部 K3 基线中“取消全部 MCP”的范围。

## 2. 开发主线与职责

```text
选择工程＋修复目标
       ↓
冻结基线、测试与允许修改范围
       ↓
MCP 读取／搜索 → 基线诊断＋可用的课题组分析
       ↓
DeepSeek 提出 edits（不是宣布修复成功）
       ↓
MCP candidate.apply → Server 校验 → 仓颉 Policy → 独立候选
       ↓
MCP candidate.build → candidate.test
       ├─ 可归因 FAIL＋剩余预算 → 诊断反馈 → 新候选
       ├─ 环境 UNKNOWN／重复／三候选用尽 → 停止并显示原因
       └─ 必需检查 PASS → diff＋结果 → 用户接受
                                     ↓
                       MCP candidate.export → 下载工程
```

### 2.1 编排方式

单 Agent＋显式状态机。模型可决定读取哪些允许文件、是否需要辅助分析，以及怎样修改代码；控制层决定阶段、预算、工具许可和必需检查，不能让模型跳过构建／测试直接导出。

最初不必依赖模型厂商的复杂原生 tool-calling：Provider 可返回严格的结构化行动，控制层将合法行动转换为真实 MCP 调用。模型只看到当前阶段的有限工具，不获得服务地址、密钥、审批接口或任意 shell。

保留 Generate → Verify → Judge → Feedback 思路，但不要把旧 C/Python 验证器、硬编码八轮和远端 `agentic_repair` 再生成代码搬入主线，避免双重修复循环。

### 2.2 三种角色要区分

- **本地工程 MCP 工具**：提供读取、候选、构建、测试、导出等操作，是执行主线。
- **课题组分析 MCP 工具**：提供其真实支持的规则／符号／切片等能力，是可选增强；工具数量不是算法数量。
- **仓颉 Policy**：原生三态策略进程，影响真实动作；不是分析器，也不是 OS 安全沙箱。

如果没有课题组工具可分析仓颉，仍可交付“MCP 驱动仓颉工程验证与修复”；不得改称“已完成课题组仓颉语义分析”。这不会取消 MCP 工具执行主线。

### 2.3 最小状态

`READY → DIAGNOSING → GENERATING → APPLYING → BUILDING → TESTING → REVIEW_PENDING → EXPORTING → DELIVERED`。

可修复 FAIL 回 GENERATING；另有 `UNREPAIRED / BLOCKED / REJECTED / CANCELLED / IN_DOUBT`。候选最多三个；原始失败不覆盖。相同候选或连续两轮没有有效新反馈时提前停止。首次就修好则直接进入审阅，不强行制造一次失败。

## 3. 工具、数据与页面设计

### 3.1 九个工程 MCP 工具

所有请求由控制层补齐 task_id／request_id，候选 ID 与允许工程根由 Server 管理。结果统一带 `operation_status, data, error, record_refs`；编译／断言 FAIL 是有效检查结果，不与 MCP 传输错误混淆。

| 工具 | 特定输入 | 主要输出 | 执行责任 |
| --- | --- | --- | --- |
| `workspace.list_files` | 工程 ID、目录前缀 | 文件路径、大小、构建根 | 基线只读 |
| `workspace.read_file` | 路径、可选行范围 | 源码、原始行号、文件摘要 | 范围／大小校验 |
| `workspace.search` | 文本、可选路径范围 | 匹配文件、行和片段 | 首版只做有界字面搜索 |
| `project.diagnose` | 基线或候选 ID | 构建／测试诊断、适用分析观察、位置和限制 | 复用同一个 Verifier，不另写编译判断 |
| `candidate.apply` | 基线 ID、`edits[path,before_hash,content]` | 新候选 ID、树摘要、修改清单 | 合并 create＋apply，staging 全部成功才发布 |
| `candidate.diff` | 候选 ID | 实际 diff、摘要 | 从真实基线／候选计算，不信模型描述 |
| `candidate.build` | 候选 ID、期望树摘要 | state、退出码、诊断、日志引用 | 固定 SDK／argv／工作目录 |
| `candidate.test` | 候选 ID、期望树摘要 | state、非零用例计数、断言和日志 | 仅同候选 build PASS 后执行 |
| `candidate.export` | 候选 ID、接受记录 ID | 导出 ID、最终树摘要、下载引用 | 校验检查、接受与内容一致 |

`project.diagnose`对基线执行一次 build；有编译失败则返回该诊断，不运行 test。构建成功才执行冻结测试。对已检查候选复用相同树、配置与计划的结果，不重复消耗验证。辅助分析未配置或不支持时返回明确限制，不伪造发现。

### 3.2 课题组分析工具选择

首日只检查 `code_scan`、`ast_symbol_extractor`，以及有希望适用的 `sympas_slice`／`sympas_dep_graph`。用自产 `.cj` 正常／缺陷／无效语法样例确认是否真有作用；语言目录里出现 cangjie 不代表语义支持。

选择结果只允许三种：接入演示主链、作为按需辅助、当前排除。无效结果不丢给模型当确定事实；不等待所有工具，不以“缺一个可选图工具”阻断修复。

Server 可以在内部将这些分析请求适配到遗留 HTTP 服务；Agent 到 Server 的工具边界仍为真实 MCP。不要把所有旧工具定义直接镜像给模型。

### 3.3 六类最小记录

| 对象 | 最少字段 | 用途 |
| --- | --- | --- |
| Task | id、baseline_id、goal、allowed_paths、test_plan、status、attempt_count | 保存目标、范围与进度 |
| ModelCall | id、task_id、origin、model_id、request_ref、response_ref、usage、status | 标识实际模型参与和调用失败 |
| Candidate | id、task_id、baseline_hash、edits、tree_hash、diff_ref、attempt | 保存独立修改版本 |
| ToolCall | id、task_id、candidate_id?、tool、status、result_ref、policy_ref | 查询 MCP 调用与策略决定 |
| Check | id、subject_id、plan_hash、tree_hash、kind、state、counts、log_ref | 保存真实构建／测试与失败输入 |
| Acceptance | id、candidate_id、tree_hash、check_set_hash、expires_at、export_id? | 绑定用户接受与导出 |

SQLite 可使用对应表与一个轻量事件表；原始请求、响应、diff、日志落盘。所有文件仅存当前任务必要内容；不做签名、远程证明和审计大屏。接受与导出记录分阶段更新，防止重复点击产生多个交付。

检查状态固定为 `PASS / FAIL / UNKNOWN / NOT_RUN`。test PASS 必须来自真实非零测试、无失败且无必需跳过；日志缺失、不可解析和基础设施故障为 UNKNOWN。控制层而非模型设置 origin、model_id、可信 ID 和最终状态。

### 3.4 单页布局

顶部“工程／目标／开始修复”，中间“当前阶段”，下方双栏“修改 diff／验证结果”，底部“接受并导出／下载工程”。工具调用与日志折叠显示。默认不铺内部 ID、token、原始 JSON 和长篇机制解释。

刷新只查询已有任务；开始和导出按钮需幂等，运行中禁止重复提交。展开面板采用箭头标题，执行按钮采用明确主次样式。先保证桌面布局和可操作，再补窄屏，不做复杂动画。

## 4. 演示工程与完成目标

### 4.1 工程方案

采用一个小型“订单校验与费用计算”仓颉工程，不接数据库／Redis／登录。规划 3—5 个源码文件，至少分出数量校验、费用计算和订单处理；测试使用 SDK 实际支持的测试组织方式。具体源码在 SDK 验证后创建，本文件不预造未编译的仓颉示例。

建议冻结的业务约定：数量范围 1—1000，单价为非负整数且最多 1,000,000；合法订单总额为数量乘单价，非法输入明确拒绝。取值范围保证示例运算不依赖溢出行为。这是演示项目的设计约定，不是通用业务规则。

主案例至少验证 `(3,100)→300`、`(2,100)→200`、`(1,0)→0`、数量 0／负数拒绝、1000 允许／1001 拒绝。多个输入防止直接返回固定值也能通过。

### 4.2 场景优先级

| 场景 | 展示能力 | 优先级／验收 |
| --- | --- | --- |
| A 主案例：边界逻辑错误 | build 成功、测试失败，模型根据断言修改并回归 | 必须；至少一次 LIVE 候选目标和回归 PASS 后真实导出 |
| B 接口／类型错误 | 编译诊断、定位、修复后构建与测试 | 主链稳定后增加 |
| C 跨模块契约错误 | 读取相关文件，1—3 文件修改，完整工程回归 | B 后增加，不为演示大工程额外扩架构 |
| D 越权修改测试 | 仓颉 Policy 拒绝，保护文件不变 | 必须；与成功场景分开演示 |

如果 A 没有修复成功，只能报告流程已联通或未修复，不能称核心修复能力已完成。B/C 未完成不阻断 A＋D 的有限范围版本；材料明确实际范围。

### 4.3 稳定展示方法

演示前恢复干净基线、预装依赖、验证模型额度和 MCP 连接、预热 SDK；主案例连续完整复演三次，记录真实耗时和异常。模型的语法资料只用固定 SDK 的必要信息，不提供参考修复答案。

准备成功录像与历史报告做断网备援，使用时明确标注历史运行。不要固定模型回答、预造 PASS，或强制安排“恰好两轮成功”。演示范围小可以，结果必须来自实际运行。

## 5. 阶段目标与截止前排期

以下按当前日期 2026-10-17 安排，不倒填已完成状态。若实际启动较晚，先压缩 B/C 场景和界面装饰，不顺延代码冻结与提交缓冲。

| 阶段 | 建议日期 | 阶段目标 | 退出条件／能看到的结果 | 对应任务 |
| --- | --- | --- | --- | --- |
| S0 环境与案例 | 10/17 | SDK、模型配置、来源和主案例明确；检查可选分析 | 最小仓颉工程真实 build/test；MCP 协议版本和依赖可用；可选工具得到取舍结论 | T1、T2 开始 |
| S1 MCP 基础 | 10/17—18 | 标准 Client/Server 及工程读／搜 | 经真实协议列出工具、读取 fixture；不是直接调用 handler | T2、T3 |
| S2 无模型验证链 | 10/18 | 候选、Policy、构建测试与 diff | 手工提交候选也能经 MCP 完成 apply→build→test；失败状态准确 | T4—T6 |
| S3 LIVE 修复循环 | 10/19 | 模型候选、反馈、三候选停止 | A 案例真实修复；失败反馈路径另有确定性测试，不强求现场多轮 | T7 |
| S4 用户闭环 | 10/20 | 一页操作、接受、导出，按需分析 | 用户从开始到下载走完；交付是已验候选 | T8、T9 |
| S5 稳定性与扩展 | 10/21 | 三次主案例复演，B/C 能做多少做多少，D 拒绝场景 | 选定最终展示范围；另一成员按说明复现 | T10 |
| S6 冻结与提交 | 10/22—23 | 固定版本、视频、启动说明、提交回验 | 22 日中午冻结主要功能；23 日提前提交、下载验证 | T10 |

**关键依赖：** SDK 可用和真实 MCP 读文件可以并行；必须在接模型之前完成“无模型的真实候选验证”。必须在录视频之前完成实际审阅和导出。不要把第一次集成留到最后一天。

### 5.1 五人分工参考

- A：Provider、候选生成、反馈循环；跑通后协助页面。
- B：MCP Server、九工具路由和可选课题组适配；协议通后协助审批接口。
- C：MCP Client、Workspace、主状态机和系统集成。
- D：SDK、仓颉 Policy／IPC、受限 runner、Verifier 和报告解析。
- E：轻量记录、页面、演示案例、复现和材料协调；不是独自写全部测试。

各模块负责人提交自己的测试。人数与技能尚未由本文确认，按实际能力分配；单人实施时沿 T1—T10 顺序串行，不开多条互相等待的空模块。

## 6. 文件地图与实施约定

以下路径相对未来**正式新工程根**，不是要求改旧 `HW-CodeArts` 或当前文档目录的产品源码。

```text
pyproject.toml                         最小依赖与开发测试配置
scripts/doctor.py                      环境探针，不默认外发源码
cang_sight_server/server.py            真实 MCP stdio Server
nexus/contracts.py                    统一 Pydantic 对象与摘要规则
nexus/store.py                        SQLite 状态和日志引用
nexus/mcp/client.py                    MCP 生命周期、发现与调用
nexus/mcp/tools/workspace.py           list/read/search
nexus/mcp/tools/project.py             diagnose／可选分析组合
nexus/mcp/tools/candidate.py           apply/diff/build/test/export 路由
nexus/execution/workspace.py           基线与候选目录、原子发布
nexus/execution/delivery.py            接受占用、包生成与导出对账
nexus/policy/client.py                 仓颉 JSONL IPC
nexus/policy/gate.py                   Server 侧唯一受控执行入口
cangjie/policy/                        原生策略与自身测试
nexus/adapters/cangjie/verifier.py     固定 SDK 构建与测试
nexus/adapters/cangjie/report_parser.py SDK 实际测试格式解析
nexus/adapters/sympas.py               可选课题组工具适配
nexus/llm/provider.py                  真实模型调用与原始结果
nexus/repair/cegis_loop.py             单循环、反馈与停止
nexus/web/app.py                       Flask API 与页面入口
nexus/web/templates/workbench.html    单页模板
nexus/web/static/workbench.js          轮询、diff 与审阅交互
tests/                                单元、协议、SDK、LIVE 分层测试
fixtures/order-demo/                   登记的自产仓颉演示工程
docs/runbook.md                        安装、启动、演示、故障处理
```

这些模块可抽取审计报告中的机制，不整包迁移原网关、旧验证器和所有 Skills。来源框架在另一环境，本轮未直接检查其源码；实施前核对选定副本、许可、模块依赖和版本。只记录实际复用文件，不制造历史提交。

下列测试名、签名和命令是新工程待实现合同，不是已有 API。每任务先写断言并确认失败，再实现并跑绿；在有 Git 的正式工程中提交该任务相关改动，无 Git 时先明确版本管理，不凭空写“已提交”。

## 7. 可执行开发任务

### Task 1：环境探针与自产仓颉基线（S0）

**Files:** Create `pyproject.toml`、`scripts/doctor.py`、`fixtures/order-demo/`；Test `tests/test_doctor.py`、`tests/sdk/test_order_demo.py`。

**Interfaces:** Produces `inspect_environment() -> dict[str, object]`，含 Python／SDK 路径版本和配置存在性，不返回密钥。固定演示工程的位置、业务约定、构建根及测试组织交给 T3、T6。

- [ ] 写 `test_doctor_missing_sdk_is_unavailable_not_pass`，断言找不到 SDK 时能力 unavailable 且无模拟 PASS；写主案例正常／边界／回归断言。
- [ ] 运行 `python -m pytest tests/test_doctor.py -q`，确认新代码未实现时测试失败。
- [ ] 实现探针，在合法且受支持的环境跑最小 `cjpm build -V`／`cjpm test`，记录实际版本；模型服务配置只检查存在性，实际请求留 T7。
- [ ] 运行上述单测，再在已配置 SDK 的环境运行 `python -m pytest tests/sdk/test_order_demo.py -q`；基线正常版真实通过，缺陷版出现预期断言失败。
- [ ] 记录环境选择和可选课题组分析取舍；提交本任务文件。SDK 未解决必须报告，不能继续用 MOCK 充当编译。

### Task 2：最小契约与任务记录（S0—S1）

**Files:** Create `nexus/contracts.py`、`nexus/store.py`；Test `tests/test_contracts.py`、`tests/test_store.py`。

**Interfaces:** Produces 严格的 `TaskRecord / CandidateProposal / CandidateRecord / ToolResult / CheckResult / AcceptanceRecord`；模型 proposal 只含允许文件的完整替换内容与需求引用，模型身份／origin／候选 ID 由服务端记录。`RunStore.create_task(baseline_id: str, goal: str, allowed_paths: list[str]) -> TaskRecord`、`RunStore.append_record(task_id: str, kind: str, payload: dict[str, object]) -> str`、`RunStore.get_task(task_id: str) -> TaskRecord`。

- [ ] 写 `test_proposal_cannot_set_verified_or_approval`、`test_task_reloads_without_resetting_attempts`，断言未知权限字段拒绝、任务重载不清零轮数。
- [ ] 运行 `python -m pytest tests/test_contracts.py tests/test_store.py -q`，确认缺实现时失败。
- [ ] 实现第 3.3 节六类记录和只增日志引用；规定摘要包含全部源码、测试和构建配置，排除明确的构建产物。
- [ ] 重跑同命令，验证错误 origin、外任务引用和同任务重复编号不能混入；日志不含密钥。
- [ ] 提交本任务；不引入完整事件溯源或第二套数据库。

### Task 3：真实 MCP 连接与工程读取（S1）

**Files:** Create `nexus/mcp/client.py`、`cang_sight_server/server.py`、`nexus/mcp/tools/workspace.py`、`nexus/execution/workspace.py` 的基线部分；Test `tests/integration/test_mcp_protocol.py`、`tests/test_intake.py`。

**Interfaces:** Consumes T2 契约。Produces `WorkspaceStore.import_project(source: pathlib.Path, build_root: str) -> str`、`WorkspaceStore.read_file(baseline_id: str, path: str) -> str`；`ToolClient.list_tools() -> list[dict[str, object]]`、`ToolClient.call_tool(name: str, arguments: dict[str, object]) -> ToolResult`均为 async 方法。`ToolClient`异步上下文管理器启动／关闭独立 stdio Server。

- [ ] 写 `test_real_stdio_lists_and_reads_fixture`，用独立 Client/Server 读取 fixture，断言工具清单和返回源码与原文件一致；写 `test_ambiguous_build_roots_require_selection` 和越界／符号链接拒绝断言。
- [ ] 运行 `python -m pytest tests/integration/test_mcp_protocol.py tests/test_intake.py -q`，确认协议或工具缺失导致失败。
- [ ] 用固定官方 SDK 实现 initialize、list、call 与关闭；先只注册 list/read/search。本地工具注册不等待远端分析服务。
- [ ] 重跑同命令；额外断言丢失连接的未知写请求不会自动重放，错误参数返回真实错误，stdout 不混普通日志。
- [ ] 提交；此时页面不必存在，也不调用模型。直接调 handler 不能代替协议测试。

### Task 4：独立候选与真实 diff（S2）

**Files:** Extend `nexus/execution/workspace.py`；Create `nexus/mcp/tools/candidate.py` 的 apply/diff；Test `tests/test_workspace.py`、`tests/integration/test_candidate_tools.py`。

**Interfaces:** Consumes T2 `CandidateProposal`、T3 基线。Produces `WorkspaceStore.apply_candidate(task: TaskRecord, proposal: CandidateProposal) -> CandidateRecord`、`WorkspaceStore.diff(candidate_id: str) -> str`。MCP `candidate.apply`统一完成创建和物化，不另外暴露半成品 create。T4 只在单元测试的可信临时目录验证物化；Server 写路由在 T5 接通真实 gate 前默认拒绝，不能临时无策略放行。

- [ ] 写 `test_two_file_edits_publish_all_or_none`、`test_baseline_unchanged_after_candidate`、`test_duplicate_diff_does_not_create_new_attempt`；第二个文件 before_hash 错误时整候选不发布。
- [ ] 运行 `python -m pytest tests/test_workspace.py tests/integration/test_candidate_tools.py -q`，确认未实现时失败。
- [ ] 从同一基线建立 staging，先校验 1—3 个允许文件，再整体发布；禁止测试、配置、绝对路径、链接和越界写入。
- [ ] 重跑同命令，检查 diff 来自实际文件；同名不同目录不混淆，基线摘要不变；MCP 集成测试在真实 gate 未就绪时断言写入拒绝，T5 后再验证允许路径。
- [ ] 提交；候选成功只表示文件修改已物化，不标“修复成功”。

### Task 5：仓颉 Policy 与统一 gate（S2）

**Files:** Create `cangjie/policy/`、`nexus/policy/client.py`、`nexus/policy/gate.py`；Connect T4 的写操作；Test `tests/integration/test_policy_gate.py`。

**Interfaces:** Produces `PolicyClient.decide(request: dict[str, object]) -> dict[str, object]`为 async 方法；`gate_and_execute(request: dict[str, object], action: Callable[[], Awaitable[ToolResult]]) -> ToolResult`为 async 函数。request 至少包含 action、task、路径、候选摘要、参数摘要和剩余预算，来源是可信控制层而非模型自报许可。

- [ ] 写 `test_deny_never_calls_action`、`test_dead_policy_blocks_materialization`、`test_changed_arguments_rejected`，分别断言拒绝时执行计数 0、进程崩溃后候选不落盘、参数变化旧决定无效。
- [ ] 运行 `python -m pytest tests/integration/test_policy_gate.py -q`，确认缺少真实 IPC／规则时失败。
- [ ] 固定 SDK 编译仓颉 JSONL 策略，最小规则为工具、路径、三候选预算和最终接受；Allow/Deny/NeedApproval 有稳定原因码。消息默认最多 64 KiB、单次 2 秒；stdout 只输出协议。
- [ ] 重跑同命令，再测超时、无效 JSON、request_id 错误均拒绝；将 build/test/export 同样接入 Server 侧 gate。
- [ ] 提交；不把应用层 gate 当作恶意代码隔离，不为实现完整规则库延误主链。

### Task 6：真实 build/test 和统一诊断（S2）

**Files:** Create `nexus/adapters/cangjie/verifier.py`、`report_parser.py`、`nexus/mcp/tools/project.py`；Extend `nexus/mcp/tools/candidate.py`；Test `tests/test_report_parser.py`、`tests/sdk/test_verification_tools.py`。

**Interfaces:** Consumes T4 候选与 T5 gate。Produces async `CangjieVerifier.build(subject_id: str) -> CheckResult`、`CangjieVerifier.test(subject_id: str) -> CheckResult`；`parse_test_report(text: str) -> CheckResult`按固定 SDK 实际输出生成用例计数。subject_id 必须由 Store 解析，不能是模型提供的宿主路径。注册 diagnose/build/test。

- [ ] 写 `test_zero_or_skipped_tests_not_pass`、`test_build_fail_test_not_run`、`test_changed_source_invalidates_check`，以及实际 fixture 的 build PASS、断言 FAIL。
- [ ] 运行 `python -m pytest tests/test_report_parser.py tests/sdk/test_verification_tools.py -q`，确认缺实现或错误判定时失败。
- [ ] 实现固定 argv、工作目录、最小环境、每命令初始 90 秒超时、stdout/stderr 合计 2 MiB 上限和进程树收尾；超限记 UNKNOWN，不拿截断日志判 PASS。测试格式先用 SDK 真实输出建立解析样例，不猜报告结构。
- [ ] 重跑同命令，再通过真实 MCP 调用 hand-written candidate 的 apply→build→test；stdout 退出码与测试计数都可查，坏环境为 UNKNOWN。
- [ ] 提交。若没有适用课题组工具，diagnose 仍返回真实编译／测试诊断和“未启用课题组仓颉分析”，不阻塞 T7。

### Task 7：LIVE 模型与三候选修复循环（S3）

**Files:** Create `nexus/llm/provider.py`、`nexus/repair/cegis_loop.py`；Test `tests/test_repair_loop.py`、`tests/live/test_repair_live.py`。

**Interfaces:** Consumes T3 `ToolClient`、T2 Store 与契约。Produces async `ModelProvider.propose(context: dict[str, object]) -> CandidateProposal`、`RepairLoop.run(task_id: str) -> TaskRecord`。Provider 的实际 model_id、origin、原始响应由适配器记录，模型不能指定可信字段。

- [ ] 写 `test_real_fail_feedback_enters_next_prompt`、`test_first_pass_stops_without_forced_retry`、`test_three_candidates_stop`、`test_late_response_cannot_overwrite_cancelled_task`；替身只用于确定性分支。
- [ ] 运行 `python -m pytest tests/test_repair_loop.py -q`，确认缺循环或错误分支时失败。
- [ ] 实现阶段化上下文、严格提案和 MCP 调用；初始单任务 8 分钟、最多三候选，单次模型输出至多 20,000 tokens，服务不支持则明确错误；不截断补丁后应用。模型调用前留记录，不自动重放未知付费请求。
- [ ] 重跑同单测；获准配置就绪后单独运行 `python -m pytest tests/live/test_repair_live.py -q`，A 案例真实完成模型→MCP→build/test。缺配置显式 BLOCKED，不把 skip 算通过。
- [ ] 提交；成功后若有时间接入通过仓颉样例的小量分析工具。可靠失败才进入下一轮，SDK／网络故障停止。

### Task 8：最终接受与导出（S4）

**Files:** Create `nexus/execution/delivery.py`；Extend `nexus/store.py`、`nexus/mcp/tools/candidate.py`；Test `tests/test_delivery.py`。

**Interfaces:** Produces `DeliveryService.accept(candidate_id: str, check_set_hash: str) -> AcceptanceRecord`、`DeliveryService.export(candidate_id: str, acceptance_id: str) -> dict[str, object]`。accept 只供用户 Web／CLI 调用，不注册为模型 Tool；export 必经 MCP 与 gate。

- [ ] 写 `test_changed_candidate_rejects_old_acceptance`、`test_concurrent_export_reserves_acceptance_once`、`test_export_contains_checked_tree`、`test_export_failure_can_be_reconciled`。
- [ ] 运行 `python -m pytest tests/test_delivery.py -q`，确认未实现时失败。
- [ ] 事务内条件占用接受记录并绑定唯一导出 ID；临时生成包、核对 manifest、发布后记完成。重复请求返回同一导出 ID，失败保留可对账状态，不在导出成功后才无条件标记消费。接受默认 30 分钟有效，范围绑定候选与检查集合。
- [ ] 重跑同命令，未通过检查、审批过期、候选改变和重复使用不同参数均不能导出；包中无环境密钥和私有历史数据。
- [ ] 提交；下载的是独立候选，不覆盖原项目。

### Task 9：一页操作与进度展示（S4）

**Files:** Create `nexus/web/app.py`、`templates/workbench.html`、`static/workbench.js`；Test `tests/test_web.py`。

**Interfaces:** Produces `create_app(store: RunStore, loop: RepairLoop, delivery: DeliveryService) -> flask.Flask`。页面通过 `POST /api/tasks`、`GET /api/tasks/{id}`、`GET /api/candidates/{id}`、`POST /api/candidates/{id}/accept`、`POST /api/candidates/{id}/export`操作；后端把副作用路由到既有循环／MCP，不再写另一套执行流程。

- [ ] 写 `test_refresh_only_reads_task`、`test_duplicate_start_returns_same_task`、`test_accept_requires_user_route`和`test_optional_analysis_unavailable_does_not_disable_repair`；断言刷新零模型调用。
- [ ] 运行 `python -m pytest tests/test_web.py -q`，确认缺页面／接口时失败。
- [ ] 实现第 3.4 节单页，先轮询任务状态，不先实现复杂 SSE 恢复；绑定本机地址、校验副作用请求 Origin／本地会话，输出源码按文本转义。
- [ ] 重跑同命令并用浏览器走完整 A＋D，查看桌面双栏及窄屏堆叠；主按钮触发动作，折叠只显示已有内容。
- [ ] 提交；页面可操作后再微调视觉，不增加第二个前端构建系统。

### Task 10：复演、材料与冻结（S5—S6）

**Files:** Create `docs/runbook.md`、`docs/demo-script.md`、`docs/third-party-and-ai.md`；Extend 演示 fixtures；Test `tests/integration/test_full_journey.py`。

**Interfaces:** Consumes T1—T9。Produces 可启动的单入口、三个可选场景的实际范围说明、至少 A＋D、冻结源码包和视频。第三人照 runbook 操作，不要求知道内部模块。

- [ ] 写 `test_full_journey_matches_exported_candidate`，断言主链输出包对应检查版本；增加不同数量／单价输入，固定返回值不能蒙混过关。
- [ ] 运行 `python -m pytest tests/integration/test_full_journey.py -q`，先确认遗漏路径可被测试发现。
- [ ] 修正最后的主链问题，A 场景连续三次真实复演；有余力再加 B/C。每次恢复自产基线，预装 SDK／依赖、检查额度，不预制当前任务回答。
- [ ] 运行默认离线回归 `python -m pytest tests -m 'not sdk and not live' -q`，再显式运行 SDK／LIVE 层；相应 markers 在 T1 配置。另一成员从干净配置按 runbook 启动并下载修复结果。
- [ ] 22 日中午冻结主要功能，生成真实版本／包摘要，录与版本一致的视频；23 日提前提交并下载回验。只提交实际相关文件，缺陷或未知项保留说明。

## 8. 启动与验证入口目标

正式工程完成后拟提供：

```bash
python scripts/doctor.py
python -m nexus.web.app
python -m pytest tests -m 'not sdk and not live' -q
python -m pytest tests/sdk -q
python -m pytest tests/live -q
```

`doctor`默认不调用付费模型、不发送源码。测试缺 SDK 或 LIVE 配置时明确不可运行；不能用全 skip 宣称验证通过。真实 MCP 进程测试属于默认本机集成层，不以直接调用 Python handler 代替。

本轮仅写开发文档，没有安装依赖、运行这些未来命令、编译仓颉、调用模型／MCP或修改产品代码。当前文档存放在本机设计目录；它不证明另一台机器的正式新工程已经建立。

## 9. 首次开工检查与交付判定

开始写产品代码前，只确认四件事：新工程的实际路径与代码来源、可用仓颉 SDK 环境、真实模型配置、主案例。不要先扩写总体文档或完整工具目录。

- [ ] SDK 能真实构建测试自产工程。
- [ ] MCP Client 能真实连接 Server 并读源码。
- [ ] 手工候选可经 MCP 完成 apply→build→test。
- [ ] LIVE 模型可完成 A 主案例，并通过非零目标／回归检查。
- [ ] Policy 能拒绝保护文件修改，故障时不旁路。
- [ ] 页面能操作主链，用户接受后导出的是同一已验候选。
- [ ] 原工程不变，日志／diff 能定位，缺环境不显示成功。
- [ ] 另一成员能够复现；视频与冻结版本一致。

上述全部满足，称“受控仓颉工程的完整修复闭环已完成”；B/C 和可选分析工具独立列出已完成／未完成。不称任意工程、全部算法或普遍修复正确性已经支持。

**开发优先级总结：先真实 MCP 与 SDK，再无模型验证链，再 LIVE 修复，再用户交付，最后扩案例和优化演示。**
