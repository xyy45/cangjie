# 独立成员复现回执（待实际执行）

请由未参与本机实施的成员按runbook从源码快照建立干净配置，不复用本机.runtime运行记录。此文件是回执模板，不是通过证明。

- 执行人：待填写
- 主机与系统：待填写（当前已验证环境仅macOS ARM64 + macOS15.4开发SDK）
- 源码commit／ZIP SHA256：待填写
- Python／Cangjie／stdx版本：待填写
- doctor、离线与SDK测试实际输出路径：待填写
- LIVE task_id／模型实际ID／耗时／候选数：待填写
- 11项测试结果、Policy D拒绝与保护文件不变：待填写
- 浏览器接受后下载包SHA256，与manifest核对结果：待填写
- 问题与处理：待填写
- 执行日期与确认：待填写

使用各自获准的模型配置；不要把API Key写进回执、聊天或源码包。完成后提供实际回执与脱敏输出，不能只将复现复选框改为完成。

## 从交付包独立启动

1. 用 `shasum -a 256` 对照 `release-manifest.json` 核对源码、视频和修复包。将源码ZIP解压到自己的新目录，不复制开发者的 `.runtime`、`.venv` 或 `.env`。
2. 确认macOS ARM64、Python 3.12+以及 `/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`。其他系统或仅有SDK26.5时停止，记录环境差异；不要改用模拟结果。
3. 按runbook“环境”执行创建虚拟环境、安装锁定依赖、官方运行时安装、原生Policy编译和doctor，再分别运行离线与SDK测试，保留实际日志。运行时需要网络下载，摘要由安装器核对；缺系统SDK须先解决系统开发环境。
4. 复制 `.env.example` 为 `.env`，填写自己的获准API配置；源码ZIP不含 `.git`，先确认 `.gitignore` 中包含 `.env` 排除规则；若已自行初始化Git，再用 `git check-ignore .env` 验证排除。避免上传密钥。配置变量是 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL。按runbook启动服务。
5. 启动后，按runbook在自己的可信终端读取本机生成的.operator-key，仅输入自己的授权页；不复制开发机凭据，不交给模型。新会话未配对时任务/审批/导出均403，配对后才能操作，重启要求重新配对。随后运行已获费用授权的LIVE测试，或在浏览器完成A案例。必须看到实际模型调用成功、同一候选build PASS及11项测试通过后再接受下载；核对归档manifest。遇余额、权限、SDK错误停止并记录，不能以离线测试替代。
6. 执行页面D保护探针，保存Deny原因、写动作0与冻结文件未变证据。刷新确认已接受的下载仍能恢复。
7. 填写上方回执，并交回脱敏日志、实际运行ID、截图和下载包摘要。不要手动套用开发机运行ID。若任一步不符，明确标记FAIL/BLOCKED及原因，不勾选通过。

三次付费复演不是每次启动的必要条件；需验证稳定复演时再按runbook执行 `scripts/rehearse.py`。独立复现完成后，由队长另行处理赛事平台、准确截止时刻、提交和回下载核对。

## V1.1 附加核查

- 核实版本及V1.1进度账本；旧V1技术交付包仍是历史版本，不能按名字视为新版已验收。
- 首次安装必须重新执行`python scripts/build_policy.py`，生成匹配源码/编译器的本机Policy构建记录。只复制旧二进制不足以通过预检。
- 检查需求卡确认、历史读取、旧候选不可审批、拒绝后不可导出、取消后不继续执行；这些操作不得暗中调用模型。
- 验证新下载包的`project/`和`evidence/`分区；按manifest逐文件核对，并记录外部导出回执中的ZIP SHA256。
- 停止本成员自己的服务后再重启，确认候选和检查保留、未完成操作显示BLOCKED/IN_DOUBT、启动不新增模型调用；不要根据不明PID清理其他成员进程。
- 核对固定来源、许可和实际复用范围，见`docs/v1.1/m1-dispatch-acceptance.md`及`docs/third-party/sympas/`。页面确认后创建应POST `/agents/runs`，任务runtime_binding记录固定base_commit/adapter_sha256，出现一次SYMPAS_RUN_QUEUED/STARTED/FINISHED；分派完成后业务状态仍须等待真实检查和人工批准，不等于已交付。外部成员复现、赛事平台、正式提交继续PENDING，需真实回执。


## 无密钥阶段与费用授权

可以先在没有`.env`和真实API Key的源码目录执行离线及显式SDK测试。SDK中的脚本化生成/手写提案会明确标注，不能填写为LIVE成功；真实MCP/Policy/cjpm与接入机制仍应实际验证。当前开发机测试计数为离线144、SDK/HTTP11、Node15，成员需保存自己的输出及任何差异。普通启动不会自动请求模型。只有本人/团队获得费用授权后，才按第5步运行真实模型或点击开始；不要把三次付费复演当作安装必做步骤。

技术包的历史LIVE和当前执行器重新验证项目只能作为开发证据，不能复制其运行库、批准或操作者凭据作为自己的通过记录。独立复现执行人及外部回执仍待实际填写。
