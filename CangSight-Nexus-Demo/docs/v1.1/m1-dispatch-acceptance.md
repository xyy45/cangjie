# M1 指定基座分派核心接入验收

日期：2026-10-18。结论：M1/AC-03在设计规定的最小网关/分派核心适配范围内通过。本结论不等于V1.1总验收或比赛提交完成。

## 范围与依据

设计第5节明确“不导入整份旧网关应用，不默认启用医疗、部署和云入口”，第7.1节要求小型适配器调用当前RepairLoop、统一ID/状态/事件及至少一项真实基座集成测试。此前仅脱敏/查询的派生模块缺少实际分派核心调用，不能据其完成验收；本轮补入固定来源的真实通用分派核心及主页面创建入口。原样启动完整旧create_app不是该设计规定的前置条件。整库、旧领域编排和原始全量应用均未接入，也不宣称完全复用。

来源为用户指定nuptpisa/CangSight@5db0c7eeeb6a62812fc04e9e88497339fed5e11f，Sympas-Nexus/nexus/gateway/app.py。原文件SHA256为420b78df711af7f2e4e7de2437736460bb37bb1312da81a396051ee6a98ab89c。根Apache-2.0原文保留在docs/third-party/sympas/LICENSE；经用户许可处理指令核对，网关无单独许可/版权例外，插件MIT元数据差异保留于来源报告，没有将网关改为MIT。原分派函数完整摘录、来源清单和逐行修改diff均保留。

## 源码与验收证据

| 要求 | 当前源码及行为 | 测试/原始证据 | 判定 |
| --- | --- | --- | --- |
| 实际指定基座复用 | sympas_runtime.py:_execute_run保留原分派生命周期、handler运行上下文、事件发射、完成/失败路径；注入当前处理器/存储，移除旧领域全局注册表和默认数据库，异常仅记录类型 | dispatcher-source-provenance.json、dispatcher-source-diff.patch、third-party/sympas/upstream-execute-run.py.txt | PASS，明确派生范围 |
| 主入口发起仓颉任务 | workbench.js确认后POST /agents/runs；gateway.create_run入队并启动原基座派生分派器，handler只调用既有RepairLoop.run | tests/sdk/test_sympas_dispatch_loop.py；dispatcher-real-loop-summary.json；dispatcher-node.txt | PASS |
| 稳定RuntimeBinding及唯一事实库 | web.start_task原子保存task/starts；同值run_id/task_id、固定base_commit和实际加载的adapter_sha256持久绑定；RuntimeBridge仅投影分派事件，失败时通过原生CAS停止活动任务；无第二套可写完成状态 | tests/test_sympas_gateway.py；真实SDK结果中绑定与模块哈希一致、一个入队/开始/结束、重复创建同一ID | PASS |
| 同ID查询真实工具/候选/结果 | gateway.get_run读当前task_view和真实tool_call记录；真实基座线程运行唯一RepairLoop，MCP全部为官方Client/stdio Server，Policy和cjpm实际执行 | 新SDK自动链9次实际MCP调用、4项检查：基线FAIL，候选build/test PASS，11项业务测试通过；原始report/log在dispatcher-real-records | PASS，脚本化生成不计LIVE |
| 顺序事件与重启查询 | 原RunStore事务序号与SQLite持久化；事件after_event_id/Last-Event-ID只读分页；旧配对重启后需重新授权 | tests/test_sympas_gateway.py；tests/sdk/test_sympas_gateway_sdk.py重开库后同ID、候选和工具记录相同 | PASS |
| 版本/权限/失败停止 | 仅契约1和cangjie-repair；需求先确认；沿用loopback、CSRF、操作者及执行所有者；分派错误为IN_DOUBT且不自动重放，不回显异常敏感值 | 未知版本/能力、未确认、匿名/错误Origin/只读、线程启动失败及幂等重试控制测试；真实SDK链无自动接受/导出 | PASS，受测边界 |

特别说明：原基座的completed现在只表示分派调用结束，在SYMPAS_DISPATCH_STATE事件的dispatch_payload中记录。业务TaskRecord始终由当前修复/交付状态机决定。真实自动测试最终为REVIEW_PENDING，acceptance和model_call记录均为空，下载地址为空；没有借分派completed制造修复成功、人工批准或DELIVERED。

测试仅将候选生成替换为显式ScriptedGeneration；未替换基座分派函数、RuntimeBridge、RunStore、RepairLoop、MCP Client/Server、仓颉Policy或cjpm。API配置存在性检查使用synthetic值及example.invalid，未调用真实模型，不计作新版LIVE。

## 最终命令与结果

- `.venv/bin/python -m pytest -m 'not sdk and not live' -q`：144 passed、12 deselected，27.83秒；dispatcher-offline-final.txt。
- `.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py -m 'not live' -q --basetemp=.runtime/m1-dispatch-final`：11 passed，73.00秒；dispatcher-sdk-final.txt。
- `node --test tests/workbench-race.test.cjs tests/operator-auth.test.cjs`：15 passed；dispatcher-node.txt。保留原13项竞态和2项配对测试，仅更新创建入口/契约断言。
- 原Sympas453文件与开工哈希清单完全一致；dispatcher-original-integrity.json。

原始证据目录为docs/evidence/v1.1/m1-upstream。dispatcher-real-loop-summary.json包含真实事件、9项tool_call和4项check；dispatcher-raw-manifest.json记录原始目录和已保存检查日志/报告哈希。早期旧模块和未接入分派器时的PARTIAL结论只代表当时版本，不覆盖本次结果。

## 总目标剩余边界

AC-04当前整版真实DeepSeek LIVE未再执行；历史一次授权已使用，不自动追加费用。独立成员复现/回执、赛事平台和正式提交仍PENDING。Native已有真实shell/产物/凭据/HTTP边界测试，不证明所有Mach IPC、进程信息、资源耗尽与逃逸进程组后代路径；强制但未验证的安全边界继续NOT_VERIFIED/BLOCKED，不把候选目录称为安全沙箱。不引入Docker。

现有技术复核ZIP仍为旧固定快照，尚未替换为本轮源码。主服务运行版本与部署烟测另行记录，不以新测试app实例冒充正式服务已更新。


## 正式服务更新

应用源码固定9a41097。确认无在途任务并保存0600数据库备份后，已重启正式8765服务。只读烟测证明配对页200、未配对API/基座查询403、实际静态脚本通过/agents/runs创建；任务及模型记录数量未变，未提交真实操作者凭据。见dispatcher-service-smoke.json。旧会话需重新配对。该烟测不冒充一次真实模型修复。
