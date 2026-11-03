# 业务规则辅助生成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户已于2026-10-25明确确认实施，现按任务顺序执行；尚未完成的复选框仍保持未勾选。

**Goal:** 用户上传现有受限仓颉源码后，可生成并审阅业务规则／公开测试草案；仅经用户确认的实际内容进入现有冻结和修复流程。

**Architecture:** 复用Flask、SQLite、原生JS、UploadService、validate_examples和validate_contract。新增与修复任务分开的草案请求账本及模型适配器；后台工作线程沿用当前本机服务模式，不引入队列／新服务。模型输出只能形成建议，服务端校验和用户确认都不可省略。

**Tech Stack:** 当前Python环境、Flask、Pydantic、httpx、SQLite、原生JS、固定仓颉SDK1.0.5／core2。以执行时实际版本核验为准，不在此计划更新依赖。

**Spec:** ../../后续能力提升开发目标.md（第1项及全局约束）。

## Global Constraints

- 产品代码前按既有八节提示词流程取得本轮一次性确认；常规实现与阶段切换随后持续执行，不重复确认。
- 第一项仅支持现有Int64／Bool、受限同包工程、最多3个允许生产路径，不扩大语法和权限。
- 源码、需求、函数与路径由服务端从已登记上传读取；不接受前端或模型伪造的源摘要／所有权／许可。
- 生成前必须明确同意当时向现有配置的模型服务发送选定源码和需求；现有“开始修复时发送”同意不复用为提前发送许可。
- 新模型调用数预算默认未授权；先完成离线／HTTP夹具／真实SDK测试。旧批次剩余12次不是本轮预算。
- 草案请求使用独立账本，不伪造修复task_id，不消耗或修改修复候选轮次。
- 不读取／打印.env原文，不保存Authorization；错误、响应、日志和诊断沿用脱敏原则。
- 模型同源生成的例子和规则不能证明业务语义正确；用户逐项核对并确认后才冻结，原需求和草案假设保留。
- 已冻结工程与验证依据不能被草案生成／应用修改；手动填入／导入路径保持兼容。
- 使用合适的codex/分支或工作树，保留所有历史未提交改动；不自动提交、推送、部署。

## Review Focus

- 当前程序本身有缺陷：模型是否把当前输出当作正确答案，或把自洽的错误规则标成已验证业务规则？由Task1和Task4覆盖。
- 同会话切换函数、路径、源码或窗口：晚到响应是否写入新上传或覆盖用户输入？由Task2和Task4覆盖。
- 请求已发送但本机／网络中断：读状态、刷新、重启、重复key、新key是否导致再次调用？由Task2和Task3覆盖。
- 新草案功能发生在修复之前：是否绕过原有传输同意或只读实例／运行所有权？由Task2和Task4覆盖。
- 用户修改草案后确认：最终验证是否绑定实际确认内容，而不是错误地绑定原模型输出？由Task5覆盖。

## File Map（实施范围）

- Create `nexus/uploads/rule_drafts.py`：草案快照／校验、所有权、持久化状态与请求绑定；如实际实现过大再按职责拆分，避免空壳层。
- Create `nexus/demo/rule_draft_provider.py`：独立草案模型适配器，复用model_config和脱敏，不能复用修复任务预算。
- Modify `nexus/uploads/routes.py`：草案创建／读取／应用预览路由及错误码；既有准备／确认不自动调用模型。
- Modify `nexus/uploads/service.py`：可选草案来源与实际确认内容的冻结绑定；无草案的旧调用语义不变。
- Modify `nexus/execution/ownership.py`及实际应用启动入口（如需要）：持有运行所有权的进程可写；恢复将不确定草案请求标记IN_DOUBT，不重发。
- Modify `nexus/demo/templates/demo.html`、`nexus/demo/static/upload.js`：新增发送同意、生成／预览／应用按钮及状态；保持现有浅色主题与整体布局。
- Create `tests/test_rule_drafts.py`、`tests/test_rule_draft_routes.py`、`tests/test_rule_draft_provider.py`、`tests/rule-draft-ui.test.cjs`及相应SDK集成测试。
- Create `docs/demo/next-phase-1-verification.md`，证据目录`docs/demo/validation/next-phase-1/`。

## Task 1: 草案契约与有界校验

**Interfaces:** 拟定`draft_snapshot(upload,function,allowed_paths)`读取已登记材料，输出服务端绑定快照；`validate_suggestion(raw,snapshot)`输出`DRAFT_READY`／`NEEDS_CLARIFICATION`／`INVALID`及结构化问题。`DRAFT_READY`只表示结构校验完成，不表示业务正确或已批准。

- [x] RED：正常Int64／Bool签名、target／regression例子与规则；零值／负值／极值、Bool冒充Int64、null expected、重复输入不同预期、未知参数、脚本调用、除0／溢出、错误JSON及超限输入。
- [x] RED：需求明确但当前源码错误时不执行当前源码生成expected；有未解疑问或缺少边界时不允许应用成可用规则。
- [x] 使用现有validate_examples／validate_contract和明确Pydantic schema校验；建议项数量／文本长度有上限，例子和规则各不超过现有8KiB限制，响应不超过1MiB。
- [x] 原始模型内容与规范化内容分别存储摘要；模型不能设置绑定、状态、actor、允许路径或执行命令。
- [x] GREEN：上述专项通过，非法草案无文件／任务／模型副作用。

## Task 2: 所有权、持久请求与幂等

**Interfaces:** `create(upload_id,actor_id,expected_version,function,allowed_paths,request_key,consent)`只持久化意图；`run(id)`用CAS取得唯一执行权；`get(id,actor_id)`只读，不启动或重放请求。

请求状态拟定`CREATED→STARTED→SUCCEEDED/FAILED/IN_DOUBT`；草案内容状态单独记录，不与任务的READY或REVIEW_PENDING混用。已应用来源另存不可变记录，不覆盖原生成内容。

- [x] RED：跨actor隔离、未同意／只读实例拒绝、同key同输入同ID、同key换输入409、并发重复请求只有一个上游调用、源码／函数／路径／版本变化拒绝旧绑定。
- [x] RED：请求STARTED后刷新／进程恢复不重发；同一输入已有未决请求时，新key也不能绕过未知状态重新调用。窗口关闭不承诺撤回已经发出的请求，服务端保留最终已知／未知结果。
- [x] 增加最小SQLite请求表，绑定actor／请求key／输入hash／上传来源／生成契约版本／状态／原件引用；网络等待在写事务之外。
- [x] 沿用运行所有权校验与应用恢复模式；恢复只记录UNKNOWN事实，不推定上游未收费或请求未送达。
- [x] GREEN：并发、恢复、所有权、篡改与读取无副作用测试通过。

## Task 3: 草案模型适配器与HTTP接口

**Routes（实施时核对现有路由前缀）:**

- `POST /api/uploads/repair/<identity>/rule-drafts`：函数、expected_version、request_key、生成发送consent，工程另有allowed_paths；同意与允许额度在服务端校验，返回202及草案ID／状态地址。
- `GET /api/uploads/repair/<identity>/rule-drafts/<draft_id>`：同actor只读状态／草案／问题；不得因GET触发生成。
- `POST /api/uploads/repair/<identity>/rule-drafts/<draft_id>/apply-preview`：重新核对源和版本，返回可编辑的规范化examples_json／oracle_json及来源绑定，不写入冻结工程、不创建任务。

**Provider:** 实际使用`prepare(snapshot)`及异步`complete(body)`，分别持久化请求内容与执行单次调用；只读取服务端已选生产源码、目标和函数；输出建议／假设／疑问。每次已获准生成最多一个模型请求、6000输出tokens、120秒HTTP超时，不自动修正重试错误JSON；具体调用原件在独立账本绑定。

- [x] RED：未授权无模型请求，真实DeepSeek形状的HTTP夹具覆盖正常、401／429／5xx、超时、无usage、不完整输出、超限、含密钥／编码密钥的错误体、注入提示、错误绑定。
- [x] 复用现有配置／脱敏；在发送前记录STARTED和请求摘要，完成后保存脱敏响应、usage、实际模型ID及确定状态；未知调用不重发。
- [x] 只取选定允许生产文件，排除原测试／配置／私有规则与holdout；构造有界上下文，过大明确拒绝，不静默截断关键需求。
- [x] 明确404隔离、409版本／状态冲突、400校验错误、503本机不可用；未知状态与上游错误不得伪装为新草案成功。
- [x] GREEN：HTTP／提供器／现有上传路由兼容测试通过，所有夹具明确NOT_LIVE。

## Task 4: 前端预览、显式应用与失效处理

**Flow:** 读取函数→同意生成发送→点击生成→只读轮询→查看假设／问题／参数／例子／规则→用户显式应用到编辑框→手工核对／编辑→再次确认冻结。

- [x] RED JS：未同意不能生成；生成不覆盖输入、不勾选修复确认；应用前提示替换现有内容；有疑问／非法草案不能应用。
- [x] RED JS：切函数、工程路径、上传记录、关闭窗口、重新打开、用户编辑后的晚到响应均不覆盖新输入；旧读取／轮询结果按generation和绑定丢弃。
- [x] 保留现有导入与手动流程；显示“模型草案／结构校验完成／待业务核对”，不显示“业务已证明正确”。
- [x] 首版不新增需求聊天系统；需要澄清时显示具体缺项，用户修订预期行为并重新准备上传。
- [x] GREEN：JS交互测试及实际浏览器夹具验收通过，保存截图并注明夹具；请求未知时只显示查询／等待，不提供自动重发。

## Task 5: 确认绑定、SDK闭环与最终验收

- [x] RED：手动无草案原路径兼容；已冻结上传不能重新生成／应用；伪造来源、草案跨上传／跨会话／过期版本、用户编辑后内容与来源不符不得错绑。
- [x] 设计可选来源字段接入既有confirm：原草案引用与用户实际确认payload分别摘要绑定；用户编辑是允许的，但必须标记为编辑后的确认版本。
- [x] 用户确认仍调用既有例子／oracle校验并冻结；要求来源记录不能授予新权限，也不能使不合法内容跳过校验。
- [x] 真实SDK＋明确HTTP模型夹具：数量边界单文件、两文件计费分别完成生成→应用／编辑→确认→修复／独立搜索，验证原源码／配置／测试受保护。
- [x] 独立审阅本项关键权限、状态、数据版本和语义风险；Important先失败复现再修复；最后相关与全量离线Python／Node／差异检查通过。
- [x] 功能可审阅后再为真实生成联调列出精确请求预算；未获批不调用。未真实联调时必须单独标为未测，不能将夹具称为模型效果。
- [x] 更新next-phase-1-verification及总路线图，重读下一项。不能因本项离线实现通过而将第2–5项勾成完成。

## Validation Commands

在CangSight-Nexus-Demo目录，新增测试文件写入后执行：

```bash
../.venv/bin/python -m pytest tests/test_rule_drafts.py tests/test_rule_draft_routes.py tests/test_rule_draft_provider.py -q --tb=short
node --test tests/rule-draft-ui.test.cjs tests/upload-ui.test.cjs tests/project-upload-ui.test.cjs
../.venv/bin/python -m pytest tests/test_upload_service.py tests/test_upload_routes.py tests/test_upload_oracle.py tests/test_oracle.py -q --tb=short
../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short
node --test tests/*.test.cjs
git diff --check
```

以上专项文件已实现；实际执行结果见本项验收记录，命令清单本身不表示通过。真实SDK测试的最终文件名在Task5编写时记录；完整回归保留live未运行数、实际依赖和core身份。测试中使用placeholder与本地HTTP夹具，不消耗真实模型预算。

2026-10-25收尾进度：页内两次点击替换先RED3fail／5pass，再GREEN24pass（88.34ms）；全量Node108pass（224.28ms）。SDK单文件／两文件2pass（43.46s）。完整Python仍执行中，尚不得声称全量通过。旧原生confirm导致本机浏览器测试页输入／关闭超时，改为页内确认后，最终浏览器链路待恢复重验；已请求人工关闭8897测试页。真实模型3次计划已生成，实际新增调用0，预算待批。

最终离线结果：冻结身份2797940b...bea1下Python712pass／1live未运行，802.12s；Node108pass224.28ms；git diff --check退出0。Task4浏览器GREEN和Task5最终路线图验收尚未满足，不执行task-done伪造完整完成。当前等待8897测试页人工关闭／恢复及3次真实生成预算回复，真实调用0。

2026-10-25真实联调：用户明确批准最多3次，实际完成3次、3981tokens。明确业务两例均因suite对象而INVALID，缺需求例正确NEEDS_CLARIFICATION。已保留原件和历史源码快照；新增提示v2的严格例子schema及单字符串说明，3RED／1pass→98GREEN。没有追加请求；新2例计划已准备，批准0／实际0。完整离线回归重新执行中，产品源码冻结。浏览器通过键盘取得现有草案→首次确认未覆盖→二次填入→编辑加2×3=6→单独勾选修复确认→确认进入工作台；后台CONFIRMED且edited_by_user=true，fixture仍只有1次请求。鼠标自动化不稳定保留说明，不再作为整项外部阻塞。

2026-10-25最终验收：追加2次批准后已完成，共5次／6803tokens，额度关闭。v2单文件DRAFT_READY并经本地测试作者确认后接入真实SDK；跨文件NEEDS_CLARIFICATION保留为生成质量局限，另走人工规则回退，SDK两场景均缺陷FAIL／人工参考PASS且原件不变。无网络历史源码重放5份完整请求及校验、SDK日志／工程hash通过。范围为工程协议闭环验收，不是模型稳定成功率或跨文件自动生成成功承诺。Task5最后命令采用无网络原件重放，避免无产品变更再重复13分钟SDK全量；全量717／108已在本轮实际执行。
