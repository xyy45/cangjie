# 仓颉原生核心强化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将确定性边界、精确范围／状态和审批版本决策接入真实仓颉组件，绑定运行证据与状态版本。

**Architecture:** 新增无副作用的单文件仓颉core，通过有界JSON行IPC调用；旧policy1.1保留旧证据读取／兼容测试，新功能不得以旧组件或Python结果自动降级。服务负责可信事实、持久化和短事务CAS，仓颉负责确定性计算／决策。先完成边界生成纵切，再逐步切换门禁和状态写入。

**Tech Stack:** 固定仓颉SDK1.0.5、已有stdx.encoding.json、Python3.12、SQLite、pytest。

**Spec:** docs/升级改进开发计划.md；docs/superpowers/plans/2026-10-24-native-core-preflight.md。

## Global Constraints

- 延续用户已批准的持续开发；当前隔离分支保留所有旧改动。不重复确认，不进行无关提交或发布。
- 只有真实编译和执行可证明原生能力；组合／随机／保留输入过滤仍为Python，不宣称全部搜索原生。
- IPC总预算2秒、输入和输出分别最多64KiB；严格版本、字段、请求／载荷摘要、退出状态、组件前后摘要校验。失败关闭，无Python降级。
- 单个main.cj是完整编译源集合；若扩展文件集合必须同时修改构建清单和身份校验。
- 不在SQLite写事务中等待原生进程、编译器、模型或网络；提交时CAS检查版本。
- 阶段4付费实验尚未执行；最终同一组件版本重新比较。
- 本次不做自动Git提交，避免把大量历史未提交改动混入提交；保留逐项测试／审阅证据。

## Review Focus

Int64最小／最大值邻近不溢出；Bool不能当整数；损坏／多响应／超大响应／挂起进程失败关闭；原生证据被篡改或组件变动不得通过验证；决策后任务或审批版本变化不得执行副作用。分别归任务1、2、3、4测试。

### Task 1: 原生边界组件与有界IPC

**Files:** Create cangjie/core/src/main.cj, scripts/build_core.py, nexus/policy/core.py, tests/integration/test_native_core.py。

**Interfaces:** `NativeCoreClient(root).call(operation, payload, deadline_at=None) -> proof`（异步），`component_identity() -> dict`；proof含request/response/component。`boundary.axes`接收0..16个具名Int64／Bool域，返回稳定去重二维axes；0参数保持既有常量函数规则语义，返回空轴但生成一个空参数调用。Int64域min/max均为Int64，points最多8个且在域内；顺序与既有axis_values一致。

- [x] RED：不存在组件时调用不可能得到成功；真实进程对[-2,3]points[1]返回[0,-2,3,1,2,-1]；Bool返回[false,true]；极值、不合法域、重复名字、未知字段拒绝。
- [x] 运行 `../.venv/bin/python -m pytest tests/integration/test_native_core.py -q --tb=short`，Expected: 新能力缺失导致FAIL。
- [x] 实现native轴和版本化IPC；构建以独占临时目录编译、校验源／编译器未变、原子替换二进制与记录；身份覆盖全部实际源／二进制／编译器。
- [x] 真实SDK构建并运行上述测试，Expected: PASS；补充绑定错误、非零退出、超长／第二行响应、超时、缺失／变动组件测试，Expected: 拒绝。

### Task 2: 独立搜索使用原生边界并归档

**Files:** Modify nexus/repair/oracle.py, nexus/repair/exploration.py, tests/sdk/test_exploration.py；Create tests/test_native_boundaries.py。

**Interfaces:** Task1 proof；generate_inputs(contract, axes=None)、shrink_inputs(contract,args,axes=None)保持默认纯Python规则校验用途，生产ExplorationService必须传入经原生组件验证的axes。组合、随机、缩减附加邻近值与封存输入过滤仍使用Python。

- [x] RED：真实SDK搜索／交付报告必须含native_boundary，组件与engine绑定；无组件返回UNKNOWN且无探测批次；篡改proof不能verify／交付。
- [x] 运行上述测试，Expected: 新proof／门禁缺失FAIL。
- [x] 请求一次原生轴，搜索及缩减使用同一不可变轴；记录完整proof，重放验证请求等于确认规则域、响应绑定／类型／轴值及组件身份；原生失败不调用Python生成替代结果。
- [x] 运行 `../.venv/bin/python -m pytest tests/integration/test_native_core.py tests/test_native_boundaries.py tests/test_oracle.py tests/sdk/test_exploration.py -q --tb=short`，Expected: PASS，真实公开PASS→搜索FAIL→下一候选PASS及交付保留proof。

### Task 3: 精确范围／状态／审批版本门禁

**Files:** Extend core main.cj and nexus/policy/core.py；Modify cang_sight_server/server.py, nexus/adapters/cangjie/verifier.py, nexus/demo/probes.py；Create tests/integration/test_native_core_policy.py。

**Interfaces:** `policy.decide`可信facts由服务从当前任务／需求／审批原件派生；绑定实际allowed_paths、status、revision、树、需求／验证计划、当前check_set和审批覆盖版本／期限。新活动调用显式使用新原生核，不按错误自动回退旧policy。

- [x] RED：范围外／重复路径、状态不匹配、旧树／旧需求／过期审批时动作计数0；合法修复与导出允许；新核缺失不执行。
- [x] 实现并真实编译；重用既有门禁的参数摘要和组件前后复查，验证计划绑定新组件。
- [x] 运行新测试及现有policy/MCP/SDK交付回归，Expected: PASS。

### Task 4: 状态转换原生决策与版本CAS

**Files:** Extend core；Modify nexus/store.py, nexus/execution/workspace.py, delivery.py, review.py, ownership.py, nexus/repair/cegis_loop.py；Create tests/integration/test_native_state.py。

**Interfaces:** 原生`task.transition`检查from/to/revision/attempt；持久化使用原生决策覆盖版本短事务CAS；全部权威状态写入口一致覆盖，包括循环claim、交付reserve/finish和恢复。

- [x] RED：终态复活／非法转换拒绝，决策后并发revision变化无法登记候选或发布；合法恢复／幂等导出保留。
- [x] 实现全部状态入口的原生检查与CAS，不在长操作期间锁库。
- [x] 新测试及原CEGIS/ownership/review/delivery测试，Expected: PASS。

### Task 5: 验收与交接

- [x] 独立审阅任务1–4的实际改动，重要问题用RED→GREEN修正；保存证据。
- [x] `DEEPSEEK_API_KEY=upgrade-test-placeholder DEEPSEEK_BASE_URL=https://fixture.invalid DEEPSEEK_MODEL=test-model ../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`；Expected: 全部离线PASS，live未运行明确记录。
- [x] `node --test tests/*.test.cjs`；`git diff --check`；Expected: PASS。
- [x] 更新阶段5验证文档、总计划，重读总计划继续第6阶段；若只完成子项如实标为执行中。
