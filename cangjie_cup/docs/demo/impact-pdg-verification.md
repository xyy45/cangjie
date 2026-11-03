# 修复影响对比 PDG 回退验收

日期：2026-10-22。

有效 DDG 保持优先；没有有效 DDG 时，使用经过原始响应和源码绑定校验的 MCP PDG，展示修改行节点及一跳邻接，并标明 DDG / PDG。原工具 EMPTY / FAILED 状态和总体 PARTIAL 状态保持真实含义。

历史报告不改写：读取时校验原分析 actor、源码内容/摘要、切片准则、原观察摘要与冻结报告 tools 索引，新增 display_graph 投影。导出仍保留原 report.json 字节，另增 display-graphs.json 并纳入 manifest。原分析缺少 PDG 时保持原结果，不伪造图、不自动重发 MCP。

页面分别显示尚未生成、当前侧分析中、等待另一侧、分析中断、缺少结果或工具返回的空/失败原因。分析期间按钮显示“分析中”。图形设置明确像素尺寸，避免继承全局 SVG 图标 18px 样式。

## 实测

- 用户截图候选 `c_079abb8fc80840318817c4dfc64f2fa4`：两侧原 DDG 为空，已有 PDG 各 3 节点 / 2 边；只读接口各展示 2 个相关节点 / 1 条边，无重发。导出原报告字节不变，全部 manifest 摘要校验通过。
- 内置校验计费候选 `c_e57ab0e2480446359a6fed4a01f994b8`：浏览器首次执行工具对比，quantity 两侧 PDG 原图各 3 节点 / 2 边，fee 各 4 节点 / 3 边；每侧显示修改行附近 2 个节点。等待提示和最终图形通过网页核对。没有付费模型调用。
- 浏览器测得四张 PDG SVG 各约 366.6 × 182 px，已不再是 18px 图标。

## 回归

- `python3 -m pytest tests/analysis -q --tb=short`：158 passed。
- 合成 DeepSeek 配置下 `python3 -m pytest tests -m 'not live' -q --tb=short`：397 passed，1 deselected，333.84s。配置使用测试占位值和 fixture.invalid，不含真实密钥。
- `node --test tests/*.test.cjs`：76 passed，0 failed（含最后的 SVG 尺寸回归）。
- 只读代码复查通过；`git diff --check` 通过。

证据：[历史报告派生结果](validation/impact-pdg/legacy-live.json)、[Python 回归](validation/impact-pdg/python-full.txt)、[前端回归](validation/impact-pdg/node.txt)。
