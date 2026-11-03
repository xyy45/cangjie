# 第5项部署与复现：现状与缺口

更新于2026-11-03。隔离锁定依赖安装及从原始归档重新安装SDK／构建core已通过；4D仍在最终回归与独立审阅阶段，本记录不代表4D已验收，也不代表第5项已交付。主站没有切换，原开发Python环境和依赖未修改。

本阶段要求来自[后续能力提升开发目标](../后续能力提升开发目标.md)第5项。现有代码、命令输出和已保存的实际环境记录为依据；历史运行手册中的旧主机路径与版本不能直接用于当前复现。

后续产品实施见[部署设计](../superpowers/specs/2026-11-03-deployment-reproduction-design.md)及[四任务计划](../superpowers/plans/2026-11-03-deployment-reproduction.md)。自检、诊断／程序包、SQLite实测与完整复现尚未因计划文档而计为完成。

## 当前交付能力与缺口

| 需求 | 当前实现与证据 | 仍需完成的验收 |
| --- | --- | --- |
| 记录并对齐Python／依赖组合 | 原开发环境有25项版本与锁文件不同；新Python3.12.4隔离环境已离线解算并安装原锁文件全部40项，安装版本／wheel摘要一致，`pip check`退出0；152项契约测试及4项真实本地MCP stdio测试通过 | 原锁文件暂不改动；需在该组合完成完整应用部署闭环，不能将156项专项验证称为全量兼容验收 |
| 固定仓颉SDK与stdx | 固定SDK1.0.5及stdx1.0.5.1归档先按原项目摘要核验，再复制到独立目录缓存，由原安装脚本真实解包；安装退出0，SDK／stdx根均非已有目录链接 | 需从最终交付内容复现；本次使用缓存原始归档，不证明当前官方网络下载可用。MacOSX15.4开发SDK仍为宿主已有依赖 |
| 核心构建身份 | 在新安装SDK中重新编译core2退出0，源码／编译器／二进制摘要自有记录；真实IPC完成边界轴、允许和越界拒绝3项调用 | 新二进制摘要不复用旧批准；仍需在完整应用上传／修复／审阅／交付中验证该构建身份 |
| 启动与端口处理 | `python -m nexus.demo.app`默认8877、loopback、DeepSeek；支持`--port`和`--provider`，数据根固定为应用内`.runtime/demo-workbench` | 验证缺少配置、依赖、SDK／core、端口被占用时的退出与诊断；记录实际启动命令和受支持场景 |
| 单写者与正常重启 | `RuntimeOwner`以OS flock为所有权依据，PID仅提供信息；持有锁后重启核对旧任务，保守记BLOCKED／IN_DOUBT，不自动续跑 | 从交付包完成停止／重启与未知操作控制，确认会话归属及历史材料保留；不能通过修改运行库伪造恢复成功 |
| 本机自检 | 原doctor直接入口失败保留。部署独立副本已实现JSON分项检查、完整锁版本、工具／core／固定开发SDK、配置存在性和端口检查；直接／module退出0／1／2一致，新22项及组合44项／旧接口5项通过 | 未传播到当前应用／8877；仍需诊断／程序包集成及最终干净环境验证。旧`inspect_environment()`接口未改，UNKNOWN非通过 |
| 诊断包 | 未找到独立诊断包命令。当前doctor JSON不是完整诊断包 | 提供有明确字段／文件范围的诊断交付物；不含`.env`、密钥、用户源码／上传、模型请求响应、运行数据库或浏览器会话 |
| 可运行程序包 | 现有源码和运行说明可供开发；当前源码快照／证据ZIP服务于阶段验证 | 制作有明确输入清单及摘要的运行包和配置模板，从包安装启动；不能直接打包开发工作区或运行数据 |
| 完整复现流程 | 4D隔离浏览器与SDK闭环已有阶段证据；当前完整回归仍在运行 | 在明确的干净安装组合执行安装→构建core→启动→上传→分析／修复验证→审阅／归档，并保存退出状态及实际下载摘要。模型／分析夹具与真实外部调用分开记录 |
| 大原件与SQLite并发 | 先前一次Sequence纯校验的cProfile记录24.18秒，伴有并行回归负载，不是当前服务延迟基线 | 测量真实大原件校验时SQLite锁持有、另一连接等待及请求耗时；完成测量后再决定优化，不承诺尚未测量的容量或延迟 |

Demo入口直接使用本机会话，不要求操作者配对；`nexus.web.app`是另一个保留操作者授权的入口。部署文档必须区分这两个入口，避免把旧工作台配对流程写成默认Demo运行步骤。当前也没有`--runtime-dir`参数，不能在命令示例中杜撰该选项。

## 依赖下载预检的实际结论

最初的pip官方源探针在TLS连接阶段失败，不能据此认定锁定版本不存在。系统HTTPS客户端访问同一索引返回200，部分文件能够下载并匹配官方PyPI元数据摘要。一次指定IPv4的annotated-types下载控制成功，后续完整下载尝试仍出现传输超时，未放宽TLS校验。

初始预检取得4份校验通过的完整包。后续certifi的正常TLS断点续传返回206，完整136983字节匹配发布摘要；在该控制依据上进行的有界串行下载批次取得16份完整包，24项因网络超时／重置未完成，结果为PARTIAL。这是保留的早期结果，后续未删除部分文件或改写失败。

随后按[TUNA官方PyPI镜像说明](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)使用HTTPS镜像传输同版本wheel，仍以官方PyPI所选文件的大小及SHA-256认证。最终40份wheel全部校验通过，共10682196字节；没有放宽TLS、替换版本或使用源码包。元数据来源保留区分：原始HTTPS JSON与6份经web工具读取官方JSON后形成的派生文件描述符不能互称原始响应。

新Python3.12.4环境的安装前基线确认`include-system-site-packages=false`、仅含pip24.0、不能导入Pydantic或MCP。随后使用`--no-index --only-binary=:all: --require-hashes --no-cache-dir`先解算、再从已校验本地wheel安装，两个步骤均退出0。全部40项安装版本与原`requirements.lock`一致，包括Pydantic2.12.5、MCP1.26.0；安装报告只含本地文件来源，`pip check`无破损依赖。未复制site-packages，也未改变原开发环境。152项契约／解析与4项真实本地MCP stdio专项通过；它们不替代完整应用部署验收。

依赖离线材料v2包含40份wheel、带摘要的锁、来源记录和校验清单，共44个文件，ZIP摘要`85154837a26f593a5e5a107b3ec0775bdfbbeaf1cb59d1ca81a786e5972194db`。v2只修正首份说明里遗漏`install`子命令的错误；首份原件保留，wheel和锁逐字不变。该ZIP不是完整可运行程序包。

## 从原始归档安装SDK与重新构建

固定归档来源为原工程缓存，按当前安装脚本中的预设摘要重新核验：SDK归档186714867字节、SHA-256 `e07d22584237f065b30a771b7110a87a8931334c40be3a148090944ae916ed1f`；stdx归档6852742字节、SHA-256 `202b91110996c60de35f2dc07c278bc19a08df2029dc3376710c9f3e84121e7b`。新目录中的原安装脚本完成真实解包，未复制已有SDK树或将其符号链接进新目录。

当前408文件产品源码封存不包含全部未改动脚本，第一次准备在安装前因缺少`install_runtime.py`失败。该目录和失败记录保留；新独立尝试从2302输入执行快照补入原安装／构建／doctor三个脚本，分别核对摘要，不修改源快照。安装2.086秒、core重新构建3.333秒、module doctor1.306秒均退出0；408产品文件和3个补充脚本未改变，源归档也未改变。

新core源码摘要`d2629c31b029f3152d1da91c72b8333d59a71f0df5d3411ba3e6e79713bf1790`，编译器摘要`f65a65c20cb570e15185b04376a19fba00581efd477665d31ed5cc47fb58f1f7`，二进制摘要`0e08b05f081b26a36a76d92fa79c3c97afc0b028b15b9bb8fdf2e05d8bc279cc`。新核心真实完成边界轴、合法范围Allow、越界OUTSIDE_SCOPE拒绝3项IPC调用；证明与该构建身份绑定，没有继承旧组件批准。

以上是同一macOS ARM64宿主上的隔离安装／重新构建，仍使用宿主MacOSX15.4开发SDK；不是另一台全新机器安装、官方SDK下载连通或完整应用交付验收。未启动新应用、未改变8877、未读取原运行数据或模型密钥。

上述原始记录位于仓库根`.superpowers/sdd/2026-10-30-bounded-packages/`：

- `task7-deployment5-environment-preflight.json`、`task7-deployment5-pip-check.txt`。
- `deployment5-lock-probe.txt`、`deployment5-pypi-curl-head.txt`、`deployment5-ipv4-control.json`。
- `deployment5-download-preflight-result.json`、两次有界下载日志，以及完整／部分下载文件。
- `deployment5-range-control.json`、`deployment5-declared-lock-wheelhouse/manifest-range-attempt3.json`及对应第三批下载日志。
- `deployment5-clean-venv-baseline.json`、空环境bootstrap记录，证明安装前隔离基线。
- `deployment5-declared-lock-wheelhouse/manifest-mirror-retry1-complete.json`、派生元数据及HTTPS控制记录，证明40份完整wheel来源与摘要。
- `deployment5-declared-hashed-requirements.txt`、解算／安装报告、`deployment5-install-binding.json`和`deployment5-clean-installed-versions.json`，证明原40项锁安装；`deployment5-locked-contracts.txt`及`deployment5-locked-stdio.txt`为专项结果。
- `deployment5-python-dependencies-macos-arm64-v2.zip`、`deployment5-dependency-bundle-v2-verification.json`；首份错误说明材料保留。
- `deployment5-clean-doctor-cli.txt`为清除隐式路径后的直接脚本失败，`deployment5-clean-doctor-module.txt`为旧链接SDK的module探测；两者不能代替后续新SDK构建。
- `deployment5-fresh-sdk-initial-preparation-failure.json`保留首次缺脚本准备失败；`deployment5-fresh-sdk-retry1-result.json`及安装／构建／doctor日志绑定新目录与归档。
- `deployment5-fresh-sdk-native-ipc.json`及日志为新core的3项真实IPC验证。

## 运行材料的边界

- 当前受支持的验收目标为macOS ARM64及固定仓颉工具链；Linux／Windows另行验收。
- `.runtime`中的SDK、core构建产物、工作数据和本机会话属于不同材料，不能把整个目录复制进发布包。干净安装需要明确的工具来源和新构建记录。
- SDK版本探测或模型配置字段非空，不等于成功构建、可用模型API或可用MCP语义分析。
- 新增付费模型调用仍需单独的数量预算；当前预检调用数为0。离线复现可验证本地链路，必须明确外部响应是否使用夹具。
- 不在现有8877主站中执行测试；主站切换仍受4D最终验收与空闲审计门槛约束。

## 自检Task1的隔离实施

开发副本为仓库根`.superpowers/sdd/2026-11-03-deployment-reproduction/app`。从4D已冻结执行输入逐字复制，不包含运行库；开发期明确链接新安装SDK并使用其新core，不冒称最终交付安装。仅修改doctor的CLI入口并新增检查模块与测试，现有readiness使用的`inspect_environment()`函数体保持原样。当前实际应用目录的doctor仍为旧入口，不能把独立实现描述成主站已更新。

RED为缺少新模块；默认沙箱首次执行因不允许绑定回环端口产生2失败／4通过／16设置错误，保留日志。源代码不变，在获准的专项执行环境中22项全部通过（2.85秒）；新增与页面／配置／OS所有权／SIGKILL恢复组合44项通过（7.28秒），旧doctor／readiness5项通过（1.04秒）。实际子进程验证无PYTHONPATH时直接与module输出一致、rule无模型配置退出0、deepseek缺配置退出1、非法端口退出2、占用端口退出1；不发送任何网络模型请求。

2301文件开发快照摘要`84968884598978c2ab8bfb74237479490250a7573821b1b24c72cd62eea5c5eb`，对应`task1-source.zip`／`task1-source-freeze.json`及`task1-verification.json`位于该部署阶段目录。仍待Task2诊断／运行包、Task3并发测量、Task4完整复现与独立阶段审阅；后续4D若有修正，必须先合入并核对版本，再进行第5项最终验收。

## 已定位的文档差异

`docs/runbook.md`保留了Python3.12.14、旧用户绝对路径和历史工作台描述；本次实际Python为3.12.4，默认演示入口也已不同。第5项完成时需根据实际安装验证重写相关章节，并保留历史LIVE／SDK证据的版本归属，不能把它们转换成新环境通过证明。

已有重启控制测试包括`tests/test_ownership.py`和`tests/integration/test_rule_draft_recovery.py`。它们覆盖原有行为，本次只核对代码和测试范围，没有据此宣称新的干净环境或完整部署验收已通过。
