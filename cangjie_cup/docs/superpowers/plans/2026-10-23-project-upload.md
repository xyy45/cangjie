# 多文件仓颉工程上传与修复 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. 按已确认升级目标连续执行，每个任务保留RED/GREEN及集成证据，不因阶段切换重复询问授权。

**Goal:** 将用户自己的仓颉小工程通过ZIP或目录导入现有修复闭环，定位和修改跨文件业务缺陷，保留其测试及接口，并兼容阶段1独立反例验证。
**Architecture:** 安全归档读取与工程索引独立；复用现有上传身份/需求确认、冻结清单、候选副本、原生MCP、策略门禁及交付链。工程模式与单文件模式显式区分。项目级符号索引链接多个生产文件，不能把相互调用误判成外部调用；MCP暂按真实接口逐文件提供结果，不伪造工程级图。
**Tech Stack:** Python zipfile/tomllib、现有Flask/SQLite/JavaScript、固定仓颉SDK和沙箱。
**Spec:** ../../升级改进开发计划.md（阶段2）

## Global Constraints

- 单文件上传及阶段1规则/反例闭环全部保持。
- 不允许路径穿越、重复/大小写或Unicode归一化冲突、符号链接、隐藏执行材料、build.cj、动态安装依赖。
- 对不支持的工程清楚拒绝，不静默替换源码、伪造测试或改写用户预期。
- 初版工程支持现有Int64/Bool普通函数在同一仓颉包内跨文件调用。函数签名保持，扩展语法另行逐类验证；不直接移除原语言限制。
- 原配置与测试冻结；候选仅修改经确认的生产源码。允许文件、构建根、规则、测试映射和工具链与计划绑定。
- 导入工程不执行任何代码；运行继续经过candidate.build/test策略门禁及现有沙箱。
- 归档安全读取上限：压缩上传2MiB，最多100文件，解压总2MiB，单文件128KiB，生产.cj仍64KiB/1000行；入口拒绝不支持材料。目录上传复用相同清单校验。

## Review Focus

- ZipSlip、链接、重复/规范化冲突、压缩炸弹和非法配置在注册前拒绝，失败无半成品。
- 工程多文件存在同包函数调用时索引必须识别；重复定义、缺失调用、跨包/外部能力明确拒绝。
- 公开测试和规则不能被候选修改；搜索探测必须编译所有相关生产文件，不能仅复制一个文件而遗漏缺陷。
- 修改2个文件的提案保持基线摘要、接口和累计修改；重试不能跨候选混用结果。
- 文件目录选择切换、迟到响应、确认版本变化和不同浏览器会话不能混淆工程或泄露源码。

## Task 1: 安全工程归档读取

Files: create nexus/projects/__init__.py, archive.py; tests/test_project_archive.py.
Interfaces: read_archive(data:bytes)->dict[str,bytes]; read_entries(entries:dict[str,bytes])->dict[str,bytes]。输出规范相对路径、未经改写的文件字节；单个共同外层目录可归一化，多个构建根须明确拒绝/选择，不猜测根。
- [x] RED：两生产文件+原cjpm+测试的正常ZIP保留字节；穿越、重复、链接、超量/超限、歧义构建根及大小写/NFC冲突拒绝。
- [x] GREEN：只在内存按预算读取，不extractall；校验所有条目再返回，无文件副作用。

## Task 2: 工程配置与符号/测试索引

Files: create nexus/projects/index.py; extend nexus/uploads/language.py with project-aware inspection; tests/test_project_index.py.
Interfaces: inspect_project(files)->项目名/构建根/生产文件/函数签名及声明位置/公开测试标识/限制；validate_project_candidate(files,baseline_index)->None。
- [x] RED：同包跨两个文件调用被正确链接；未知函数、签名变化、重复定义和外部能力被拒绝。
- [x] 校验cjpm静态包与无外部依赖配置。保留原始源码与测试，明确支持的测试结构，对无法可靠映射的结构拒绝而非猜测通过。
- [x] GREEN：真实SDK构建新生成的小工程，确认跨文件调用及原测试标识与索引相符。

## Task 3: 上传确认与执行闭环

Files: projects/service.py, routes.py（或复用uploads/routes.py）；modify uploads/service.py, requirements/service.py, repair/cegis_loop.py, analysis/repair.py, repair/exploration.py, execution/archive.py；tests/test_project_service.py, tests/sdk/test_project_repair.py。
- [x] 为工程上传保留原归档/清单、冻结测试与配置、会话所有权和幂等确认；显式kind=PROJECT并维持旧记录兼容。
- [x] 确认允许修改的生产文件及可选规则；规则可选目标函数来自工程索引。
- [x] 模型上下文按文件提供正确基线摘要；校验多文件累计提案。工程MCP调用范围真实标识，不伪造完整跨文件分析能力。
- [x] 普通工程构建/测试使用原测试；独立规则探测复制全部必要生产文件，在原工程包内追加服务持有的探测测试。
- [x] 真实SDK与确定性模型夹具验证：新导入工程必须改两个文件才能通过独立验证，原源码/测试/配置不被改写，交付清单包含完整工程及证据。

## Task 4: 上传界面与阶段验收

Files: demo/templates/demo.html, static/upload.js（按职责拆分工程导入组件）；tests/project-upload-ui.test.cjs；fixtures/projects/；docs/demo/upgrade-phase2-verification.md。
- [x] ZIP/目录选择、工程树与构建根、函数选择、公开/独立验证状态、确认范围；有错误时显示具体文件及原因。
- [x] 浏览器上传→修复→审阅→交付闭环；原单文件界面和阶段1回归保持。
- [x] 全量离线Python、Node及差异检查；独立审阅修正重要问题；记录真实工具/夹具模型/未覆盖限制。
- [x] 更新并重读主计划，进入阶段3切片驱动定位。

## Execution Ledger

2026-10-23：阶段1全量413 passed/1 deselected（396.40s）、Node83 passed后重新读取主计划，开始阶段2。先实现内存归档读取和工程索引，不扩大运行权限；在完整工程、冻结测试与规则探测接入前，不对外宣称已支持工程修复。

阶段2 Task1：已实现纯内存ZIP/目录清单读取，专项16项通过（0.05s）。含路径穿越、大小写/NFC及父目录冲突、文件/目录冲突、链接、无效ZIP、歧义根、源码编码与文件/归档预算测试。尚未接入上传API，不声明工程修复已可用。下一步执行Task2工程索引，再集成运行闭环；阶段1验收证据仍保留。

阶段2 Task2：工程配置/符号/测试索引16项通过；与归档和原语言门禁合计55项通过（0.10s）。真实SDK专项1项通过（4.79s），跨文件调用初始两测试失败，修改fee后同标识测试通过且原配置和测试字节不变。Task3服务/旧上传专项累计66项通过（1.27s），两文件三轮修复和SDK索引集成2项通过（37.72s）；仍待界面、全量回归和独立审阅。

Ruling: 首版测试索引仅接受标准@Test类内@TestCase零参方法中的单条@Expect(生产函数(字面量参数), 字面量预期)，不解释任意测试辅助代码 — 可精确绑定测试标识和实际原件，避免把不可识别测试视为已验证 — 复杂测试需要后续逐类扩展。
Ruling: 保持现有单次最多3个编辑文件的策略/预算，工程可包含其他只读源码，但确认时必须明确1至3个可修改文件 — 复用原策略边界 — 不支持一次修改任意大工程。

阶段2最终验收：Python461 passed/1 deselected（437.25s），Node87 passed，差异检查通过。独立审阅两项Important修正且复核无剩余。最终浏览器ZIP→范围确认→真实SDK普通测试4项／独立搜索64项→接受→导出→下载HTTP200，原ZIP字节一致。验证模型为确定性夹具，未调用付费DeepSeek。证据见docs/demo/upgrade-phase2-verification.md及validation/upgrade-phase2。
Ruling: 最终冻结工程沿用WorkspaceStore总预算100文件／2MiB，包含追加测试、补充锁文件和可选规则 — 在确认前检查，超限清除暂存并保持DRAFT，明确要求精简材料 — 上传接近上限的用户工程可能需要删减文档；不会确认后才发现无法导入。
