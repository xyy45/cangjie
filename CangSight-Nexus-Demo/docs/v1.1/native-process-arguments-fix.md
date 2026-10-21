# Native 进程参数读取边界修复（2026-10-18）

生产执行配置发现同用户其他进程参数可被候选读取的路径，现已最小修复。此结论仅覆盖下述实测路径，不证明完整系统隔离；独立候选目录不是安全沙箱。

## 修改与可复现证据

- `nexus/execution/runner.py:execution_profile`：同时限制 `kern.procargs` 的 sysctl 读取和 `process-info*`，仅保留自身/子进程检查以兼容 SDK。单独施加其中一种限制不足以封堵实测路径。
- `tests/sdk/test_native_process_arguments.py:test_candidate_cannot_read_owned_peer_or_ancestor_arguments`：编译真实 C 探针，分别读取本测试启动的同用户兄弟进程和祖先进程参数。无约束正向对照必须读到合成标记，生产配置必须返回 EPERM/EACCES。未访问实际工作台进程、密钥或会话数据。
- 原配置 RED：`docs/evidence/v1.1/m1-upstream/process-arguments-red.txt`；修复后 GREEN：`process-arguments-green.txt`（2 passed，含既有真实仓颉操作者边界测试）。
- 中间探针 `native-owned-process-*.json` 保留原始结果。只查询参数缓冲区大小可能被权限拒绝，不能证明真正的数据读取被拒；正式测试使用固定缓冲区并要求无约束正向对照成功。早期环境变量未命中的探针不作为安全通过证据，不声称已经单独证明所有环境变量读取途径不可用。

## 完整回归

实际命令及原始输出均在 `docs/evidence/v1.1/m1-upstream/`：

```
.venv/bin/python -m pytest -m 'not sdk and not live' -q
# process-arguments-offline-final.txt: 144 passed, 13 deselected in 27.45s
.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py -m 'not live' -q --basetemp=.runtime/process-arguments-sdk-final
# process-arguments-sdk-final.txt: 12 passed in 78.22s
```

SDK 回归实际执行仓颉构建、测试与 MCP/HTTP 链；没有本轮付费模型调用。未修复登记基线仍为 10 通过/1 失败，不能将其改称成功。

## 版本与验收限制

`21eec36` 技术复核包不包含本修复，保留为历史版本，不能用其替代本修复后的源码。更新包必须重新固定源码、在无 `.git` 解压目录构建 Policy 并运行离线回归。执行器摘要变化使旧检查/批准失效，需要真实重验证和新批准；重放历史模型提案仅证明新执行器验证，不算新 LIVE。

一般 Mach IPC、进程内存、脱离进程组与资源边界尚无完整证明；强制要求未覆盖的部分保持 BLOCKED/NOT_VERIFIED。Docker 不属于本轮前置条件。另一成员实际复现、新整版 LIVE 与比赛正式提交仍待各自证据。
