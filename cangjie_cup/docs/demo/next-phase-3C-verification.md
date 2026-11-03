# 第3C项：连续操作与状态序列验收记录

状态：已验收并激活。当前8877运行独立冻结3C快照，沿用原数据与会话路径；整体目标仍有4A—4D及部署复现。

上传单个 `.cj` 或受限同包工程时，可导入并确认状态序列 JSON。状态由函数的一个 Int64／Bool 参数显式传入，返回值作为后态；固定上下文贯穿整条路径。仓颉 SDK 在同一真实 case 内连续调用函数，首次实际返回偏离模型时输出结束标记并停止尾部。Python 从原始日志重建实际步骤、前态、返回、参考状态、结束原因与观测计数。

配置后的顺序为公开测试 → 数值规则 → 单次属性 → 成对关系 → 状态序列；只执行已配置的项。失败的完整可达前缀进入下一轮修复及基线静态定位；UNKNOWN 停止后续模型请求。接受、导出、归档和下载要求当前报告及前置原件有效。模型不能修改测试、状态模型、配置或允许路径。

## 支持范围与界限

- 同包、最多三个允许修改的生产文件；同一被测函数 1—4 个 Int64／Bool 参数，返回类型与状态参数相同。
- JSON 最多 16KiB；初始状态 1—16 个，操作 1—4 个，不变量 1—8 个，固定上下文参数最多三个。
- 搜索最多 16 条轨迹、每条 2—8 步，共最多 128 个计划调用；最多两批缩减，每批最多八条／64 个计划调用。真实缩减可保留一步反例。
- 每份报告最多保留八条不同失败前缀用于反馈和累计；全部历史有效保留前缀去重后的并集不能再次按八条截断。必需回归超预算时 UNKNOWN，完整批次仍保留。
- 转移只依赖实际可见 state／arg 参数；每个预检完整输入上，所有匹配操作模板的参考输出必须一致。模型矛盾、溢出或越状态域属于模型错误。
- 计划调用数与有效实际观测数分别报告；缺少 case／step／结束标记、错误前态、输出超限、超时及取消不能当作业务通过。
- SDK 搜索与缩减执行阶段共享 90 秒、每批最多 60 秒，输出 2MiB；材料绑定与报告重验另有开销，不承诺端到端 90 秒。
- 不覆盖多字段对象、多个函数入口、跨包、数据库、外部副作用或并发；有限路径验证不是完整语义证明，也不保证全局最小反例。

## 已获得的专项证据

Task 4 的 93 项服务兼容检查及 10 项真实 SDK 测试通过；两文件库存扣减再取消的公开测试通过，而状态序列发现未准确恢复的缺陷，参考修复实际回归两条旧前缀。

Task 5 的 132 项控制／定位／交付兼容测试通过；两轮 HTTP 模型夹具与分析图夹具配合真实仓颉 SDK、原生策略及本地 stdio MCP 的集成测试通过。第一轮三个前置检查 PASS、序列 FAIL，第二轮序列 PASS；接受后修改 END、公开日志或模型，实际下载接口分别返回 400。该证据不代表真实大模型修复质量或远程 6240 分析准确率。

Task 6 的 149 项 Node 测试和 43 项 Flask／上传／工作台检查通过。浏览器已实际选择自建 `.cj`，导入公开测试和状态模型文件、显式确认并只读回载；浏览器夹具禁止 SDK、原生执行、模型及远程分析调用，未点击开始修复。导入原文和存储的 USER_CONFIRMED 记录已核对，媒体按真实 JPEG 格式保存。

独立审阅两项 Important 均有真实 RED→GREEN：相同完整输入的操作模型矛盾、旧 single／relation 日志汇总后混入序列标记。集中修复后 164 项相关测试通过。确认框缺少“状态模型”名称为暂缓的 Minor；显式确认和所选验证契约冻结仍生效。

## 最终验收结果

- 最终263文件摘要：`b5046454a94613af90ad1027f95341a2ce9a2a910c844e158ccb19054ef3b642`。
- `../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short --basetemp=/private/tmp/cangsight-3C-final-validation-20261027-r2`：1249 passed、1 deselected，1861.60s，退出0。
- `node --test tests/*.test.cjs`：153 passed、0 failed，260.406083ms；`git diff --check`退出0。
- 首次完整回归为1249 passed、1 deselected／1928.64s，旧源码与封存保留在 `pre-reject-refresh-fix/`。完成审计另加两个真实失败回归，再修复详情刷新失败后的拒绝入口；没有将旧执行改记为新版本。
- 最终封存469个真实SDK原件、3个服务运行／5份报告／8份协议样例；源码、core和原件在禁止SDK执行、原生IPC、联网的独立子进程重放PASS。第2项、3A、3B按各自冻结源码重放PASS。
- 补充自建输入重新在最终源码下真实运行：9个更小且仍带MODEL-OP-CANCEL标识的可达失败前缀，评分[2,61]→[2,43]，初态10／上下文10，扣减1后取消1，实际[9,9]、参考[9,10]。独立65文件封存重放PASS。不保证全局最小。
- 浏览器：实际导入／显式确认／只读回载；PASS47计划／47实际观测及2条累计回归；FAIL63计划／60观测；只改隔离副本END后，UNKNOWN覆盖缓存PASS，当前徽标待验证。原日志已恢复。两浏览器夹具均无新增SDK／模型／远程分析执行，媒体格式和来源已核对。
- 有限扫描5个含嵌套ZIP的归档／1002成员／10527919字节：当前配置模型凭据匹配0，禁入文件0，未预期私有路径0。四类已检查的core调试／SDK对象及运行时路径按原样保留，不能声称全路径脱敏或通用DLP。
- 切换前39次历史模型请求均SUCCEEDED、176条工具请求COMPLETED，无在途请求；8877切换后真实HTTP的demo.js／sequences.js摘要匹配冻结源码。44任务（31待审、10已交付、3已拒绝）与工具记录数量保持，没有自动重试未知请求。

证据索引：[artifact-index.json](validation/next-phase-3C/artifact-index.json)。主站运行快照位于 `.runtime/active-stage-3C`，原3B快照保留。新模型和远程分析调用均为0，既有付费额度不复用。浏览器页面截图是显式隔离夹具，不代表真实大模型或远程6240执行。

## 已采取的实现裁量与暂缓项

以下按执行台账保留。代码未提交，台账不删除；没有声称已推送GitHub或工作区干净。

- Ruling: reuse authorized codex/upgrade-counterexamples-20261023 checkout despite normal .git=.gitcommon; enormous historical dirty changes and user instruction preserve in-place work, no newworktree/commit/reset/cleanup. Main8877 stays independent immutable3B snapshot. Cost: branch history still uncommitted, exact source manifests/diffs required at review.

- Ruling: relocation to /Users/jxy/Desktop/mass/CangSight-main found readonly and source244 hashesmatch;6 internalbrokenlinks repairedrelative, SDK1.0.5/nativeidentity/main44tasks176completed kept,3BarchivedreplayPASS. No historicalarchive rewritten; default toolcwdoldmissing requires explicitnewworkdir/bin/sh.

- Task1 evidence:64missing-contract assertionRED→64GREEN3.07s. Added raw-cumulative budget and out-of-domain publictype tests3RED (all DID NOT RAISE)→67GREEN3.12s. Final targeted legacycompatibility159PASS11.87s; no SDK/model/MCP. Ruling: candidate_checks counts raw mandatory attempts before dedup as well as structured/random attempts, preventing duplicate input bypass of4096structured/8192total bound; public values typechecked allpositions even if anotherparameter outside modeldomain. Mandatory historicalunion9preservedunder16; max8rejects9 rather than drops. ProductsequenceUI/execution notimplemented yet.

- Task2 evidence:34missing-sequence-protocol+2oldprotocol-mixedprefix36RED→86GREEN2.12s. Added post-summary OBS/END controls2RED(PASS incorrectly)→88GREEN6.78s. RealSDKattempt1 7PASS/1FAIL20.62s; Boolfixture omitted newline after ifblock, compilerdiagnosticconfirmed expectedsemicolon/newline, notproductprotocolbug. Preserved all8originals+oldtestsource/freeze beforefix; onlyfixture newline corrected, production14of15filesandassertionsunchanged. SDKattempt2 all8PASS21.34s:23SDKcases,146planned145actualcalls,7businessPASS/1expectedbusinessFAIL,8step16case128call boundary,LOW/Bool/nonfirststate andoutput/target/class collision verified.15sourcefilesfrozen throughout; archive0fe567cc... preserved beforetemppruning. Taskdone88compatibilityPASS1.98s; no model/remote analysis/coreIPC claimed for standaloneSDK. Ruling: sequence decoder rejects reserved markers anywhere after SDKsummary, cannot silently discard footerforgery; old normalharnessbytes/closedkindset unchanged.

- Task4 formal task-done93PASS211.58s; plan Task4 checkboxes complete. Ruling: strict typed metadata digest verification added after four negative controls showed edited seed/algorithm/public_test_state/schema_version were otherwise accepted. Shared public helper extracted without AST body changes; both relation and sequence bind its source identity. Cost: previous current-code reports invalidate on helper edits, while immutable3B archives/main use their own source. Task5 not yet implemented.

- Task5 Ruling: task-done uses fresh evidence/source-integrity checker over the just-observed terminal-success pytest runs instead of rerunning132+SDK tests without new edits or unresolved concerns; higher-priority instruction prohibits unnecessary repeat testing. Original exact commands/results and logs remain in ledger/workspace, checker does not claim new pytest execution. Cost: checker relies on the captured same-turn real outputs plus unchanged210filefreeze.

- Task5 Ruling: optional call_id extends existing mapping key without replacing SDK test_id or changing legacy cases; sequence_calls groups labels and orders eachfailedstep before predecessors, build_focus retains existing8targetcap/truncated, full feedback prefix remains uncut. Cost: static locations remain baseline hypotheses, not dynamic-path proofs.

- Task7 Ruling: standard review-package refuses empty a882913..HEAD under explicit no-auto-commit rule; fresh reviewer receives exact current3C vs accepted3B244file manifest diff instead. Archive source-freeze.json excluded as metadata, all244realbaselinepaths included. Cost: review traceability relies on frozen manifests rather than commit history; both retained.

- Final: Ruling: Task7 fullsuite/browser/freeze/replay/activation was intentionally pending reviewer scope — mustfinish beforeactivation; cost if skipped is unverifieddelivery.

- Final: Ruling: reviewer prohibited fresh SDK/IPC/MCP/network/model and only rebuilt existing originals — finalfullsuite willprovide freshlocalexecution; cost is no independent runtime reexecution by reviewer.

- Final: Ruling: real model/6240 accuracy unsupported by explicitHTTP/analysisfixtures — make no quality claims ornewbudgetcalls; cost is limited externallyvalidatedefficacy.

- Final: Ruling: arbitrary unsampled semantics/globalminimum outside finitecontract — fix consistency on everyprecheckedfullinput, not global symbolicproof; cost is untested paths remainpossible.

- Final: Ruling: dynamicexecution/rootcause proof outside staticfocus — retain real candidateprefix and baselinehypothesis labels; cost is static clues remain hypotheses.

- Final: Ruling:90seconds budget applies execution only — no end-to-endpromise,282.89s wholefixture measuredincludesmanychecks/downloads; cost is no UIlatencyguarantee.

- Final: Ruling: oldreport transparentmigration not promised — preserve own frozen3B archives andinvalidate changedengine reports; cost is older current-code checks mayrequire newtasks.

- Final: Ruling: main8877/historicaldirtytree outsidefreshdiff — author mustauditidle/snapshotactivation withoutGitcleanup; cost is no repository-wide reviewclaim.

- Final: Ruling: objects/multipleentry/DB/external/concurrency outside3C — preserve remainingroadmap4A..4D/5; cost is currentstate remainsoneprimitivefield.

- Final: Ruling: finite scan retains four exact pinned core debug/object/runtime paths byte-for-byte; no configuredcredential matches or unexpectedprivatepaths in1002members5archives. Cost: evidence contains toolchain hostpaths and is not universalDLP/redacted material.

- Final: Ruling: no commit or workspace deletion because user preservation and .git write restrictions override skill cleanup; exactfilefreeze/reviewdiff/ledger retained. Cost: no clean-branch/committed-history completion claim.

暂缓Minor：确认文案未点名“状态模型”；显式确认、选定契约冻结仍生效。

## 下一阶段

已重读总目标，按持续授权进入4A有界字符串设计。真实SDK已完成1个case／16个语义断言，见[实施前调研](next-phase-4A-preflight.md)。这只证明工具链语义，尚未开放字符串上传或声称全链支持；真实模型／远程分析预算0。
