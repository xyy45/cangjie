# 业务缺陷评测集 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans，延续已确认总目标逐项实施；以RED／GREEN及最后独立审阅验证，不重复请求阶段切换授权。

**Goal:** 建立先30、再100个有源码／公开示例／独立验收／参考修复的可重放仓颉业务缺陷任务，提供相同模型与最大预算的三流程评测。

**Architecture:** 新增本地benchmark模块与CLI，复用上传冻结、RepairLoop、DeepSeekProvider、MCP分析和独立SDK运行。数据集与运行结果独立存放；参考修复与最终验收材料不进入模型上下文。每个任务／模式独立运行目录，已开始的运行不得自动重发模型请求。

**Tech Stack:** Python现有契约／解析器／SQLite、固定仓颉1.0.5 SDK、JSON及Markdown报告；不新增服务或依赖。

**Spec:** ../../升级改进开发计划.md（阶段4）及本文的比较契约。

## 比较契约

三个模式均使用同一模型、temperature=0.2、每次输出上限6000 tokens、最多3次请求、RepairLoop总480秒；各模式公开编译／测试反馈相同。DIRECT是无静态MCP的模型＋公开验证反馈；MCP添加基线MCP分析与公开失败定位；CEGIS再添加已确认业务规则的有限搜索及其反例反馈。DIRECT不是一次性回答基线，报告须写清定义。

最终holdout用例在循环结束后独立执行，绝不作为任何模式的修复反馈。CEGIS的搜索规则是实验处理的一部分，不能把搜索PASS直接记为holdoutPASS。最终选定同一规则：有选择候选则使用选择候选，否则使用最后实际产生候选；没有候选记为未修复。构建、公开测试、holdout均PASS才计入可验证修复。

所有流程保留真实请求原件、源／数据／工具链摘要、公开测试、holdout日志、轮次、调用次数、usage、总耗时及状态。MCP额外开销计入总耗时；没有usage或价格配置时记UNKNOWN／null，不能编造token或费用。价格只有显式输入的每百万输入／输出价格，币种和计价假设随报告保存。

数据集为团队自建合成基准，不能宣称独立工业分布或市场领先。100任务的参数化变体必须标明family／variant，按family分组报告，不能当成100种不同语义缺陷。先30种不同业务规则验证，再扩展受控变体。

## Global Constraints

- 继续使用同包Int64／Bool受限生产语法、静态cjpm配置、无依赖／外部调用和冻结接口；保持原工作台行为不变。
- 数据集清单绑定全部文件字节；重放前拒绝源码、规则、公开／验收用例、参考修复及清单变更。路径不得逃逸或使用链接。
- 原始缺陷必须真实编译可运行并被至少一个验收用例击穿；参考修复必须通过全部公开和holdout。所有UNKNOWN／失败原样报告。
- 模型上下文不得读取参考源码、holdout或评测标签；三模式获得相同自然语言需求和公开源码／测试。
- LIVE与FIXTURE结果明确标记并隔离统计；离线模型夹具不得报告真实模型修复率。网络不确定结果不重试／复用。
- 不读取或打印密钥；沿用DeepSeekProvider私有配置和脱敏机制。不自动执行大规模付费比较，先完成可审查数据及dry-run预算；真实调用须有明确数量预算。

## Review Focus

- Bool和Int64严格区分、负数除法规则、乘法／除法及极值不得使oracle和仓颉实际语义无意分叉。
- 参考修复不等于真实模型效果；数据作者的参考PASS不能记入模式成功率。
- 任务／模式／模型／种子／预算缺失或不一致的行不得合并为同预算比较；失败任务仍计入分母。
- 重跑不得覆盖已有结果、重发IN_DOUBT请求或读到其他任务原件；每次独立目录并拒绝覆盖。
- 报告只从实际日志重建；元数据或日志变更使结果校验失败。缺失模型usage／价格必须显示未知。

## Task 1: 自建数据与质量门禁

Files: nexus/benchmark/corpus.py、fixtures/benchmark/v1/、tests/test_benchmark_corpus.py。
Interface: load_corpus(root,limit)->经摘要校验任务；material(task,version)->生产工程；public_context不含private材料。
- [x] RED：30种不同业务语义、公开／holdout分离、严格值类型、原件摘要、路径／引用限制与可重现清单。
- [x] GREEN：版本化数据集生成／校验，30任务后扩100个标明族和变体的任务，附需求、公开例子、holdout、独立规则和参考修复。
- [x] 真实SDK质量验证：缺陷工程编译成功且holdoutFAIL，参考工程公开＋holdoutPASS；保存日志和源摘要，任意未知阻止计为合格。

## Task 2: 三模式同预算运行器

Files: nexus/benchmark/runner.py、__main__.py、tests/test_benchmark_runner.py、tests/sdk/test_benchmark.py。
- [x] RED：三模式开关区别、相同公开输入／预算、holdout从不反馈、任务和模式目录隔离、重复／不确定运行拒绝。
- [x] GREEN：复用上传与确认构建任务，按模式注入已有enricher／oracle；循环后使用独立固定SDK探测最终候选的holdout，不改变生产门禁。
- [x] 一任务三模式真实SDK＋明确模型夹具验证；CLI默认list／plan不发模型请求，live有明确任务／模式及最大请求数，超出预算拒绝启动。

## Task 3: 可重放报告与成本

Files: nexus/benchmark/report.py、tests/test_benchmark_report.py、docs/demo/upgrade-phase4-verification.md。
- [x] RED：失败和UNKNOWN不丢分母、family聚合、usage未知、价格缺失、混合模型／预算／夹具不能冒充LIVE比较、篡改拒绝。
- [x] GREEN：JSON／Markdown结果表从摘要绑定的运行原件重建，输出任务级结果、运行时间、请求／tokens及有条件费用估算；重放不请求模型。
- [x] 全量Python／Node／差异检查、独立审阅，文档列出真实SDK质量证据和未运行的真实模型比较。
- [x] 更新主计划；只有同预算真实比较有证据才将阶段4整体完成。需要费用预算时保留准确待办，不把fixture当完成证据。

## Execution Ledger

2026-10-24：阶段3验收收尾时只读核对现有循环／提供器／SDK接口。Ruling: 复用三轮公开反馈作为DIRECT，差异限定静态分析与主动反例搜索 — 保持请求预算公平、避免额外改造生产循环 — 报告明确DIRECT定义并非one-shot。

Ruling: 采用30种业务规则＋70个标明family的变体扩至100 — 兼顾先做可靠语义覆盖和复现实验规模 — 族内相关性必须披露，不能把重复变体当独立创新。

Ruling: 大规模真实模型实验先输出精确任务数／模式数／最大请求数预算，不用默认运行隐含授权付费 — 已授权开发和常规联调可继续 — 阶段4实际模型比较在明确运行预算前保持未测。

2026-10-24独立审阅：初版holdout与搜索输入高度重叠，初版质量成绩仅证明参考修复可运行，不可作为有效对照。修正为私有搜索规则v2：保留输入集合严格类型／域／数量校验，冻结集合必须恰好等于holdout输入；搜索、缩减、累计反例及重放均拒绝这些输入。最终验收使用单独未过滤v1规则，搜索与验收的业务语义字段相同。旧数据及证据保留为superseded快照，修正后重新跑30／100真实SDK验证。

Ruling: 单点边界缺陷封存唯一反例会降低主动搜索发现机会 — 验收输入隔离优先于看起来更好的成绩 — 文档披露该限制，不能据此宣称主动搜索对所有族均有效。

初版另有CEGIS尚未搜索时grade_summary调用verify抛错，导致失败任务缺少result；已区分不存在NOT_RUN、运行中UNKNOWN、已完成完整核验，不吞掉已有证据篡改异常。RED覆盖上述两个Important。

2026-10-24：Task1／2与Task3工具验收完成。sealed质量30／30 PASS40.928s、100／100 PASS131.654s，SDK三模式等2测试PASS60.66s；持久演练重放FIXTURE_ONLY，0真实模型请求。最终501 Python通过／1未运行（535.66s）、93 Node通过、差异检查通过，主服务8877无活动任务时已更新并返回HTTP200。实际LIVE同预算比较待用户调用预算答复，阶段4整体仍未完成。

## Follow-up: 批次计划与中断统计

2026-10-24完成性复查重现：计划2任务×3流程，但只把1任务3个成功结果传给报告，仍返回LIVE_COMPARABLE。根因是报告不知道计划，整个缺失任务不会进入分母。

Ruling: 批次计划升级为显式来源和摘要绑定的schema2，新增按批次重建报告；缺失／中断项逐项占位UNKNOWN、不算成功、请求／usage不确定保留未知。没有计划的逐行报告只描述明确提供的结果范围，不允许声称计划整体可比较 — 防止中断后只挑成功任务 — 旧独立FIXTURE报告仍可读，真实完整比较须引用批次计划。

- [x] RED：2任务6项计划、只完成3项时分母仍为每流程2项；STARTED模型请求无结果时计数保留、费用未知；篡改／错源／重复项／链接拒绝；CLI异常中断后保留计划并停止后续调用。
- [x] GREEN：runner.plan_runs增加origin／plan_hash；cohort.py严格重建计划并逐项验证结果／收集不完整快照；report.py汇总可区分COMPLETE／MISSING／INTERRUPTED及未知成本；CLI支持report --batch并记录停止原因类型。
- [x] 复用真实SDK三流程测试验证完整计划报告；专项、完整回归、独立审阅和证据更新。真实模型预算提问仍待答，不发付费请求。

Follow-up验收：19专项通过8.41s，独立审阅8项通过4.52s，两处Important关闭。最终509 Python通过／1未运行530.63s、93 Node通过、差异检查通过；真实SDK三流程及完成证据目录链接攻击回归通过，原件重放FIXTURE_ONLY／COMPLETE／3项。付费预算提问未获答复，仍未调用真实模型。工具子项已验收，重读主计划后推进独立原生核心开发，阶段4整体未完成不变。

2026-10-24最终：按用户18次上限授权完成两任务×三模式唯一LIVE试评测，6项通过、6实际请求、40579tokens；同最终执行版本，原件解压重放报告一致。费用UNKNOWN。阶段4获准试评测范围完成，100任务全量模型实验未测；详见demo/upgrade-phase6-verification.md。此前未测／预算待答均为历史记录。
