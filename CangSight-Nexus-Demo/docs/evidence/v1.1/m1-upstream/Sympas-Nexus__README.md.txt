# Sympas-Nexus：多智能体安全分析编排框架

Sympas-Nexus 是基于 Sympas MCP 安全分析服务与 ECC LLM 库构建的多智能体协同编排框架，支持 OODA 自主决策、CEGIS 自动修复、SF 超级智能体告警推理以及华为 HW-CodeArts 流水线集成。

## 架构概览

```
Sympas-Nexus/
├── nexus/
│   ├── llm/          # demo/replay/online/strict 四模式 Provider 路由（strict 仅国产合规路由）
│   ├── memory/       # ChromaDB 向量记忆（RAG 注入）
│   ├── prompts/      # 系统提示词包（AH-SecAgent / SF-SuperAgent）
│   ├── core/
│   │   ├── hooks.py           # PreToolUseGuard + PostToolUseObserver
│   │   ├── plugin_registry.py # UASP 技能注册 + 沙盒执行
│   │   └── dag_planner.py     # 拓扑 DAG 并发规划器
│   ├── repair/
│   │   └── cegis_loop.py      # CEGIS 自动修复循环（最多 8 次迭代）
│   ├── hw/
│   │   ├── spec_processor.py  # spec.yaml 驱动的代码生成与验证
│   │   └── cci_deployer.py    # 华为 CCI 容器云部署
│   ├── agents/
│   │   ├── ooda_agent.py      # OODA 自主安全分析智能体
│   │   ├── sf_superagent.py   # SF 告警分类与零干预响应
│   │   └── hw_codearts_agent.py  # HW-CodeArts 质量门禁流水线
│   ├── gateway/
│   │   ├── hitl_gateway.py    # HITL 人类审批 SSE 网关
│   │   ├── app.py             # REST + 可续传 SSE + 只读 Dashboard（Flask）
│   │   ├── run_store.py       # SQLite 运行状态、事件游标、归档与重启恢复
│   │   └── rest_api.py        # 兼容入口包装
│   ├── runtime/
│   │   ├── autonomous.py      # 任务队列 / 调度 / 预算控制
│   │   ├── checkpointing.py   # 检查点保存与恢复
│   │   ├── council.py         # 四声部 council 决策
│   │   └── homunculus.py      # Instinct 提取与晋升
│   ├── submission/             # 三赛题同源打包、演示时间轴与披露门禁
│   ├── adapters/
│   │   └── sympas_mcp/
│   │       ├── capabilities.py # 54 项离线契约、校验与能力快照
│   │       └── skill_sync.py   # 在线发现、部署漂移与状态同步
│   ├── evals/
│   │   ├── run.py             # 评测套件执行器（python -m nexus.evals.run）
│   │   └── compare.py         # 评测结果对比器（python -m nexus.evals.compare）
│   └── sf/
│       ├── sequential_pipeline.py  # 顺序批量流水线执行器
│       ├── baseline_runner.py      # SF 基线任务一键执行
│       └── react_demo.py           # SF 零干预 ReAct 演示入口
├── skills/
│   └── sympas_mcp_skills.json # 54 工具 UASP 离线注册包
├── requirements.txt
└── pyproject.toml
```

## 快速启动

### 1. 安装锁定依赖

```bash
python -m pip install -r requirements.lock
```

### 2. 配置环境变量

```bash
export SYMPAS_MCP_URL=http://<host>:<port>
# 或拆分配置：
export SYMPAS_MCP_HOST=<host>
export SYMPAS_MCP_PORT=<port>
export SYMPAS_MCP_TOKEN=<your_token>
# online/strict 模式还需显式配置 Gateway API Key 与获授权的国产模型 Provider。
export NEXUS_API_KEY=<your_gateway_key>
export NEXUS_RUNTIME_MODE=strict
```

### 3. 一键启动 REST/SSE 控制平面与 Dashboard

```bash
# Windows
.\scripts\start_demo.ps1

# Linux/macOS
bash scripts/start_demo.sh

# 仅做环境检查，不启动进程
python scripts/start_gateway.py --mode demo --check-only
```

默认地址：`http://127.0.0.1:7800/health`；Dashboard：`http://127.0.0.1:7800/dashboard`。
online/strict 模式不会在未配置鉴权时降级放行，使用 `start_online.ps1/.sh` 前必须由环境注入凭据。

### 4. 独立 HITL 兼容网关（可选）

```bash
python nexus/gateway/hitl_gateway.py
# 默认监听 :7700
```

### 5. 执行评测与回归

```bash
# 运行某个套件（示例：L2 AH-SecAgent）
python -m nexus.evals.run --suite l2_agents/ah_secagent --eval-root evals --strict

# 对比两次结果并输出 HTML 评分差异
python -m nexus.evals.compare results_v1.json results_v2.json --output evals/scorecards/latest/scorecard_diff.html
```

### 6. 一键网关联调 E2E

```bash
# Python 入口
python scripts/run_gateway_e2e.py


# 指定输出报告文件
python scripts/run_gateway_e2e.py --output evals/scorecards/latest/gateway_e2e_summary.json
```

### 7. 三赛题材料与演示脚本门禁

```bash
# 严格生成：外部 PDF/视频/云截图缺失时返回非零，不生成可提交包
python scripts/generate_submission.py --contest all

# 预检：生成带 .preview.zip 和“不可提交”声明的检查包
python scripts/generate_submission.py --contest all --allow-incomplete

# 3/5/8 分钟时间轴漂移检查（统一 {{RUN_ID}}）
python scripts/generate_demonstration_scripts.py --check

# AI/开源/团队掌控披露；正式提交前必须不带 --allow-pending 通过
python scripts/check_material_disclosures.py --allow-pending
```

## 核心 API 端点

| 方法   | 路径                       | 说明                          |
|--------|----------------------------|-------------------------------|
| GET    | `/health`                  | 健康检查 + 技能统计           |
| GET    | `/skills`                  | 列出所有已注册技能            |
| GET    | `/skills/catalog`          | 54 项定义覆盖与线上部署快照   |
| POST   | `/skills/<id>/run`         | 执行指定技能                  |
| POST   | `/run/ooda`                | 启动 OODA 自主安全分析任务    |
| POST   | `/run/cegis`               | 启动 CEGIS 自动修复循环       |
| POST   | `/run/security_pipeline`   | 运行 DAG 安全分析流水线       |
| GET    | `/sse/telemetry`           | SSE 实时遥测推流              |
| GET    | `/agents/pending`          | 列出 HITL 待审批任务          |
| POST   | `/agents/approve/<task_id>`| 审批 / 拒绝挂起任务           |
| POST   | `/agents/runs`             | 创建持久化运行                |
| GET    | `/agents/runs/<run_id>`    | 查询运行状态                  |
| GET    | `/agents/runs/<run_id>/events` | SSE `Last-Event-ID` 断点续传 / JSON 分页 |
| GET    | `/dashboard`               | 三赛题统一只读证据作战台       |

## 技能注册包

`skills/sympas_mcp_skills.json` 包含 **54 个公开工具的离线 UASP 注册快照**。框架启动时继续以在线 `/tools` + `/tools/schema` 做发现，但不会用通用在线 Schema 覆盖本地精确契约。

系统严格区分三种口径：

- `defined=54`：离线定义覆盖，不代表远端已经全部部署。
- `live_available` / `missing_from_live`：当前服务端实际广告与缺失情况，以能力快照为准。
- `successful_tool_calls`：某次评测中严格 `status=success` 的调用数；能力缺口不计成功。

新增 24 项能力已接入 AH-SecAgent 的 OODA 证据链、SF-SuperAgent 的流路径/增量风险链和 HW-CodeArts 的语言预检/修复预览/回归门禁。远端未广告或网络状态未知时，注册表返回 `capability_unavailable`，不会发起伪成功调用。

所有 Sympas 访问地址统一通过 `SYMPAS_MCP_URL` 或 `SYMPAS_MCP_HOST` + `SYMPAS_MCP_PORT` 解析，不再依赖固定的本地地址。

## 技术方案文档

详细设计说明见 `docs/TECHNICAL_SOLUTION.md`。

## 安全说明

- online/strict 模式除健康检查外默认鉴权、限流、CORS 白名单和请求体上限，且不会把审批 token 暴露给 Dashboard/SSE。
- 破坏性动作按策略强制 HITL；审批网关不可用、超时、伪造或重放时失败关闭。
- 所有 MCP 调用通过 `Authorization: Bearer <SYMPAS_MCP_TOKEN>` 完成鉴权。
- Prompt 注入检测由 `PreToolUseGuard` 在工具执行前自动拦截。
- 默认锁定环境包含 `cryptography` 与 `cbor2`，EAT 帧使用 Ed25519 并可导出标准 CBOR `COSE_Sign1`；HMAC/纯哈希仅作为显式降级证据。
- 运行状态与事件保存在 SQLite；进程重启时未完成运行恢复为 `paused`，过期记录先归档后清理。
