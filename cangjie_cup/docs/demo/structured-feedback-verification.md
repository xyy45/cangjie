# 结构化反例与六案例 MCP 覆盖

日期：2026-10-20。范围是已批准的 1+2；未增加上传文件修复。

## 如何使用

六个修复案例点击“开始”，均收集该任务允许修改的生产源码的真实 MCP 分析。页面“分析依据”展示各工具状态、入模情况与模型引用，可打开同版本的原图／切片。三个策略探测保持原流程，不调用模型。

当候选测试失败时，CEGIS 区域显示该候选的“验证反例”。选择历史失败轮次可查看当时的输入、预期值、实际值、需求关联和诊断出处。切换候选会清空不属于该候选 id／树摘要的内容。失败反馈事件与下一轮 DeepSeek 请求使用同一组结构化反例。首轮通过时没有失败卡片；历史记录不补造新字段。

## 解析与兼容边界

- 只接收验证器确认失败的用例，识别固定 SDK 的 `Expect Failed` 相等断言与 left/right，忽略汇总重复项。每个用例仅取首条可识别断言。
- 输入仅在日志表达式确实为数字／布尔字面量函数调用时显示；变量表达式不会冒充已观测运行时参数。无法提取的字段为 null，页面显示“未提供”，原诊断保留。其他断言格式、复杂类型值、编译错误继续使用日志，不以模型填充。
- 需求仅有测试套件级映射，页面明确标注，不声称定位到单条需求的因果关系。
- 证据字符位置相对于去除终端控制符的 check.diagnostics，不是原始日志字节偏移；log_ref 仍指向原始完整日志。诊断被截断时可能无法识别完整断言。
- 私密诊断不产生公开反例；旧 RepairFeedback 可读取，原记录不重写。通过验证仍等待人工接受。
- 每任务至多三份允许修改的生产文件，每文件三项工具请求。只纳入 VALID 结果；单项最多24000字节，总工具数据最多64000字节，并按原上下文大小缩减。超限数据不入模，原证据仍保留；模型最终256KiB限制与三轮／480秒预算不变。
- MCP 的切片失败、空DDG等状态不因本轮扩展而变成成功。没有新增静态分析算法或普遍语义正确性证明。

## 真实验证

### 六案例远端 MCP

实际运行新的 RepairAnalysis，逐项检查请求源码及绑定证据：

| 工程 | 文件 | 工具请求 | 结果 |
| --- | ---: | ---: | --- |
| order-demo-bug | 3 | 9 | PARTIAL |
| order-price | 1 | 3 | PARTIAL |
| order-discount | 1 | 3 | PARTIAL |
| cross-validation | 2 | 6 | PARTIAL |
| cross-discount | 2 | 6 | PARTIAL |
| cross-stock | 2 | 6 | PARTIAL |

共33次真实工具请求、零模型请求，失败／空结果均保留。记录见 [六案例结果](validation/six-case-mcp-live.json)。运行原始证据位于本机 `.runtime/feedback-mcp-validation/`，不进入源码交付包。

### 页面真实 DeepSeek

价格案例任务 `2d98615b6fda4826a3336bbd2541f06a`：一次真实模型请求，首轮生成修复，将 `< 1000000` 改为 `<= 1000000`，构建通过、测试5/5通过，状态 REVIEW_PENDING，无人工接受或导出。其三项 MCP 结果中结构线索有效，切片 FAILED、DDG EMPTY；模型实际引用了有效结构线索。检查保存的请求确认模型上下文与原始分析事件一致，未把失败工具数据作为有效依据。见 [真实价格联调](validation/structured-feedback-live-price.json) 与 [页面截图](six-case-mcp-price.png)。

### 两轮真实 SDK / MCP，模型使用测试夹具

集成测试第一轮只修数量边界，真实编译测试得到计费反例，例如 `calculateFee(3, 100)` 预期300、实际103。第二轮请求中的反例与已保存反馈完全一致，保留第一轮正确修改后修复计费，真实构建和测试通过。该测试使用 MockTransport 返回模型提案，不计为真实 DeepSeek 调用。见 [原始失败日志](validation/structured-feedback-sdk-failed.log)、[绑定验证](validation/structured-feedback-sdk.json)、[使用正式组件的验收截图](structured-feedback-sdk.png)。

## 回归与审查

- `python3 -m pytest tests -m 'not live' -q --tb=short`：312 passed、1 deselected，246.07秒，包含实际固定 SDK／原生 MCP 两轮反馈测试。
- `node --test tests/*.test.cjs`：56 passed，覆盖反例值、缺失数据、空候选、切换轮次及所有案例入口。
- 分析／反馈／循环／报告解析定向回归：124 passed。
- 独立只读审查未发现可确认缺陷；审查环境自身的 SDK 测试受沙箱限制，主执行环境使用获准的原生进程权限完成上述312项完整回归。

日志：[Python完整输出](validation/structured-feedback-python.txt)、[Node输出](validation/structured-feedback-node.txt)、[定向输出](validation/structured-feedback-focused.txt)。
