# 第2项验收：组合业务难例与修复轨迹

2026-10-26。**本阶段已验收，保留真实模型格式失败与未观察到迭代增益的结论。** 总体升级目标尚未完成，下一步是第3项3A业务属性验证。

## 已交付

- 新语料版本business-hard-bench-v1-sealed：先10类合格后扩展30项，每类3个逻辑缺陷变体。旧30／100语料摘要不变。
- 版本化原始缺陷、参考修复、公开规则／示例、独立搜索与封存验收；搜索、累计与缩减排除全部holdout。
- 只读轨迹报告按候选、树、轮次、请求／响应、反馈事件和原件摘要关联，区分首轮遗漏、搜索发现、已反馈与反馈后修复。
- 同版同预算的两任务三流程真实模型批次、完整计划分母、失败分类和原版源码重放。

全部任务是团队自建合成缺陷；本阶段范围为Int64／Bool、最多4参数、同包最多3个允许修改的生产文件。30项质量合格不等于30项均已跑真实模型。

## 验证证据

| 检查 | 真实结果 | 原件 |
|---|---|---|
| 首批10项SDK质量 | 10/10合格，14.383秒，日志重放一致 | [质量原件](validation/next-phase-2/hard10-quality/result.json) |
| 扩展30项SDK质量 | 30/30合格，40.166秒，日志重放一致 | [质量原件](validation/next-phase-2/hard30-quality/result.json) |
| 缺陷与参考版本 | 全部baseline公开PASS／封存FAIL；reference公开／封存PASS | 各质量目录logs与projects |
| 变体审阅 | 每类3种不同逻辑，不以数字替换充数 | [变体矩阵](validation/next-phase-2/variant-matrix.md) |
| 三文件三流程SDK夹具 | 全通过，56.74秒，未调用真实模型 | [日志](validation/next-phase-2/three-mode-sdk.txt) |
| 两轮迭代SDK夹具 | 首轮公开PASS／搜索FAIL，下一请求带真实反例，第二轮搜索／封存PASS | [最终轨迹](validation/next-phase-2/feedback-fixture-final-trajectory.json) |
| 独立审阅 | 2项Important均已修正，相关63项通过 | [审阅记录](validation/next-phase-2/independent-review.md) |
| 完整Python／SDK | **759通过／1 live未运行，914.61秒，退出0** | [日志](validation/next-phase-2/python-full.txt) |
| 前端 | **108通过／0失败，239.407375毫秒** | [日志](validation/next-phase-2/node.txt) |
| 真实对照 | 计划6条、完成6条，5个可验证修复、1个格式拒绝 | [完整报告](validation/next-phase-2/live-result/final-report/report.md) |
| 归档源码重放 | 质量10／30、夹具轨迹、真实6条报告／轨迹均重建一致 | [重放结果](validation/next-phase-2/archived-live-replay.json) |

首次全量收集因两个新增SDK测试与单元测试重名而退出；仅将SDK测试重命名后完整重跑，未跳过失败检查。真实批次始终使用上述完整回归对应的冻结源码，没有改提示来挽救本批答案。

质量摘要：10项be2768d72916f258e07d602eb536ba985a64053f1309976935957cfaba0de0c0；30项a0ce6d4f83d19b80e085c7b60ba993614c44ba804e2ac51a2912b85d715bd692。

## 真实模型结果

任务为三文件会员校验business_hard_009、分段计费封顶business_hard_010。两任务各跑DIRECT、MCP、CEGIS；模型实际返回deepseek-flash，配置和执行版本一致，每条最多3轮／480秒／每次6000输出tokens／temperature0.2。用户本批独立批准最多18次请求，实际6次，未使用的12次上限已关闭，不转作其他任务授权。

| 流程 | 任务／完成 | 可验证修复 | 请求 | tokens | 两条合计耗时 |
|---|---|---:|---:|---:|---:|
| DIRECT | 2／2 | 2 | 2 | 9641 | 39.814秒 |
| MCP | 2／2 | 1 | 2 | 17512 | 59.268秒 |
| CEGIS | 2／2 | 2 | 2 | 17499 | 71.267秒 |

总prompt tokens41074，completion tokens3578，合计44652。缺少经确认的计价规则，费用为UNKNOWN；不能从tokens直接宣称节约了多少费用。

5次成功均在首轮。两次CEGIS独立搜索均通过，未发现反例，因而**本批未观察到真实反例反馈增益**；首轮遗漏、搜索发现、已反馈、后续修复计数均为0。这里只能报告已测两任务，不能推断全部30项或工业项目的成功率。

MCP009返回的建议列了order、amount、validation三个文件，但proposal.edits只修改order；已有严格响应契约要求两者路径集合完全一致，因此已知格式拒绝，没有登记候选，也没有重试该槽。这是模型输出质量限制，不是MCP分析失败；四份真实分析上下文共24个工具结果均经原件复核为VALID，见[mcp-evidence-summary.json](validation/next-phase-2/live-result/mcp-evidence-summary.json)。

初始CLI在这一REJECTED结果后保守停止，原STOPPED和部分报告完整保留。确认HTTP响应、用量与格式失败均已知后，仅用原公共run_case、同一源码／计划／预算继续原先尚未启动的4条；独立驱动和CONTINUATION记录可查。没有重跑拒绝槽，没有继续任何UNKNOWN，没有改模型答案或缩小分母。不能把此次过程描述为原CLI不间断完成。

6240实际是项目既有团队分析服务47.94.83.64:6240；此前提案称为“本地”不准确，派发前已对用户纠正并在授权记录中保留。只发送自建任务选定源码、需求、公开例子、有效分析及允许的失败反馈；私有规则、参考修复和封存测试没有进入模型上下文。

## 轨迹与能力边界

六份实际轨迹位于live-result/trajectories；其中模型结构拒绝单列GENERATION_OUTPUT_INVALID，首轮无候选不伪造为“修复后失败”。未知请求与未知验证保持UNKNOWN，不能当作零成本或修复成功。

退款001另有已保存的SDK夹具搜索遗漏：保留缺陷的候选通过公开测试与32项有限搜索，但封存FAIL，未触发第二轮，见[证据说明](validation/next-phase-2/finite-search-miss-fixture/README.md)。没有更改搜索预算或隐藏此失败。有限采样不证明任意输入正确。

分段计费的两轮SDK轨迹使用显式模型／图响应夹具，真实SDK发现反例并验证后续修复；它证明链路可运行，不能代替真实LLM增益。报告允许同一首轮树的holdoutFAIL证明首轮遗漏，但不把后续树的结果归给首轮，不将封存输入作为反馈。

## 冻结与复现

冻结实现73cf669ec2a0d04d43b3de8cb40124e596891df2a94d6faa06c31f099a609c48，计划7d720766836d62cebac2e900c5bc4ef6576ee15ccb30679990481bb0ac6ba702。

execution-source.zip包含80个Python／依赖身份文件及绑定的仓颉core源码；core-runtime.zip另保存本项目原生core二进制和构建记录，不包含SDK或凭据。live-result/batch-run.zip保存六条运行的源文件、冻结材料、日志及索引，排除编译target、所有真实API／分析凭据和操作者会话文件；打包前已在内存核对实际密钥未出现在材料中。

用项目虚拟环境执行：

```bash
../.venv/bin/python docs/demo/validation/next-phase-2/replay_offline.py
```

重放解压归档源码及原core，借用固定SDK／stdx环境，禁用网络，SDK执行／模型／MCP请求均为0，报告和轨迹hash一致。它是原固定环境上的证据重建，不是干净机器部署验证；部署／复现仍是第5项的完整交付目标。

## 下一阶段

重读总目标及[第3项准备文档](next-phase-3-preflight.md)，先设计并实施3A单次属性，再分别实现3B关系与3C操作序列。当前属性产品能力尚未实现。模型建议／修改路径不一致作为已报告的协议质量问题，后续明确提示约束时仍保留原校验器与历史失败，不将旧评测成绩套用于新提示版本。没有自动提交、推送或发布。
