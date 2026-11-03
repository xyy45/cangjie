# 受限操作序列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. User has approved continuous roadmap execution; preserve inline method, no repeated routine approval, no automatic commits/push/merge/cleanup. One fresh whole-stage review at completion.

**Goal:** 用户冻结显式状态模型后，通过真实仓颉状态串接产生可达操作序列反例，并驱动修复、重验和可追溯交付。

**Architecture:** 新sequence契约／解释器／服务，复用受限原始类型域、安全AST、原生轴、SDK副本和短事务CAS；公开原件助手仅作最小共享抽取。实际状态首次偏离参考后停止该轨迹，完整证据重建后由Python裁决业务。

**Tech Stack:** 既有Python3.12／Flask／SQLite／原生JS、仓颉1.0.5 SDK及core2；不新增服务或依赖。

**Spec:** `docs/superpowers/specs/2026-10-27-state-sequences-design.md`。可行性原件`docs/demo/validation/next-phase-3C-preflight/`；3B验收及冻结源码归档保持原样。

## Global Constraints

- 实际root /Users/jxy/Desktop/mass/CangSight-main，app为其CangSight-Nexus-Demo；工具默认旧cwd已不存在，所有命令显式workdir和/bin/sh。命令以下均从app执行。迁移记录在docs/demo/validation/relocation-20261027，不创建旧路径别名。
- 同包／最多3允许修改生产文件，选定同一函数1..4个Int64／Bool参数，1个状态参数与返回同类型；无对象／多字段／多函数入口／数据库／网络／并发。
- sequences_json原始UTF-8最多16KiB、严格14字段、version1/kindsequence；initial_states1..16、context_params0..3、operations1..4、invariants1..8、表达式1..1024字符、seed32bit。
- max_sequences8..16，max_steps2..8，搜索最多16轨迹／128计划调用；缩减可1步，最多2批、每批8轨迹／64计划调用。候选检查结构化／固定seed分别4096、总8192。
- 转移只允许state和arg<i>；初始状态／step_index可用于不变量，不能伪造函数不可见历史。参考模型矛盾／溢出／越状态域是拒绝或UNKNOWN，不冒称候选缺陷。
- 每轨迹一个真实SDK case；实际后态传下一步，在首次模型不等时输出结束并return，尾部不执行。完整SDK／协议成功后才可FAIL或PASS；异常／缺标记／错误前态等UNKNOWN。
- 保留输入任一步命中则整个模型轨迹不执行；所有已配契约保留集合相同。每份报告最多8条失败前缀进反馈／未来累计；历史保留并集不按8再次截断，raw全留且披露截断，累计超预算UNKNOWN。
- SDK执行阶段共享90秒、单批60秒、2MiB输出，不承诺端到端90秒。STARTED／未知／取消不自动重放，事务不跨IPC／SDK／文件哈希。
- 本阶段真实模型／远程分析预算0。SDK／原生核／本地MCP可真实执行；HTTP模型／分析夹具显式标注，不作为模型质量或6240准确率成绩。
- 保持8877独立已验收3B快照，后续产品修改不得影响其原文件；最终接受前不激活3C。保留大量历史脏改动及工作区，不reset／clean／自动Git集成。

## Review Focus

- 首次偏离以后不得执行可能命中保留输入的尾部；不能把计划步数冒称实际调用数；Task2／4真实SDK证明。
- 同SDK case的不同step完整args不同，定位不得碰撞或捏造SDK caseID；同step多个失败标签不得丢失；Task5验证。
- 初始状态不是整个状态域，公开中间状态例子仍校验模型；context整条恒定，隐藏历史转移与矛盾模型不得执行；Task1／3验证。
- 前置公开原件、关系报告或共享核验助手变更时，序列、接受、导出／下载均不得保持PASS；Task4／5验证。
- 迟到序列导入／草案响应、原始大Int64、当前UNKNOWN与缓存PASS冲突，不得覆盖确认或开放接受；Task6验证。

---

## Task 1: 契约、Markov参考链与有限轨迹

**Files:** Create `nexus/repair/sequences.py`, `tests/test_sequences.py`；只在必要时为既有oracle／properties暴露最小类型接口，旧语义不变。

**Interfaces:** `validate_contract(value,signature,examples)->normalized`；`sampler(contract)->oracle-compatible raw-axis settings`（raw值池不执行候选，不按保留集合提前删原始轴）；`trace_key(trace)`／`trace_score(trace)`；`reference_trace(contract,trace)->{eligible,steps,reason}`（初始前提false或保留命中eligiblefalse，模型错误抛ValueError）；`generate_traces(contract,axes=None,cumulative=[])->{traces,candidate_checks,regression_traces}`；`evaluate_step(contract,reference_step,actual)->{state,applicable,failures}`；`shrink_traces(contract,trace,failure_id,axes=None)->最多8轨迹`。trace恰为{initial_state,context,steps}，steps每项{operation_id,args}，args不含状态槽。

- [x] 写失败测试：`test_contract_rejects_hidden_history_in_transition`，transition含initial_state或step_index时ValueError；`test_public_middle_state_is_checked_outside_initial_states`，initial_states=[0]但域0..10，公开state7/amount7/paid10 expected14与模型cap10冲突时ValueError；`test_context_is_fixed_across_all_steps`，错误context槽或后步改context拒绝；Bool／Int64类型精确及输入对象后改不影响规范化契约。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequences.py -q --tb=short`，Expected缺失模块／接口RED，保存原始输出。
- [x] 实现严格14字段及16KiB、ID／类型／安全AST、初始显式列表／ctx索引别名、状态域与模型前后态、不变量模型一致性及公开匹配操作校验。保留输入允许域外但类型精确，不允许公开输入被保留。
- [x] 补RED：`test_reference_trace_preserves_reachable_states`，退款initial0、步骤7/7得到模型[7,10]；`test_reserved_intermediate_call_filters_entire_trace`，保留[7,7,10]后整条不执行；`test_invalid_model_is_not_silently_filtered`，参考溢出／域外／不变量false抛错；无适用初始或覆盖缺失拒绝，未匹配公开例子不冒称模型覆盖。
- [x] 实现原生轴等价的纯生成、同操作同参数重复／有序对／交替路径、固定seed补充、必需前缀先放；总8192、每通道4096，不展开大乘积。`test_generation_is_deterministic_and_bounded`断言同contract/axes结果相同、candidate_checks<=8192、轨迹<=16且总steps<=128；累计超预算抛错不截断。
- [x] 补RED并实现缩减：删操作及原始值缩减保持初始前提／context恒定／参考合法／保留过滤／failure_id仍可适用，严格trace_score下降，每批<=8；不执行候选或推断实际失败。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequences.py tests/test_relations.py tests/test_property_contract.py tests/test_oracle.py -q --tb=short`，Expected全PASS；旧语料身份与表达式不改变，无SDK／模型／MCP。

## Task 2: 逐步实际状态SDK协议

**Files:** Create `nexus/repair/sequence_trace.py`, `tests/test_sequence_trace.py`, `tests/sdk/test_sequences_sdk.py`；Modify `primitive_trace.py`, `tests/test_primitive_trace.py`（只增加保留协议前缀识别，正常harness不变）。

**Interfaces:** `sequence_trace.harness(contract,traces,package,token)->bytes`；`interpret(contract,traces,token,log,exit_code,problem,*,require_coverage=True)->dict`。结果恰含state、execution_state、counts、planned_calls、observed_calls、unexecuted_calls、observations、failures、per_operation、per_invariant、reason；UNKNOWN的observed_calls仅为0个已验证调用、unexecuted_calls=None，不冒称物理未执行数。observations每轨迹含sequence_id／真实test_id／initial_state／context／steps数组／planned_steps／observed_steps／unexecuted_steps／stop_reason／end_source。失败为business_sequence并保留该实际前缀，另含step_index／operation_id/text／before_state／actual_return／expected_state／model_mismatch／failure_ids／violations／source。有效1..16唯一eligible轨迹，1..8步；search完整覆盖要求all operations与invariants实际观测，shrink可require_coverage=False；有完整真实失败可FAIL，不因后来未执行覆盖把已验证首次偏离伪称成功。协议和结束字段严格遵照spec。

- [x] RED：`test_before_state_is_previous_actual_return`拒绝错误before；`test_model_mismatch_requires_exact_early_end`对3步计划的2步观测14、END2MODEL_MISMATCH解释FAIL并计planned3/observed2/unexecuted1；多余第3步、首步不等却ENDCOMPLETE、缺END、重复／乱序／跨case／nonce／STDERR均UNKNOWN。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequence_trace.py -q --tb=short`，Expected缺接口RED。
- [x] 实现可信逐步harness、目标函数类型别名／局部变量避名、固定model expected仅控制早停；每条轨迹单case，每step实际状态串接。decoder完整SDK summary集合、canonical Int64／Bool、日志坐标、唯一END和首次偏离重建，报告typed实际args／前态／返回／参考态和原件来源，不编造尾部。
- [x] RED旧primitive混入sequence OBS／END必须UNKNOWN；正常single／relation harness与3B归档golden字节一致。实现仅保留前缀识别，更新依赖hash覆盖，不改变旧协议kind集合。
- [x] 真实SDK：`test_sdk_sequences_chain_actual_state_and_stop_at_first_mismatch`、`test_sdk_bool_state_and_nonfirst_state_parameter`、`test_sdk_int64_low_and_128_planned_calls`；至少退款bad0→7→14早停、good0→7→10→10、Bool链、状态不在第0槽、16×8=128计划调用真实执行，无去重。同case test_id相同而step_index与source不同。保存CONFIG／LOCK／源／harness／完整SDKlog／执行argv／输入与结果。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequence_trace.py tests/test_primitive_trace.py tests/test_property_trace.py tests/test_relation_trace.py -q --tb=short`及`tests/sdk/test_sequences_sdk.py`，Expected全PASS。SDK运行期间不编辑其绑定源码；技术探针不能代替这些产品测试。

## Task 3: 上传确认与模型私有冻结

**Files:** Modify `nexus/uploads/service.py`, `routes.py`, `nexus/execution/workspace.py`；Create `tests/test_sequence_uploads.py`。

**Interfaces:** UploadService.confirm增加`sequences_json=None`；保存sequences_contract/hash/json/origin；profile仅放行`verification/sequences.json`为VERIFICATION_ONLY；case提供`independent_sequences`。无字段旧确认哈希保持相同。

- [x] RED单文件／同包工程、16KiB原始空白、重复键／非有限值／错类型、签名返回不匹配、四契约完整保留集合不等、oracle-v1非空保留、公开模型冲突、源码／路径／确认重放及跨actor／CSRF拒绝。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequence_uploads.py -q --tb=short`，Expected缺参数／字段RED。
- [x] 实现确认前严格校验与冻结，原文本保持、USER_CONFIRMED来源；保持100文件／2MiB计数和精确私有路径白名单，模型草案不取得序列所有权或许可，无SDK／MCP／模型执行。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequence_uploads.py tests/test_relation_uploads.py tests/test_property_uploads.py tests/test_upload_routes.py tests/test_project_service.py tests/test_rule_draft_confirmation.py -q --tb=short`，ExpectedPASS。

## Task 4: 服务、真实序列搜索与报告重建

**Files:** Create `nexus/repair/sequence_service.py`, `verification_evidence.py`, `tests/test_sequence_service.py`；Modify `relation_service.py`, `tests/test_relation_service.py`；Extend `tests/sdk/test_sequences_sdk.py`。

**Interfaces:** `verification_evidence.public_evidence(store,check,task,plan)->dict`抽取现有RelationService原件核验；旧方法委托；`SequenceService(ExplorationService).binding(candidate_id)`、`async run(candidate_id,deadline_at=None)`、`verify(candidate_id)`。sequence_runs唯一CAS；search／shrink batch保存原始计划、原生轴、harness、日志、END及typed结果。顶层计数使用search_traces、shrink_traces、regression_traces、search_planned_calls、shrink_planned_calls、observed_calls；最终步骤来源增加相应log_ref，不改变ANSI_STRIPPED_FULL_LOG坐标。

- [x] RED`test_changed_public_original_blocks_before_sdk`与`test_changed_relation_predecessor_invalidates_sequence`；共享助手返回事实与原实现相同，助手源码变化使新序列及关系旧PASS失效，缺报告不执行。运行service新测试Expected缺模块RED。
- [x] 抽取小型公开原件助手，关系引擎摘要纳入它；实现新service绑定顺序public／oracle／single／relation当前报告与原件，JSON契约／树／需求计划／源码依赖／SDK／原生核全绑定，CAS STARTED不重放。
- [x] RED并实现：仅同任务更早已验证失败前缀累计、每报告8条保留及多ID归组／明确截断；历史并集超过8但未超max_sequences时仍全部执行，不静默截断；可重建搜索／2批缩减计划及实际次数；改initial／context／步骤／END／参考状态／harness／日志／已复制生产材料均verify拒绝；取消／90秒执行预算／60秒单批／2MiB超限UNKNOWN。
- [x] 真实SDK`test_two_file_stock_sequence_fails_and_reference_regresses_prefix`、`test_real_sequence_shrink_reexecutes_reachable_prefix`：公开PASS而扣减取消失败，参考PASS且先前前缀实际重新执行；缩减删除操作／参数后仍由SDK证明原failure_id，不能直接运行任意中间状态冒称序列。原候选树及生产材料不变。
- [x] 保存纯服务及真实SDK原件。运行`../.venv/bin/python -m pytest tests/test_sequence_service.py tests/test_relation_service.py tests/test_property_service.py -q --tb=short`及`tests/sdk/test_sequences_sdk.py`，Expected全部PASS；verify无网络／SDK／原生IPC。

## Task 5: 控制、真实前缀反馈、定位与交付

**Files:** Modify `cang_sight_server/server.py`, `nexus/repair/cegis_loop.py`, `focus_service.py`, `localization.py`, `nexus/demo/deepseek.py`, `nexus/execution/delivery.py`, `archive.py`；Create `tests/test_sequence_gates.py`, `tests/sdk/test_sequence_loop_sdk.py`；Extend localization测试。

**Interfaces:** candidate.test返回可选sequences；RepairLoop按配置识别必需门禁并核对当前binding；failurekind business_sequence包含完整真实失败前缀。`localization.sequence_calls(failures,function)->(confirmed_cases,call_failures)`保留真正test_id，另给call_id=sequence_id+step_index，映射键增加可选call_id；最多8目标优先各失败步，再前置步骤，完整prefix仍在反馈／报告。

- [x] RED公开／前三项PASS但sequenceFAIL不得进入待审；前项失败不执行序列；成功包缺必需序列／候选树或契约不符仍拒绝；UNKNOWN停止后续模型。无sequence旧流程保持。
- [x] RED`test_steps_sharing_sdk_case_do_not_collide_in_focus`两个不同args共用test_id，实际step／call_id区分；多个失败标签同一步不丢失；>8定位目标明确truncated且反馈原始前缀完整。保留baseline源坐标和候选失败事实，不推断动态路径／根因。
- [x] 运行新gates／localization测试ExpectedRED，再实现门禁、带typed初态／每步／actual／expected／source反馈、提示及私有材料隔离。模型不能改配置／测试／契约／允许路径。
- [x] RED并实现check_set_hash／accept／export／archive／download均要求当前sequencePASS及先前报告有效；归档加evidence/sequence-report.json和sequences.json及原始全部材料，接受后改END／前置公开log／模型均阻断。
- [x] HTTP模型／分析夹具＋真实SDK／core／本地MCP两轮测试：首候选前项PASS且sequenceFAIL，第二个模型请求带真正可达前缀与不碰撞定位，第二候选PASS并审阅归档；改日志后实际HTTP下载400。禁止真实模型／远程分析请求。
- [x] 运行`../.venv/bin/python -m pytest tests/test_sequence_gates.py tests/test_relation_gates.py tests/test_property_gates.py tests/test_repair_loop.py tests/test_localization.py tests/analysis/test_repair_localization.py tests/test_delivery.py tests/test_project_archive.py tests/test_user_review.py tests/test_deepseek_demo.py -q --tb=short`及新SDKloop，ExpectedPASS。

## Task 6: 导入、逐步状态与当前验证展示

**Files:** Create `nexus/demo/static/sequences.js`, `tests/sequences-ui.test.cjs`, `tests/sequence-upload-ui.test.cjs`, `tests/test_sequence_web.py`；Modify `demo.html`, `upload.js`, `demo.js`, `feedback.js`, `localization.js`, `nexus/web/app.py`, `property_view.py`及必要已有UI测试。

**Interfaces:** 现有候选GET含verify后sequences，任务摘要含当前状态；`SequenceUI.render/roundState`沿用可选验证组合。服务端primitive_text增加initial_state／before_state／reference_before／expected_state／context／args的规范文本，原typed值不改。上传body可选sequences_json，原始Int64 JSON文本不经JS舍入。

- [x] Node／Flask先RED：16KiB导入、取消／错编码／大数原文、源码／函数／范围／关闭／手动编辑epoch使旧响应失效；模型草案应用保留手动序列，确认后只读，无配置无空面板。
- [x] 显示完整实际前缀、每步before／actual／expected、真实case＋step、源坐标、计划／观测／未执行尾部、缩减／累计／截断。最小UNKNOWN不出现undefined，全部textContent。
- [x] 新摘要UNKNOWN和缓存详情PASS双向冲突均UNKNOWN，失败刷新不得保留接受能力；拒绝入口仍可用。先RED后实现，并保留actor／CSRF，无新匿名执行接口／自动许可／模型请求。
- [x] 运行`node --test tests/*.test.cjs`及`../.venv/bin/python -m pytest tests/test_sequence_web.py tests/test_relation_web.py tests/test_property_web.py tests/test_sequence_uploads.py tests/test_upload_routes.py tests/test_workbench_race.py -q --tb=short`，ExpectedPASS。

## Task 7: 整体审阅、验收、归档与第4项衔接

**Files:** Create `docs/demo/next-phase-3C-verification.md`, `docs/demo/validation/next-phase-3C/`；Update本计划及总目标。

- [x] 明确禁调用浏览器夹具：导入／显式确认／只读回载、真实SDK序列FAIL／参考PASS／原件变化UNKNOWN与当前徽标，原始typed值核对，保存实际媒体格式／AX和来源。
- [x] 一次fresh整体审阅，Critical／Important集中RED→GREEN修复；Minor记ledger不顺带扩展；不二次审阅。保持工作区，不自动Git或删除原件。
- [x] 最后冻结对应源码和验证助手，运行完整`../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check`，Expected0失败；被测源码不可并行编辑。环境超时保留失败原件、诊断、同条件验证，不改断言或门槛冒充通过。
- [x] 封存源／core／真实SDK材料，反例与完整报告在禁SDK／原生IPC／网络的隔离重放PASS；第2项／3A／3B仍以各自源码独立重放。归档及嵌套ZIP有限配置凭据／私有路径检查，排除SDK安装包／.env／会话／用户上传原件。
- [x] 完整接受后检查8877在途操作，使用独立冻结3C快照沿用原数据／会话路径激活，绝不自动重试未知请求。只标3C完成，整体目标还有4A..4D／第5项；重读总目标再调研第4项。

## Plan self-review

契约／参考路径／保留、真实链／早停／计数、用户确认、报告与CAS／依赖、迭代／case-step映射／交付、精确页面、整体封存均有对应任务与RED→GREEN验证。Task1 trace/reference接口被Task2执行与Task4重建共同消费；Task3独立冻结供Task4／5；Task5typed完整前缀供Task6。8条保留与8定位目标是不同限制，完整原件不截断。公开模型只依赖可见参数，不再有隐藏历史例子歧义。builder无重要未决问题；常规执行沿用现有授权。
