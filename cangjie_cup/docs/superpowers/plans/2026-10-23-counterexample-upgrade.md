# 独立反例驱动修复 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Track actual verification below; do not stop for ordinary phase transitions.

**Goal:** 在现有上传修复中加入确认规则、有限边界搜索、缩减反例、下一轮修复和交付门禁。
**Architecture:** 独立规则解释器/输入生成器与仓颉探测执行器分离。确认规则存入冻结工程非源码文件并绑定验证计划；普通测试之后执行搜索，记录独立证据，经现有candidate.test策略门禁调用，不修改原测试与候选。
**Tech Stack:** Python 3.12、Flask、SQLite、原生JavaScript、固定仓颉1.0.5、现有沙箱。
**Spec:** ../../升级改进开发计划.md

## Global Constraints

- 原有测试/候选不可改写；不eval/exec规则；无规则保持旧行为。
- Int64/Bool现有上传范围、三轮候选及480秒总预算不放宽。
- 所有PASS须由实际执行、匹配工具链/源码/规则摘要的日志支撑。
- 不提交密钥、私有会话及运行目录；不发布或推送到main。

## Review Focus

- 规则与公开预期矛盾：拒绝确认。
- 表达式类型混淆、溢出、零除、恶意语法：拒绝或UNKNOWN，不能变成候选失败/成功的假证明。
- 重复请求、重启、结果缺失：不回放未知执行，不复用旧候选结果。
- 原测试PASS但搜索FAIL：禁止审阅/交付；新候选须再次执行累积反例。
- 规则、来源、日志或探测工程被改变：摘要检查阻止使用/交付。

## Task 1: 规则契约与可重放输入

Files: create nexus/repair/oracle.py; tests/test_oracle.py.
Interfaces: validate_contract(value, signature, examples) -> canonical dict; expected(contract,args) -> Int64/Bool; generate_inputs(contract) -> list[list]; shrink_inputs(contract,args) -> list[list].
- [x] 写失败测试：临界点1000/1001/1500/1501、Bool组合、种子重放、类型/越界/非法语法/规则矛盾。
- [x] 执行测试确认RED；实现白名单解释器与有预算生成/缩减；执行确认GREEN。

## Task 2: 上传确认及冻结绑定

Files: modify nexus/uploads/service.py, routes.py, requirements/service.py; tests/test_upload_oracle.py.
- [x] 先测试：规则可选、确认幂等绑定、相同请求不能换规则、公开用例一致性、冻结清单包含规则，旧接口兼容。
- [x] 在上传confirm增加可选oracle参数，非源码验证文件加入VERIFICATION_ONLY，计划与原始来源绑定。
- [x] 执行专项及旧上传回归。

## Task 3: 实际执行、反馈及门禁

Files: create nexus/repair/exploration.py; modify cang_sight_server/server.py, nexus/repair/cegis_loop.py, nexus/execution/delivery.py, archive.py; tests/sdk/test_exploration.py; tests/test_exploration.py.
Interfaces: ExplorationService.run(candidate_id,deadline_at) -> persisted report; verify(candidate_id) -> validated report or error.
- [x] 先写真实SDK反例验证/两轮修复集成测试及失败门禁测试，确认RED。
- [x] 普通candidate.test通过后在现有策略门禁内运行搜索；单独工程内生成仓颉断言，保留原日志与摘要。
- [x] 受限批量缩减与累计反例；反馈中加入已验证失败；关闭不确定状态；交付验证并归档。
- [x] 验证原候选、公开测试字节不变，规则/日志篡改不能交付。

## Task 4: 页面与验收

Files: modify nexus/demo/static/upload.js, demo.js, templates/demo.html; add UI tests; docs/phase1-validation.md.
- [x] 规则JSON输入/导入及示例；确认勾选绑定规则；展示普通验证与搜索分开状态、用例、规则依据、反例/缩减。
- [x] 页面专项测试及浏览器检查；运行全量离线回归。
- [x] 记录真实SDK证据、夹具模型边界和失败情形；更新主计划，重读并继续阶段2。

## Execution Ledger

2026-10-23：方案已由用户确认，直接在现有非main工作分支实施，保留未提交历史更改。为避免中断当前运行项目，先保存被修改文件的阶段前副本；不清理工作树。后续集成审阅仅比较本阶段差异。

2026-10-23 实施记录：Task1规则引擎与Task2上传绑定专项已通过；真实SDK首批3用例通过（公开PASS→搜索FAIL→缩减→下一轮PASS→归档）。Node当前83项通过。初次非提权Python回归4项因沙箱/端口权限失败，已保留日志；随后完整离线回归407 passed、1 deselected、330.38s。独立审阅发现并修正公开诊断隐藏、编辑用例清空规则、规则手工编辑事件、探测工程完整性及非法表达式类型问题；新增RED测试已复现，修正后完整回归仍在运行，故阶段1尚未验收完成。

Ruling：规则私密性只针对独立规则JSON，不对上传项目自己的公开测试/编译日志进行全局隐藏；真实隐藏测试仍遵循原策略。探测工程保留用于验收时复核其源码和配置，不仅验证归档日志。没有规则仍保持原功能。
Ruling：当前分支承载此前用户的未提交改动，暂不批量提交；本次变更用 /private/tmp/cangsight-upgrade-prephase1/ 的阶段前副本核对，避免把历史改动混入本阶段提交。

2026-10-23 阶段1完成：最终全量离线Python413 passed/1 deselected（396.40s）、Node83 passed、diff检查通过。保留原候选及冻结测试、规则，独立搜索证据纳入交付门禁。重新读取主计划后继续阶段2。
