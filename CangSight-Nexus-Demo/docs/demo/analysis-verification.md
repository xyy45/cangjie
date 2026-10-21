# 仓颉源码分析验收记录

实际采集覆盖2026-10-19的样例与2026-10-20的上传验收；时间以原始JSON中的UTC时间戳为准。

## 已实现与实际工具

现有工作台新增“源码分析”，先完成本地样例真实调用，再沿同一服务完成上传。通过当前课题组HTTP工具入口调用 `sympas_slice`、`sympas_dep_graph`、`ast_symbol_extractor`，没有把本地字符串提取或LLM生成的图当成课题组分析。当前合同见[analysis-contract.json](validation/analysis-contract.json)。

三个登记样例实际调用9次，保存输入和脱敏原始响应。页面初次查看使用与源码摘要一致的记录快照，标记“样例快照”；重新分析才创建新请求。上传、历史恢复和重新分析共用受保护接口，上传从不使用样例结果回退。

| 样例 | 切片 | DDG | 整体 |
| --- | --- | --- | --- |
| 直线依赖 l1_sum3.cj | 5个变量，有效 | 14节点／17边 | COMPLETE |
| 循环累加 l2_loop.cj | 内部SIL错误，失败 | 14节点／31边 | PARTIAL |
| 跨函数调用 l3_calls.cj | 内部SIL错误，失败 | 35节点／51边 | PARTIAL |

所有请求原文中的code、filename、source_sha256均已与当前本地样例逐项核对；标准化状态和结构重新解析原始响应后保持一致。图由实际JSON节点和边布局，带合法行号的节点才关联源码。符号视图仅称“结构线索”，不称官方编译器AST。

## 真实上传与下载

- 浏览器通过文件选择器上传 `fixtures/analysis/upload_pricing.cj`，预览时旧样例结果、切片变量和统计立即清空。
- 用户操作流程勾选发送至课题组MCP后真实分析，取得 `netPrice`、`charge`、`finalAmount` 对应结构。结果4个切片变量、11节点／14边；源码摘要以 `79ba5fabd511008c` 开头，区别于固定样例。
- 第一次上传任务 `fda42864f4fe46c885d2f690c51746b6`，COMPLETE；服务重启重新配对后，从“最近分析”恢复，再明确点击“重新分析”，新任务 `e9d09abee4e14fdda868da4c6324f6ea` COMPLETE，7.91秒，实际三次工具请求。两任务各工具一次，没有自动重试。
- 实测选择 `c@sum3` 高亮 `[1,3,4,6,7]`；选择上传文件的 `finalAmount@netPrice` 及L3图节点，能关联实际源码。缩放、滚动、样例切换、私有历史恢复、证据弹窗和下载均已浏览器观察。
- 最终通过浏览器下载新任务ZIP，逐项核对源码原字节、三个工具原始记录和清单SHA-256；下载的result.json与服务端已验证的原始result.json完全相同，并与API公布的result_sha256一致。
- 概要：[analysis-upload-live.json](validation/analysis-upload-live.json)。上传与私有结果保存在本机.runtime，不随源码ZIP交付；公开上传演示源文件由本轮新建，不含用户私密代码。

## 测试与审查

| 检查 | 实际结果 | 原始输出 |
| --- | --- | --- |
| `python3 -m pytest tests -m 'not live' -q --tb=short` | 237 passed，1 deselected；211.77秒 | [完整回归](validation/analysis-python-full.txt) |
| 相关分析后端最终回归 | 46 passed | [分析回归](validation/analysis-python-focused.txt) |
| Node前端与原工作台状态测试 | 35 passed，0 failed | [Node回归](validation/analysis-node.txt) |
| 实际本地样例工具分析 | 3份源码／9次调用，结果如上表 | [真实调用概要](validation/analysis-live-samples.txt) |

Python完整回归包含原仓颉MCP/Policy/SDK、人工批准和导出链。模型付费测试被排除；本轮分析控制器没有调用DeepSeek。MockTransport测试仅证明HTTP合同和异常处理，不计真实服务分析。无新增依赖或版本升级，运行环境沿用原[环境记录](validation/summary.json)。

独立只读审查发现两项P2：迟到的初始样例目录覆盖上传选择；导出重新序列化导致结果文件与已公布摘要不一致。均新增失败复现测试后修复：按选择epoch保护上传；导出确切存储字节，打包前再次核对所有摘要。仅修正样例结果文件/清单打包，原始源码和响应SHA保持不变。复核无未解决重要项，之后执行上述最终全量回归。

测试覆盖单文件UTF-8/扩展名/路径/大小/行数限制、配对与CSRF、actor归属、重复请求和双worker领取、源/证据篡改、重启IN_DOUBT、空结果、内部错误、悬空边与越界行、超时无重试、重定向、凭据转义脱敏及迟到响应。

## 边界

上传限制为单个UTF-8 .cj，64KiB／1000行，不是完整工程上传。当前使用已验证的SymPas后向切片和DDG；复杂语法与IR、行准则精度、图标签简化存在已观测限制。静态结构观察不代替编译、类型或行为正确性验证。

输入摘要证明本次请求与已保存源码的绑定，不是远端签名。45秒期限取消客户端等待，不证明远端任务已经终止；不自动重发。在途服务重启记为IN_DOUBT，不能解释为完成。分析不会在本机执行上传代码或将本地模型密钥传给课题组服务。

截图：[固定样例](analysis-sample.png)、[实际上传结果](analysis-upload.png)、[证据弹窗](analysis-evidence.png)。逐条完成审计见[analysis-completion-audit.json](validation/analysis-completion-audit.json)。
