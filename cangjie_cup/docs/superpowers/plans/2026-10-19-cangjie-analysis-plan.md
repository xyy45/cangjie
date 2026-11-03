# Cangjie Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 本地样例和上传.cj经真实课题组MCP，前端呈现源码绑定的切片、DDG与结构观察。

**Architecture:** 在现有Flask内增加独立分析服务与SQLite索引，不修改修复控制器。服务端固定工具、限额和地址；JSON标准化后由原生SVG绘制真实节点/边。

**Tech Stack:** Python3.12/Flask/httpx/SQLite，原生JavaScript/CSS/SVG；无新框架。

**Spec:** docs/superpowers/specs/2026-10-19-cangjie-analysis-design.md

## Global Constraints

- 上传仅UTF-8 .cj，64KiB/1000行；不执行上传代码、不传模型密钥。
- 三工具各一次，45秒/HTTP、2MiB/响应、并发1，不自动重试。
- 原修复、审批和导出接口保持；所有新写接口沿用配对/CSRF/所有权。
- 历史/缓存明确标记，上传不能回退样例；源码与证据摘要绑定。

## Review Focus

- 外层success伴随内部失败，必须分工具识别。
- 节点/边/行号与源文件不匹配，不渲染有效结果。
- 上传文件名、编码、大小、JSON和图标签均不作为命令/HTML。
- 迟到响应和重复请求不得污染其他文件或重复远端调用。
- 重启、超时和远端不可达不自动重放或伪造结果。

## Tasks

- [x] 1. 写标准化与上传边界测试，观察失败；实现解析、输入约束和固定远端客户端；MockTransport验证真实HTTP合同与失败边界。
- [x] 2. 写持久化/接口/并发测试，观察失败；实现分析服务、样例登记、后台任务、证据ZIP与路由。
- [x] 3. 调当前服务只读目录并按实际合同调用受控本地样例，保存输入与原始输出，验证非空切片和DDG及内部失败处理。
- [x] 4. 写前端状态/图关系测试，观察失败；增加分析视图、切片高亮、可选择节点和工具证据，保留既有工作台。
- [x] 5. 验证固定样例之后，实际上传不同.cj并核对新输出；浏览器验证操作/失败/重载，运行相关及全量回归。
- [x] 6. 独立只读审查，修复发现问题并回归；更新演示文档、截图、源码ZIP及秘密排除校验，逐条完成审计。

本目录不是Git仓库，不创建伪造提交。执行命令和结果记录在docs/demo/analysis-verification.md。

## 完成记录

六项均已完成。初始25项协议/输入测试、服务及路由测试、实际样例9次调用、真实浏览器上传与重分析、独立审查修复及最终237项Python/35项Node的结果见docs/demo/analysis-verification.md。用户确认属于同一任务的持续授权，未在普通步骤间再次要求确认。
