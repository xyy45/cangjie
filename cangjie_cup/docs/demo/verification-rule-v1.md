# 演示版验证记录

日期：2026-10-19。以下结果在本机实际执行，不代表独立成员真人验收。

## 自动验证

| 检查 | 实际结果 | 原始记录 |
| --- | --- | --- |
| `python3 -m pytest tests -m 'not live' -q --tb=short` | 164 passed，1 deselected；154.98秒 | [python-full.txt](validation/python-full.txt) |
| `node --test tests/demo-race.test.cjs tests/demo-flow.test.cjs tests/workbench-race.test.cjs tests/operator-auth.test.cjs` | 26 passed，0 failed | [node.txt](validation/node.txt) |
| 新增规则全链 + 演示后端复核 | 7 passed；16秒；后续缺SDK与鉴权后端再次7 passed | [rule-journey.txt](validation/rule-journey.txt) |

完整Python回归包含固定SDK、真实MCP、原生Policy、HTTP交付及新规则修复。付费模型LIVE测试被明确排除。宿主沙箱限制下执行sandbox-exec会返回Operation not permitted；真实本机回归在获准的本地执行环境运行，不修改或跳过生产执行门禁。

环境：Python、Flask、MCP、pydantic等实际版本见[summary.json](validation/summary.json)。本机MCP SDK为1.28.1，与上游锁文件1.26.0存在差异，当前结果仅证明所列实际环境；跨机安装应按锁文件独立复核。仓颉沿用固定1.0.5 SDK，原生策略在新工程重新编译，有3项上游Console弃用警告，构建退出码0。

## 浏览器验收

- 实际观察桌面宽度1265及窄屏宽度631的布局；窄屏侧栏转换为顶部导航，代码区域独立横向滚动。
- 订单回放：开始、待审阅、接受、下载；11项用例、原候选diff及历史来源可见。
- 跨文件模拟：两文件切换、报告、接受与模拟下载；来源持续为“模拟”。
- 策略拒绝：到策略节点停止，接受与下载不可用。
- 真实规则：本机配对→基座分派→MCP→仓颉Policy→完整工程构建/11项测试→测试操作者接受→真实下载。
- 真实差异：quantity >= 0 修改为 quantity >= 1，实际源内容取自受保护API；新模型调用0。
- 历史：包含实测、回放、模拟来源，重新打开真实交付能恢复当前后端结果；交付列表具有对应下载链接。
- 异步回归：启动切换、取消重置、过期历史、未验证需求不能变绿、原生拒绝、拒绝请求切换均有Node测试。

真实下载包的文件摘要、项目树摘要与原生导出清单已经逐项核验，导出ID与ZIP摘要见summary.json。截图见[screenshots](screenshots/)。浏览器点击接受属于自动测试操作者，不宣称用户本人或独立成员已经审阅。

## 范围

此版交付的是已批准的最小演示闭环。十二任务、同预算对照、通用项目修复、云部署、完整自动恢复和完整Native隔离仍未实现，不计入本次完成声明。规则模式不调用模型，历史AI回放与跨文件模拟不计作新AI修复。
