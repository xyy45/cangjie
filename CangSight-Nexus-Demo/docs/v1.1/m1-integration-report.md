# M1 最小派生网关集成报告

最新状态：本报告记录较早来源核查/初版派生模块。当前已补真实基座分派核心及主页面入口，按设计最小适配范围通过M1/AC03，证据与范围以[m1-dispatch-acceptance.md](m1-dispatch-acceptance.md)为准；不宣称整库接入或新版LIVE通过。

日期：2026-10-18。范围：正式工程增量实现，不修改原始Sympas-Nexus。

## 实现及真实复用

上游固定为nuptpisa/CangSight@5db0c7eeeb6a62812fc04e9e88497339fed5e11f的Sympas-Nexus/nexus/gateway/app.py。新增nexus/integrations/sympas_runtime.py，实际保留两项上游函数（AST逐函数一致），适配运行查询路由结构；不是整个上游create_app。来源及Apache-2.0原文见docs/third-party/sympas；源文件与派生文件哈希、修改清单见derived-source-provenance.json。修正上游Set-Cookie字段归一化失配，保留响应递归脱敏。

POST /agents/runs只接受schema_version=1、team_profile=cangjie-repair及payload；payload为现有project/spec_id/idempotency_key，需求必须已经通过现有人工确认。调用同一个start_task，沿用同一事务、单RepairLoop、环境检查和实际工具链。基座来源、契约版本、同值external_run_id/internal_task_id在创建任务前绑定并原子保存；无新映射表、运行库或竞争执行器。两入口共享幂等表，同一key若改变入口来源契约会明确拒绝，不能替换来源。

GET /agents/runs/<id>返回同一任务、候选、基线检查、事件和实际MCP调用引用；/events支持after_event_id或Last-Event-ID的顺序分页。均通过正式工作台原有loopback、操作者配对、写入所有者与CSRF保护；不注册旧领域、旧审批或旧CEGIS路由。重启后重新配对可查同一SQLite历史。

## 实际验证

- 完整离线：`.venv/bin/python -m pytest -m 'not sdk and not live' -q`，141 passed、10 deselected，29.62s；derived-offline-final.txt。
- 真实SDK/HTTP：`.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py -m 'not live' -q`，9 passed，71.17s；derived-sdk-regression.txt。随后仅查询输出增加run_id/tool_calls，针对最终版本再次运行新增SDK测试，1 passed，10.61s；derived-gateway-sdk-final.txt。
- 针对性控制层测试：8 passed；derived-gateway-unit.txt。覆盖未知版本/能力、未确认需求、未配对、错误Origin、只读所有者、幂等、查询游标、同ID和数据库重开。控制层Loop替身明确不计修复成功。
- Node既有配对和竞态：15 passed；derived-node-final.txt。
- 新增tests/sdk/test_sympas_gateway_sdk.py从派生入口创建真实任务，实际MCP诊断出基线失败、应用明确手写提案、原生Policy决定、cjpm build/test通过11项，重开库后查询到相同候选及工具记录。不是模型LIVE，不模拟PASS，不声称由RepairLoop自动生成提案。
- 新探针4条真实工具调用、4项真实检查及20个原始证据文件哈希，见derived-gateway-summary.json和derived-gateway-evidence-manifest.json。原始文件保留在.runtime/m1-derived-sdk-final/test_derived_gateway_task_has_0；授权能力原文不额外复制到交付文档。未调用付费模型。
- 原参考453文件与开工清单完全相同；original-integrity.json。

证据路径均相对于docs/evidence/v1.1/m1-upstream。

## 验收边界与剩余工作

M1从“无实际适配”推进为PARTIAL：已有可定位、可测试、真实复用上游代码的最小派生网关，贯通同一任务及真实MCP/Policy/cjpm。没有启动完整原始create_app，亦没有从该原样应用发起任务，不能把派生模块测试称为原始完整基座验收。如果AC-03必须由未改原始网关应用发起，仍未满足；本报告不静默改写验收定义。后续应明确以小型派生网关适配实现设计要求的具体范围，并补自动RepairLoop链路及独立成员复现证据。

Native shell子进程边界仍未修复。本轮只是试验执行白名单，修正了试验中文路径转义问题，真实SDK能够构建并运行基线11项；可写target执行权限与复制执行绕过风险尚未完成验证，试验规则未进生产。无Docker。现有正式服务进程没有自动重启，新路由需按runbook重启后使用；测试均启动新app实例。

已有a19f6d7技术复核ZIP仍是旧固定快照，不含本次派生模块；未将其改写为新版本。完整M1范围、Native强制安全要求、当前新版LIVE、另一成员复现和比赛正式提交不能据本轮测试标记完成。
