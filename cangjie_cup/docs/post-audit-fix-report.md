# CangSight-Nexus 审计后最小质量修复报告

日期：2026-10-17（Asia/Shanghai）。基准：`docs/plan-compliance-audit.md` 的 F1～F4。修复源码提交：`a20b21f84ff1cd87b452cfa111f279a9da0f4386`。

**本轮指定的 F1～F4 修复和验证已完成，可以交给其他组员独立复现。** 这不是“外部独立验收已通过”，也不是“比赛项目全部完成”。本轮真实 DeepSeek API 调用数为 **0**，没有重新进行 LIVE 模型修复；原有 LIVE 历史证据保留。

## 1. 逐项结果

| 问题 | 修复结果 | 验证与边界 |
| --- | --- | --- |
| F1 源码ZIP依赖.git | 测试在无.git目录检查实际 `.gitignore` 的 `.env` 排除规则；存在本工程.git时继续运行真实check-ignore及索引检查，索引命令必须得到“未跟踪”exit1，不能把任意Git错误算通过 | 旧测试在无父级仓库目录实际exit128并失败；修复后发布包无.git全离线回归60通过。另测无Git调用、删除排除规则会失败、真实Git强制跟踪.env会失败。最终ZIP逐成员检查不含.env/真实密钥，规则检查不冒充归档检查 |
| F2 workspace.search | 经独立官方MCP stdio Client/Server实际调用；未改变搜索实现 | 有效命中、未命中、空query拒绝、105行命中截断为100条；逐项验证相对文件路径、1起始行号和完整预期行内容；工具发现精确断言九项集合 |
| F3 安全断言 | 权限字段测试使用先验证合法的基础提案，逐字段确认唯一extra_forbidden错误；合法MCP提案在独立Server中遇真实不存在的Policy执行文件时拒绝 | 无候选目录/记录、轮数0、基线摘要不变；分别测试仅错误request_id、仅错误arguments_hash，并用正确响应作阳性对照；额外验证64KiB超限与原生Policy预算0/4拒绝 |
| F4 页面迟到响应 | 保留单页轮询架构；为刷新增加递增代次及捕获taskId，任务/候选响应和错误回写前核对归属；开始新任务立即废弃旧刷新；接受流程捕获候选并约束迟到接受/导出结果 | 直接加载发布workbench.js，用Node原生vm/node:test和可控网络/DOM夹具验证6个确定性竞态。修复前5失败/1通过，修复后6通过；旧任务、旧候选、旧错误、开始POST等待期间、迟到接受、迟到导出均覆盖，并确认当前候选接受/导出仍使用正确ID和hash |

页面竞态测试是对实际JS代码的确定性单元测试，不是新浏览器LIVE录制，也不声称夹具中的PASS来自SDK。MCP搜索测试实际跨进程调用，未直接调用handler。Policy响应绑定测试使用明确的故障IPC夹具；原生预算、D拒绝与SDK集成另行真实执行，未用夹具冒充原生成功。

## 2. 修改文件

产品源码仅修改：

- `nexus/web/static/workbench.js`：响应代次/任务归属检查、当前候选快照及接受/导出迟到保护。没有修改后端MCP-CEGIS主链、Policy规则、runner或Verifier。

相关测试：

- `tests/test_provider_config.py`：发布目录排除检查、真实Git检查及反向断言。
- `tests/integration/test_mcp_protocol.py`：精确九工具发现、真实search四类查询与内容核对。
- `tests/integration/test_candidate_tools.py`：以合法提案替代空参数“死Policy”测试，真实MCP会话拒绝落盘。
- `tests/integration/test_policy_gate.py`：分离响应绑定错误、消息大小和原生候选预算边界。
- `tests/test_contracts.py`：隔离非法权限字段，不再由空edits触发无关错误。
- 新增 `tests/workbench-race.test.cjs`、`tests/test_workbench_race.py`：6个原生JS竞态场景，纳入默认pytest，无npm包或新前端框架。

文档/证据：

- `docs/runbook.md`：说明默认测试需要Git命令和Node.js18+，发布目录不要求.git。
- 保留并纳入快照 `docs/plan-compliance-audit.md`（审计历史，不改写其结论）。
- 新增本报告、`docs/evidence/post-audit/` 下RED/GREEN、回归及归档核验记录；SDK测试同时生成pytest-71的正常/缺陷原始日志。

未开发B/C、未增加模型或Agent、未更换构建验证机制。已有 `.DS_Store` 未跟踪文件没有纳入提交或源码ZIP，也没有删除用户文件。

## 3. 实际测试命令与结果

以下命令在正式工程根执行。完整输出均保留，非根据交付报告倒推。使用Python3.12.14、pytest9.1.1、Node v26.3.1、Cangjie1.0.5/stdx1.0.5.1、macOS ARM64及15.4开发SDK。

| 命令 | 实际结果 | 输出 |
| --- | --- | --- |
| `.venv/bin/python -m pytest /private/tmp/cangsight-post-audit-red/tests/test_provider_config.py::test_project_dotenv_is_git_ignored -q`（修复前测试副本） | 1 failed；git exit128；正确复现F1 | `docs/evidence/post-audit/f1-red.txt` |
| `node --test tests/workbench-race.test.cjs`（修复前JS） | 1通过、5失败；无skip | `docs/evidence/post-audit/f4-red.txt` |
| 同上（修复后JS） | 6通过、0失败/取消/skip | `docs/evidence/post-audit/f4-green.txt` |
| `.venv/bin/python -m pytest tests/test_provider_config.py tests/test_contracts.py tests/integration/test_mcp_protocol.py tests/integration/test_candidate_tools.py tests/integration/test_policy_gate.py tests/test_workbench_race.py -q` | 24 passed，4.44秒 | `docs/evidence/post-audit/targeted.txt` |
| `.venv/bin/python -m pytest tests -m 'not sdk and not live' -q` | **60 passed、5 deselected，9.64秒** | `docs/evidence/post-audit/offline.txt` |
| `.venv/bin/python -m pytest tests/integration/test_mcp_protocol.py tests/integration/test_candidate_tools.py tests/integration/test_policy_gate.py -q` | **14 passed，4.65秒**；真实MCP与原生Policy测试 | `docs/evidence/post-audit/mcp-policy.txt` |
| `.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py tests/test_web.py::test_native_policy_probe_denies_and_preserves_frozen_files -q` | **5 passed，23.37秒** | `docs/evidence/post-audit/sdk-a-d.txt` |

初次针对性测试出现1失败/23通过：空查询由官方MCP SDK schema拒绝，错误文本为“should be non-empty”，并不含测试先假定的query字段名。保留 `targeted-initial.txt`，随后改为核对ERROR、非空错误及空data，不为测试修改产品错误行为。

SDK层包括正常/缺陷仓颉断言、错误语法build FAIL后test NOT_RUN、真实MCP候选build/test、用户接受/导出/下载同版，以及原生Policy D拒绝。A验证使用明确标注的手写候选来回归工具链，不将它称为新的DeepSeek LIVE成功；模型主链后端未改，原有真实LIVE记录未覆盖。

## 4. 无.git发布目录独立回归

测试对象是下节**最终源码ZIP本身**，不是手工复制当前工作树。解压目录：

`/Users/jadya/Documents/CangSight-Workspace/02-开发工程/.cangsight-post-audit-repro-apr08yng/CangSight-Nexus`

- 解压前ZIP无.git、.env、.runtime、.venv；目录及父级无Git仓库，`git rev-parse --show-toplevel` 实际exit128。
- 未复制模型配置、旧数据库或任何运行任务记录。
- 只通过符号链接复用本机已固定的SDK/stdx目录，使用现有Python依赖环境；在解压源码根实际执行 `python scripts/build_policy.py`，重新编译本目录原生Policy，输出为 `nogit-policy-compile.txt`。
- 在该目录执行 `<正式工程>/.venv/bin/python -m pytest tests -m 'not sdk and not live' -q`：**60 passed、5 deselected，9.69秒**，exit0。证据：`docs/evidence/post-audit/nogit-offline.txt`。
- 同目录执行 `<正式工程>/.venv/bin/python -m pytest tests/integration/test_full_journey.py tests/test_web.py::test_native_policy_probe_denies_and_preserves_frozen_files -q`：**2 passed，7.96秒**，真实SDK A链及原生D保护。证据：`nogit-a-d-journey.txt`。

这是“同机无Git元数据源码发布环境”的回归，**不是另一机器从零安装依赖的独立成员验收**。Node/Git命令仍需可用；无.git不等于机器没有Git程序。其他成员应按runbook安装自己的锁定依赖和运行时，不复制本机虚拟环境/SDK软链接/配置。

## 5. 新源码交付ZIP与完整性

路径：

`/Users/jadya/Documents/CangSight-Workspace/02-开发工程/CangSight-Nexus/.runtime/releases/CangSight-Nexus-source-post-audit-a20b21f.zip`

- SHA256：`42c50916b9ee132b113304586bd60ba61c65efe1106386cc20636ceae0b65964`
- 大小：794081字节；文件条目167个。
- 由 `git archive --format=zip --prefix=CangSight-Nexus/ ... a20b21f84ff1cd87b452cfa111f279a9da0f4386` 生成。
- `ZipFile.testzip()`通过；所有文件路径与该提交的git ls-tree一致，逐文件字节与git show一致。
- 逐成员排除.git/.env/.runtime/.venv/__pycache__/.DS_Store；`.env.example`保留供成员自行配置。实际API Key仅在内存中用于字节扫描，未显示、未记录、未发现于归档成员。
- 重新比较原始Sympas-Nexus开工清单：**453文件SHA256全部一致，无新增**。证据：`docs/evidence/post-audit/final-integrity.json`。

元数据在 `docs/evidence/post-audit/source-release.json`。本报告、无.git回归结果和最终核验记录在固定源码ZIP产生之后生成，作为旁附交接材料保存，不回写已验ZIP，避免改变已验证的归档摘要。旧源码ZIP、旧操作视频和历史LIVE证据保留，不覆盖为本轮新测试。

## 6. 剩余风险与交接判断

可以开始团队独立复现验收：F1发布包回归阻断已排除，九工具注册精确断言和search成功路径已有真实协议证据，指定权限边界与页面竞态已有针对性验证。

仍需明确：

1. 另一成员/另一主机的从零安装、启动、LIVE修复及下载回执仍为 **PENDING**；本机无.git验证不替代它。
2. 本轮未请求DeepSeek；当前余额、模型权限和网络即时状态未重新验证。若后续需要付费LIVE复测，应先说明原因并取得用户授权。
3. 当前支持macOS ARM64+Cangjie1.0.5/stdx1.0.5.1+macOS15.4开发SDK；历史系统exit9风险仍保留，未承诺其他系统兼容。
4. JS竞态是确定性单元级验证，没有重新录制浏览器完整LIVE操作；后端同版接受/导出及原生SDK另有真实集成回归。
5. 审计中更广的同名不同目录、480秒总预算、所有HTTP故障及多轮相同反馈停止等完整边界矩阵未全部扩充。本轮优先修复指定F1～F4和关键权限边界，未为增加数量扩展功能。
6. 接受/下载仍有既定30分钟有效期；比赛平台、准确截止时刻、正式提交和平台回下载仍为 **PENDING**。本轮不宣告完整比赛交付完成。

交接时同时提供新源码ZIP、本报告、`docs/independent-reproduction.md`和无.git回归证据。成员使用自己的配置，保留实际运行ID、原始日志、Policy拒绝结果及下载摘要后，再判定外部验收是否通过。
