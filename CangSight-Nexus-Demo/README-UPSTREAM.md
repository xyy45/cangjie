# CangSight-Nexus

真实 MCP 驱动的受控仓颉工程修复原型：独立候选、原生仓颉 Policy、固定 SDK 构建测试、用户接受与导出。

**V1.1 历史版本已通过一次授权的真实 LIVE A＋单独标注的 D 探针；当前 Native 安全补充另以真实 SDK/协议测试验证，不冒充新的 LIVE。** 实际模型请求1次、首候选经真实 MCP/仓颉 Policy/cjpm 构建及11项测试通过，由测试操作者批准并完整导出。需求确认、失败反馈、拒绝/取消、完整证据归档、中断核查及历史浏览已接入。M1已按固定来源的最小网关/分派核心范围接通，工作台经真实基座分派器调用唯一RepairLoop；保留Apache-2.0和来源差异。当前整版新LIVE、外部成员复现、未覆盖Native强制安全边界及比赛提交未完成。见 [V1.1 验证报告](docs/v1.1/validation-report.md) 和 [实施记录](docs/v1.1/implementation-progress.md)；V1三次复演仍只作旧版历史证据。

```bash
source .venv/bin/activate
python scripts/doctor.py
python -m nexus.web.app
```

打开 <http://127.0.0.1:8765>。首次使用或服务重启后，需按runbook使用本机 `.runtime/workbench/.operator-key` 配对浏览器；不要将此凭据交给模型或加入交付包。初次安装、SDK 与模型配置、验证命令及故障处理见 [runbook](docs/runbook.md)。实际进度和待办见 [实施记录](docs/progress.md) 与 [演示脚本](docs/demo-script.md)。原附件验收合同见 [开发计划](docs/delivery-plan.md)。

V1.1不引入Docker，保留Native；候选目录不是安全沙箱。实测安全边界与未验证项见 [Native安全修复报告](docs/v1.1/native-security-fix-report.md)。


交付版本和ZIP摘要以技术包外层`release-manifest.json`及“先读我”文件为准；原生策略必须在成员本机重新编译。当前受测源码离线144项通过，真实SDK/HTTP11项通过，Node15项通过；这些结果不代替成员独立回执。M1证据见[基座适配验收](docs/v1.1/m1-dispatch-acceptance.md)，执行阶段及边界见[Native执行说明](docs/v1.1/native-execution-staging.md)。
