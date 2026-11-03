# 演示服务免配对验证

日期：2026-10-20。用户已确认删除演示服务的操作者配对，打开页面即可使用。

## 修改

- 移除演示页面右上角钥匙按钮、配对弹窗、密钥提交、修复启动门禁和源码分析配对门禁。
- 演示工厂显式使用 `require_operator=False`，不注册配对接口；启动时不再生成或读取 `.operator-key`。
- 本地 GET 自动初始化签名浏览器会话的 CSRF 与 actor_id。上传分析仍按浏览器会话归属，重启保留签名密钥时可以恢复。
- 保留 localhost／Host／Origin 检查、CSRF、只读实例拒绝写入、候选单写者、当前检查集与人工接受／导出绑定。CEGIS 循环保持原行为。
- 默认底座工厂仍要求操作者配对。其鉴权测试继续适用于默认底座；演示服务对本机请求不再区分操作者，本机进程也可建立自己的免配对会话。

## 验证

- 定向 Python：82 passed，覆盖无需配对即可创建需求／分析、无会话读取、重启、CSRF、localhost、只读锁和原分析恢复功能。
- 前端 Node：47 passed，新增首次打开直接启动测试；轮次切换、取消等原测试继续通过。
- 完整非付费 Python 回归：275 passed、1 deselected，251.09 秒，见 [输出](validation/direct-access-python-full.txt)。包含真实固定 SDK／MCP；旧底座原生鉴权测试第一次在外层受限沙箱因无法绑定本地测试端口失败，完整回归使用本机原生权限，未放宽执行器。
- 会话检查：未配对上传记录创建成功（停留 READY，未向外发送）；重启后原 cookie 可恢复（200），其他浏览器会话不可读取（404）；配对接口返回 404，新演示实例不生成操作者密钥。见 [脱敏记录](validation/direct-access-session.json)。
- 浏览器：服务重启后页面无配对按钮，直接开始“测试保护拦截”；真实原生返回 `Deny / PROTECTED_PATH`，工具动作未执行，基线未变化、候选写入为零。任务 `0f1c18f3d960487c96c0b1b7091f94c3`，模型请求为零。见 [记录](validation/direct-access-browser.json) 和 [截图](direct-access.png)。
- 独立只读审查：未发现重要的非预期回归；核对默认底座鉴权、会话初始化、CSRF、运行所有权、分析会话隔离及候选接受／交付绑定。

复核命令（项目目录）：

```bash
python3 -m pytest tests -m 'not live' -q --tb=short
node --test tests/*.test.cjs
```

无需再次配置或输入配对密钥；启动仍使用 `启动演示.command` 或 `python3 -m nexus.demo.app --port 8877`。本次验证没有新增付费模型请求，也没有接受或导出原真实模型候选。
