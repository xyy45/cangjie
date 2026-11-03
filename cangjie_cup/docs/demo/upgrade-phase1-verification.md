# 阶段1：独立规则与反例驱动修复验收

日期：2026-10-23。阶段状态：已验收完成。

## 已实现路径

上传单个受限仓颉文件 → 用户确认公开测试和可选规则JSON → 冻结独立规则文件及来源 → candidate.test策略门禁内执行公开测试 → 公开PASS后在隔离工程内搜索边界输入 → 有限批量缩减 → 原生事件/日志/摘要记录 → 反馈下一轮候选 → 再次执行公开测试、搜索及累计反例 → 人工接受 → 交付校验并归档证据。

没有规则保持原模式。规则与公开预期矛盾时拒绝确认。没有明确正确性依据时不自动猜测预期值。候选、冻结测试及规则文件不因搜索而改变。

## 真实SDK验证

`../.venv/bin/python -m pytest tests/sdk/test_exploration.py -q --tb=short`（预算用例新增前）：4 passed，84.06s。

- 首轮公开测试PASS但规则搜索FAIL，找到并缩减到`f(3)`预期3实际0；新候选满足公开测试和累积反例。
- 过期验证返回UNKNOWN，交付门禁拒绝。
- 真实MCP两轮闭环：公开PASS→搜索FAIL→反馈→修复→归档。
- 真实MCP三轮闭环：公开FAIL→搜索FAIL→修复PASS，公开诊断可见、规则JSON不进入模型文件上下文。
- 检查日志、探测工程源码或配置被改动后，验证不可继续作为交付依据。

`../.venv/bin/python -m pytest tests/sdk/test_exploration.py::test_search_failures_exhaust_candidate_budget_without_review_or_delivery -q --tb=short`：1 passed，39.93s。三轮候选都通过公开测试但被独立反例否决，最终UNREPAIRED，没有接受或交付记录。

上述模型HTTP响应是确定性测试夹具，仓颉编译/测试、沙箱、策略与MCP调用是真实执行。不把这些结果称为真实DeepSeek修复成功率。本阶段未执行付费模型联调。

## 页面验证

- Node：83 passed、0 failed，覆盖规则文件导入、原始大整数文本保留、编辑撤销确认、异步导入竞争、候选证据绑定和公开PASS不提前标绿。
- 浏览器独立预览8878：真实上传shipping.cj、填写目标、读取函数、导入规则、确认与重载冻结记录；修正后验证修改公开例子保留规则并撤销勾选。
- 独立预览禁用任务/影响分析执行；未向外部MCP或模型发起请求。用户8877实例未被打断，确认端口无运行进程后已启动最新代码。
- 截图：`validation/upgrade-phase1/oracle-upload.png`。完整搜索展示逻辑通过Node组件测试；真实搜索事件通过SDK集成验证。

## 回归记录与修正

- 初次受限执行：4项端口/嵌套沙箱权限失败，375 passed；未将其当作产品通过。
- 提权完整离线回归首次：407 passed、1 deselected，330.38s。
- 独立审阅修正：公开诊断过度隐藏；编辑示例误清空规则；规则手工编辑未撤销确认；探测工程缺少运行后完整性绑定；非字符串规则表达式引发500。
- 新增SDK回归发现探测目录误用`_ref`后缀，被MCP文件证据索引拒绝，任务正确停在IN_DOUBT；修正为`project_path`并继续保留目录安全检查及清单核验。
- 最终完整回归：413 passed、1 deselected，396.40s；Node 83 passed、0 failed；`git diff --check`通过。原始日志在 `validation/upgrade-phase1/python-full.txt` 和 `node.txt`。

## 使用材料与边界

样例在 `fixtures/exploration/shipping/`，包含源码、需求、公开测试、独立规则JSON和说明。支持的表达式语法见该目录README。

固定算法`boundary-search-v1`、种子、有限输入预算；默认不穷尽笛卡尔积，不承诺发现所有漏洞。最多两批反例缩减，不保证全局最小。原上传语言/资源限制保持。独立规则仍依赖用户正确确认，不能替代业务规格审阅。

测试环境：Python 3.12.4、Flask 3.1.3、Pydantic 2.13.4、MCP SDK 1.28.1、pytest 9.1.1、Node 22.13.1；仓颉固定工具链1.0.5。Pydantic/MCP SDK实测版本高于项目声明，本阶段未修改依赖锁或声称额外版本兼容性。
