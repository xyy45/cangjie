# 上传单文件修复：已批准范围与执行记录

## Task
实现上传单个仓颉文件、确认行为示例、真实 MCP / DeepSeek / CEGIS、人工审阅和下载。

## Background
用户批准了上一条五步闭环并明确“开始实施”。复用已有任务、策略、验证、反馈和交付，不另建运行平台。目录无 Git；原地实施，不改其他工程。

## Requirements
- 单个 UTF-8 .cj（64KiB/1000行）；预览函数签名，填写目标和选择待测函数。
- 至少两组 JSON 输入/预期输出，明确 target/regression 分组；确认后冻结，模型不得修改测试。
- 本轮支持 Int64/Bool 普通函数、局部变量、算术/比较/逻辑、条件、while 和同文件函数调用。
- 词法与完整受限语法检查覆盖基线及所有候选；禁止导入、宏、类、字符串、外部调用和顶层执行。
- 保留源文件原始字节，系统生成工程清单与测试；需求/示例/源码共同绑定摘要。
- 准备/确认不调用远端；开始修复明确同意发送源码和公开示例至 MCP / DeepSeek。
- 上传记录与任务绑定浏览器会话，跨会话不得查询、修改、下载或复用启动键。
- 复用三轮480秒和原有模型预算；失败停止、不伪造；接受后导出证据。

## Constraints
不支持任意工程/外部包/任意测试源码。只运行经受限语法检查的上传与候选；保留原生运行沙箱。历史验证因验证器代码升级可能需重新验证，不重写旧报告。

## Reference Files
nexus/requirements/service.py、execution/workspace.py、execution/runner.py、adapters/cangjie/verifier.py、analysis/repair.py、demo/app.py 与前端。

## Expected Output
上传修复弹窗及工作台入口、冻结测试和需求、可恢复任务、验证证据与最新版源码包。

## Validation Commands
python3 -m pytest tests -m 'not live' -q --tb=short
node --test tests/*.test.cjs
受限语法攻击拒绝、会话隔离、幂等、真实SDK失败到修复、真实MCP/模型单次联调、页面上传/确认/历史恢复。

## Definition of Done
上传代码真实参与修复，真实测试判定通过/失败，候选不能扩大执行能力或改测试；旧六案例和策略探测回归通过；使用说明明确支持范围及仅覆盖确认示例。

## 执行顺序
1. 受限源码与示例契约（测试先行）。
2. 上传服务、冻结工程、任务/审批/证据绑定及会话隔离。
3. 上传UI和现有闭环连接。
4. 原生/远端/页面验证及独立审查，交付。

进度：四项完成。

原生裁定：无package的文件由工程副本补固定package，原始字节单存并归档，前缀纳入上传证据；提供package的CRLF文件原样编译。

安全回归：bareCR／Unicode行分隔与嵌套块注释先观察3项失败，修复词法边界；标准库同名重载经原生探针确认风险，追加3项先失败回归，改两遍签名收集、原始类型检查和IO预留名拒绝；未更改原生沙箱权限。所有权get(None)回归先失败再修复。候选与执行前均复核受限程序和冻结配置。

最终验证：Python342 passed、1 deselected（292.28秒）；Node61 passed。带／不带package两种上传的真实SDK两轮反馈和归档通过。模型HTTP夹具与真实模型证据明确分开。

实际页面：新上传样例经3项真实MCP工具、1次DeepSeek模型请求修复，6/6测试通过，REVIEW_PENDING，未替用户接受。类型检查器升级后公开RuntimeOwner+MCP重验同候选仍6/6；浏览器历史恢复无模型重放。修复UI首条旧报告覆盖最新结果及verified使用历史PASS的遗漏，两个方向回归先失败后通过，独立复核关闭。

交付说明：docs/demo/upload-repair-verification.md；原始上传与运行库不进入源码ZIP。
