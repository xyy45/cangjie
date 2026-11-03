# CangSight-Nexus 中文技术交付报告

交付日期：2026-10-17。正式工程为本仓库。Task 1～9 技术开发及 Task 10 可自主执行部分已完成；**比赛正式提交尚未完成**。独立成员复现、平台确认、正式提交及平台回下载均为 PENDING，不以本机测试替代。

## 交付内容

已实现真实 MCP stdio Client/Server、九项工具、仓颉原生三态 Policy、受限 cjpm 构建测试、DeepSeek MCP-CEGIS 修复、候选审阅接受与归档导出、单页工作台。源代码、测试和环境说明都在源码快照内。源码版本、各交付件 SHA256 及大小由技术交付包内 `release-manifest.json` 固定。

原始 Sympas-Nexus 的 453 个文件最终逐项核对未变。产品仅写入新工程，模型只能修改登记案例允许的已有源码，测试和配置受到保护。`.env` 自动从正式工程根加载，已有环境变量优先；实际密钥不输出、不跟踪、不打包。

## 真实验收结果

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 最小 DeepSeek 连接 | HTTP 200，实际模型 deepseek-flash，9 tokens | evidence/deepseek-connectivity.json |
| 最终离线回归 | 53 passed，5 deselected（SDK/LIVE另测） | evidence/final-offline.txt |
| SDK／完整工具链集成 | 4 passed，23.70秒 | evidence/final-sdk.txt |
| Task 7 LIVE | 1 passed，9.16秒；首候选真实构建通过、11项测试通过；已接受导出 | evidence/task-07-live-configured.txt、task-07-live-delivered.json |
| 三次连续 LIVE 复演 | 全部 DELIVERED，8.981／8.934／8.456秒；各首候选、11项测试通过 | evidence/task-10-live-rehearsals.json |
| 浏览器 A 主案例 | 实际生成、审阅、接受、下载；下载字节与服务归档一致 | evidence/recorded-browser-download.json、workbench-live-delivered.jpg |
| 浏览器 D 权限拒绝 | 原生 Policy Deny / PROTECTED_PATH；写动作0，冻结文件不变 | evidence/workbench-live-policy.jpg |
| 原工程保护 | 453文件未变，无新增 | evidence/original-source-final-recheck.json |

LIVE 由实际 DeepSeek 返回候选，MCP、Policy、cjpm 均实际执行。确定性测试只用于验证失败反馈、协议和竞态边界，不当作模型 LIVE 成功。历史缺配置 BLOCKED 和一次系统 exit 9 保留；最新通过结果不抹除这些限制。

## 演示与复现

技术交付包包含源码 ZIP、真实修复工程 ZIP、操作视频、本文、启动说明、测试报告、独立复现指南和验收审计。视频为 227 帧实际浏览器采集剪辑，25.796秒、无音轨，长等待已缩短；不是未剪辑连续录屏。视频中的导出候选树摘要为 `8c4ffd1468cc61ba21db8feb5e1a1aecd4e5953ee66becd0c9eb1e4b9685986b`，下载包 SHA256 为 `e26fc1dfdb476ca3502323647e985a02e9a88c3105b44536c3e07bb64e3389a0`。

其他成员从源码包按 `runbook.md` 和 `independent-reproduction.md` 建立自己的环境与密钥，保留真实输出和回执。验证范围是 macOS ARM64、Python 3.12.14、Cangjie 1.0.5、stdx 1.0.5.1、macOS 15.4 开发 SDK；其他系统尚未验证。安装器校验官方运行时摘要，运行时和系统 SDK 不随源码包分发。

## 适用边界与待办

这是受控订单案例的固定修复工作流，不能据此声称任意仓颉工程都可修复。B/C 可选案例、课题组语义分析未准入。Policy 不替代 OS 沙箱；cjpm 单测需要本机 TCP。服务只用于本机演示。

- [x] Task 1～9 实现与本机验收证据
- [x] 最终回归、A/D、三次真实复演、操作视频
- [x] 当前源码快照、版本固定、交付包和敏感信息检查
- [ ] PENDING：另一名团队成员独立复现并提供实际回执
- [ ] PENDING：队长确认比赛平台、入口和准确截止时刻
- [ ] PENDING：比赛正式提交、平台回下载和材料摘要核对

目前只确认截止日期为 **2026-10-23**，具体时刻未知。当前固定版本是2026-10-17技术交付候选，不冒充后续10/22团队冻结或正式提交的证明。技术材料已就绪，外部验收完成后才能宣告整体比赛交付完成。
