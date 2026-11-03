# 原生静态切片表接入验收

日期：2026-10-21。默认切片工具改为 `sympas_slice_table`，固定参数为 `lang=cangjie`、`method=SymPas`、`direction=Bwd`、`table_formats=["json"]`。其余 DDG、符号提取及原生调用图 SVG 保持原有分析流程。

## 数据含义与校验

返回值为整个文件的变量后向切片表。页面按变量选择行集合，源码与依赖节点使用同一组行号高亮。“源码定位行”用于导航和定位，不会作为新工具的行级切片准则，也不会从返回表中伪造行级切片。

仅接受成功状态、正确工具/方向/算法、匹配变量计数、非空结构。每个变量名须为非空有界字符串，每个变量只允许当前文件，行号必须为源码范围内整数（拒绝布尔值）。源码及工具原始返回使用 SHA-256 绑定；读取和导出时核对原始证据。空表、失败、结构不匹配均不启用有效高亮，不进入有效模型依据。

标准化数据保留 `scope=VARIABLE_TABLE`、`direction=Bwd`、`method=SymPas`。修复桥接沿用既有“VALID 且未超预算才进入上下文”的规则，因此新工具名称、完整表作用域及证据引用一同进入后续模型上下文。本轮没有发起 DeepSeek 修复请求。

## 兼容与默认样例

新任务以分析配置版本 4 运行。旧 `sympas_slice` 的会话、原始证据、导出及日志解析展示继续可读；新工具结果不会退回旧日志解析。影响分析不会把旧配置记录复用为新工具结果。

新样例保存在 `fixtures/analysis/snapshots-native/`，保留此前 `snapshots/` 的原始证据。默认展示新样例快照及其真实原生调用图 SVG；点击“重新分析”才再次请求远端工具。

## 真实验证

| 来源 | 有效变量 | 三个工具状态 |
| --- | ---: | --- |
| 直线依赖 | 5 | 全部 VALID |
| 循环累加 | 4 | 全部 VALID |
| 跨函数调用 | 10 | 全部 VALID |
| 上传定价源码（服务链路） | 4 | 全部 VALID |
| 上传定价源码（网页） | 4 | 全部 VALID |

网页实测跨函数样例选择 `index@aggregate`，高亮行严格为 `[14,15,17,21,23,25,26,27]`，与原生 JSON 相同。页面证据显示 `sympas_slice_table`，无日志恢复派生数据。

网页上传任务：`a72105fd067b4bb08e02728581989b9d`。下载包逐项 SHA-256 校验通过；请求源码与包内源码一致，原始 `backward_slices` 与标准化切片相同，未包含派生切片文件。

## 回归

- `python3 -m pytest tests -m 'not live' -q --tb=short`：374 passed，1 deselected，274.89 秒。
- `node --test tests/*.test.cjs`：64 passed，0 failed。
- 分析专项：135 passed。
- [真实分析摘要](validation/native-slice-table/live-summary.json)、[Python 完整回归](validation/native-slice-table/python-full.txt)、[前端回归](validation/native-slice-table/node.txt)。

以上确认当前样例及上传链路的结构有效、来源绑定和展示行为，不代表任意仓颉语法均受远端引擎支持，也不构成切片算法语义正确性的证明。
