# 第6阶段：运行可靠性

状态：已完成本轮本机可靠性实施、最终回归、独立审阅修正，以及获准的两任务真实试评测。新机器安装与全量100任务模型实验未测。

## 任务1：图模式与终态展示

- 取消根据返回结果自动在DDG／PDG之间切换。默认变量表／DDG，用户手动选择后，切换样例、历史恢复和重新分析保持选择；PDG缺失时显示不可用，不悄悄展示另一种图。
- 显式定位跳转附带源码行时选择point，保留语句定位行为；不改变工具图或伪造依赖。
- 已交付、已取消、已拒绝和待核实任务显示对应反馈；真实失败诊断／停止原因仍优先保留，不把历史失败改写为成功。

RED：新增6项真实JS交互断言，22通过／6失败（114.76ms）；两个模式跳变与四种终态均复现。

GREEN：`node --test tests/*.test.cjs`：**99通过，0失败（189.12ms）**；差异检查通过。Python后端未因本子项修改，最近完整后端结果仍为第5阶段的575通过／1未运行（705.99s）；不能把它当后续缓存／异常处理改动的验收。

实际浏览器：8877新页面默认DDG；手动point后切换跨函数样例，仍为point／程序依赖PDG；再切table并切换直线样例，仍为table／数据依赖DDG。仅读取已有样例快照，没有重新请求MCP或模型。截图见validation/upgrade-phase6/browser-pdg.jpg和browser-ddg.jpg；该浏览器验证不冒充真实远端重新分析，异步新结果由JS测试覆盖。

## 当前完成范围

任务1–5已完成。用户批准business_001、business_030×direct/mcp/cegis共6项、最多18次DeepSeek请求；唯一真实批次实际6次、6项全部完成。后续不自动追加调用或重跑。最终证据及限制见本文末尾。

## 任务2：有界定位与原生启动异常

5项RED复现了3种超长／无位置定位裁剪越界、启动RuntimeError越过拒绝边界、错误标成IN_DOUBT；修复后定位／core／控制器61项专项通过（31.26s）。完整原件保留摘要，投影无法保留的目标明确省略，不捏造位置。原生许可不可用时动作不执行，也不会触发第二次模型请求。日志：/private/tmp/cangsight-reliability-boundaries-{red,green}.txt。

## 任务3：同会话已验证结果复用

20项缓存服务RED→GREEN（0.67s）；HTTP命中不启动工具线程、强制新执行及非布尔选项验证，JS首次上传请求复用／重新分析强制工具／原时间来源显示RED→GREEN。缓存／HTTP／影响对比53项通过（9.41s），全部Node100项通过（168.49ms）。早先分析目录192项回归中1项因旧impact硬编码profile5失败，已改为共享profile6，并在53项专项中覆盖修正；该专项之后的最终后端全量已完成，见最终验收。

复用默认关闭，网页首次分析按需开启；只复用同actor、相同输入／条件、同工具端点与凭据作用域、同执行代码、300秒内的COMPLETE结果。源码、三项工具输入与原始输出、封存结果及时间均重新核验。请求别名保持幂等；单活动租约不绕过。旧分析可读，内部修复／评测未开启新缓存。本缓存专项未进行远端MCP或模型请求；后续真实预检及试评测另行记载。

## 任务4与独立审阅

schema3计划保存实际Python执行源码／依赖版本／requirements.lock摘要／固定cjc和cjpm／core2身份；STARTED和schema2结果绑定implementation_hash。无候选的失败也记录身份，重放校验当前版本，旧schema2计划只读保留但不能升级成同版本LIVE成绩。doctor显示已核验的core2版本、构建身份及build_core修复命令，模型连通性仍明确NOT_PROBED。

22项初始专项通过（12.45s）。独立审阅指出三项Important：未知验证未停止后续调用、IN_DOUBT有结果文件被误算完整、嵌套链接源码未纳入身份；5项RED复现后，28项专项全部通过（18.75s）。CLI改为依据任务与验证状态停止并保存结构化原因；报告保留task_status并把未决执行标UNFINISHED；源码包任何嵌套链接均拒绝。已完成的业务验收UNKNOWN仍诚实保留在分母，不宣称修复成功。

另使用隔离的实际源码文件变化夹具验证：报告生成途中源码变化会拒绝且不发布报告，0工具／模型请求，见report-drift-proof.json。独立审阅Minor留待后续测量：缓存事务中最多20个完整原件校验可能增加SQLite锁持有时间，目前无网络／原生等待，不影响已测试的正确性；未声称大原件压力测试通过。

浏览器缓存验收为独立8896本地传输夹具，非真实远端MCP；上传add.cj命中完整记录后可见“缓存复用”与原分析时间，证据详情同样显示原时间；重新分析清除缓存标记并创建新的READY记录。截图browser-cache-fixture.jpg，临时标签及实例已关闭。主服务8877已更新为新后端。

修订前首次完整后端611通过／1未运行（740.61s）保留为历史；独立审阅修正后的最终完整回归为617通过／1未运行（738.92s）。前者不作为最终验收。最新全部Node100通过（212.132ms）；差异检查通过。该回归完成前模型已用0次；随后唯一授权真实批次实际使用6次，见下文。

本机依赖实际版本与原lock有差异（例如MCP1.28.1／Pydantic2.13.4），二者均记录在执行快照；全新机器安装及整个SDK库逐字节可复现性未测。该限制不由本机SDK集成测试或配置存在性代替。

## 最终验收与唯一真实试评测

2026-10-24最终离线回归：617 passed、1 live deselected，738.92s；Node100通过，212.132ms；git diff --check通过。离线排除的live测试未算通过；另行运行的真实试评测由benchmark CLI执行，单独保留证据。

执行代码冻结为`67d93b9c38e0eab172ff6cd2bbf695895e9cefd28b9267f3cd60a39bfd5930b1`；源码快照execution-source.zip共77文件，不含.env。真实MCP预检三项均VALID，归档mcp-preflight-evidence.zip；此预检使用公开sum3样例，无模型请求，不进入六项对照成绩。

唯一真实批次目录：`.runtime/benchmark-live-trial-20261024`。模型请求与实际响应均为deepseek-flash；未声称提供方权重版本已获独立证明。计划schema3，摘要`d8bddb324d04021c4671772ca76b8282cd94e2039d2c13dbf164684a2ab4c4e0`。两任务分别为数量边界business_001、跨文件计费business_030；每模式最多3请求／480秒／单次6000输出tokens／temperature0.2，最后私有验收单独最多60秒，不反馈模型。

| 任务 | 流程 | 构建／公开／私有验收 | 独立搜索 | 请求 | 总tokens | 耗时秒 |
|---|---|---|---|---:|---:|---:|
| business_001 | direct | PASS／PASS／PASS | 未启用 | 1 | 4172 | 18.688 |
| business_001 | mcp | PASS／PASS／PASS | 未启用 | 1 | 5910 | 25.172 |
| business_001 | cegis | PASS／PASS／PASS | PASS（32输入） | 1 | 6133 | 24.761 |
| business_030 | direct | PASS／PASS／PASS | 未启用 | 1 | 4762 | 18.409 |
| business_030 | mcp | PASS／PASS／PASS | 未启用 | 1 | 9776 | 33.275 |
| business_030 | cegis | PASS／PASS／PASS | PASS（32输入） | 1 | 9826 | 29.540 |

实际6次模型请求，prompt38035、completion2544、合计40579tokens；运行时长合计149.845秒（不包含回归／预检／报告重放）。每模式2项均可验证修复。缺失／未完成0项；没有未知请求重发，没有另开批次。未提供计价单价，费用UNKNOWN，不能以token上限或0元替代实际账单。

处理差异核对：DIRECT没有静态分析上下文／工具引用；MCP、CEGIS在数量任务纳入3项有效工具结构，在跨文件任务纳入6项有效工具结构，模型各引用2项分析证据。跨文件任务三流程均实际修改src/amount.cj和src/logic.cj。两项CEGIS各执行32个未与holdout重叠的搜索输入，native boundary证明通过核验，未发现新反例，缩减及累计回归新增0项。各流程均首轮通过，本批没有展示真实模型的多轮反例修复收益；该能力已有真实SDK＋明确模型HTTP夹具的独立回归，不能混称为本批真实模型效果。

从原件重建报告为LIVE_COMPARABLE／COMPLETE，6项分母完整，报告摘要`8da82b02113c93fd559dd513a9d6a61c81dd062dd50b3cd0f4453bdbbd3bc754`。live-trial-evidence.zip包含688文件、743061字节，排除target编译产物，保留源码、SQLite、原始模型／MCP记录、测试日志与验收工程。扫描未发现本机API密钥原文；解压到独立临时目录再次重建，报告摘要完全相同，原件／归档中STARTED均为6，没有额外模型调用。归档SHA256：`73149f4efffb9aa5bce66d21baaabc1e3393c4f95ffe14b30c83c021baba7359`。

证据入口：[JSON／Markdown报告](validation/upgrade-phase6/live-trial-report/report.md)、[运行原件包](validation/upgrade-phase6/live-trial-evidence.zip)、[归档重放证明](validation/upgrade-phase6/live-trial-archive-proof.json)、处理差异live-trial-treatment-audit.json、搜索证明live-trial-search-audit.json；CLI原始摘要见live-trial-cli.json。

仅2个团队合成任务，不足以判断三流程统计优势、工业泛化或市场领先；100任务数据质量通过不等于100任务已真实模型评测。全部任务停在REVIEW_PENDING，表示验证完成待人工审阅，不是自动批准交付。新机器安装、完整SDK库逐字节复现和大原件缓存锁等待压力测试未测；当前支持范围仍为既有Int64／Bool、受限同包工程，未放宽复杂语法、依赖、并发或权限边界。
