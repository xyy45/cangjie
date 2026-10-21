# 工具日志切片恢复验收

日期：2026-10-20。用户批准范围：把工具已经输出的文本切片表本地结构化后展示，保留原始失败状态、来源及限制。本轮远端分析请求0次，模型请求0次。

## 当前效果

| 样例 | 原工具切片状态 | 展示结果 |
| --- | --- | --- |
| 直线依赖 | VALID，原生JSON有效 | 原有5变量，不启用日志恢复 |
| 循环累加 | FAILED，后续引擎错误，JSON为空 | 本地从原日志恢复4变量 |
| 跨函数调用 | FAILED，后续引擎错误，JSON为空 | 本地从原日志恢复10变量 |

在“源码分析”中切换循环或跨函数样例即可看到恢复结果，无需点击重新分析。切片卡片显示提示色“日志解析恢复”，说明栏明确原引擎检查未通过。变量选择、源码高亮、图节点的对应行高亮共用既有交互；恢复高亮使用提示色。DDG节点和边未改变，不能将恢复切片解释为已修复图或语义证明。

浏览器实际选择 `index@aggregate`，恢复高亮行精确为 `[14,15,17,21,23,25,26,27]`；DOM读回每行均携带恢复标记。切回默认 `bounded@transform` 后，源码3、6、8等行可见提示色高亮。直线依赖仍使用原生JSON及原有绿色状态。

## 解析与来源

新增 `nexus/analysis/recovery.py` 使用版本 `sympas-text-v1` 的确定性解析器，仅接受已知的Backward Static SliceTable表头、分隔符与单行格式。不执行日志内容，不使用eval或AI补齐。

解析前核对源码字节摘要、原始响应摘要、原请求源码与文件名，以及SymPas后向分析方式。表内文件名必须等于当前输入，行号必须为源码范围内整数。重复变量、畸形行、未知表头、多张表、越界或超限内容使整张派生表REJECTED，不拼接部分有效行。没有已知表格时不生成恢复结果；有效原生JSON始终优先。

结果作为顶层 `derived_slice` 单独输出，包含origin、parser_version、raw_ref、raw_sha256、source_sha256、原始状态、原日志表行范围和限制说明。原observations保持FAILED，整体状态仍是原PARTIAL；不会转换为VALID或COMPLETE。REJECTED派生结果不会启用变量高亮。

## 原始证据和下载

恢复发生在已验证记录的只读投影中，不修改已有数据库、原始响应、`result.json` 或样例 `manifest.json`。私有分析、历史分析及修复绑定分析沿现有鉴权入口读取，同样可以恢复展示。

下载增加 `derived-slices.json`。私有分析的现有导出清单纳入其摘要；样例导出保留原 `manifest.json` 字节，额外提供 `derived-manifest.json`，同时索引原始文件和派生文件。

浏览器下载的 `CangSight-analysis-sample-calls.zip` 实测8项文件；原始源码、result、三份工具记录和原清单逐字节一致；派生清单中每个SHA-256匹配，恢复10个变量。三个登记样例的原清单及所有原文件摘要均重新核对通过。[机器可读审计](validation/slice-recovery-audit.json)。

恢复数据只用于辅助展示。现有修复桥接继续只选原observations中VALID且预算内的数据，`derived_slice`不会自动进入DeepSeek上下文、模型引用或独立验证结论。既有待审阅任务及批准状态未改变。

## 验证结果

| 检查 | 实际结果 | 输出 |
| --- | --- | --- |
| `python3 -m pytest tests -m 'not live' -q --tb=short` | 267 passed，1 deselected，231.15秒 | [完整回归](validation/slice-recovery-python-full.txt) |
| `python3 -m pytest tests/analysis -q --tb=short` | 70 passed，1.52秒 | [相关回归](validation/slice-recovery-focused.txt) |
| `node --test tests/*.test.cjs` | 44 passed，0 failed | [前端回归](validation/slice-recovery-node.txt) |

完整回归使用现有固定仓颉SDK及本机原生执行权限。新增恢复用例先观察缺失功能导致失败，再实现并通过；包括样例实际日志、私有上传、只读复用、来源错配、整表拒绝、下载字节与摘要、JSON优先和恢复高亮绑定。独立只读审查未发现需要阻断的新增问题，另实跑18项恢复Python、8项分析UI测试通过。

适用范围限当前已知日志格式。恢复只证明文本能按约定解析、文件及行号绑定通过，不证明切片语义或完整性，也没有修复远端SIL错误。

截图：[跨函数恢复](slice-recovery-calls.png)、[循环恢复](slice-recovery-loop.png)、[原状态与派生来源](slice-recovery-evidence.png)。
