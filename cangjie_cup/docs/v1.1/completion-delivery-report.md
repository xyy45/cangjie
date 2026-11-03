# V1.1 本轮技术复核交付报告

源码提交：6d8784b。本轮未新增付费调用；此前授权的一次LIVE请求已完成，1候选、4313 tokens、金额UNKNOWN。没有自动追加或重试模型请求。

## 已验证结果

| 项目 | 实际命令/证据 | 结果 |
| --- | --- | --- |
| 离线回归 | .venv/bin/pytest tests -m 'not sdk and not live' -q；completion/final-offline.txt | 125 passed、8 deselected，24.38秒 |
| SDK/HTTP | .venv/bin/pytest tests/sdk tests/integration/test_full_journey.py -q；completion/final-sdk.txt | 7 passed，57.61秒，真实cjpm |
| 原LIVE提案重新验证 | .venv/bin/python docs/evidence/v1.1/completion/revalidate-executor.py | DELIVERED，9.768秒；真实MCP/Policy/cjpm、11通过，新测试操作者批准，新增模型请求0 |
| 无Git发布目录 | 无.git/.env/旧数据库的临时解压目录运行同一离线命令 | 125 passed、8 deselected，24.46秒；重新编译Policy，本机解释器和SDK/stdx复用，非外部成员复现 |
| 原始参考 | 453文件SHA256映射逐项对比 | 不变 |
| 归档与敏感排除 | ZIP testzip与嵌套归档逐字节扫描实际配置Key | 完整、未包含.env/.DS_Store、Key无匹配，未打印密钥 |
| 工作台重启 | 无活动任务检查、SQLite备份、GET / | 200，当前范围选择页面已加载；没有发起模型任务 |

修复：范围选择和确认冻结、业务错误码及原始技术原因留证、在途未知/权限拒绝分类、输出目录符号链接保护。修改文件和验收矩阵见completion-audit.md以及提交6d8784b。

## 固定交付

- 技术复核包：/Users/jadya/Documents/CangSight-Workspace/02-开发工程/CangSight-Nexus/.runtime/releases/CangSight-Nexus-v1.1-技术复核包-6d8784b.zip
- SHA256：a8b1d79bda0d906d5d49ea3f8e3d965c6a8403ab02bb4f997e876aaadf0197a2
- 源码ZIP SHA256：8f940c8ad7fcefab3b411ca274aa76fde343ef9dab87ed12c3e241f2f733053d
- 当前执行器重验证完整归档 SHA256：9f4a3f7bddac2d0f5018bdedc930f277d419776a6a564c8c34772194cbd01721
- 外部清单：.runtime/releases/CangSight-Nexus-v1.1-completion-manifest-6d8784b.json。
- 历史32c0034/a20b21f包均保留。视频是历史一次LIVE记录的只读帧回放，非当前实时录屏。

## 尚未满足

M1实际指定基座身份与入口集成PARTIAL；AC-12另一成员独立环境运行和下载PENDING；平台/具体截止时刻确认、比赛正式提交PENDING。当前loopback许可允许候选进程连接本机工作台端口；隔离试验未兼顾真实SDK，已撤回试验规则并保留原始失败证据。这个限制未修复，不宣传任意不可信代码安全执行，也不宣告技术总验收完成。

可以将本包交给成员做登记案例范围的独立技术复核，须先阅读上述边界；不能将本机解压测试或测试操作者批准当作该成员的完成回执。原始一次LIVE仍是真实历史证据，当前源码的模型生成链未做第二次付费LIVE。
