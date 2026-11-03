# Deployment and Reproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从无密钥运行包完成指定macOS ARM64环境的真实安装、构建、启动、自检、诊断和一次上传至交付的复现。

**Architecture:** 扩展已有doctor入口，使用明确字段的诊断包及白名单源运行包；现有Flask／SQLite／core2／修复服务保持。独立新目录执行复现和并发测量，主站与历史原件保持。

**Tech Stack:** CPython3.12.4、原40项requirements.lock、Flask、SQLite、原生JS、仓颉SDK1.0.5／stdx1.0.5.1、MacOSX15.4开发SDK；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-03-deployment-reproduction-design.md`

**2026-11-03 用户范围变更：** 只合入已完成的跨包修复及本计划Task1／Task2部署工具，重启8877供测试。Task3和Task4完整干净部署旅程暂停，不继续自动实施。审阅、必要集成验证、数据保持和主站切换已完成，详见`docs/demo/next-phase-4D-verification.md`；不能将此范围变更写成第5项原始目标全部完成。

## Global Constraints

- 验收目标macOS ARM64／CPython3.12.4；其他平台／版本未验收，不宣布通用兼容。
- 新付费模型／远程6240调用预算0；HTTP模型和图夹具显式标识，本地SDK／core／stdio与下载真实。
- 不读取原`.env`、主站运行库或会话；不包含用户源码、浏览器记录、模型原始调用及历史批准于诊断／程序包。
- 不进行Git写入、分支、提交、推送、清理；不覆盖历史失败、归档、快照、main或旧运行实例。
- 4D408份审阅源保持；本阶段产品实施在独立副本，未完成4D审阅不能据此切换8877。
- 原依赖锁不因现有环境25项差异而盲目升级；所有新产物独立清单并复读核验。
- 常规阶段沿用既有批准；一次阶段独立审阅和作者重要问题修正，不逐任务分派审阅。

## Review Focus

1. 诊断的缺项错误或路径信息不能间接包含密钥／源码；Task2用诱饵私密文件及受限读取控制固定。
2. 程序包在无.git、无PYTHONPATH、不同解压路径上能启动，避免只在开发机可用；Task1／4真实子进程固定。
3. 端口检查与启动存在竞态，二次启动不能夺取数据写权；Task1／4占用及OS锁控制固定。
4. 原件校验移出SQLite事务若发生版本变化，不能提交旧检查；Task3按测量结论决定修改并固定替换控制。
5. 重启及配置缺失不能隐式产生付费重试或借用旧批准；Task4零外部请求计数和未知状态固定。

---

### Task 1: 可执行自检与退出语义

**Files:** 修改`scripts/doctor.py`；新增`nexus/deployment/checks.py`及必要`__init__.py`；新增`tests/test_deployment_checks.py`。不改变`inspect_environment()`现有返回接口。

**Interface:** `checks.inspect(*, provider, port) -> dict`返回schema_version、target、checks、ready、connectivity=NOT_PROBED；CLI支持`--provider deepseek|rule`、`--port`，JSON默认输出，退出码0／1／2。探测只读、有界，不启动应用或新建运行库。

- [x] 首先读取现有doctor／readiness调用者和测试；RED：直接脚本与module在无PYTHONPATH时一致，锁依赖缺项／错版、SDK／core／开发SDK缺失、版本探测超时、模型配置缺省、rule模式、占用端口、非法端口／参数、敏感值不得出现在输出。
- [x] 实现最小检查模块与CLI，复用原组件身份和固定工具，不发网络请求。端口探测后关闭socket，不宣称预约成功。
- [x] 运行新专项及原provider／demo／readiness相关测试；真实独立环境运行两种入口、占用端口控制并保留实际退出状态，确认当前开发与主站环境未变。

Task1阶段证据（2026-11-03）：独立副本`.superpowers/sdd/2026-11-03-deployment-reproduction/app`，2301文件冻结摘要`84968884598978c2ab8bfb74237479490250a7573821b1b24c72cd62eea5c5eb`。缺模块RED后，新自检22通过；合并页面／配置／所有权／中断恢复专项44通过，旧doctor／readiness5通过，集合不重复相加。首次默认沙箱因禁止loopback bind产生的失败保留，同源经测试执行许可后真实端口控制通过。仅改doctor入口及新增检查模块／测试，旧inspect_environment函数体未改；没有传播到实际应用目录或8877，不代表第5项整体验收。

### Task 2: 无密钥诊断及程序包

**Files:** 新增`scripts/diagnostics.py`、`scripts/package_app.py`、`nexus/deployment/artifacts.py`、`tests/test_deployment_artifacts.py`；更新`docs/runbook.md`及无密钥配置模板／第三方说明。

**Interface:** 诊断仅取Task1允许字段，ZIP含`diagnostic.json`及manifest；程序包按明确生产路径清单组装，保留当前源码与脚本摘要、平台和锁。所有输出拒绝覆盖；路径／普通文件／大小有界；写后重新读取核验。

- [x] RED：隐藏`.env`／用户源码／SQLite／会话／模型日志诱饵不会被读取或打包；符号链接、非规范路径、重复成员／输出、输入改变、意外额外文件均拒绝。没有.git的解压包包含真正必需的模块、模板、静态资源与安装脚本。
- [x] 实现字段选择、确定清单、摘要验证与唯一输出。必要开源文件和无密钥模板纳入；依赖wheel独立提供，不复制site-packages／已装SDK／主站.runtime。
- [x] 执行专项并逐条解压检查；在新目录使用产物自检，不把依赖包或源码zip本身当成完整运行证明。更新实际命令；历史LIVE／旧平台路径与新步骤分开。

### Task 3: 大原件与SQLite并发实测

**状态：按用户最新要求暂停。**

**Files:** 新增受控开发测量脚本及`docs/demo/next-phase-5-concurrency.md`；只有测量证实必要时修改实际服务事务，并补对应并发测试。

**Interface:** 测量报告绑定源码／core／数据规模／环境，包含请求总耗时、BEGIN等待、实际写锁区间、独立读和第二写连接等待／退出；只记录SQL类别，不记录参数或原始SQL。

- [ ] 先在自建独立运行库建立真实大原件正常缓存和一份篡改拒绝控制，保留原报告／源码；不操作旧封存运行库和8877数据。
- [ ] 运行单请求及并发读／写探针，验证计时覆盖实际事务边界；实际SDK／模型等待不在事务。保存负载、原件规模、失败和结果，禁止拿此前24.18秒profile当新基线。
- [ ] 根据数据判断是否优化并记录决定。若修改校验时机，先RED真实并发替换候选／源／报告／所有权后必须拒绝旧结果，再GREEN及相关四服务／交付回归；若不修改，给出测量证据与适用限制。

### Task 4: 从交付包完整复现及最终验收

**状态：完整新环境旅程暂停。** 本轮仅完成已开发功能的审阅修正、集成回归与原库无损重启，不勾选未执行的完整旅程。

**Files:** 新增`docs/demo/next-phase-5-verification.md`及明确原件目录；更新总体路线图、运行文档、阶段计划和账本。

- [ ] 从Task2程序包解压至新目录，创建不继承依赖的venv，安装原40项锁、原始归档SDK／stdx并实际构建core；保存每条命令、退出、版本与新身份。宿主开发SDK依赖明确。
- [ ] 自检→独立端口启动→上传自建跨包工程→分析／有限迭代修复→真实SDK独立验证→本地会话人工审阅→导出／实际HTTP下载及全归档摘要核对；模型／图夹具与真实本地链路明确区分。
- [ ] 缺依赖／配置／SDK／core、占用端口、双控制器写权、正常重启／未知操作不重发、会话恢复、旧批准拒绝，均真实运行并计数外部调用0；正常关闭自有服务、保留失败。
- [ ] 一次新阶段独立审阅，作者对重要问题集中RED→GREEN修正；完成与改动相称的最终Python／Node／SDK回归、原件独立重建、有限打包扫描和diff检查。不复用4D源码结果冒称5的新版本全量通过。
- [ ] 重读总体路线图，对每项必需需求及历史未决问题核对实际证据；4D终验／切换、5完整交付和总体审阅全部完成才关闭整体目标。未测平台、真实模型质量及外部成员复现保持实际边界。
