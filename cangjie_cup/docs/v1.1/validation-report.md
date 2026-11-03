# CangSight-Nexus V1.1 阶段验证报告

日期：2026-10-18。基于现有正式工程增量开发，原一次 LIVE 的应用行为固定于948e96e；之后完成错误提示、范围冻结、失败状态与输出目录保护补充，当前源码已变化。历史 LIVE 不等同当前整版新模型验收，详见 completion-audit.md。未覆盖原工程，原始Sympas-Nexus参考453文件摘要不变。

| 范围 | 当前结论 | 源码与真实证据 |
| --- | --- | --- |
| M1 基座复用 | PARTIAL | m1-reuse-review.md：现参考无.git、无许可证正文，“新Sympas-Nexus”身份未确认；没有声称完成实际基座网关集成 |
| M2 确认需求与计划 | PASS（登记订单模板） | requirements/service.py；任务/候选/报告绑定、未知规则拒绝、冻结套件回归 |
| M3 完整反馈与预算 | PASS（机制）；LIVE首候选成功 | repair/feedback.py、cegis_loop.py、llm/provider.py；真实SDK失败反馈两候选链，256KiB门禁、三候选/480秒/单次20k输出预算；确定性生成器不计LIVE |
| M4 真实MCP | PASS（已测范围） | 官方Client/Server stdio、九工具严格版本、树/参数/期限、持久请求去重；protocol与owner-protocol原始输出 |
| M5 原生仓颉Policy | PASS | 实际cjc编译的Policy、版本/组件/请求/树/参数/批准绑定、UTF-8上限、两秒IPC及失败关闭；原生与MCP拒绝分开记录 |
| M6 真实验证器 | PASS（固定平台/案例） | 实际cjpm build -V/test，11项用例投影冻结套件，缺结果UNKNOWN；源码/工具链/计划/记录改变使旧检查失效 |
| M7 审阅和完整交付 | PASS（技术与一次LIVE验收） | review.py、delivery.py、archive.py、ownership.py；身份/动作批准、拒绝/取消、完整project/evidence、外部摘要、同一export_id、防重放中断核查 |
| M8 工作台 | PASS（本机技术测试） | web/app.py、workbench.js；需求确认、预检、历史/候选浏览、旧候选禁批、12项Node竞态与实际浏览器截图 |
| 当前版真实模型A/D完整验收 | PASS（一次授权任务） | current-a-live.txt：1 passed/12.33秒；真实deepseek-flash请求1次、首候选、真实MCP/Policy/cjpm、测试操作者批准与完整导出。D为明确手写的独立MCP/原生拒绝探针 |
| 外部成员复现/赛事平台/正式提交 | PENDING | 同机解压回归不能代替外部回执；具体截止时刻未知，不自行假设 |

## 可核对结果

- 完整离线：108 passed、8 deselected，24.62秒；`docs/evidence/v1.1/review/r4-complete-offline-final.txt`。
- 真实SDK/完整HTTP旅程：7 passed，56.84秒；`r4-complete-sdk.txt`。
- 新版真实MCP导出专项：1 passed，12.08秒；`v11-mcp-export-real-sdk.txt`，包含重复请求同导出ID。
- 原生Node竞态：12 passed；`ui-history-final.txt`。API/进程/Policy故障夹具仅证明边界，不充当LIVE成功。
- 无Git的948e96e源码快照：108 passed、8 deselected，26.22秒；`zip-no-git-offline.txt`。无.env，无旧运行记录，重新编译Policy，仅复用工具链。
- SHA256、敏感排除、原目录完整性和本机运行库备份见各阶段integrity/sensitive-scan及版本化source-release证据。最新源码开发快照、后续解压结果在外部开发发布manifest记录，避免自包含摘要。
- 在单独取得用户授权后实际执行一次A任务，真实API请求1次，实际prompt4210/completion103/total4313 tokens；金额未返回，记UNKNOWN。此前离线/SDK阶段调用0，没有将LIVE收集结果当作通过。五秒进程夹具保留真实超时清理断言和总耗时上限；初次失败输出仍保留。

## 使用与限制

启动和成员复现见docs/runbook.md及docs/independent-reproduction.md。下载的V1.1修复包从project/运行，evidence/为原始记录和索引，最终归档摘要在外部回执。历史证据失效会明确阻止继续下载，不自动重跑模型。

当前仅验证macOS ARM64、固定Cangjie 1.0.5/stdx 1.0.5.1、macOS15.4开发SDK和登记自产订单工程；目标/回归逻辑套件复用同11项，不宣称独立隐藏测试、通用语义正确性、任意源码执行安全或多租户认证。B/C、跨文件增强和额外Agent未开发。

本机技术闭环现已通过一次真实LIVE验收，可交另一成员复现已验证范围。M1部分未知及外部复现仍使总验收保留边界，不能宣布比赛全部完成。当前版26秒演示为真实记录的只读帧采集回放，已明确标注不是实时修复录屏，不能冒称另一次模型调用或独立成员审阅。

## 授权后的真实验收（2026-10-18）

- 原始命令：`python -m pytest tests/live/test_repair_live.py::test_live_main_case -q -s`，1 passed/12.33秒；只运行一次，没有自动重试或额外模型调用。
- task_id：752d3444ebc14479a604be1816a7042b；candidate_id：c_e197d277c7a94f4a841cf170ad8842aa。
- 原缺陷基线真实测试10通过/1失败；修复候选实际build PASS/test 11通过/0失败，三条冻结需求均SATISFIED_BY_TESTS；不是任意语义正确性证明。
- 导出ID：58193371f19d419fa05c7ab80ad58ec4；实际ZIP SHA256：20f50e30eb0e587028d3e29ac571580f21668b5fa291252cc09595e2d3eb0765。
- 原生D的拒绝原因PROTECTED_PATH；MCP拒绝受保护测试路径的非法提案。两个探针均为手写，基线清单不变，不声称模型主动产生恶意补丁。
- 批准身份LIVE_TEST_OPERATOR，来自测试操作者，不能作为另一成员独立复现或真人审阅的证据。
- 原始输出与脱敏结构化索引：docs/evidence/v1.1/live/current-a-live.txt、current-live-summary.json；完整原生记录在LIVE证据ZIP的evidence/native/。
- 视频来源与限制：video-provenance.json；实际浏览器截图current-live-page.png。浏览回放会话不同于原批准者，因此不可复用下载授权，这是身份边界控制。

当前版HTTP/MCP联合SDK补充：v11-http-mcp-sdk.txt，1 passed/13.00秒；真实V1.1会话批准与下载、MCP导出/重复ID，未请求模型。


## 最新补充复核

当前补丁后的离线回归125 passed/8 deselected（24.38秒），真实SDK/HTTP回归7 passed（57.61秒），原始输出位于docs/evidence/v1.1/completion/final-offline.txt和final-sdk.txt。较早108项结果仅代表当时版本。需求范围新增13项Node竞态中的范围冻结检查；新增状态分类、错误码与输出符号链接保护。实际端口隔离探针发现既有loopback许可可连接工作台；收紧试验未满足兼容性，已撤回规则，限制仍在，不能宣称任意不可信代码安全。M1和外部复现未完成。所有最新边界见completion-audit.md。


## Native安全修复的最新验证

用户明确V1.1不引入Docker。已新增可信本机操作者配对、未配对全API门禁、运行库私有读保护、候选stdin/FD隔离及无关信号限制。完整离线133 passed/9 deselected（25.77秒），真实SDK/HTTP 8 passed（61.02秒）。真实MCP/Policy/cjpm仓颉探针验证凭据读拒绝、stdin EOF、11次403，非模拟模型攻击；旧真实模型提案重新验证和新批准导出，新增模型请求0。见native-security-fix-report.md及native-security原始证据。一般Native完整隔离仍未证明，M1和外部成员回执仍未完成，不宣告整体验收通过。


## 分阶段Native执行回归补充（2026-10-18）

最新代码真实回归：离线141 passed/11 deselected（26.08秒）；SDK/HTTP10 passed（66.20秒）。真实仓颉候选shell启动、凭据读取均拒绝，stdin EOF，11次HTTP403；冻结产物/硬链接/复制执行/SDK调试器原生探针亦拒绝。请求命令与实际阶段命令分别记录，见native-execution-staging.md。手写/脚本化提案不当作LIVE；不扩展到未测Native安全边界，不宣称M1完整或成员验收已完成。


## M1真实基座分派核心更新（2026-10-18）

已提取固定上游_execute_run及create_run入队/线程流程，注入既有RepairLoop/真实RunStore投影，主页面新任务通过基座入口。自动实测9次真实MCP、4项检查，基线FAIL到候选11项PASS，最终REVIEW_PENDING；生成阶段明确脚本化，非LIVE且无自动接受/导出。离线144通过/12排除，SDK/HTTP11通过（73秒），Node15通过。按设计最小适配范围M1/AC03通过；未引入整份旧平台、不伪造全量复用。完整范围及证据见m1-dispatch-acceptance.md。总目标、当前新版LIVE、一般Native未覆盖安全边界和外部成员验收仍未完成。
