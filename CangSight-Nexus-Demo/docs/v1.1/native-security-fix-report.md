# V1.1 Native 审批与执行安全修复报告

最新补充：分阶段Native执行已落地并通过141项离线、10项真实SDK/HTTP测试；直接shell、可执行文件篡改、硬链接别名、复制程序和SDK调试器启动拒绝见[native-execution-staging.md](native-execution-staging.md)。下文早期探针是历史证据，仍不宣称完整Native隔离或整体V1.1验收通过。

日期：2026-10-18。依据用户最新确认：V1.1不引入Docker，保留Native；Docker不是开发前置条件。没有新增模型、Agent或B/C案例，没有修改原Sympas-Nexus。

## 修复结果

| 问题 | 当前实现与关键函数 | 实际验证 |
| --- | --- | --- |
| 新本机会话凭CSRF就能审批 | `web/app.py:create_app/local_guard/authorize_operator`：本机凭据配对；所有任务/候选/审批/下载API均需已配对会话。公开环境提示和授权页不含凭据 | `test_operator_authorization.py`：有效CSRF仍403；错误/Unicode/多余actor字段拒绝；正确凭据可审批，另一个会话仍403；不是靠按钮disabled保护 |
| 操作者凭据泄漏或伪造 | `execution/ownership.py:RuntimeOwner.operator_key`：随机256位hex，原子0600创建；拒绝symlink、FIFO、非普通文件、过宽权限/错误所有者。密钥不进页面、模型、候选环境或运行记录 | 权限/持久性/链接/FIFO测试；新授权页实际浏览；`operator-auth.test.cjs`验证输入立即清空、不进localStorage、失败不回显 |
| 重启后复用授权会话 | app每次启动生成独立授权epoch，仍保留签名session和CSRF | 同一签名密钥、同一operator key、旧配对cookie，在新app上仍403；只读实例可配对读取但写入503 |
| 临时目录中的运行库未被/Users读保护覆盖 | `runner.py:sandbox_profile(private_root=...)`；`CangjieVerifier._run`显式传递运行库根，排除候选/SDK以外的控制数据读取 | 实际sandbox子进程读取.operator-key、SQLite以及创建硬链接均PermissionError；真实仓颉File.readFrom凭据被拒 |
| 候选可能继承MCP标准输入/描述符 | `run_command`固定stdin=DEVNULL、close_fds=True，环境继续仅由sdk_environment白名单构造 | 真实MCP启动的仓颉生产代码11次读取stdin均EOF，不接收控制流输入 |
| 候选可向控制器等无关进程发信号 | Native profile仅允许向自己/子进程发信号 | 一次性自建sleep进程上的RED/GREEN探针；回归证明无关进程仍存活、候选能结束自己的子进程；未攻击正式服务 |

原CSRF/Origin、本机host/remote_addr限制、候选/检查/需求/修订/动作/批准期限绑定继续保留。配对不把客户端自报actor当可信身份，也不开放MCP approve工具。九工具和仓颉Policy gate未被替换，CEGIS预算和验证/导出主链保持原设计。

## 测试命令和原始证据

原始输出和Native工具记录位于 `docs/evidence/v1.1/native-security/`。

| 命令 / 层次 | 实际结果与证据 |
| --- | --- |
| `.venv/bin/pytest tests/test_operator_authorization.py -q` 首次RED | 4 failed，0.63秒；operator-auth-red.txt，缺接口/默认无授权门禁时失败，不覆盖旧结果 |
| 授权/API/审阅/所有权专项 | 33 passed，5.09秒；operator-auth-regression.txt。合成通过检查只验证HTTP分支，不作LIVE证据 |
| Native读保护、授权、输出边界专项 | 12 passed，7.17秒；native-control-final.txt（其后又补充只读实例与Node用例，已纳入完整离线） |
| `.venv/bin/pytest tests -m 'not sdk and not live' -q` | **133 passed、9 deselected，25.77秒**；offline-final.txt。包括真实MCP/原生Policy、API/存储和15项Node测试；不是LIVE模型验收 |
| `.venv/bin/pytest tests/sdk tests/integration/test_full_journey.py -q` | **8 passed，61.02秒**；sdk-final.txt。真实cjpm、MCP、Policy、HTTP批准/导出、D拒绝及新仓颉边界探针 |
| `.venv/bin/pytest tests/sdk/test_native_operator_boundary.py -q -s` | 1 passed，5.10秒；cangjie-boundary-final.txt。手写生产候选经真实MCP应用，11项测试内均先验证私有凭据读拒绝、stdin EOF、审批数据GET403；主机观测11个403 |
| `.venv/bin/python docs/evidence/v1.1/native-security/revalidate-recorded-proposal.py` | DELIVERED，11.052秒；recorded-proposal-revalidation.txt。重用原始真实模型响应中的同一提案，实际MCP/Policy/cjpm build/test 11通过，新测试操作者批准、完整导出；新增模型请求0 |

完整离线首次收集因SDK目录中引用根测试模块失败，保留offline-import-failure.txt；已改为SDK测试自身显式配对，不要求依赖根测试模块导入路径，最终命令通过。界面只读预览遇到该预览域名历史localStorage任务不属于新空运行库的提示；随后使用独立localhost会话验证首次授权成功，不清理用户浏览器存储、不修改任务来消除提示。

实际仓颉探针是明确标注的手写安全测试，不是模型生成的攻击，也不是一次LIVE修复。其 `cangjie-boundary-summary.json` 和 `cangjie-native-records/` 保存主机观测、真实命令、原始日志、Policy决定与协议记录，不包含.operator-key。SDK测试中的其他手写候选同样不冒充模型输出。

当前原提案重验证task：`b1f08c8297d441719c77b51928abde04`，归档SHA256：`56a7145441ce7558067735b73a2bd417e6959f4c62e913fdfeb8b9611b2e8c59`；明示批准者为 `EXECUTOR_REVALIDATION_OPERATOR`。新runner身份使旧检查失效，脚本先确认旧计划/批准不可继续使用，再真实重验；不是重用旧批准制造新成功。历史一次LIVE、其4313 tokens及金额UNKNOWN的记录保留，不发起第二次付费调用。

## 操作变化与回滚

正式工作台已在检查无活动任务、备份SQLite后重启。用户首次打开或服务重启后，需要在可信本机终端读取 `.runtime/workbench/.operator-key`，仅输入本机授权页。不要把它发给模型/聊天/源码包。具体命令和泄露处理见 `docs/runbook.md`。没有代用户自动提交真实操作者凭据。

新增operator.html/operator.js作为未配对时的独立页面，原workbench.js和原工作台架构未重写；授权后保留既有需求确认、任务刷新、候选审阅及导出。真实UI截图formal-operator-page.png来自正式8765服务；paired-workbench.png来自禁止模型/任务写入的只读8766预览，使用明确合成测试凭据，预览已停止。

若需要回退，应在无活动任务且备份数据后显式回退相应提交；保留现有运行记录与旧发布包。回退会重新暴露已确认的新会话审批缺口，不能继续称安全要求已满足；不要为恢复旧页面体验静默取消门禁或迁移旧检查为新通过。

## 已验证范围与未满足事项

- 已修复、实际验证：未配对HTTP会话不能读取/批准/导出，真实Native候选不能通过所测文件/硬链接/标准输入路径取得凭据，不能通过所测信号路径伤害无关控制进程，合法cjpm流程仍可运行。
- Native仍允许必要的本机TCP，授权页可达；这与“候选取得审批能力”不同，本文没有宣称网络完全隔离。安全来自受测OS限制、凭据隔离、受信授权和同版门禁共同作用，独立候选目录不是安全沙箱。
- 配对是本机持有凭据的操作者授权，不能证明屏幕前的生物身份或逐次点击意图。恶意可信操作者、泄露cookie/凭据、其他macOS IPC/调试通道、脱离进程组的子孙进程及系统级资源耗尽的完整隔离没有得到证明。若强制验收要求这些更强性质，应标记 **BLOCKED / NOT_VERIFIED**，不能用本轮通过项推导全部安全。
- 测试stdout/报告本身仍来自受测进程；Docker或Native均不自动提供不可伪造测试证明。冻结11用例只支持已覆盖业务行为，不是任意仓颉程序正确性或所有恶意输出均可识别的保证。
- M1指定“新Sympas-Nexus”的版本/许可与实际入口集成仍PARTIAL；AC-12另一成员干净环境与实际下载回执、比赛平台及正式提交仍PENDING。未完成这些就不宣告技术总验收或比赛全部完成。

Docker已明确排除出本次V1.1实施范围，不再作为前置条件；上述剩余验收缺口也不以“未装Docker”解释。


## 2026-10-18 补充：进程启动权限未收紧

在本工程独立临时登记案例副本中，以生产 `sandbox_profile(project, private_root=...)` 和剥离密钥后的 SDK 环境，实际执行 `/usr/bin/sandbox-exec -p <profile> /bin/sh -c 'printf NATIVE_SHELL_EXEC_ALLOWED'`：exit 0，输出该固定标记。因此，可信执行入口的 `cjpm build/test` 参数白名单不等于候选子进程无法启动 shell。此为直接 OS 进程权限探针，不是模型攻击，不是完整 Cangjie→shell 链路测试；不读取真实密钥、不请求工作台、不写外部文件。

两种仅 SDK/target 可执行的临时限制规则都拒绝 shell，但同时拒绝启动真实 cjpm（exit 71）。尚未定位受限执行过滤器所需的加载器/工具链权限，不能据此断言 Native 无法实现该约束。未将未通过真实构建兼容性的规则写入 runner，也未降级现有 MCP/Policy 验证。

结论：若将约束第5节“模型不能获得任意 shell”应用到候选测试的子进程能力，该边界当前未满足，必须保持 FAIL/待修复，不能沿用此前文件读取/审批403证据推导其已满足。后续需形成可用工具链执行白名单并实测 Cangjie 子进程攻击和真实 build/test；保留 Native，不将 Docker设为前置。原始命令、exit与输出：`docs/evidence/v1.1/m1-upstream/native-exec-assessment.json`。生产源码未改。


### 后续试验更正与定位

初始进程白名单探针用了JSON的ASCII Unicode转义表示中文路径，而Scheme规则需真实UTF-8路径；因此最初cjpm无法启动的结果不能证明工具链不兼容。修正路径后，逐项放行实际系统工具，最终真实 `cjpm build -V` exit0，`cjpm test`实际运行11项并报告既有基线10通过/1失败（zeroQuantity），不是安全规则导致未执行。原始全部阶段输出均保留，native-exec-assessment.json明确标记旧规则问题与后续utf8结果。

该试验只是探索，尚未投入生产。尤其不能把“拒绝/bin/sh路径”当作彻底禁用shell：为运行测试而放行可写target的执行权限，可能允许将其他可执行文件复制到target后运行。必须先验证并解决这种路径白名单绕过，再决定是否实施。MCP/Policy/Native主链不因探索而被替换。
