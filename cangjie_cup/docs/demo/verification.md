# 九案例与 DeepSeek 验证记录

日期：2026-10-19。本次在本机实际执行。历史规则版结果另存 [verification-rule-v1.md](verification-rule-v1.md)。

## 测试

| 检查 | 实际结果 | 记录 |
| --- | --- | --- |
| 完整非付费回归 `python3 -m pytest tests -m 'not live' -q --tb=short` | 190 passed，1 deselected；211.47秒 | [全量输出](validation/python-deepseek-full.txt) |
| 脱敏补强后的相关 Python 回归 | 35 passed；2.43秒 | [最终相关测试](validation/python-deepseek-focused.txt) |
| 前端状态回归 | 28 passed，0 failed | [Node 输出](validation/node-deepseek.txt) |
| 五个新增修复工程与三个策略探测，真实 SDK/MCP/Policy | 8 passed；57.26秒 | [SDK 输出](validation/sdk-scenarios.txt) |

每个新增修复工程均先验证基线构建成功、行为测试失败，再验证测试专用参考修改构建与全部冻结用例通过。旧订单真实规则链包含在全量回归。参考修改只证明案例可验证，不计模型修复证据。MockTransport 测试不访问模型，不计真实AI请求。

独立代码审查发现 JSON 转义可能绕过原字符串脱敏；已增加失败复现测试、在响应解析后及持久化前清理两层 JSON，再运行35项相关测试。审查复核通过，无未解决重要项。全量190项结果发生于该补强之前，补强后仅复跑相关测试；未额外消耗模型请求。

## 一次真实模型联调

- 模型：`deepseek-flash`，实际服务端 HTTPS 请求1次，无自动重试。
- 案例：校验计费修复，候选1份，真实修改 `src/quantity.cj` 与 `src/fee.cj`。
- 修复：数量下界 `>= 0` 改为 `>= 1`；计费加法改为乘法，中文建议来自同一模型响应。
- 实际固定 SDK 构建通过，9项测试通过；4965 Tokens，其中输入4522、输出443。
- 任务 `5eacec050995431c821ccdaade7baa5e`，状态 `REVIEW_PENDING`，未点击接受、未产生交付批准。
- 事件测得13.91秒，模型调用、建议与候选ID绑定已核验；实际运行记录保存在本机 `.runtime/demo-workbench/`，不随源码交付。
- 脱敏概要和请求／响应摘要：[deepseek-live.json](validation/deepseek-live.json)。这一次结果不外推为所有六案例均经真实模型修复。

## 浏览器

- 九个案例分为订单、跨文件和策略；新案例没有预置修复后代码，点击案例不触发模型请求。
- DeepSeek实际两文件差异、修复建议弹窗、9项验证结果和待审阅状态可见；刷新后可从任务记录恢复，无新模型请求。
- 配置保护实际探测显示“原生／已拦截”，零候选写入，不显示修复测试通过，不允许接受或下载。
- 三类策略探测在SDK回归中均实际执行，原生原因 `PROTECTED_PATH`、MCP `ERROR`、基线不变、写入0。
- 窄屏631px沿用既有布局，九案例按三组排列，代码独立横向滚动。

截图：[工作台](deepseek-workbench.png)、[修复建议](deepseek-advice.png)、[原生拦截](native-probe.png)。

## 环境及边界

沿用本机仓颉1.0.5、固定MacOSX15.4 SDK、macOS ARM64；Python/Flask/MCP等版本见原 [summary.json](validation/summary.json)。本机MCP 1.28.1与锁文件1.26.0有版本差异，跨机器需按锁文件复核。

服务端保留密钥，源码ZIP排除 `.env`、`.runtime` 和操作者凭据，并逐文件检查当前Key未出现在交付材料中。本报告对应历史单次调用版本；当前 CEGIS 版本为每任务最多三轮、每轮6000输出Tokens，见 [CEGIS 验证记录](cegis-verification.md)；没有格式合规或测试成功的保证，失败不退回固定答案。

尚未实现十二任务、同预算对照、任意工程修复、云部署和完整恢复；冻结测试未覆盖语义继续在需求弹窗和验证计划报告中列明。
