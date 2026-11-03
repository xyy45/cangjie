# Bounded Packages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在单个冻结CJPM根内支持有界跨包仓颉工程的真实分析、受约束修复及独立验证。

**Architecture:** 源码先建立逐文件导入作用域和规范符号索引，再复用既有闭合类型／表达式解析器。Scoped契约与V5观测保留包身份，固定本地SDK的依赖JSON和测试XML提供完整证据；现有同包版本逐字兼容。

**Tech Stack:** Python 3、现有Web/SQLite、仓颉SDK1.0.5、仓颉策略核、现有原生JS，无新第三方依赖。

**Spec:** `docs/superpowers/specs/2026-10-30-bounded-packages-design.md`

## Global Constraints

- 一个冻结cjpm根；100文件／2MiB；每生产文件64KiB／1000行／4000 token；每文件16函数体、总128；允许编辑最多3个已有生产文件。
- 16用户包、8段／191字符包名、64字符局部标识符、256字符规范符号；4个有限只读类型，参数／字段／方法沿用4C限制。
- 原测试256、公开2—32；测试套件ID246、用例ID311；XML257文件／288用例；扫描、stdout及XML原件合计2MiB；native IPC64KiB不扩张。
- Oracle6、属性／关系／序列5仅接受受信scope；V5对象wire2333，旧V4仍2141；禁止模型提供scope或注册表授权。
- 空外部依赖、无脚本／下载／工作区多构建根；导入／配置／接口／原测试冻结；私有入口桥接只在独立验证副本。
- 新付费模型／远程6240调用0；可用明确模型／图夹具，SDK/native/XML必须真实。不得用夹具成绩冒充模型质量。
- 不进行Git写入、提交、推送、清理；保留全部历史脏文件、失败、原件、旧快照。开发目录与运行中的独立4C主站隔离，最终验收前不切换。
- 一次设计builder检查；原生逐项执行，一次最终fresh审阅与作者修复阶段；常规阶段沿用既有确认，不重复询问。

## Review Focus

1. 包别名、局部名与同名类型叠加时，逐文件解析不能串包，也不能通过遮蔽访问非公开函数；Task1/2固定断言。
2. 公共测试与原测试使用相同类／case名或测试专用包时，XML必须覆盖全部规范ID，不能把首个Summary当全部；Task4固定断言。
3. 空根包、私有子包入口与仅签名相关导入的验证桥接不能引入环或泄漏进交付；Task3/6真实SDK覆盖。
4. 长规范名、CRLF／注释／String内伪导入与篡改XML路径不能破坏坐标、预算及原件归属；Task1/4测试。
5. 恢复／缓存／审批／导出时替换scope、图、源码、XML、桥接或工具身份必须失效；旧任务继续用各自旧协议重建；Task5/6/7覆盖。

---

### Task 1: Pure package headers and per-file scopes

**Files:** Create `nexus/projects/names.py`, `nexus/projects/scopes.py`; test `tests/test_package_scopes.py`.

**Interfaces:**
- `local_name(value: str) -> str`, `package_name(value: str) -> str`, `symbol_name(value: str) -> str`, `suite_name(value: str) -> str`, `case_name(value: str) -> str` validate separate bounded names.
- `read_header(source: str, path: str, root_package: str) -> dict` returns package, imports and original remaining `(token,line)` body items; no execution or source rewriting.
- `build_scopes(files: dict[str,bytes], root_package: str, declarations: list[dict]) -> dict` consumes exact canonical declaration records `{name,local_name,package,path,kind,public}`; returns `{packages,scopes,dependency_graph,graph_hash}`. `scopes[path]` holds package, imports, bindings, body_items. `resolve(scope: dict, spelling: str, *, kind: str|None=None) -> str` resolves local or package-qualified source spelling to canonical identity.
- Declaration graph version1 has sorted packages, production_edges/test_edges, imports with specifier/kind/alias/target_package/path/line/origin, and dependencies-first topological_order. Hash is existing canonical `digest(graph)`.

- [x] Write tests for same-named symbols, file-specific aliases, package/wildcard/type bindings, public visibility, cycles including test edges, source path-package matching, exact bounds, fake imports in comments/String and CRLF line preservation. `assert resolve(scopes['src/order.cj'],'cost') == 'bench.money.fee'` while another file without import raises.
- [x] Run `../.venv/bin/python -m pytest tests/test_package_scopes.py -q` expecting missing module RED; preserve log.
- [x] Implement only closed header and nonexecuting scope binding, sorted dependency DAG and strict name validators. This is metadata, never product admission or evidence of compiler success.
- [x] Run the above plus `tests/test_project_index.py tests/test_object_values.py tests/test_object_projects.py`; expect all PASS. Record exact counts/logs in ledger, no commit.

### Task 2: Scoped typed project index

**Files:** Create `nexus/projects/scoped_index.py`, `scoped_language.py`, `scoped_tests.py`; modify `projects/index.py`, `uploads/language.py`, `uploads/object_types.py`, `repair/object_values.py`; test `tests/test_package_index.py`, `tests/sdk/test_package_index_sdk.py`.

**Interfaces:**
- Uses Task1 headers/scopes; `inspect_scoped(files: dict[str,bytes], root_package: str) -> dict` emits index2 exactly as spec.
- Parser accepts optional trusted `scope` plus canonical `types` and declaration registry; `Parser.program(headers_only=False)` retains old output without scope. Scoped type/constructor/function/method resolution uses source aliases, never canonical source substitution.
- `object_values.type_name(value: str) -> str` admits bounded simple or canonical registered type IDs; field/method `name` unchanged.
- `inspect_project` routes only cross-package/nested/workspace-import material to index2; `validate_project_candidate` additionally binds imports/graph/scope, not body hashes of permitted files.

- [x] RED tests: identical fee/State/Cases names across3packages, aliases only file-local, qualified calls, all method bodies checked, imported names cannot be shadowed, original constructor literal and return projection mapping; reject external/private/cycle/bad path/graph change. Assert old project index byte-shape unchanged.
- [x] Verify unproven SDK cases in owned probes first: wildcard/package alias, empty root/TestOnly and coordinates; preserve each source/log/exit. No product permissions relaxed.
- [x] Implement two-pass header/symbol registry then existing typed body checks with trusted resolution; canonical IDs and source tokens/coordinates retained. Test cases use scoped constructors and full package.class.case identities.
- [x] Run `../.venv/bin/python -m pytest tests/test_package_index.py tests/test_package_scopes.py tests/test_project_index.py tests/test_object_projects.py tests/sdk/test_package_index_sdk.py -q` expecting PASS with real SDK for scoped valid/private/cyclic controls. Archive exact originals.

### Task 3: Scoped contracts and V5 independent observations

**Files:** Create `repair/scoped_signature.py`, `repair/scoped_material.py`, `repair/scoped_values.py`, `repair/scoped_imports.py`, `repair/scoped_harness.py`, `repair/scoped_sequence.py`, `repair/scoped_trace.py`; modify `oracle.py`, `properties.py`, `relations.py`, `sequences.py`, `primitive_trace.py`, `sequence_trace.py`, relevant search/value helpers and `core/` native data validation; tests `test_package_contracts.py`, `test_package_trace.py`, `test_package_core.py`, SDK `test_packages_sdk.py`.

**Interfaces:**
- `scoped_signature.validate(signature: dict) -> dict` validates exact scope keys/version, root/path/package/name/graph hash; source ownership remains service reparse.
- `scoped_trace.material(files: dict[str,bytes], signature: dict, nonce: str) -> dict` returns production-only verification files plus deterministic bridge/harness naming/bindings and their manifests.
- `scoped_trace.render(signature: dict, cases: list[dict], *, nonce: str, mode: str, binding: dict, contract: dict|None=None) -> dict` returns source bytes/path, canonical case IDs and the bound derivation hash; binding comes from material, never from model. `read(log: str, signature: dict, expected: list[str], *, nonce: str, mode: str, exit_code: int|None, problem: str|None) -> dict` validates V5 observations.
- Existing model normalize/generate/search/shrink interfaces remain; choose versions by validated scope before value kind. Native qualified tags are bounded data, not expressions.

- [x] RED: all4model version matrices, wrong nominal cross-package values, full Int64 bounds, longest wire2333, reserved/duplicate/mixed protocol headers, canonical IDs, case0, package-only and private entry bridging, generated imports only needed types, no production bridge in export.
- [x] Extend shared closed value/parser options and versions; implement scoped renderer using source-local fresh alias imports and package-level helpers; preserve all legacy rendered bytes/read rules.
- [x] Run focused contract/trace/core tests and actual SDK all4model observations, bad native tags and unknown controls. Expected exact observed values and preserved original candidate manifest. No HTTP model calls.


Task3 completes the protocol/material foundation. The explicit no-bridge-in-final-export invariant is exercised end-to-end by Task5/6; this does not mark4D accepted.

### Task 4: Compiler dependency and complete XML verification

**Files:** Create `adapters/cangjie/scoped_reports.py`, `execution/package_validation.py`; modify `execution/runner.py`, `adapters/cangjie/verifier.py`, `contracts.py`, `repair/verification_evidence.py`, public test rendering; tests `test_package_reports.py`, `test_package_verifier.py`, SDK `test_package_reports_sdk.py`.

**Interfaces:**
- `scoped_reports.dependencies(raw: bytes, *, package: str, source_root: Path, graph: dict) -> dict` validates exact compiler dependency origin/file/line against frozen declarations.
- `scoped_reports.tests(reports: dict[str,bytes], *, expected: list[str], stdout: str, exit_code: int) -> dict` returns per-canonical-case states/failure text and aggregate state, never partial PASS.
- `package_validation.scan(project: Path, index: dict, *, deadline: float, private_root: Path) -> dict` fixed SDK-only sandbox commands and bounded original outputs. `run_scoped_tests(...)` uses frozen native binaries and fixed XML path in target/.runner-tmp; no arbitrary user argv.
- Optional scoped `CheckResult.package_evidence` omitted whenNone. Pure evidence rebuild verifies input manifest, tool identity, graph, scans, XMLsha/refs and complete coverage at every gate.

- [x] RED: duplicate package-local Cases.case0 across packages, missing/foreign/duplicate/error/skipped/conflicting counts, DTD/entity/depth/budget/path/link/tampered report and SDK graph; old model_dump has no new key.
- [x] Implement fixed compile-sandbox scans and test-sandbox XML capture, 2MiB combinedbudget/257XML/288cases, immutable byte copies to records and pure report parsing.
- [x] Run focused parser/verifier tests plus real SDK mixed1PASS1FAIL package XML, empty-root/TestOnly case, unchanged old verification evidence tests; no trusting envelope or count alone.

### Task 5: Upload freeze and four repair services

**Files:** Modify projects/service.py, uploads/service.py, four exploration services, contract normalization, repair context/focus/feedback, gates and delivery binding; tests `test_package_services.py`, `test_package_feedback.py`, `test_package_delivery.py`, SDK `test_package_loop_sdk.py`.

**Interfaces:**
- Existing service public prepare/confirm/run/get APIs remain; scoped signatures are regenerated from exact frozen index2 and frozen profile, never supplied by model.
- All four probe services consume Task3 scoped material/render/read and Task4 exact CheckResult evidence; cache/identity includes every new resolver/scanner/protocol source plus core and graph.
- Public tests generated in entry package; IDs include package; temporary bridge/harness recorded separately; no candidate mutation.

- [x] RED for same-request idempotence/ownership, nonselected body privacy, frozen imports/config/types/graph, readonly deps, original test shielding, XML failure source-token mapping, unknown stops before further model, scope/bridge/source/tool tamper invalidates recovery/accept/export/download.
- [x] Implement scoped branch through existing services/context/focus/feedback and gates, preserve old branches and record shape. Model raw output cannot change dependencies/interfaces/contract.
- [x] Run actual SDK/native four-model publicPASS→independentFAIL→smallerexample→fixPASS including object state+array. Explicit model/graph fixtures only; keep all original failures and restored replays.

### Task 6: Frontend and isolated complete workflow

**Files:** Modify existing project upload/function selector/evidence panels and docs help only; tests `tests/packages-ui.test.cjs`, independent owned SDK+browser fixtures.

**Interfaces:** Existing routes expose canonical fn names, readonly package graph/source vs compiler-confirmed origin and exact evidence; UI never constructs authority-bearing scope.

- [x] RED Node tests for same-name selection, exact JSON Int64 roundtrip, frozen graph/readOnly, validationerrors and source-origin status. No layout replacement.
- [x] Extend existing views and readonly package graph details; SDK-created own flow covers draft/apply/repair/4models/counterexample/manualaccept/export/download and tamper rejection with main isolated.
- [x] Run Node suite and real browser screenshots/AX with no external requests, then inspect outputs. Verify bridge absent in export, readonly imports/config preserved and all4model history bound.

### Task 7: Review, own-version rebuild, acceptance and activation

**Files:** Add `docs/demo/next-phase-4D-verification.md`, `docs/demo/validation/next-phase-4D/*`; update roadmap and plan/ledger; retain accepted4C snapshot.

**Interfaces:** Acceptance input = source/core/compiler identity, complete required tests, raw SDK/native/scans/XML/model-fixture/browser logs, independent pure rebuild and history audit. Output = isolated accepted4D snapshot only after all gates pass.

- [x] One fresh whole-stage review with spec/plan/ledger and ReviewFocus; grade effects; author addresses Important/Critical in one RED→GREEN fix stage, no secondreview.
- [x] Full not-live Python and Node plus diffcheck over frozen execution source; preserve exact originals/exits, initial failures, own source/core manifests. Rebuild current4D and all old2/3A/3B/3C/4A/4B/4C archives with their own implementations and effects denied; finite size/path/key scan. 2026-11-03: current d953... full3242Python/187NodePASS,2302inputs unchanged;668originals/10own-source runtimes rebuilt,119archive finite scanPASS. Old9eb... results preserved separately.
- [x] Only when main idle, audit17tables/record hashes/session ownership/lock, graceful4Cstop and start independently copied4D; compare audit and homepage/assets hashes, retain rollback4C. No test work in real main data. Actual integrated4D+deployment snapshot PID48227 port8877; all44tasks/3959records/credentials metadata preserved.
- [x] Update true accepted/active status and limitations; re-read roadmap. User narrowed scope to completed4D and deploymentTask1/2 integration; further deployment5 work is explicitly paused, not marked complete. See docs/demo/next-phase-4D-verification.md.
