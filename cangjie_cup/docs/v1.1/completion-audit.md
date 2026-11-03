# V1.1 完成条件复核（2026-10-18）

本报告按设计文档 AC-01～AC-12 核对源码和原始输出。总验收尚未完成。M1 指定来源的最小网关/分派核心已接通并实测通过；另一成员复现与正式比赛提交均 PENDING。登记订单案例以外不作推广。

| 验收 | 结论 | 源码与关键函数 | 测试和实际证据 |
| --- | --- | --- | --- |
| AC-01 环境门禁 | PASS（已测环境） | preflight、web/app.py：环境检查与执行门禁 | tests/test_workbench_errors.py 环境失败不启动 worker；既有 doctor/SDK 证据 |
| AC-02 需求确认 | PASS（预配置三规则） | requirements/service.py prepare_requirement / confirm_requirement；workbench.js 范围选择与冻结 | tests/test_confirmed_scope.py 真实 MCP 拒绝范围外路径；completion/scope-contract-green.txt、scope-ui-green.txt、scope-desktop.png、scope-mobile.png |
| AC-03 实际指定基座入口 | PASS（指定来源的最小派生网关/分派核心） | sympas_runtime.py真实原基座分派流程调用既有RepairLoop，主页面经基座入口创建，同ID查真实MCP/候选/检查 | m1-dispatch-acceptance.md；144项离线、11项SDK/HTTP、15项Node；脚本化生成不计LIVE，不宣称整库或完整旧create_app接入 |
| AC-04 A 真实修复至下载 | PARTIAL（历史一次LIVE通过；Native安全版新LIVE/完整真人演示未验证） | provider.py、cegis_loop.py、verifier.py、delivery.py | live/current-a-live.txt：历史实际API一次、首候选成功、LIVE_TEST_OPERATOR批准。native-security/current-executor-revalidation.json：原提案在当前执行器重验证和新测试操作者批准；当前SDK真实HTTP配对/导出通过，但二者不等于当前整版新LIVE或独立真人回执 |
| AC-05 失败反馈与预算 | PASS（机制），模型多轮成功 NOT_VERIFIED | repair/feedback.py、cegis_loop.py、provider.py：前稿/差异/诊断、三候选和时间限制 | 真实 SDK 确定性失败候选反馈；tests/test_failure_states.py：断连 IN_DOUBT、超时未知不重发、范围外 REJECTED；completion/states-final.txt。替身仅验证分类 |
| AC-06 D 权限拒绝 | PASS（已测原生/MCP） | native Policy decide 与 MCP candidate.apply 门禁 | live/current-live-summary.json 中独立手写 D 原生拒绝及 MCP 拒绝，基线不变；不是模型生成恶意提案 |
| AC-07 可编译坏候选 | 可选 P1，非首版阻塞 | verifier.py 冻结业务用例 | 既有 SDK 反馈测试；未增加 B/C |
| AC-08 异常四态 | PASS（已覆盖分支） | verifier、provider、cegis_loop；web/app.py action_error | tests/test_failure_states.py、test_workbench_errors.py；SDK 失败是实际失败，受控 HTTP 故障不计 LIVE |
| AC-09 同版批准与导出 | PASS（已测链） | delivery.py acceptance / verify_archive；verifier.identity | 真实 HTTP/MCP 导出、重复 ID、篡改/失效拒绝；改变 runner 文件后旧检查失效，重验证不借用旧批准 |
| AC-10 取消拒绝与迟到响应 | PASS（已覆盖竞态） | review.py、workbench.js 请求代次及确认冻结 | tests/workbench-race.test.cjs 13 项；取消在途提示未知效果、旧任务/候选响应隔离；completion/errors-cancel-green.txt |
| AC-11 中断与历史 | PASS（已测边界） | ownership.py、review.py、持久请求/模型记录 | 既有 owner-protocol 与恢复测试；新超时记录有 STARTED/IN_DOUBT 时不冒称已完成且不自动付费重试 |
| AC-12 另一成员干净环境 | PENDING | docs/independent-reproduction.md | 本机无 Git 解压回归只能证明发布可测试，不能代替外部成员运行及下载回执 |

## 本轮最小补充

- API 错误使用业务码和中文提示，技术原因留在不可变事件，不回显请求中敏感字段。
- 用户可在确认前缩小允许修改文件；确认开始即冻结，真实 MCP/Policy 执行同一范围。
- runner 在创建输出目录或启动子进程前拒绝 target、临时目录和 HOME 符号链接；三个边界测试验证外部目录不变且没有启动进程。
- 网络中断、在途超时为 IN_DOUBT；非法受保护路径或已确认范围外候选为 REJECTED；无效模型格式停止，不自动重发。

## 明确未解决的限制

completion/control-ports-red.txt 等保留了只作 TCP 连接、不提交 HTTP 的本机端口探针：既有 loopback 许可允许候选进程连接 8765。尝试收紧规则未同时通过隔离探针和真实仓颉测试，已撤回试验规则。当前 runner **不提供候选进程与工作台 TCP 端口的完整隔离**；会话所有权测试不能证明网络层隔离。仅支持登记自产案例和本机可信操作者，不能宣传任意不可信代码安全执行。这个限制应在团队验收时明确评估，不能因其他测试通过而标为已修复。

M1、AC-12 和本机控制面隔离使整体验收仍有未决项。本轮没有新增模型请求，没有重用旧批准制造当前成功；历史视频仅为历史 LIVE 记录的只读帧回放，不是本轮实时录屏。

## 最终回归记录

- ` .venv/bin/pytest tests -m 'not sdk and not live' -q `：125 passed、8 deselected，24.38秒；completion/final-offline.txt。包含真实 stdio MCP 协议与原生 Policy 测试，故障替身仅证明对应分支。
- ` .venv/bin/pytest tests/sdk tests/integration/test_full_journey.py -q `：7 passed，57.61秒；completion/final-sdk.txt，实际 cjpm 构建/测试及 HTTP/MCP 交付。
- 原始参考453文件逐文件摘要一致：completion/integrity.json。真实配置中的 API Key 仅用于字节匹配扫描、没有打印：completion/sensitive-scan.json。

- 当前执行器重验证：9.768秒，DELIVERED；task_id=c76fb4b85a834c0393f6d3e4d4bb5fcf，新模型请求0；先确认旧计划/批准失效，再实际MCP诊断、应用原始真实模型提案、build/test 11通过、新测试操作者批准和完整导出。ZIP SHA256：9f4a3f7bddac2d0f5018bdedc930f277d419776a6a564c8c34772194cbd01721。新批准者为EXECUTOR_REVALIDATION_OPERATOR，外部成员仍PENDING。不是第二次LIVE模型修复。


## 后续范围与安全核查更新（2026-10-18）

Docker集成已由用户明确暂缓，不继续等待默认实施或自动安装。现有本机执行方式保留；暂缓不是取消development-constraints.md中“模型不能获得审批接口”的必需要求。

调查阶段在隔离复制的真实V1.1运行库进行HTTP路由探针：新建会话可以读取候选信息并创建批准（200），不是原需求确认/测试操作者会话；未导出、未调用模型、原运行记录摘要不变。见docs/evidence/docker-feasibility/approval-boundary-probe.json。此结果证明会话/CSRF本身不构成真人授权证明，不等于已经执行了完整恶意仓颉程序攻击。AC-09中内容/批准绑定测试仍是有效证据，但不能据其推导“真人身份与审批接口隔离已满足”；该安全要求未通过。M1与AC-12仍未完成，整体验收不通过。


## Native修复后的最新复核（2026-10-18）

此前新会话200批准与端口探针是修复前的真实历史结果。当前已通过独立本机凭据配对门禁修复已测审批能力获取路径：新会话即使有效CSRF也不能读任务/候选或批准/导出（403），正确配对会话可走完整流程，重启旧授权失效。真实Native仓颉候选读凭据被OS拒绝、stdin EOF、11次HTTP审批数据请求均403；无关进程信号与运行库硬链接边界另有真实探针。详情及原始证据见native-security-fix-report.md。

当前完整离线133 passed/9 deselected（25.77秒），真实SDK/HTTP 8 passed（61.02秒）。这支持已测试的审批、文件、控制输入、信号与合法执行兼容性，不推导完整macOS沙箱或生物身份/逐次真人意图证明。必要loopback仍存在，其他未验证IPC/调试/资源边界按强制要求保留BLOCKED/NOT_VERIFIED。Docker已排除出V1.1，不是前置条件。M1/AC-03、AC-12仍未完成，目标不标完整完成。


## 2026-10-18 子进程权限补充

生产sandbox_profile实际允许启动`/bin/sh`执行无害固定输出；工具命令白名单不能据此被解释为候选子进程执行白名单。临时进程限制同时阻断SDK，未投入生产。第5节任意shell边界按严格候选执行解释为FAIL/待修复，而非已验证通过；证据与探针范围见native-security-fix-report.md末尾。M1仍未接入；其派生源码许可声明待上游确认，已询问用户。无新增模型调用、无Docker、无原框架修改。


## Native分阶段执行最新实证（2026-10-18）

已修复前述生产子进程可直接启动shell的已测路径：真实仓颉候选经MCP/Policy构建测试，11次启动shell均被拒绝；同时凭据读拒绝、stdin EOF、11次HTTP403仍成立。编译阶段只允固定工具，测试先--no-run再--skip-build，仅已冻结Mach-O程序可执行；配置保留SDK必需写入例外并核对源码身份。自有原生程序证明冻结文件写入、硬链接、临时目录复制程序和SDK调试器执行被拒绝。实际阶段命令记录在execution_argv，非解析候选stdout。最新完整离线141通过/11排除（26.08秒），真实SDK/HTTP10通过（66.20秒）。详见native-execution-staging.md及原始证据。不能把这些测试推广为一般Mach IPC、资源隔离或所有后代生命周期证明；M1原始完整基座、当前新版LIVE和外部成员复现仍未通过总验收。


## M1分派核心验收更新（2026-10-18）

已补原始通用分派生命周期、入队/线程调用顺序和真实RunStore投影，主页面创建改走/agents/runs。自动基座线程实际调用唯一RepairLoop，真实MCP/Policy/cjpm到REVIEW_PENDING；没有自动批准/导出，分派completed不改变业务成功状态。RuntimeBinding包含固定base_commit和实际adapter文件摘要。设计要求最小适配且不导入整份旧网关，故不继续增加“原样运行完整旧create_app”这一额外门槛；实际派生范围和完整diff见m1-dispatch-acceptance.md。当前AC03在该规定范围PASS。AC04新版LIVE、Native未覆盖的强制安全边界及AC12外部回执仍未完成，总目标不标完成。

## Native 进程参数边界最新复核（2026-10-18）

已修复真实同用户兄弟/祖先进程参数读取路径；无约束合成标记正向对照成功，生产配置读取 EPERM/EACCES。源码、RED/GREEN 与证据范围见 `native-process-arguments-fix.md`。最新完整离线144 passed/13 deselected，真实SDK/HTTP12 passed；无新增模型调用。这取代前述测试数量，不扩大为完整Native隔离结论。21eec36旧交付包不含本修复，须使用后续更新包。AC-04当前整版新LIVE、AC-12与未覆盖的强制安全边界仍未完成。
