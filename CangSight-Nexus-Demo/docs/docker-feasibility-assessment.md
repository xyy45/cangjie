# Docker 可选隔离执行环境可行性调查

日期：2026-10-18（Asia/Shanghai）。检查源码提交：`5fcc53c42dcf47e7b1eace09b619530f1df37c7b`。

**结论：有条件可行，建议先批准小范围 Linux ARM64 验证，再决定正式集成。当前 Docker 实际执行、隔离验收均为 BLOCKED / NOT_VERIFIED，不能算安全问题已解决。** 本次仅调查；未安装软件、下载 SDK/镜像、启动容器、改变稳定主链或调用付费模型。本机执行方式保留。整个 V1.1 目标仍有 M1、审批接口隔离和外部成员验收缺口。

> 后续用户决定（2026-10-18）：本次 V1.1 暂缓 Docker 集成。下列原型与集成内容保留为调查方案，不是当前待执行任务；未经用户重新明确恢复，不安装运行时、不构建容器、不接入主链。暂缓不表示审批隔离约束被取消。

> 最新范围确认（2026-10-18）：V1.1明确不引入Docker、保留Native、继续修复审批与执行安全。Docker不是开发或验收前提。下文“当前”均指调查时5fcc53c源码快照，安装与D0/D1仅为历史备选方案，不待默认实施；其后Native审批门禁修复及实测见 [Native安全修复报告](v1.1/native-security-fix-report.md)。

## 1. 本机条件与安装选择

实际命令、退出码、完整输出和被检查源码摘要见 [host-and-source-inspection.json](evidence/docker-feasibility/host-and-source-inspection.json)。没有读取或输出 `.env` 内容。

| 检查项 | 当前实际结果 | 判断 |
| --- | --- | --- |
| CPU / 架构 | Apple M5，arm64，10 个逻辑核心 | 优先 `linux/arm64`，避免先引入 AMD64 模拟 |
| 系统 | macOS 26.5，build 25F71 | 符合当前 Docker 文档所述最新及前两个 macOS 主版本范围；具体安装/启动尚未验证 |
| 内存 | 16 GiB；采样 `memory_pressure -Q` 显示 free percentage 44% | 具有试验条件；此指标不是可永久分配内存承诺 |
| 磁盘 | Data 卷可用约 218 GiB | 可容纳试验镜像/VM；尚未测量实际占用 |
| 虚拟化 | `kern.hv_support=1` | 硬件虚拟化支持存在，不等于 VM 已能启动 |
| 容器环境 | PATH 无 docker/podman/colima/limactl/container/qemu-system-aarch64；常见应用、用户 Docker CLI 和两个常见 socket 均不存在 | 未发现可用本机运行时；未连接远程 Docker，也未枚举用户私有配置 |

Docker Desktop 提供 Apple Silicon 安装包，要求至少 4 GB RAM；官方说明 Rosetta 并非严格必需。首次运行需用户同意条款，某些安装设置可能要求管理员权限。本项目拟用原生 ARM64 Linux 镜像，不将 Rosetta 作为前置。[Docker Mac 安装条件](https://docs.docker.com/desktop/setup/install/mac-install/)、[权限说明](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/)。教育/个人使用条件及是否符合实际使用主体，应由安装者按官方条款确认，本报告不代为接受协议。

| 选项 | 待安装组件 | 适用性与限制 |
| --- | --- | --- |
| 首选：Docker Desktop Apple Silicon | Desktop（CLI、Engine/Linux VM）；固定版本与安装器校验信息 | 团队操作较直接；新增 VM、文件共享和 daemon 攻击面，不自动解决应用审批授权 |
| 备选：Colima + Docker CLI | Colima、其 Lima/VM 依赖、Docker CLI，Docker runtime | 官方支持 Apple Silicon；并非只装一个 CLI 即可运行容器；上下文/socket/共享目录需另核验 |
| Podman 等 | 本轮不建议同时引入 | 本轮未核实其项目适配；不以“兼容 Docker”代替具体 API、挂载、限制和生命周期测试 |

Colima 的平台与 Docker runtime 要求见 [Colima 官方仓库](https://github.com/abiosoft/colima)，VM 安装条件见 [Lima 官方安装说明](https://lima-vm.io/docs/installation/)。本轮两种方案均未安装。

试验资源建议（设计值，未经基准验证）：VM 4 CPU / 4 GiB / 30 GiB 磁盘上限起步；单候选串行，容器 2 CPU / 2 GiB、256 PID。内存不足时停止并记录，不能关闭限制换取 PASS。VM 磁盘虚拟容量不等于立即实际占用，也不构成容器写盘配额。

## 2. Linux 仓颉 SDK 的官方支持与未确认部分

[官方 1.0.5 下载页](https://cangjie-lang.cn/download/1.0.5)实际列出：

| 平台 | 官方文件名 | 页面标称大小 | 本轮证据范围 |
| --- | --- | --- | --- |
| Linux ARM64 | `cangjie-sdk-linux-aarch64-1.0.5.tar.gz` | 268.74 MB | 官方发布条目存在；未下载、解压、计算摘要或执行 |
| Linux AMD64 | `cangjie-sdk-linux-x64-1.0.5.tar.gz` | 268.67 MB | 同上；没有验证 Apple Silicon 上模拟执行 |

1.0.5 文档对两种 Linux 架构列出 glibc 2.27、Kernel 4.15 及以上、libstdc++ 6.0.24 及以上，并说明依赖 OpenSSL 3。[1.0.5 安装说明](https://docs.cangjie-lang.cn/docs/1.0.5/dev-guide/source_zh_cn/first_understanding/install.html)。完整功能测试发行版清单含 Ubuntu 18.04/20.04 等；其他发行版需自行验证依赖。[Linux 支持与依赖](https://docs.cangjie-lang.cn/docs/1.0.5/dev-guide/source_zh_cn/Appendix/linux_toolchain_install.html)。

建议试验先评估 Ubuntu 22.04 ARM64 的 glibc/OpenSSL 3 依赖组合，但**不称它属于上述完整功能测试清单**；如不兼容，再评估文档列出的 Ubuntu 20.04 加独立 OpenSSL 3 构建。最终基础镜像须固定 digest，SDK 文件须核对可信发布方 SHA256；当前未取得 Linux 包的可核对摘要，不填写猜测值。SDK 安装包的获取权限、下载可达性及镜像再分发许可仍需安装阶段核实。

现有 macOS SDK 是 Mach-O 工具链，不能直接挂入 Linux 当作 Linux SDK；现有 `DYLD_LIBRARY_PATH`、MacOSX15.4 SDKROOT、Darwin 运行库也不能沿用。Linux 环境需独立 PATH/CANGJIE_HOME/LD_LIBRARY_PATH 和 ELF 工具链验证。仓颉版本不升级，不用更新 SDK 消除本轮差异。主机 Policy 留在 macOS 原生运行，因此最小方案不要求将 Policy 迁入 Linux；若未来迁移，Linux stdx 与原生 Policy 重编译需另验，本轮未核实其发行包。

## 3. 源码接入点及影响

本节为实际源码阅读结论，拟议变更尚未实施。

| 当前文件 / 关键入口 | 现有行为 | 最小增量需要 |
| --- | --- | --- |
| `nexus/execution/runner.py:run_command` / `sandbox_profile` | 固定两条 cjpm 命令，macOS sandbox、输出/时间/进程组限制 | 保留 native；新增受信 Docker 执行器，禁止模型选择镜像、参数、挂载或 Docker context |
| `nexus/adapters/cangjie/sdk.py:sdk_environment` | 固定主机 Mac SDK 和运行库 | Docker 使用独立 Linux 工具链清单，不能复用主机变量 |
| `nexus/adapters/cangjie/verifier.py:identity/_run` | 哈希主机 cjc/cjpm、Mac SDK 路径、runner；读取日志判定结果 | 绑定 backend、平台、镜像 digest、Linux 工具链摘要、安全配置摘要；实际 argv/容器状态可审计，避免 native PASS 缓存用于 Docker |
| `nexus/requirements/service.py:prepare_task/build_verification_plan`；`nexus/contracts.py` | 冻结需求、套件和主机 toolchain_id | 将执行后端与“必须容器隔离”要求纳入版本化冻结契约；未知版本/后端拒绝，不隐式改历史任务 |
| `nexus/execution/environment.py:readiness` / `scripts/doctor.py` | 主机 SDK/Policy/模型配置就绪 | 后端分别预检；检查 Engine、架构、镜像、限制支持和配置，不能只检查 docker 命令存在 |
| `cang_sight_server/server.py:create_server`；`nexus/mcp/client.py:ToolClient` | 官方 stdio MCP，九工具、原生 Policy gate | MCP 与 Policy 保留主机控制面；检查工具内部选择已冻结执行器，不把 MCP Server 放进候选容器 |
| `nexus/execution/workspace.py:WorkspaceStore` | 主机冻结基线、候选、树摘要和权限；拒绝 symlink/build.cj | 输入只读挂载，构建产物隔离；前后由主机核验源文件与模式，不能挂整棵运行根 |
| `nexus/execution/delivery.py:accept/acceptance`；`archive.py:EvidenceArchive.files` | 同版检查、审批、完整证据和同一 export_id | 保持审批和打包在主机；加容器配置/生命周期证据引用，排除镜像层、target 和容器可控路径 |
| `nexus/web/app.py:create_app/accept/export`；`workbench.js` | 会话/CSRF、审阅、历史和导出 | 显示明确 native/docker 模式及 BLOCKED；另审查真人授权边界，不把网络隔离宣传成身份认证 |
| `nexus/repair/cegis_loop.py:RepairLoop.run` | 三候选、480 秒和失败反馈 | 维持主循环；容器故障映射现有 UNKNOWN/BLOCKED/IN_DOUBT，不新增 Agent、模型或重试循环 |

预计主要增加一个执行器模块、一个显式分派/配置点、一个独立镜像构建目录，必要修改上述身份/契约/预检/证据位置及相关测试。不是“只改一行 subprocess”。不改原 Sympas-Nexus，不替换原生 Policy，不重构稳定 MCP-CEGIS。

## 4. 容器内外的最小边界

建议只将 **cjpm 及其编译/测试子进程**放进一次性候选容器。主机保留模型 API、MCP Client/Server、Policy、SQLite、需求/审批/导出、浏览器与密钥。cjpm 控制进程和它生成的测试进程必须在同一容器网络命名空间，避免误将其内部 TCP 通信跨回主机。

`--network none` 在 Docker 文档中保留容器自己的 loopback，因此理论上可保留仓颉内部 IPv4 TCP，同时切断主机 Web；不是原 macOS 沙箱中“禁止所有 TCP”的同一种行为。**仓颉在这种网络下的真实 build/test 尚未执行。** 默认 none 网络没有 IPv6 loopback，若实际框架依赖 IPv6，需停下诊断，不切换 host/bridge 网络绕过。[Docker none 网络](https://docs.docker.com/engine/network/drivers/none/)。

| 边界 | 拟采用配置 | 必须避免 / 剩余限制 |
| --- | --- | --- |
| 网络 | 独立 `none`；无端口发布、host gateway、自定义主机映射、代理变量 | 不用 host/container共享网络；逐测127.0.0.1、::1、host.docker.internal、主机/VM IP和外部IP，单纯 DNS 失败不算隔离通过 |
| 输入 | 单一已验证候选目录只读挂载到 `/work` | 不挂父目录、工程根、主机 `/Users`、原框架、`.env`、Git、浏览器配置、其他候选或验证事实库 |
| 可写目录 | rootfs只读；`/work/target`、`/tmp`、HOME为限额 tmpfs，独立 IPC/PID；必要共享内存同样限额 | 容器结束丢弃产物；不允许源文件或审批数据可写；不得给容器任意主机输出目录 |
| 进程与权限 | 非root UID/GID、cap-drop ALL、no-new-privileges、默认 seccomp；不共享 host PID/IPC/devices | 不用 privileged、seccomp=unconfined、挂 Docker socket 或 --use-api-socket；兼容性失败先定位，不能自动放权 |
| 资源 | CPU/内存/内存+swap、PID、tmpfs、shm、nofile、日志字节、主机墙钟时限同时限制 | 仅 CPU 限速不限制墙钟；PID上限不能阻止所有耗尽；VM总磁盘/daemon日志另控 |
| 控制通道 | 主机固定 allowlist argv，stdin关闭，只接收候选 stdout/stderr为数据 | 不继承 MCP stdio、owner token、审批token、API key、SSH agent、Docker证书；不解释输出中的指令 |

配置依据：[运行参数](https://docs.docker.com/reference/cli/docker/container/run/)、[资源限制](https://docs.docker.com/engine/containers/resource_constraints/)、[seccomp](https://docs.docker.com/engine/security/seccomp/)。只读 bind 不改变主机目录权限，但挂载范围及递归子挂载语义需实测；最好只共享主机专门构造、无链接/无子挂载的输入目录。[Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)。

暂不提供可执行 Dockerfile 或一键安装脚本，防止将未经验证的镜像、SDK 摘要和限制值误作已批准部署。构建阶段可访问经确认的软件源；执行阶段离线。构建上下文仅含专用资产，禁止 `COPY .` 携带正式工程或密钥。镜像中预装全部依赖，执行时禁止自动拉镜像、apt/cjpm联网补依赖。若 cjpm 尝试写冻结的配置/lock，先明确必要可写范围和记录前后差异；不能将整个 `/work` 改成可写来消除报错。

## 5. 人工审批的实际威胁核查

**新发现：本机会话不是“真人操作证明”。** 实际源码中 GET `/` 自动生成会话 actor/CSRF；GET 候选返回 check_set_hash、task_revision；accept 路由用该会话 actor 调用 DeliveryService.accept，但该函数不要求 actor 等于需求确认者。校验的是候选/检查/修订与批准记录一致性，不能据此证明真人点击过。

实际探针在一个临时复制的 V1.1 运行库上进行：读取此前真实验证过的同一候选，状态设为待审阅，创建一个全新本机会话并调用 accept，返回 **HTTP 200**，批准 actor 属于新会话而非原操作者。原运行库逐文件摘要不变；未进行新构建、模型请求或导出。证据见 [approval-boundary-probe.json](evidence/docker-feasibility/approval-boundary-probe.json)。这是 Flask 进程内 HTTP 路由验证，不是容器测试，也不是“真实恶意仓颉程序端到端攻击已成功”。此前候选可连接8765的TCP探针与本结果共同支持可利用风险，完整串联攻击尚未执行。

| 路径 | 当前源码/证据 | Docker 最小方案需要保证 |
| --- | --- | --- |
| 通过 Web 获取并创建批准 | 新会话读取页面/候选再accept，隔离副本200；Origin/CSRF可被本机程序仿照 | 候选不能触达Web。CSRF仅防部分请求来源，不把新会话当真人认证；另评估可信主机启动配对凭据/操作者授权，需单独实现和验证 |
| Web消费已存在批准 | export/download核对actor、当前证据与审批；创建新批准后可能以其会话继续请求 | 容器不得得到会话cookie或approval ID。未在本轮调用export，不能把潜在链写成已实测成功 |
| 通过 MCP创建批准 | 九工具无accept/approve工具；严格请求字段，candidate.export验证已存在批准 | 不增审批工具；候选容器无MCP管道和主机运行库；未知工具/extra字段继续真实协议拒绝 |
| 直接通过MCP消费批准 | export_route核对任务/候选/approval绑定，并验证主机owner；此处不接浏览器actor参数 | 批准ID和受信owner通道都不进入容器；批准不是仅凭“accepted=true”自报。若攻击者已控制主机MCP/owner权限，Docker隔离候选也不能补救 |
| 读取或修改审批库/签名密钥 | RuntimeOwner的.session-key、.controller-owner.json、SQLite和records在主机 | 不挂载这些路径或其祖先；不将Flask/Policy/数据库与候选放进同一个容器 |
| 从Docker控制面逃逸 | 候选若获daemon/socket能启动新容器、改变挂载/网络 | Docker API仅可信执行器可用；不共享socket、credentials、SSH通道或Docker context；禁用候选访问daemonTCP |
| 输出、diff、报告携带指令或伪造PASS | 页面相应显示使用textContent，未发现此处innerHTML；主机日志解析仍消费不可信进程输出 | 输出不执行、不触发审批；Docker不证明测试报告真实、业务正确或消除提示注入。恶意代码伪造stdout/报告的风险需独立测试和门禁，未证明已解决 |
| 被允许的生产仓颉代码自行网络/文件/进程操作 | 仅保护测试/配置路径不能约束运行时代码行为 | 同样在隔离容器执行，限制生效须由真实仓颉探针证明，不能只用Python模拟它 |

[Docker 官方安全说明](https://docs.docker.com/engine/security/)强调daemon与挂载权限的攻击面。Docker Desktop 的 VM 与容器共享 Linux 内核/运行时相关攻击面并不等于每个候选独立虚拟机，也不是形式化隔离证明；不同候选不共享可写缓存。Rootless可减少部分daemon权限风险，但不是本方案已启用的属性，也不等价于容器中设置非root。[Rootless 文档](https://docs.docker.com/engine/security/rootless/)。Desktop主机访问存在专门网络通道，不能依赖容器里的localhost与主机不同这一条理由来断言所有路径关闭。[Desktop networking](https://docs.docker.com/desktop/features/networking/)。

## 6. 执行、日志、同版导出与失败处理方案

1. 用户/部署者明确选 native 或 docker。对要求容器隔离的任务，将要求冻结进计划和摘要；Docker CLI、daemon、镜像、限制支持任一不可用，任务在执行前明确 **BLOCKED**。不得静默回退 native，不以环境变量临时覆盖已冻结计划。
2. 原生 Policy 在主机批准 candidate.build/test 动作后，可信执行器按固定参数创建单候选容器；先实际inspect核对镜像平台、网络、mount、UID、cap、资源。配置不符时不启动候选。镜像用digest而非latest，`pull=never`，任务期间不更换context。
3. build和test复用同一候选受控生命周期/内存产物，但不跨任务复用；校验build PASS后才能test。具体采用一次容器内的固定可信调度器还是受控start/exec，在原型阶段对比后定案；无Docker socket进入容器，无任意shell拼接接口。若重建容器导致target丢失，必须真实重建，不拿旧build证据假装产物仍在。
4. 主机保存真实命令、镜像/SDK/后端配置摘要、container ID、启动/结束时间、exit/OOM/daemon状态和原始输出。输出上限延续2MiB，单步90秒及总480秒保持；镜像准备在执行任务前完成。Docker错误、OOM、启动失败、截断、零测试和必需skip不是业务FAIL或PASS，应为UNKNOWN并停止/阻塞；未知容器状态标IN_DOUBT。
5. 原生killpg只终止Docker CLI不能证明容器已经结束。必须由主机按自建container ID/label显式stop/kill、wait/inspect、remove，再确认无残留；不使用全局prune或按不明PID删除。断连、取消、控制器重启时保留容器ID和原始状态，停止后续步骤且不自动重放未知操作。
6. 完成后由主机复核源树、冻结测试与配置/模式；交付仍由主机现有DeliveryService/Policy完成。容器不能写检查索引或审批记录，也不能提供直接归档路径。新增后端证据进入完整evidence清单，候选/需求/计划/批准继续同版绑定。平台改变使旧检查/批准失效，不迁移历史LIVE为Docker证据。

Linux编译产物不能当macOS可执行交付。源码包需标注已验证目标平台；成员在native重新验证时产生新检查/批准，不能复用Docker的结果。Cangjie测试输出/中文诊断、退出状态、文件权限和只读挂载兼容性均待真实验证；现有parser通过macOS回归不证明Linux解析已正确。

## 7. 分阶段最小集成、回滚与放行条件

| 阶段 | 操作（均需用户确认实施后） | 放行条件 |
| --- | --- | --- |
| D0 环境原型 | 选择并安装一种运行时；只建专用ARM64镜像和临时案例目录 | Engine/架构/镜像digest/SDK可信摘要、真实cjc/cjpm版本可核对；不接模型、不替换现有主链 |
| D1 隔离与兼容性 | 无网络候选容器真实build/test与恶意边界探针 | 合法案例11通过；缺陷/不完整修复实际失败；审批面/MCP/daemon/密钥/文件探针被实际阻断 |
| D2 主机执行器接入 | 最小分派、版本化backend契约、预检、身份和生命周期证据；保留native | 真实MCP/Policy调用使用指定Docker后端，拒绝静默降级，原native离线/SDK回归不退化 |
| D3 交付与验收 | 新批准、同版完整导出、干净环境复现材料 | 当前Docker证据与审批绑定；团队独立回执。新增LIVE必须另行费用授权，本次不包含 |

回滚方案：在独立版本分支/提交中实施，每阶段保留原native入口和已固定6d8784b交付。关闭“新建Docker任务”入口，可显式新建native任务；已经要求Docker的任务保留BLOCKED/IN_DOUBT，不能原地切native。按ID停止并移除本项目容器，核对无活动执行后撤回代码/配置；保留原始失败证据与数据库备份，不覆盖原记录、不删除历史包。软件卸载、VM/镜像删除或清空运行库均不自动进行。回滚同样不能将旧版本宣传为满足新增隔离要求。

## 8. 后续测试矩阵（本轮未执行Docker测试）

| 测试 | 实际验收证据要求 |
| --- | --- |
| 工具链/功能 | 容器内cjc/cjpm版本、ELF架构、依赖检查；正常案例build+11通过、缺陷基线10通过1失败、编译错误和可编译坏候选真实FAIL；原native全套回归 |
| 网络/审批 | 真实仓颉代码在测试时尝试HTTP获取session/CSRF、accept/export/download；同时探测IPv4/IPv6、host.docker.internal、host/VM地址、外网。不能获取会话或创建/消费批准；主机审批数和导出数不变；容器内部TCP自测成功 |
| MCP控制面 | 真实Client/Server九工具可调用；无approve工具；伪accepted/actor/approval ID、错task/tree/hash/version被拒；候选无法继承stdio或owner token；不存在“不经Policy的Docker动作” |
| 文件/权限 | 宿主密钥/DB/其他候选不可见；源码/测试/配置只读；符号链接、硬链接、路径穿越和可执行文件/权限变化拒绝；Docker/SSH socket不存在，不暴露FD |
| 容器配置 | 主机inspect与容器内UID/cap/mount/network/PID实际结果同时匹配；禁privileged、host网络/PID、共享可写缓存和任意用户参数 |
| 资源与生命周期 | 有界的OOM、进程耗尽、日志洪泛、写盘上限、CPU超时、取消/崩溃/daemon断连、应用重启；主机仍可用、无残留进程/容器、未自动重发或降级 |
| 报告/输出 | 伪造PASS字样、异常退出、截断、零用例/skip、畸形结果不能计成功；保留原始日志和可信退出/资源状态。即使容器运行正常，也不能直接证明同进程测试输出不可伪造 |
| 绑定/导出 | 改backend/image/platform/profile/源码/计划/批准使旧结果失效；真实MCP导出同candidate，重复导出同ID；归档完整与敏感排除检查；Docker不可用的required任务BLOCKED、native未被暗中调用 |

所有主动探针仅在单独临时运行库和本项目自建容器内进行，不攻击正式审批服务、原框架或其他成员任务。故障替身只证明分支；Docker隔离与仓颉运行必须由真实进程证据证明。

## 9. 证据等级与当前阻断

| 事项 | 等级 / 结果 |
| --- | --- |
| 本机架构、资源、虚拟化能力、常见运行时未发现 | ACTUALLY_VERIFIED：本轮只读命令；具体输出在host-and-source-inspection.json |
| 审批入口及新会话批准 | ACTUALLY_VERIFIED：源码 + 隔离运行库HTTP探针200；不宣称端到端恶意程序攻击已执行 |
| 原运行库未变、产品源码未变、原Sympas未变 | ACTUALLY_VERIFIED：探针前后原运行目录摘要、受检源码摘要与453文件基线复核 |
| Linux ARM64/AMD64 SDK | OFFICIAL_DOCUMENTATION_VERIFIED：发行条目和环境说明；实际安装/运行NOT_VERIFIED |
| none网络可保留内部loopback、Linux容器可限制权限资源 | DOCUMENTED / THEORETICALLY_FEASIBLE；尚无本机容器证据 |
| Docker中cjpm内部通信、11例、Policy/MCP联合链和安全探针 | BLOCKED / NOT_VERIFIED：未安装运行时，未构建镜像，尚未获准实施 |
| LinuxSDK摘要/镜像依赖与再分发、目标系统组合、性能与上限 | 未验证；必须在镜像准备和D0/D1中解决，不能猜测SHA或复制Mac二进制 |
| M1指定基座、外部复现与比赛提交 | 仍独立未完成；本调查不能替代 |

## 10. 调查时提出的实施范围（现已暂缓）

建议首先只批准 **Docker Desktop Apple Silicon + 专用Linux ARM64仓颉1.0.5镜像的D0/D1原型**。需要安装运行时、下载基础镜像/SDK/系统依赖，使用约4GiB VM内存和可配置磁盘；这些本轮均未执行。若选择Colima，则改为安装Colima/Lima与Docker CLI，不能两套同时试装。

D0/D1只新增专用镜像/探针与证据，不改稳定主链；通过后再确认D2预计涉及执行器、工具链/计划身份、预检、日志/生命周期和交付证据的源码修改。主要风险是Linux SDK依赖/平台差异、只读目录兼容性、资源不足、daemon权限/挂载配置错误、容器逃逸残余风险和应用层审批授权不足。当前新会话可批准的结果必须纳入修复评审，不能仅凭Docker启动成功关闭安全问题。

**调查交付完成；用户已决定暂缓 Docker 集成。现有 native 模式保留，Docker 实施不再作为当前待执行事项。后续恢复需用户重新明确授权。要求容器隔离的验收仍须标记 BLOCKED，不能拿 native 结果替代。当前尚未实施 Docker 后端及 required-backend 契约，此处是执行/验收约束，不是宣称产品代码已经实现该后端门禁。**
