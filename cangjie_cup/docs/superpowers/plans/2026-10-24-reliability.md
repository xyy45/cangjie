# 运行可靠性与两任务真实试评测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 稳定分析／修复展示，支持有来源的同会话分析复用，完善未知状态与版本核验，然后在18次请求总预算内完成两任务试评测。

**Architecture:** 延续现有Flask、原生JS、SQLite与core2，逐项增量修改。缓存只复用已校验的同actor原件，并保留幂等请求别名；修复和评测内部分析默认不使用缓存。试评测先冻结执行身份，逐模式顺序执行，异常和未知状态停止后续模型调用。

**Tech Stack:** 已固定Python3.12／Flask／httpx／MCP、仓颉SDK1.0.5／core2、Node原生测试。

**Spec:** docs/升级改进开发计划.md；docs/superpowers/plans/2026-10-24-reliability-preflight.md。

## Global Constraints

- 第5阶段最终验收后重读总计划再开始产品代码；本计划在其全量回归期间准备，不表示已经实现。
- 用户已授权持续执行，无需重新询问常规实现步骤；同一隔离分支保留全部历史改动，不自动提交／推送。
- 用户已授权business_001、business_030各direct/mcp/cegis共6运行，最多18次DeepSeek请求，每请求6000输出tokens，temperature0.2，原480秒修复／60秒封存验收预算。已用0次。
- 不做额外模型健康请求、不重发未知请求、不另起批次消耗第二份预算。网络／SDK无法执行则保留真实失败、UNKNOWN及未完成分母。
- 不读／打印.env原文；模型与分析配置仅由现有私有加载器在进程内使用，凭据不进入报告／缓存原文。
- 不增加服务、队列、Redis或新前端框架，不放宽仓颉语法／工程保护范围，不变更整体布局与主题。
- 缓存不伪造新的MCP执行，保留时间／来源／原件；强制重新分析必须触发工具请求。

## Review Focus

异步轮询不能覆盖图模式选择；终态不能显示待审批；UNMAPPED空位置不能裁剪越界；缓存不能跨actor／端点／权限范围或复用损坏／未知原件；同批试评测不能混用执行版本或超出18次预算。分别由任务1–5覆盖。

### Task 1: 稳定图模式与终态渲染

**Files:** Modify nexus/demo/static/analysis.js, demo.js；Test tests/analysis-target.test.cjs, tests/demo-race.test.cjs。

**Interfaces:** 显示模式由用户选择（默认变量表／DDG）；保持开始分析、轮询、同源重分析及历史恢复期间选择。`openBound`显式定位仍可选择point与目标行。缺PDG显示不可用，不能退回DDG却保留PDG标题。

- [x] RED：新增真实JS交互测试，DDG开始后收到有效point_graph仍保持DDG；手动point在轮询后仍point；缺图不替换；显式openBound仍点到指定行；DELIVERED／CANCELLED／REJECTED反馈不出现待审阅。
- [x] `node --test tests/analysis-target.test.cjs tests/demo-race.test.cjs`；Expected: 新行为FAIL。
- [x] 移除轮询按结果自动adoptMode，保存模式选择；只显式定位操作可切point。按终态选择修复反馈文案，保留历史失败证据。
- [x] 同命令Expected: PASS；再运行全部Node测试Expected: PASS。

### Task 2: 有界定位与原生进程失败

**Files:** Modify nexus/repair/localization.py, nexus/policy/core.py；Test tests/test_localization.py, tests/integration/test_native_core.py及相关控制器测试。

**Interfaces:** `model_view(report)`输出最多16384字节的明确裁剪投影，保留完整原件context_hash；无法保留长未知元数据时明确省略／不可用，不捏造位置。NativeCoreClient.call在启动RuntimeError时也失败关闭，输出有界的ValueError；控制器不能重发模型请求。

- [x] RED：超长UNMAPPED test_id且locations=[]，裁剪不IndexError、不泄漏大数据、不编造位置；启动依赖RuntimeError时拒绝副作用，原生许可不可用时无第二次模型调用。
- [x] 对应pytest专项Expected: FAIL。
- [x] 实现最小空集／预算处理和安全异常边界，保留CancelledError与进程清理语义；不增加Python许可降级。
- [x] 专项Expected: PASS；原真实SDK反例反馈不受影响。

### Task 3: 同会话有证据分析缓存

**Files:** Modify nexus/analysis/service.py, routes.py, client.py（安全身份辅助如需要）, nexus/demo/static/analysis.js；Test tests/analysis/test_service.py, 新tests/analysis/test_cache.py与JS交互测试。

**Interfaces:** `AnalysisService.create(...,reuse_cache=False)`保留旧默认强制新执行，按需返回cache_hit与原记录时间。请求别名索引保存actor_id／request_key／输入指纹→job；复用必须同actor、同源码SHA／文件名／origin／criterion、当前profile和安全工具身份摘要、COMPLETE、300秒内，且`get`原件核验通过。内部修复／评测不启用缓存。

- [x] RED：同actor相同完整源码命中不再调用工具；不同actor／token作用域／端点／profile／line／filename／源SHA均不命中；PARTIAL／FAILED／IN_DOUBT、TTL到期和强制重分析不命中；同key换源仍冲突；原件被改时拒绝，不假成功。
- [x] RED JS：首次同源“分析”可请求复用，点击“重新分析”强制工具；缓存命中保留旧时间和可见来源，不显示成新执行。
- [x] 专项Expected: FAIL；不调用真实远端或模型。
- [x] 使用现有SQLite短事务绑定别名，完整原件核验在复用前执行；凭据仅进入安全摘要计算，不保存／打印原文。保留单活动租约／impact互斥与旧request_key读取行为。
- [x] 专项Expected: PASS；回归原分析、callgraph、point、impact与恢复测试。

### Task 4: 统一试评测执行身份与自检

**Files:** Modify nexus/benchmark/runner.py, cohort.py, report.py, __main__.py；nexus/execution/environment.py／scripts/doctor.py如需；Test benchmark的unit／SDK／CLI测试及doctor。

**Interfaces:** 新计划版本绑定`implementation_hash`，身份包含实际nexus／MCP执行Python源码、requirements.lock、依赖版本、固定SDK与core2身份（不含.env）。相同身份随STARTED、结果和批次报告重建，源码／原生／依赖变动不能标同版本可比；失败且无候选的运行也覆盖。历史文件只读保留，不升级成新版本成绩。

- [x] RED：无候选失败行仍绑定执行身份；异版本六行不能LIVE_COMPARABLE；STARTED／result／plan身份错配拒绝；报告期间源码变化拒绝；CLI dry-plan零模型调用。
- [x] 保留完整分母、原件目录链接拒绝、同模型／同预算校验、usage未知不填0、成本无价格则UNKNOWN。
- [x] 扩充本机自检确认core2版本／构建身份与修复指令，不以配置存在冒充API连通；缺失SDK／core失败关闭。
- [x] 专项与真实SDK FIXTURE三模式集成Expected: PASS，均不消耗模型预算。

### Task 5: 验收后执行唯一真实试评测批次

**Files:** 新docs/demo/upgrade-phase6-verification.md及validation/upgrade-phase6；最终更新阶段4证据和总计划。

- [x] 独立审阅任务1–4，修正Important，完成整个离线Python／Node／diff检查；必要浏览器验证模式、缓存和终态。工具链及代码冻结后再调用模型。
- [x] 只读配置存在性、实际SDK／core检查通过；不发送额外模型请求。创建一个新的明确LIVE输出目录，不复用已开始目录。
- [x] 通过CLI运行两任务×三流程，`--max-model-requests 18`；每项只执行一次，UNKNOWN／异常停止后续调用。记录实际STARTED、usage、失败／未知，不自动另开付费批次。
- [x] 从同一完整计划和原件重建JSON／Markdown报告，验证实际请求总数≤18，保存6项分母；不完整批次不得标成功比较。无显式价格时费用UNKNOWN。
- [x] 向用户报告每任务／流程结果、实际请求数／tokens／耗时、未覆盖能力；2合成任务仅是试评测，不给统计优势或工业泛化结论。
- [x] 重读总计划。只有全部阶段要求与真实证据齐全才完成总目标；不能因阶段5／6功能完成而漏掉真实试评测。

## 最终验证命令

- `DEEPSEEK_API_KEY=upgrade-test-placeholder DEEPSEEK_BASE_URL=https://fixture.invalid DEEPSEEK_MODEL=test-model ../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`：Expected 全部离线PASS，live未运行数披露。
- `node --test tests/*.test.cjs`：Expected PASS。
- `git diff --check`：Expected PASS。
- 执行真实批次仅在上述验收后，取消placeholder环境并由现有加载器读取本机获准配置。不得把密钥写入命令／日志。

Final acceptance:617PythonPASS/1live-deselected738.92s,100NodePASS,diffcheckPASS;3Important RED→GREEN. UniqueLIVE6/6PASS,6requests/18cap,40579tokens,149.845s,costUNKNOWN; archive688files replay identical report hash8da82b02…bc754. Tests, current-scope rulings and deferred minor are recorded in upgrade-phase6-verification.md and ledger. No automatic new model batch, Git commit or push.
