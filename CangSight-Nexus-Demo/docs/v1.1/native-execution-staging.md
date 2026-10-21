# Native 分阶段执行与可执行文件保护

日期：2026-10-18。仅支持已登记演示工程、当前固定 macOS ARM64/Cangjie 1.0.5 环境，不宣称任意代码完整安全隔离。

## 问题与修改

原执行器仅限制入口命令为 `cjpm build -V`、`cjpm test`，但候选测试继承的 OS 策略允许启动 `/bin/sh`。仅限制可执行路径到 SDK 和整个 target 也不足够：target 可写，且 SDK 内有不需要的调试器。

`nexus/execution/runner.py:run_command/execution_profile` 现在分开编译和运行：

1. 构建仍实际运行 `cjpm build -V`，仅放行固定编译工具路径，禁止执行候选产物。
2. 测试先实际运行 `cjpm test --no-run`，成功后核对测试目录、符号链接、Mach-O 文件、单硬链接及可执行文件内容摘要。
3. 随后实际运行 `cjpm test --skip-build`。只放行固定 SDK 必需程序和刚编译测试程序的具体路径，测试程序保持只读；运行后再次核对其内容摘要。
4. 测试运行阶段只额外允许 `.runner-tmp`、SDK 的 `tmpFile` 加六位字母数字临时文件，以及 `incremental-cache.json` 数据文件写入。不能写入其他 target 产物；复制的程序即使位于可写临时目录也不能执行。整个 SDK 和系统工具目录不被笼统放行，调试器不在白名单。

两阶段共享原请求的90秒时限和2MiB原始输出预算，每阶段保留stdin `/dev/null`、关闭额外FD、进程组清理、用户数据读取/控制库保护及原网络/信号限制。没有放宽MCP工具、仓颉Policy或候选修改权限；没有Docker或静默降级。

`CheckResult.argv` 继续表示请求的固定验证命令；新增 `execution_argv` 记录可信执行器实际发起的阶段命令，原始日志也记录阶段头。该字段不从候选输出中解析，避免用可伪造stdout补写执行步骤。编译失败、产物无效、超时、输出超限或内容改变均不能计测试PASS。执行器/验证器文件身份变化会使旧验证计划和旧批准失效，不复用旧检查冒充当前成功。

## 实际验证及证据

- 完整离线：`.venv/bin/python -m pytest -m 'not sdk and not live' -q`：141 passed、11 deselected，26.08秒。
- 完整真实SDK/HTTP：`.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py -m 'not live' -q --basetemp=.runtime/native-staged-final`：10 passed，66.20秒。包含A修复/验证/同版交付、D权限拒绝、反馈及派生网关查询；手写/脚本化提案不计作模型LIVE。
- `tests/sdk/test_native_operator_boundary.py`：真实MCP/Policy/cjpm运行仓颉候选，11项测试中每次启动shell均被拒绝，凭据读取被拒绝、stdin为EOF、工作台HTTP均403。使用明确手写探针；没有模型调用或用户接受。中文项目路径使用真实UTF-8字面量，避免错误的JSON Unicode转义。
- `tests/sdk/test_native_execution_boundary.py`：真实本机编译的自有C原生程序验证：不能写冻结产物、不能创建其硬链接别名、不能执行shell；编译阶段拒绝执行候选程序；测试阶段拒绝复制到临时目录的可执行文件及SDK调试器。它是OS能力测试，不冒充仓颉模型攻击。
- `tests/test_runner.py` 的脚本SDK替身只验证有界输出、超时与进程组清理，显式使用文件/网络基础策略；不用于证明生产执行白名单通过。生产策略由上述真实SDK/OS测试覆盖。

原始输出：`docs/evidence/v1.1/m1-upstream/staged-literal-offline-final.txt`、`staged-literal-sdk-final.txt`；仓颉详细摘要为 `staged-cangjie-summary.json`，原始检查日志和报告位于 `staged-cangjie-records/`，哈希为 `staged-cangjie-raw-manifest.json`。早期失败输出保留：路径转义、临时文件规则、配置打开方式及成功测试后缓存写入问题均实际修正，不计入成功次数。

子进程API参考：[官方std.process文档](https://docs.cangjie-lang.cn/docs/1.0.1/libs/std/process/process_package_api/process_package_classes.html)。是否支持及实际拒绝由本机固定SDK编译/运行证明，不仅依据在线文档。

## 仍然存在的边界

cjpm仍需要以可写方式打开`cjpm.toml`/lock，沿用既有受限写入例外，检查后完整源码树必须保持原身份；不能称所有配置已被OS设为只读。为SDK提供的回环通信没有取消。未证明所有Mach IPC、调试/进程信息路径、资源耗尽和逃逸进程组后代边界，因此不宣称完整macOS安全沙箱；更强的强制安全要求仍按未验证/BLOCKED处理。

完整原始Sympas网关入口M1验收、当前新版付费LIVE、另一成员独立复现和正式比赛提交没有因本轮回归而完成。原始Sympas 453文件仍与开工清单相同。正式服务已在确认无在途任务、备份数据库（0600）后重启到源码2580e62。实测配对页200、未配对/api/tasks和/agents/runs均403，任务及模型记录数量未变，助手未提交真实操作者凭据。用户浏览器需重新配对。启动烟测为staged-service-smoke.json。旧技术ZIP不包含本次修改。
