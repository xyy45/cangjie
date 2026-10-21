# 最终测试报告与验收清单

日期：2026-10-17。结果只覆盖本机支持环境，完整范围和逐任务证据见 acceptance-audit.md。

| 层级 | 命令／操作 | 当前结果 |
| --- | --- | --- |
| 离线 | `.venv/bin/python -m pytest tests -m 'not sdk and not live' -q` | 53 passed，5 deselected，8.64秒 |
| SDK | `.venv/bin/python -m pytest tests/sdk tests/integration/test_full_journey.py -q` | 4 passed，23.70秒 |
| LIVE | `.venv/bin/python -m pytest tests/live/test_repair_live.py -q` | 1 passed，9.16秒 |
| 连续复演 | `.venv/bin/python scripts/rehearse.py` | 三次独立基线，均实际模型、首候选、build PASS、test 11 PASS、DELIVERED |
| 浏览器 | A生成→审阅→接受→下载→刷新；D受保护路径探针 | 下载归档字节相同；D拒绝、写0、文件不变 |

离线测试涵盖严格对象、真实 MCP 协议、路径保护、原子修改、Policy 故障关闭、检查失效、解析 UNKNOWN、取消竞态、接受/导出并发与归档篡改。SDK测试执行实际编译器和原生Policy。LIVE层使用实际配置的DeepSeek；未自动重试付费错误。本轮未发生余额、权限或SDK阻断。

## 验收记录

- [x] 正常基线11项测试通过，缺陷基线实际失败
- [x] 独立stdio初始化、工具发现与实际调用
- [x] 原生Policy三态及拒绝证据
- [x] 受限runner执行真实cjpm，零/跳过/矛盾/异常不判PASS
- [x] 模型不能改测试或配置；完整工程树校验
- [x] LIVE同候选检查、接受、导出、下载摘要一致
- [x] 三次连续真实交付，原始证据分别落盘
- [x] 原始Sympas-Nexus 453文件未改
- [x] 最终交付源码和嵌套归档排除密钥、.env与运行缓存
- [ ] 外部成员独立复现（PENDING，回执模板不是通过证据）
- [ ] 比赛平台实际提交与回下载（PENDING）

`docs/evidence/final-offline.txt`、`final-sdk.txt`、`task-07-live-configured.txt` 保存实际pytest输出；其余LIVE/下载摘要与截图在同一目录。历史故障输出保留，不能从本轮通过推导任意主机稳定性。视频已完整解码检查，并抽取中段和末段核验画面；等待被缩短且无音轨。
