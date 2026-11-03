# 第1项：业务规则辅助生成验收记录

日期：2026-10-25。状态：已验收（受限工程闭环；真实生成质量局限见下）。当前提示v2全量Python717／Node108通过，浏览器确认、实际模型草案与SDK衔接及五份原件离线重放有证据。跨文件模型本次过度澄清，使用手动回退验证，未宣称该例自动生成成功。

## 已实现的使用流程

上传单个.cj或现有受限同包工程→读取函数／选定1至3个生产文件→单独同意生成时发送→生成草案→查看摘要、假设、疑问、测试和规则→显式填入编辑框→核对／修改→原有确认冻结→修复／独立搜索→人工审阅／交付。

已有测试或规则时，首次点击“应用草案”只提示替换，第二次点击“确认替换并填入”才请求应用预览。编辑、切换来源、函数、范围或关闭窗口会使待应用状态失效。草案不会自动覆盖编辑器、勾选修复确认或创建修复任务。

首版维持Int64／Bool、同包、最多3个生产文件的边界。单次生成最多6000输出tokens／120秒，响应最多1MiB；每个会话用户每份上传最多3个新草案请求。此产品交互上限不等于批准代理执行付费联调。

## 服务端依据

- 草案绑定服务端上传ID、版本、原始源码摘要、函数签名、需求、允许范围和契约版本；工程上下文只含选定生产源码。
- `POST /api/uploads/repair/<upload>/rule-drafts`登记意图，后台CAS认领；GET列表／单项只读；`POST .../<draft>/apply-preview`重新核对绑定，返回编辑内容及来源引用。
- 请求状态`CREATED→STARTED→SUCCEEDED/FAILED/IN_DOUBT`与草案内容`DRAFT_READY/NEEDS_CLARIFICATION/INVALID`分开。成功HTTP请求可能产生不可用草案。
- 同key同输入返回原记录；待核实的同输入请求不能换key或重传同源上传绕过。不确定请求重启时保留IN_DOUBT，不自动重发；不能据此承诺上游只收费一次。
- 保留input/request/response/result四份不可变数据及摘要。请求保存的是完整JSON对象内容；HTTPX实际序列化字节可能不同，未宣称逐字节网络抓包。
- 例子经既有严格类型、target／regression、冲突检测校验；v1规则经既有表达式、参数域、溢出和例子一致性校验。疑问未解不能应用。
- `business_verified=false`始终保留。模型同源生成的例子／规则自洽不证明业务正确；用户核对后冻结实际确认版本，保存原生成hash、确认hash及edited_by_user。
- 交付工程只额外准入`verification/rule-draft/`内五个固定JSON数据文件；不放宽任意JSON、脚本或未知嵌套路径。生成原件不进入后续修复模型上下文。

## 已取得的验证证据

| 验证 | 实际结果 | 证据 |
|---|---|---|
| 契约初始TDD | RED33失败→相关46通过，0.69秒 | validation/next-phase-1/rule-contract-{red,green}.txt |
| 独立账本TDD | RED13失败／33通过→46通过，0.94秒 | validation/next-phase-1/rule-service-{red,green}.txt |
| 提供器／路由／上传兼容 | 109通过，3.38秒 | 执行账本Task3原件 |
| 确认绑定相关 | 117通过，4.07秒 | validation/next-phase-1/rule-confirm-green.txt |
| SDK完整闭环 | 单文件／两文件2通过，43.46秒 | validation/next-phase-1/rule-sdk-flow.txt |
| 元数据响应记录大小 | 复现合法线上大小被本地重复封装误拒绝后修复；12通过，0.88秒 | validation/next-phase-1/rule-record-limit-green.txt |
| 页内替换确认 | RED3失败／5通过→专项24通过，88.34毫秒 | validation/next-phase-1/rule-inpage-{red,green}.txt |
| 全量Node | 108通过，224.28毫秒 | validation/next-phase-1/next-phase1-node.txt |
| 首次全量Python | 711通过／1失败／1 live未运行，799.18秒；失败为运行中注释编辑触发执行版本保护 | validation/next-phase-1/next-phase1-python.txt |
| 失败项冻结后单独复跑 | 1通过，62.97秒 | validation/next-phase-1/next-phase1-benchmark-rerun.txt |
| v1源码冻结后全量Python | **712通过／1 live未运行，802.12秒，退出0** | validation/next-phase-1/next-phase1-python-frozen.txt |
| 浏览器HTTP夹具链路 | 查询／预览／两次确认替换／编辑／独立修复确认／进入工作台完成 | browser-verification.json、browser-draft-applied.png、browser-confirmed-workbench.png；鼠标派发超时后使用文档支持的原生键盘API |
| 真实模型第1批 | 已批准并完成3次，3981tokens；DRAFT_READY=0，INVALID=2，NEEDS_CLARIFICATION=1 | live-result/report.md、原件、approval／attempt／执行源码快照 |
| 提示v2专项 | RED3失败／1通过→98通过，6.11秒；历史三份校验结果不变 | rule-draft-schema-{red,green}.txt |
| 提示v2完整回归 | **Python717通过／1 live未运行，803.50秒；Node108通过，196.40毫秒** | phase1-prompt-v2-python.txt、phase1-prompt-v2-node.txt |

SDK测试实际使用固定仓颉SDK1.0.5及core2，完成冻结、候选编译／公开测试／独立搜索／人工接受夹具／ZIP原件验证；草案HTTP和修复候选均明确为本地夹具。这证明工程衔接，不证明真实模型理解业务或修复成功率。

独立审阅没有发现已证实的Critical／Important。审阅者独立执行契约＋确认58项通过（1.52秒）。曾怀疑大原件造成工程超限，改用实际提供器MockTransport复现后证伪，未因此修改业务代码。唯一Minor是请求字节措辞过强，已更正注释与本文为JSON内容级证据；未改网络或绑定语义。

## 仍需完成

- [x] 当前代码冻结后的完整Python回归；全部产品文件与冻结清单一致。最终差异检查退出0。
- [x] 实际浏览器确认仅预览、首次未覆盖、第二次填入、追加2×3=6、独立勾选后确认进入工作台；原件CONFIRMED、edited_by_user=true且仅1份生成记录。
- [x] 已按明确新批准额度执行首批3次真实草案生成，记录成功HTTP与不可用格式的区别；没有重试、没有修复模型或MCP调用。
- [x] 提示v2完整回归结束，Python717／Node108通过；本地8877已重启加载新提示，启动未调用模型。
- [x] 用户追加批准2次并完成。单文件DRAFT_READY；跨文件NEEDS_CLARIFICATION，保留为质量局限并验证人工回退，未追加调用或改写结果。
- [x] 将真实结果和质量局限回写总路线图；第2项从独立难例离线建设开始，未将其算作已完成。

本地8877服务已重启到新代码。启动前核对修复、分析、影响对比均无运行中操作；现有待审阅及交付数据保留。HTTP200包含4个新增草案控件，返回JS与磁盘原件相同，主运行草案请求数0。见validation/next-phase-1/main-server-check.json。仅此HTTP检查不代替最终浏览器交互验收。

当前执行身份`2797940be47c7a5ce3c4c3b6867316af5f2d68c4f5be5984f33e4d0a7ba4bea1`；使用项目`../.venv/bin/python`采集，完整身份及9个产品文件hash见source-bindings.json。曾使用系统python生成的中间身份已纠正，未安装／升级依赖。预算等待中，未将测试夹具改标为真实生成或修复效果。

## 2026-10-25继续验收：真实进程强制终止

新增tests/integration/test_rule_draft_recovery.py，独立运行1通过（3.08秒）。子进程实际持有RuntimeOwner文件锁，真实RuleDraftService持久化STARTED和请求后进入本地提供器夹具；父进程确认信号后发送SIGKILL，并由新控制器取得已释放的锁。恢复后为IN_DOUBT，无响应／结果文件，不能再次run、换key重发或apply，原始input/request字节不变，上传仍DRAFT且无修复任务。

这是实际进程中断／重启证据；提供器副作用是本地计数夹具，没有HTTP／模型／MCP调用，不证明远端执行幂等、上游计费、断电或文件系统故障持久性。新增测试未修改产品代码，执行身份与原3次联调计划保持相同；上表712项为此前完整回归，本条是追加1项专项，不宣称已做713项单次完整回归。

浏览器重新取得空标签页列表后开新页，已实际打开上传窗口并载入fee.cj记录。随后查询按钮的locator和坐标操作仍发生CDP派发超时，页面日志无错误，尚不能判断更具体原因；未据此修改产品代码、重启仍存活的服务或宣称浏览器闭环成功。

## 当前最新进展：真实3次完成与提示修订

详见[live第1批报告](validation/next-phase-1/live-result/report.md)。两份明确业务回复把每项suite写成同时含target／regression的对象，被EXAMPLES_INVALID拒绝，原件保持INVALID。离线诊断另以明确的乘法／x+100参考计算核对所列数字，得到一致；这不修复原结构，也不把同源例子与规则当语义证明。缺需求案例返回7条有用疑问，未编造可应用规则。

提示修订rule-draft-prompt-v2明确suite单字符串及数组整体覆盖两组，并按函数签名构造参数／返回值JSON schema。它只修改生成约束，未改变既有协议v1或校验器；三份历史校验结果可原样重建。当前执行身份9b7e8308...17e3，第一批原始执行2797940b...bea1的源码已在live-result/execution-source.zip封存。不可将前一版本712项全量成绩当作新提示版本的完整回归成绩。

浏览器通过原生键盘完成查询、显示模型草案、两次显式替换、编辑和确认进入工作台。鼠标／locator派发存在环境超时，工具超时时先读焦点和后端记录，没有重复提交。最终DB为CONFIRMED，实际确认有3个例子且edited_by_user=true；HTTP夹具生成仍只有1次。此为本地HTTP夹具验收，不是上述真实模型响应自动应用。

2026-10-25最终离线收尾：提示v2源码冻结下完整Python717通过／1 live未运行（803.50秒），完整Node108通过（196.404292毫秒），git diff --check退出0。8877旧服务经核对无活动任务后重启，页面HTTP200，未发起模型健康探测。当前执行身份`9b7e830870103d1a29c624e03e541a5e68a026e0ce887c9f20523f7bb53b17e3`，追加两个明确业务案例的待批准计划仍与此版本一致。首批3次原件保持原执行身份和原失败结论。

## 最终范围与门禁结论

第二批详见[live第2批报告](validation/next-phase-1/live-result-v2/report.md)：实际单文件草案经本地测试作者审阅／冻结后，真实SDK对缺陷实现FAIL、人工参考修复PASS；项目案例因模型过度澄清不可直接应用，转入已设计的人工规则回退，SDK同样FAIL→PASS，原件均未改变。这里没有LLM修复代码请求，没有MCP调用，也没有宣称替生产用户作出人工审批。

状态“已验收”指已实现的生成协议、范围／类型约束、失败及澄清拒绝、用户应用编辑、确认冻结、SDK衔接与追溯闭环，**不代表模型对任何明确需求都能自动产出可用规则**。本次跨文件过度澄清作为生成质量局限保留；没有给出必须达到的生成成功率，因此不以改写响应或继续付费抽样来制造两个案例全过。正常项目链路另有HTTP夹具＋真实SDK完整测试，真实项目生成效果如实列出。

两个批准批次累计5次／6803tokens，额度全部关闭。无网络重放5份请求／结果并核对4个SDK日志及输入工程hash通过，见[重放结果](validation/next-phase-1/trial-replay.json)与[重放脚本](validation/next-phase-1/replay_trials.py)。当前执行身份9b7e8308...17e3，源代码与对应冻结清单一致；全部717项Python及108项Node结果为该版本。
