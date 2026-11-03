# 组合业务规则难例评测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking。用户已授权按总目标连续开发；常规阶段不重复确认。第1项已验收（保留生成质量局限）；本计划已进入第2项实施。

**Goal:** 新增10个可被真实SDK证实的组合业务缺陷，合格后扩至30个，并在独立新预算下完成同版本DIRECT／MCP／CEGIS对照及反例轨迹报告。

**Architecture:** 保留旧v1生成器、任务格式、质量门禁、runner与重放报告。增加独立hard语料版本及目录，加载器明确识别版本／数量组合；只读轨迹分析从原始候选、测试及搜索记录推导首轮遗漏、反例反馈和后续修复，不改模型的候选或验证依据。

**Tech Stack:** 既有Python、SQLite、固定仓颉SDK1.0.5／core2、MCP分析与DeepSeek适配器，不新增运行依赖。

**Spec:** ../../后续能力提升开发目标.md 第2项；../../demo/next-phase-2-preflight.md 为已核实接入点及初批10类候选。

## Global Constraints

- 先10个不同组合规则，质量门禁通过后再扩到30。未执行数据／模型结果不得标已完成。
- 保持Int64／Bool、每函数最多4参数、同包和最多3个允许生产文件；本阶段不扩字符串／数组／跨包／真实数据库。
- 公开、搜索与封存验收分离；搜索及缩减继续排除全部holdout，规则不能泄漏到模型上下文。
- 新hard目录与旧v1／v1-30分开，旧清单字节和旧generator语义保持不变。
- 参数域保证参考表达式可在Int64下计算；非法输入的错误返回及前置条件写入公开业务规格，不能仅写在私有答案里。
- 模型三流程同标识、最多3轮／480秒／每次6000输出tokens，使用既有预算契约；未知状态停止，不重发。
- 真实批次前冻结代码／数据／执行身份并生成dry-plan，另取得新任务与总请求上限。草案生成预算和旧评测预算均不复用。
- 保留全部历史未提交改动，不自动提交／推送／部署；只读准备阶段不能改产品代码以免破坏正在执行的身份门禁。

## Review Focus

- 公开示例过强、参考答案或规则混入模型上下文：Task1及Task3断言上下文字段与完整目录可见性。
- 伪难例或仅编译失败：Task2要求baseline真实可编译且被holdout击穿，reference公开和holdout全PASS。
- 同一首轮候选的记录被错接到后续候选：Task3按candidate_id、tree_hash、attempt及源记录hash关联，缺失返回UNKNOWN。
- 未运行任务／提前停止从分母消失：Task4保留完整原计划，分类MISSING／UNFINISHED／UNKNOWN，不压缩为已完成小样本。
- 封存输入由反例缩减间接泄漏：Task1与Task2验证生成／累计／缩减所有输入均与holdout不相交。

## File Map

- Create `nexus/benchmark/hard_catalog.py`：版本常量、10／30个明确业务规格与缺陷变体，返回自建任务材料。
- Create `nexus/benchmark/hard_corpus.py`：`build_hard_corpus(root,count=10)`生成独立目录和既有格式原件。
- Modify `nexus/benchmark/corpus.py`：只扩展明确版本／数量组合校验，加载返回实际generator；旧build_corpus字节不变。
- Create `nexus/benchmark/trajectory.py`：只读、绑定原件的反例与失败分类分析。
- Modify `nexus/benchmark/__main__.py`：必要的只读trajectory子命令，现有plan／run预算和停止语义不变。
- Create `tests/test_hard_benchmark.py`、`tests/test_benchmark_trajectory.py`、`tests/sdk/test_hard_benchmark_sdk.py`。
- Create `fixtures/benchmark/hard-v1-10/`、合格后`hard-v1-30/`及README；创建阶段2验收和证据目录。

## Task 1: 版本化难例契约与首批10个材料

**Interfaces:** `hard_catalog.tasks(count:int)->list[dict]`返回id、family、variant、goal、function、source、reference、domains、expression、public_inputs、holdout_witnesses；`build_hard_corpus(root,count=10)->str`返回corpus_hash。`load_corpus`继续返回既有运行器所需task形状。

- [x] RED `test_hard_ten_families_and_interfaces`：10个任务、10个不同family、参数≤4、生产文件≤3，包含至少1个两文件／三函数组合；所有目标含明确错误返回／边界。
- [x] RED `test_old_corpus_bytes_and_profiles_unchanged`：旧30／100生成hash与修改前留存值相同；未知generator、旧generator+10、hardgenerator+100均拒绝。
- [x] RED `test_hard_material_visibility_and_reserved_inputs`：public_material无reference／oracle／holdout；公开与封存输入按typed input_key不相交；v2搜索排除集合等于完整holdout集合；篡改文件、接口、路径、清单或符号链接拒绝。
- [x] 执行 `../.venv/bin/python -m pytest tests/test_hard_benchmark.py -q --tb=short`，Expected：新增接口缺失或断言失败；保存RED。
- [x] 实现新catalog/builder与明确loader版本分派。初批业务规格按preflight的10类编写，先复用既有表达式及项目解析器校验，不能放宽类型／表达式限制。
- [x] 重跑专项及`tests/test_benchmark_corpus.py`，Expected：全部PASS；旧语料快照不变。保留范围内差异，不自动commit。

## Task 2: 真SDK质量门禁及30个有区别缺陷扩展

**Interfaces:** 消费Task1 corpus，使用既有`validate_quality(corpus,output)`／`verify_quality(root,output)`；不新增替代SDK的Python解释器来判定仓颉程序正确。

- [x] RED `test_hard_baseline_reference_quality`先对代表性的退款／取整／多文件运行SDK，分别要求baseline_build PASS、baseline_holdout FAIL、reference_build/public/holdout PASS；未生成／缺陷未击穿时必须失败。
- [x] `../.venv/bin/python -m pytest tests/sdk/test_hard_benchmark_sdk.py -q --tb=short`，实际：既有通用门禁直接通过3项代表SDK集成检查；没有人为制造失败。30项新增契约先RED→GREEN，真实SDK日志另存。
- [x] 对10项执行CLI quality、verify-quality；Expected：10/10 qualified、两次result_hash一致。UNKNOWN或编译错误必须修正规格／实现／测试，不能计入合格数据。
- [x] 10项合格后扩30项，每个family使用3种不同缺陷：边界遗漏、规则顺序或计费组合错误、合法性／极值防护错误；目标业务规格保持明确，不能仅改变阈值充数。记录每个变体的真实差异和独立击穿输入。
- [x] RED `test_hard_thirty_defects_not_numeric_clones`断言每族有3个不同缺陷说明／源码逻辑与证据，不能以hash差异单独证明语义差异；人工审阅变体矩阵。
- [x] 30项quality／verify-quality，Expected：30/30 qualified和日志重建一致；重新检查所有搜索／缩减轨迹与holdout分离。未通过时状态保持执行中。

## Task 3: 可重放的反例轨迹与失败分类

**Interfaces:** `trajectory.analyze_run(corpus_root,run_root)->dict`先调用既有verify_run，输出schema_version=1、result_hash、record_manifest_hash、initial_candidate、rounds、observed_counterexample_feedback、later_repaired、failure_class及自身hash。只读；记录不完整为UNKNOWN，不启动SDK／模型请求。

- [x] RED `test_trajectory_first_round_miss_then_real_counterexample_feedback`：以SDK夹具造首轮公开PASS／独立搜索FAIL、第二轮修复PASS；报告关联同candidate/tree/attempt并指向实际反馈事件；标记FIXTURE，不能算真实模型增益。
- [x] RED `test_trajectory_first_round_success_not_claimed_iteration_gain`、`test_unknown_missing_or_wrong_tree_never_counts_success`：首轮成功不算反馈后修复；缺失搜索、模型未知、错误树引用、反例未发送或篡改源记录均不推断成功。
- [x] `../.venv/bin/python -m pytest tests/test_benchmark_trajectory.py -q --tb=short`，Expected先FAIL；实现最小只读分析及CLI，Expected全部PASS。
- [x] 失败分类至少区分生成输出无效／策略拒绝／构建失败／公开行为失败／搜索反例后耗尽／封存验收失败／基础设施未知。报告保存原状态，不用优先级分类抹掉UNKNOWN。
- [x] 原始运行结果协议不修改；轨迹附属报告绑定result_hash和原件，重放后hash一致。已有报告／完整分母兼容测试通过。

## Task 4: 冻结计划、获准真实对照与交付

**Interfaces:** 消费合格语料、既有`plan_runs`／CLI run、既有batch report与Task3轨迹。实际任务清单在门禁完成后确定，不能先宣称反例反馈必定出现。

- [x] 离线三流程SDK闭环及独立审阅；重要问题RED→GREEN；完整Python（排除live）／Node／git diff --check通过。测试期间源码完全冻结。
- [x] 为代表难例生成具体dry-plan（同模型和三流程），列任务、预期最大请求数、每次输出上限与输入材料；向用户申请精确新预算。未获批只保留NOT_STARTED，不能请求模型健康探测。
- [x] 获批后在相同执行身份上串行run；每个任务的三流程使用同预算，无人工替换模型答案，无削弱DIRECT对照。UNKNOWN停止整个批次，保留未启动分母。
- [x] 重放报告和轨迹，分别报告首轮修复、首轮遗漏、搜索发现、确已反馈、后续修复、失败及未运行数量；没有观察到反馈增益则明确写未观察到。
- [x] 在密钥／会话／上传数据排除后封存本批执行源码及必要原件，以便后续代码升级后使用对应原版本复现；不修改旧报告来适配新身份。
- [x] 写`docs/demo/next-phase-2-verification.md`、更新总目标真实进度，重读第3项；本阶段未全部满足时不得打勾或关闭整体目标。

## Plan self-review

本计划覆盖数据10→30、质量门禁、公开／搜索／封存隔离、同预算三流程、实际反馈轨迹、完整分母、版本与原件重放；新的付费预算保持独立。规格未授权的平台／语法／数据库／并发不在本阶段。实现方法继续由当前主代理逐项完成，结束时按既定流程一次独立审阅；不重新发起常规实施确认，不自动Git提交。Task1–3已完成，真实SDK质量与夹具轨迹见docs/demo/validation/next-phase-2；Task4全量回归、冻结与独立新预算仍在推进。
