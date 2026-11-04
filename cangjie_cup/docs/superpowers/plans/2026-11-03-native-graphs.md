# Native Graph Gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在cangjie_cup源码分析页安全展示MCP原生七类图，整行、全图适配、无图内滚动条。

**Architecture:** 新增analysis/native_graphs.py负责限额下载及不可变产物绑定；现有client/service/routes扩展native_graphs schema1，同时保留Cg接口。新native-graphs.js负责原图类型选择及img缩放拖拽，不改切片计算。

**Tech Stack:** 原Flask、httpx、ElementTree、原生JS/CSS；无新增依赖。

**Spec:** docs/superpowers/specs/2026-11-03-native-graphs.md

## Global Constraints

- Cfg/Cg/Cdg/Ddg/Pdg/Sdg/Dfg，单图2MiB／总8MiB／30秒；无自动重试。
- 原SVG字节与原始响应／源码绑定，前端只用img，同源路由CSP sandbox。
- 保留旧Cg、旧记录、JSON与行号切片；profile7不借用旧profile6缓存。
- DeepSeek0；真实MCP最多一份自建源的一次完整分析；不测试主运行库，不Git写入。

## Review Focus

- 图类错配或同类冲突地址不得显示别的图；Task1负控。
- 七份大图累计下载和缓慢响应必须有总预算；Task1流式／时限负控。
- 原件或路径／源码绑定变化必须拒绝下载；Task1服务／路由篡改负控。
- 旧缓存请求幂等保持，新结果不得复用旧profile；Task1兼容测试。
- 异步图片晚到、源码切换、缩放／全屏和移动端宽度不能显示旧图或产生内部滚动条；Task2状态与浏览器检查。

### Task1: 原生七类图及证据接口

**Files:** 新native_graphs.py、test_native_graphs.py；改client/service/cache/routes/repair/demo.app。
**Interfaces:** client returns native_graphs={schema_version:1,graphs:{kind:metadata}}, private _native_graph_bytes map; service.native_graph_bytes(id,kind,actor_id)验证并返回bytes；GET .../graphs/<kind>.svg兼容同会话／修复／影响分析来源。

- [x] RED：七类真实字节、缺图独立失败、冲突／外域／实体／大小／超时／凭据、原件篡改／来源错配、导出、旧Cg及缓存幂等。
- [x] 实现上述固定schema和有界获取／持久化／复核；原始JSON不改变语义，profile7。
- [x] GREEN：tests/analysis及相关缓存／桥接／影响回归；保留RED日志。

### Task2: 整行原生图界面

**Files:** 新native-graphs.js及native-graphs.test.cjs；改analysis.js/demo.html/demo.css/deployment-files.json。
**Interfaces:** NativeGraphUI.mount({select}) -> {render(report,kind),zoom(delta),fit(),fullscreen()}；工具SVG只在img中使用，通过view_url/download_url访问。

- [x] RED：7种类型、旧Cg／缺图、非法URL、选图与源码版本、全图尺寸／缩放；运行原analysis交互回归。
- [x] 实现七按钮、整行画布、fit及拖拽／全屏／下载，保留源码行／变量／point模式；清除旧图并保护晚到事件。
- [x] GREEN：全部Node与页面／分析Python测试，独立预览视觉检查。

### Task3: 实测、一次审阅、合入重启

- [x] 一次自建仓颉源真实MCP分析，保存实际七类SVG状态／原件／HTTP测试；不执行DeepSeek。
- [x] 一次整体独立只读审阅；作者集中修正重要项并验证，不重新分派审阅。
- [x] 核对基线哈希后仅合入相关文件；空闲审计、正常停止旧服务、在cangjie_cup重启，前后原任务／记录／会话一致；浏览器／HTTP确认新资产。
- [x] 更新实际结果、源路径、已知限制和用户测试入口，保留所有失败。用户未要求Git，不进行提交／推送。
