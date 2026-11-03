# 审批端口隔离追加核查（2026-10-18）

本次只在临时目录执行探针，没有修改正式产品源码、冻结用例、SDK或原始参考。新增模型请求0，工作台仅作TCP连接目标，没有向其提交HTTP动作。

## 实际结果

- Seatbelt最小规则探针：显式单端口许可与单端口拒绝能分别产生连接成功/PermissionError；但将loopback许可与端口排除组合后，本机8765连接仍成功。因此不能将这类组合规则当作已验证隔离。原始profile、退出码和stderr见network-isolation/seatbelt-port-filter-probe.json、seatbelt-filter-combinations.json。
- 临时复制正常订单案例，在候选沙箱中撤去全部出站许可，实际执行cjpm test --no-capture-output --parallel 1。12秒到限后终止整个自建进程组。实际输出为std.unittest.Transport.fromDefaultConfiguration的SocketException: Failed to connect 1: Operation not permitted；测试未完成，不能计PASS。配置与完整原始日志见netless-cjpm-probe.json。
- 上述flags仅用于临时诊断，没有加入正式命令白名单。没有通过关闭测试、伪造报告或放宽验收来解决隔离。

## 对验收的影响

development-constraints.md第5节明确要求模型不能获得审批接口，并要求区分Policy与操作系统隔离。当前候选进程可连接工作台，因此该边界仍未证明；会话所有权、CSRF和受保护路径测试不能代替这一要求。完整出站禁用又会阻断当前版本仓颉测试传输，简单删除loopback许可不可作为正式修复。

6d8784b源码包和98bcb17证据索引未改变，原技术复核包仍仅用于受限案例的团队技术核查，不能按完整安全验收通过处理。M1指定基座实际接入与AC-12外部成员回执也仍未完成。本轮不追加付费LIVE、不重新打包相同应用代码。
