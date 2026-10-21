# CangSight-Nexus 本机启动与复现

V1.1历史版本已通过一次授权LIVE任务及独立标注的D探针；后续Native审批/执行安全补充不冒充新的LIVE验收。M1最小网关/分派核心已接通；外部复现/正式提交仍待办。当前页面先“准备需求”，显示冻结业务约定，用户再“确认需求并开始修复”；新任务必须绑定确认需求和验证计划。页面确认后的创建请求经指定来源的/agents/runs派生网关，基座分派器调用现有RepairLoop；RuntimeBinding记录固定上游commit和适配代码摘要。详情见docs/v1.1/m1-dispatch-acceptance.md。下文的LIVE成功和三次复演是V1历史证据，当前版实际验收状态见docs/v1.1/validation-report.md，不能把旧证据当作V1.1完成证明。

当前受控仓颉主案例已经真实 LIVE 修复、页面接受下载及连续三次完整复演验证；独立成员复现与赛事提交仍待外部验收。仅支持登记自产工程；不要上传或执行任意来源工程。所有源码位于本仓库，原始 Sympas-Nexus 不改写。

## 环境

已验证主机为 macOS ARM64、Python 3.12.14、Cangjie 1.0.5 LTS、stdx 1.0.5.1、macOS Command Line Tools SDK 15.4。默认 macOS SDK 26.5 与此仓颉链接器不兼容，不能只按 doctor 的可执行文件存在性宣称构建可用。其他平台还未验证，不能把这里的命令当作 Windows/Linux 已支持。

在工程根执行，先确认 Python 3.12+（系统 Python 3.9 不满足）。默认离线回归还需要 Git 命令（验证真实仓库排除规则）和 Node.js 18+（运行原生 JS 的异步竞态测试，无需 npm 依赖）；源码发布目录本身不需要 `.git`：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python scripts/install_runtime.py
python scripts/build_policy.py
python scripts/doctor.py
python -m pytest tests -m 'not sdk and not live' -q
python -m pytest tests/sdk tests/integration/test_full_journey.py -q
```

本机 Python 可用路径：`/Users/jadya/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。当前已创建 `.venv`，可直接 `source .venv/bin/activate`。依赖版本在 requirements.lock 固定。install_runtime 仅从官方 SDK/扩展库发布地址下载到本工程 `.runtime`，验证固定 SHA256；不执行下载的 shell 安装器。macOS15.4 系统开发 SDK 必须已安装在 `/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`。缺少则停止并处理系统开发环境，不换成模拟编译。

## 配置与运行

将 `.env.example` 复制为 `.env`，在本机填写 DeepSeek 密钥、实际可用模型 ID 和服务 base URL。不要把密钥发到聊天或放进源码、日志、提交与交付包。`.env` 已被 Git 排除。Provider 自动读取正式工程根目录 `.env`，不依赖启动时的当前目录；已有进程环境变量优先（override=False）。首次配置完成后可开始新任务；修改已加载的配置后请重启本机服务，避免进程保留旧值。配置加载测试不调用API，`.env`已通过Git排除和未跟踪核查。Provider 只支持 HTTPS，HTTP 请求不自动重试，拒绝被截断的候选。单次最多 20,000 output tokens，接口不支持会报错，最多三候选／任务 8 分钟。

```bash
python -m nexus.web.app
```

浏览器打开 <http://127.0.0.1:8765>。首次打开或服务重启后，先授权本机操作者。请在可信本机终端读取：

```bash
cat .runtime/workbench/.operator-key
```

只将结果输入本机授权页，不贴入聊天、模型、截图、源码或日志。该文件由持有运行库锁的启动进程随机生成，权限必须为0600；读取时拒绝符号链接、非普通文件和过宽权限。它与DeepSeek API Key不同，不从.env读取，不交给候选。配对只授权当前浏览器会话，重启后需要重新配对；凭据不进入浏览器localStorage。若泄露，先停止自己的服务，在可信终端处理凭据文件后重启生成新值，不通过网页或模型自动重置。未配对会话不能读取任务、候选或下载，不能准备任务、批准或导出；只读实例即使配对也不能执行写动作。

Flask 开发服务只用于当前本机演示，不做公网部署。选择订单边界缺陷案例，填写业务目标，先点击“准备需求”，核对需求卡后点击“确认需求并开始修复”；缺模型配置将如实显示“运行受阻”。刷新仅恢复现有任务。检查候选 diff 与构建/测试结果，全部必需检查通过后“接受并导出”，再点击下载。

LIVE 验证会发送自产源码和诊断到已配置 DeepSeek，并产生真实 API 费用：

```bash
python -m pytest tests/live -q
```

成功标准是 REVIEW_PENDING、LIVE SUCCEEDED ModelCall，以及同候选真实 build/test PASS。没有配置时此层明确失败/BLOCKED，不 skip，也不计入通过数。当前手写候选集成测试只证明 MCP/SDK/Policy/接受导出链，不证明模型修复成功。

## 状态与证据

- `.runtime/workbench/runs.sqlite3`、`records/`：本机页面任务、请求响应、检查日志、diff、policy 事件。
- `.runtime/live/<运行ID>/`：显式 LIVE 测试证据。
- `docs/evidence/`：已保存的开发 RED/GREEN、SDK 输出和 UI 截图；历史结果与当前运行分开。
- `docs/progress.md`：逐任务范围与尚未完成项。
- `docs/delivery-plan.md`：原附件的原文副本，验收以该计划为准，里面的原始状态文字不代表当前实施进度。

检查状态 PASS / FAIL / UNKNOWN / NOT_RUN 分开。零测试、跳过、不完整日志、环境异常不能 PASS。源码、测试、配置改变使旧检查或接受失效；导出归档读取时再次验证 manifest。接受默认30分钟有效；并发导出同一接受记录只占用一个导出 ID。打包故障保留 FAILED，再次使用同一接受 ID 对账。进程异常中断后保留 IN_DOUBT/在途信息，由操作者核查；不提供通用自动恢复。

## 执行边界和故障处理

Native执行由macOS sandbox-exec限制工程外写、用户目录/运行库控制数据读、外网出站及向无关进程发信号；候选stdin为/dev/null，额外文件描述符关闭。SDK 测试框架需要动态 TCP 监听和本机回环连接，所以不能把它称作网络完全隔离。候选目录本身不是安全沙箱，不宣称任意仓颉程序的完整安全隔离。不要在本机运行非登记工程。测试和配置在模型编辑范围外；cjpm 因文件打开方式需要 toml/lock 的写权限，执行后完整树摘要必须保持一致。每请求90秒、输出2MiB，超限 UNKNOWN，清理进程组。测试内部先实际运行`cjpm test --no-run`，冻结测试可执行文件后实际运行`cjpm test --skip-build`，共享上述预算；具体实际命令在检查报告`execution_argv`中。仅固定编译工具和已冻结测试程序可执行，不放行整个SDK目录或可写target目录，直接shell、复制程序和SDK调试器执行拒绝。细节及未验证边界见docs/v1.1/native-execution-staging.md。

模型 HTTP 故障、未知付费调用或 MCP 在途写断连不自动重放；先查看本任务原始记录。Policy 不可用或无效响应时停止，不旁路。可选课题组仓颉分析未启用，不影响真实 cjpm 主线，也不显示虚构分析结果。

第三人成员需要独立按上述步骤复现并记录主机、版本、运行ID、下载包摘要与结果；目前该外部复现未进行。已制作当前应用版本的实际页面操作视频（帧采集剪辑，长等待缩短），版本和摘要见交付报告；赛事提交与回下载仍需实际平台证据。


## 三次真实复演

```bash
python scripts/rehearse.py
```

此命令连续建立三个干净基线任务，每次实际请求已配置模型，通过真实MCP/原生Policy构建与11项测试，执行CLI测试操作者接受、MCP导出和归档核对；产生真实API费用。任一任务不成功即停止，不重放未知付费请求或SDK故障，不强制多轮。结果与全部原始记录在 `.runtime/rehearsals/<会话ID>/`。2026-10-17 的三次实测耗时为8.981/8.934/8.456秒，均首候选交付，证据见 `docs/evidence/task-10-live-rehearsals.json`。

实际浏览器已完成A审阅、导出、下载与摘要核对，并完成D保护探针。原生Policy拒绝修改测试，写动作0、冻结文件不变。主案例通过的是固定受控测试约定，不宣称任意仓颉工程正确性或课题组语义分析已支持。

## V1.1 审阅、交付与中断处理

1. 页面先准备并确认需求，再开始任务；最多三个模型候选，每次输出上限20,000 tokens，整个任务480秒。环境预检只证明本机配置就绪，不证明API连通性。
2. 历史任务下拉框和候选浏览均为读取；浏览旧候选不会把它改成待审阅对象。只有服务端当前选中且检查有效的候选可接受或拒绝。
3. “拒绝修改”记录本地会话身份及可选原因，任务终止，不自动再付费。“取消运行”停止后续步骤，在途写入或模型费用不能撤销；结果不明会明确记录，不能重新点击来假设成功。
4. 接受仅授权`candidate.export`，绑定需求、计划、候选、检查集和本地会话，30分钟到期。双击导出使用同一批准预约的同一export_id。已交付任务不支持原地重新审阅；审批失效或会话丢失时新建任务，不沿用旧批准。
5. V1.1下载包与V1历史包结构不同：从`project/`运行`cjpm build -V`和`cjpm test`；`evidence/`包含实际diff、需求/计划、检查与原始日志、调用记录及批准索引。`manifest.json`核对文件摘要，最终ZIP摘要保存在运行库`export_artifacts`；归档快照中的导出状态为预约，不能伪写尚未发生的完成记录。
6. 原始证据缺失或摘要改变会阻止导出/下载，不用摘要替代原生记录。手写SDK候选归档明确标记无模型调用，不当作LIVE成功。
7. `python -m nexus.web.app`使用运行库OS文件锁确认控制器所有权；无法取得所有权只允许读取，不能根据旧PID盲目杀进程。确认取得锁后，旧READY任务标记BLOCKED，旧活动阶段保守标记IN_DOUBT，并追加CONTROLLER_RESTARTED事件；保留候选/检查，不自动续跑、请求模型、执行补丁或导出。
8. `.runtime/workbench/.session-key`以0600权限保存本机浏览器会话签名密钥，以便正常重启后识别原会话；不要分享运行库、此文件、`.env`或原始用户配置。此身份是本机单用户会话绑定，不是多租户或法定身份认证。新功能部署前的旧临时会话不能伪造为已持久化会话。
9. 工程导入只修改本机副本，规范源码文件0644、源码目录0755；后续读取/验证/导出会核对权限。内容摘要不包含权限，权限单独校验；ZIP中的project文件也固定0644。原始参考目录不被规范化或改写。

V1.1当前真实模型验收状态以`docs/v1.1/implementation-progress.md`为准。不要用历史视频或旧LIVE记录替代当前版本的失败或尚未运行。
