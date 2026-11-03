# M1：现有能力与Sympas参考基座核查

最新状态：本报告记录较早来源核查/初版派生模块。当前已补真实基座分派核心及主页面入口，按设计最小适配范围通过M1/AC03，证据与范围以[m1-dispatch-acceptance.md](m1-dispatch-acceptance.md)为准；不宣称整库接入或新版LIVE通过。

日期：2026-10-17。依据用户补充确认：继续现有正式工程，Sympas-Nexus-GitHub只读参考，不覆盖、不整库迁移；无法确认“新框架”身份时明确保留未确认，不阻塞其他模块。

## 版本与许可

参考目录：`/Users/jadya/Documents/CangSight-Workspace/01-原始代码/Sympas-Nexus-GitHub`。`git rev-parse --show-toplevel`实际exit128；未发现.git元数据，不能给出可验证commit，也不采用README中可能出现的提交号作为证明。plugin.json声明版本1.0.0、license=MIT；递归检查未发现LICENSE/COPYING/NOTICE文件。声明与完整许可文本/版权来源核实是不同证据，尚不据此迁移其源码。

以453文件规范SHA256清单标识本地快照，清单总摘要 `8284982d803b30488a853108f9c0ac821e71879c762f6dc8ddc524fae917d107`。与本工程开工清单完全一致。本次只用AST/文本读取接口，未import或运行参考应用，没有启动医疗/CodeArts入口，没有在原目录写pycache或数据库。

## 复用清单（实际与可借鉴分开）

| 参考能力 | 实际检查的接口 | 正式工程当前实现 | 判定/后续 |
| --- | --- | --- | --- |
| 编排 | nexus/core/dag_planner.py:DAGPlanner、DAGNode，技能依赖、并发、重试 | nexus/repair/cegis_loop.py:RepairLoop是独立串行修复状态机 | 无直接导入/复制；只借鉴阶段概念。不引入第二修复循环，不把DAG重试用于未知付费/写请求 |
| 网关 | nexus/gateway/app.py:create_app(run_store=...)，run/cegis、查询和事件路由 | nexus/web/app.py:create_app为本工程Flask入口 | 不是参考网关已挂载的cangjie能力；AC03真实基座入口测试缺失，不能标完成 |
| 持久运行库 | nexus/gateway/run_store.py:RunStateStore.create_run/update_run/get_run/append_event/get_events/recover_running_runs | nexus/store.py:RunStore使用自己的tasks/records SQLite | 参考确有SQLite持久库，不是纯内存；但update_run无expected_status CAS、状态更新与事件各自提交，初始化默认执行恢复，不能直接替换当前库或维护两份可写状态 |
| 审计索引 | nexus/audit/eat_db.py:EATDatabase.persist_frame/load_session_frames/list_sessions | 当前只增JSON+SQLite索引和摘要 | 未直接复用，不另加EAT事实库；若以后引入只能作投影，不反向决定任务成功 |
| MCP/Policy/仓颉验证 | 参考框架旧工具/技能接口与HTTP服务线索 | 正式工程独立官方stdio Client/Server、原生Policy和真实cjpm | 这三项已实现并验证，应保留；不能因同名目录或相似技术栈称“直接复用了参考代码” |

原始路径/类/公开方法及文件SHA256见 `docs/evidence/v1.1/m1-reference-inspection.json`。全文搜索正式产品代码未发现nexus.gateway、RunStateStore、DAGPlanner、EATDatabase或Sympas引用，与既有third-party-and-ai.md“独立创建、未直接复用”一致。

## M1验收判断

- 当前已满足CangSight自身的统一任务ID、MCP记录、候选、检查、SQLite持久化和本机网关基础；不应重复开发这套修复内核。
- 尚不能证明设计所称“新Sympas-Nexus”身份，也没有通过实际原框架网关发起仓颉任务的集成测试。因此M1整体为**PARTIAL / 基座身份与接入未确认**，不是FakeAdapter测试通过即可完成。
- 暂不为了制造复用名称新增空适配器，或因参考库已有SQLite就搬库。后续若确定实际基座版本及可迁移许可，应采用最小网关/状态适配；唯一任务事实源、CAS、事件事务和原控制链不得退化。
- 上述不确定性不阻塞需求、反馈、版本契约、验证评审、交付及界面独立增量；按用户指示继续推进。


## 2026-10-18：指定 GitHub 来源的实际核查（取代上文来源未知结论）

用户指定仓库 `https://github.com/nuptpisa/CangSight`、目录 `Sympas-Nexus/`。通过真实 `git ls-remote`、clone 对象及 `git show` 核查，未采用 README 中的版本串代替 Git 证据。

- 查询时 main 的固定提交：`5db0c7eeeb6a62812fc04e9e88497339fed5e11f`。
- 该提交的 Sympas-Nexus Git tree：`e5b2d43086b274a963a48ec5c976d1b7acc450ec`。
- 该目录最近修改提交：`300eb8ff012dec91a6541aaf24ec52e3bbea1f76`。这不是仓库 main HEAD，两者不能混称。
- 固定版本上游 447 文件与本地对应文件逐字节 SHA256 全部相同，0 改动、0 上游独有。本地另外 6 份说明/比赛材料的路径见原始 JSON。因而可确认本地包含该固定版本完整子目录；不能据此推断它最初下载自哪个历史提交（相同 subtree 可能跨多个 commit）。
- 本地原参考 453 文件与开工哈希清单完全一致，未在原目录 import、运行或写入。

### README、许可与版权

上游 README 将其描述为安全分析编排平台，包含 OODA、SF、HW、旧 CEGIS 和网关；并非现成仓颉修复应用。项目 pyproject 版本为 0.1.0，插件版本为 1.0.0，不能用它们替代固定源码身份。

仓库根 LICENSE 是 Apache License 2.0；另一个 LICENSE 位于 HW-CodeArts/CangSight-main。指定 Sympas-Nexus 子目录没有 LICENSE/COPYING/NOTICE，但插件元数据声明 MIT。根许可证与插件元数据存在声明差异；未发现足以确认 MIT 授权范围的正文，也不将 Apache 附录的 `[yyyy] [name of copyright owner]` 占位符当成实际版权人。已保存两份原始许可正文和插件声明，未伪造归属。该问题需要在分发改编上游源码前明确记录和处理；不等于断言仓库没有许可证，亦未作法律结论。

固定来源链接：
- [源码目录](https://github.com/nuptpisa/CangSight/tree/5db0c7eeeb6a62812fc04e9e88497339fed5e11f/Sympas-Nexus)
- [根许可证](https://github.com/nuptpisa/CangSight/blob/5db0c7eeeb6a62812fc04e9e88497339fed5e11f/LICENSE)
- [插件声明](https://github.com/nuptpisa/CangSight/blob/5db0c7eeeb6a62812fc04e9e88497339fed5e11f/Sympas-Nexus/.claude-plugin/plugin.json)

### 真实接口及接入评估

`nexus/gateway/app.py:create_app(*, run_store=None)` 只提供运行库注入；没有仓颉能力、handler 或 Blueprint 注入参数。真实入口 `POST /agents/runs` 在创建旧状态后启动 `_execute_run`，后者只分派模块私有 `_TEAM_HANDLERS` 中四类旧任务。`POST /run/cegis` 则直接构造旧 RepairContext 并调用旧 CEGISRepairLoop，不能当成当前 MCP-CEGIS 入口。原有 `/agents/approve/...` 与运行批准路由亦不能直接暴露给当前候选。

`RunStateStore` 是实际 SQLite，并非纯内存；其 `update_run` 无当前任务 CAS 语义，不能直接替换本工程 RunStore。两工程均叫 `nexus`，同进程直接导入会造成包遮蔽或导入错误。`create_app` 的模块导入静态耦合多个旧领域，不符合设计“不导入整份旧网关应用、不默认启用旧领域入口”的直接挂载方式。

在临时固定版本副本、剥离密钥环境、禁止写 pycache 的进程中实际执行 `from nexus.gateway.app import create_app`：exit 1，首个缺失依赖为 `flask_cors`；没有调用 factory、启动服务、运行模型或伪造成功。它证明当前正式工程锁定环境不能原样加载指定网关，不证明安装一个依赖即可完成接入。未为了通过 import 给正式环境安装整个旧平台依赖。

最小后续方案应先在固定版本外部副本中拆出真正可独立挂载的网关扩展点，或维护具有明确来源和许可通知的小型网关派生模块；只注册 `cangjie-repair`，将入口委托给当前需求确认/执行服务，沿用操作者、CSRF、所有者保护和同一任务事实库。必须再用该真实入口走 MCP/Policy/Native cjpm、查询/重启及拒绝测试。只有新建同名路由、改私有 handler 字典或用 FakeAdapter，均不能替代这项验收。本轮没有实现或验证上述方案，不宣称其已可用。

### 实际复用判定与状态

对上游 Python 与正式工程 nexus/cang_sight_server 作完整字节及函数 AST 比较：没有完全相同的 Python 文件或非平凡函数。结合既有导入/人工接口核查，当前未证实直接代码复用，现状仍是独立实现及设计借鉴。AST 不同不能证明从未发生改编，比较结果不充当原创性证明。

来源核查 **PASS**；实际基座网关到仓颉修复的 M1/AC-03 **BLOCKED（尚未实现与验收）**。当前不是“仍找不到来源”，实际障碍是网关/依赖/审批与唯一状态库适配仍未完成。不得把本轮独立工程回归计为基座集成测试。

原始证据：`docs/evidence/v1.1/m1-upstream/` 中 source-comparison.json、gateway-interfaces.json、reuse-comparison.json、gateway-import-probe.txt、original-integrity.json；README、pyproject、plugin 和 LICENSE 原文同目录保存。无 Docker、无付费模型请求、无原库改动。


### 本轮其余主链回归（2026-10-18）

- `.venv/bin/python -m pytest -m 'not sdk and not live' -q`：133 passed、9 deselected，27.38s；原始输出 offline-regression.txt。
- `.venv/bin/python -m pytest tests/sdk -m 'sdk and not live' -q`：7 passed，51.30s；原始输出 sdk-regression.txt。此命令范围为 tests/sdk，不能与以前包含其他目录的8项验收混称。
- `node --test tests/operator-auth.test.cjs tests/workbench-race.test.cjs`：结果见 node-regression.txt。

这验证当前独立工程的既有能力；不计作真实基座入口、当前新版付费 LIVE、团队独立复现或比赛提交通过。M1接入、未覆盖Native安全边界、成员复现与外部提交仍保留原有未完成状态。未重打包旧技术交付物，避免把新核查材料误标为已完成M1的发布版本。


## 2026-10-18 用户许可处理指令后的范围复核

用户指示优先采用根Apache-2.0，同时检查网关例外。已检查仓库根/子目录层级全部许可证路径、README、pyproject、插件声明及gateway全部源码中的SPDX、license与版权标记。指定目录及其父目录无另行LICENSE/COPYING/NOTICE；gateway源码未发现MIT/SPDX/版权例外。插件MIT字段保留为插件元数据差异，不据此把gateway改为MIT。根据用户处理指令及根许可覆盖的通常工程约定，后续最小网关派生代码采用根Apache-2.0并附原文；没有材料证明网关被明确排除。此判断不声称已获得维护方单独确认，也不补写作者/版权年份；若出现明确网关例外必须停止使用并记录。

实际复用时须保留根LICENSE、来源仓库、固定commit、原始文件路径/哈希，修改文件注明变更。仓库未发现NOTICE；不能制造一份“原始NOTICE”。本项目可另写来源说明，明确这是新增归属记录，不冒充上游声明。原始范围核查输出：license-scope-review.txt。M1尚未实现；许可处理不再作为要求用户回复才能开始适配的前置条件。


## 最新实施状态：最小派生网关已实现

前述“未直接复用/尚未实现”是适配前快照。现已新增真实上游脱敏函数及查询路由结构的最小派生网关；同任务ID、真实MCP/Policy/cjpm、重开库历史及审批门禁测试通过。M1最新状态为PARTIAL，不称完整原始网关create_app已启动或其入口验收通过。来源、命令、原始证据及验收边界见m1-integration-report.md。Native子进程边界仍未修复，不标V1.1总体完成。
