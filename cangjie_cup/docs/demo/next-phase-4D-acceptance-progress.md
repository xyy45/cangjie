# 4D 跨包阶段终验进展

更新于2026-11-03。**最新结果：4D跨包与部署工具已合入，并在8877激活；其他开发按用户要求暂停。** d953...完整Python3242项／Node187项通过，2302冻结输入未变；77项部署集成检查和1条真实SDK跨包两轮完整闭环通过。17张主站表、44任务、3959记录及会话保持，旧4C保留。详见[最终集成验收](next-phase-4D-verification.md)。下文早期进展保留时间与版本归属；不代表第5项原计划完整干净部署／性能测量已经完成。

## 已完成的验收准备

| 范围 | 已读取的实际证据 | 结论及边界 |
| --- | --- | --- |
| 旧阶段同版本重建 | 2、3A、3B、3C、3C缩减、4A、4B、4C共8条离线程序，全部退出0 | 各自使用归档源码及核；未新增模型、远程分析、SDK或原生IPC执行 |
| 当前4D V5协议与测试程序 | 4份历史源码、30组实际SDK输入／结果对 | 测试程序逐字节、源清单和重建结果一致；未将缺少cases结构的桥接探针计为协议样本 |
| 当前4D扫描与XML | 2份源码各重建4个真实SDK包 | 保留PASS、FAIL、UNKNOWN，未将空报告升级为通过 |
| 修复／交付服务完整重建 | 初次及最终两轮修复、两条UNKNOWN停止、浏览器交付、XML篡改控制，共6个原始运行 | 28份构建／测试记录和17份业务规则报告与对应原件一致；两个已交付流程的检查集摘要与历史批准记录一致；篡改控制仍拒绝交付 |
| 有限归档扫描 | 最新55份ZIP及64份内嵌ZIP，共52044个条目、643777983字节展开内容，包含审阅修正原件、旧回归封存和依赖材料 | 规范路径、重复名称、符号链接、指定私密文件名及3类密钥形态检查无命中；不是通用秘密检测或发布批准，早期扫描仍保留 |
| 字符串断言反馈修正 | 原有2项和新增6项真实SDK验证全部通过，69.26秒；关联166项通过 | 覆盖字面量分隔符、引号、换行、反斜杠及带String参数的数值断言；公开反馈／定位与原测试私有性一并核验 |
| 字符串修复原件同版本重建 | 6份对应源码／核、29个历史运行全部核验一致 | 19份成功字段反馈与保存的JSON完全一致，10次历史解析拒绝仍按原版本重现；最终版本8份反馈全部一致。未重跑SDK、原生IPC、模型或网络 |
| 已审阅源码完整回归 | 408文件9eb...：Python3238通过／1项live排除，4202.30秒；Node187通过，0.448秒；两者退出0 | 执行记录及封存时再次核对2302份输入未变。该成绩属于修正前源码，不冒充d953...的新版本完整通过 |
| 当前修正源码 | 408文件摘要`d953cdc3fd44e4ab8f9aa1a2c71a180226d74a0b008357f1daffac5c73e36260`，仅解析器及两个测试文件改变 | 新2302输入摘要`5cec59ff640c720cd9265a31fcbfee852a45cad23644e7343fa76bc897c6c0fd`；84项字段／反馈兼容通过，9项真实SDK通过73.75秒，Node187通过0.455秒；新完整Python运行中 |
| 审阅修正原件同版本重建 | 668条原件封存；旧9eb...反引号失败1个运行、新d953...成功9个运行均按各自源码重建 | 旧解析拒绝准确复现，9份反馈与保存JSON完全一致；子进程禁止SDK／native／网络／文件写，SQLite不可变只读，前后原件字节一致 |

完整服务重建先把2261份原始文件与已封存ZIP逐字节核对，再运行各自版本的真实验证方法。SQLite连接使用`mode=ro&immutable=1`，拒绝非预期数据库；子进程禁止SDK／原生执行、网络和文件写入。既有构造器对已经存在目录的`mkdir`只得到EEXIST，没有创建目录。核验后再次比对原件，未恢复或改写任何历史状态。

SDK报告中的绝对源码坐标保留原路径。这些结果证明原件和对应实现能够一致解释历史运行，不代表已经完成跨机器路径迁移或干净环境部署。没有续期历史批准，也没有重新导出。模型与图分析仍为明确的HTTP夹具；实际SDK、扫描、XML、原生核和stdio执行证据来自先前阶段原始运行。

## 终验门槛逐项状态

1. **一次独立审阅完成，重要问题的作者修正待新整轮收尾。** 在账户窗口实际恢复后完成只读整阶段审阅，核对109条变更和408份源码。结论WITH FIXES：Critical无、Important一项、Minor一项。重要问题为合法String参数中的反引号使typed XML解析失败，原测试映射异常进一步中断公开反馈／定位；作者真实SDK在9eb...复现，随后以外层包络和引号外比较符分隔修正，保留冻结token及原件绑定。84项相关测试、含反引号的9项实际SDK通过，当前新完整回归尚在运行。没有重新分派复审；完整审阅、分级及7条范围裁定保存在`task7-independent-review-20261103.md`。
2. **修正前完整回归通过，修正后正在重新执行，历史失败仍保留。** 首次运行漏建证据目录，经独立复现后正常中断并保留1失败／441通过的部分报告。补齐目录后的第一次完整运行退出1：3236项通过、2项失败、1项付费测试未选择，4317.44秒，2301份输入未变。两项失败分别是测试隐式依赖已有模型配置，以及快照缺少`.gitignore`；仅显式设置合成配置并补齐资源，没有削弱断言或产品就绪逻辑。关联17项通过（1.82秒），新快照无真实模型配置时原两项均通过（0.46秒）。9eb...第二次完整复跑终态Python3238通过／1项live未选择、4202.30秒，Node187通过，输入未变。现在Important修正产生d953...，新完整Python回归与旧运行分开，未取得终态前不勾最终回归通过。
3. **主站切换尚未执行。** 需要主站空闲时完成表／原始记录／会话／锁审计，独立复制4D并核对页面和资源，保留4C回退版本。主站真实数据不用于测试。
4. **第5项部署与复现已完成部分隔离准备，未整体验收。** 原40项锁定依赖在新环境安装及专项验证通过；原始归档SDK安装、新core构建及3项真实IPC通过。仍需启动／自检／诊断、明确平台完整应用闭环、SQLite并发测量及交付记录。

延后Minor：`evidence-core.js`在当前检查已因原件变化变为UNKNOWN时，仍可能展示历史`scan_state=PASS`，造成显示矛盾；审批与导出仍被真实门禁阻止。按一次重要问题修正的计划先记录，不将此项描述为已修复。此前4B摘要共享数组引用Minor仍须在总体目标收尾核对。

独立审阅留下的字符串解析疑点已由作者用真实SDK确认：含` != `的预期字面量被错误拆分，原测试转义文本又在匹配冻结token之前被过度解码；多行XML差异的缩进和带String参数的数值断言也会触发错误分类。这会使已绑定的公开字段反馈和定位生成失败，按用户影响记为重要问题。现已改为引号外分隔、冻结原token优先匹配、区分数值与字符串诊断；真实SDK的8项测试验证通过，String仍为TEXT_ONLY，不推断完整实际返回值。此项作者修正不能代替尚未完成的整阶段独立审阅。初始失败、两次尚未完整通过的修正结果、最终通过原件和各自源码均保留。

## 第5项隔离安装准备

实际环境为macOS 26.6.2 ARM64、Python 3.12.4、Node 22.13.1。原开发环境40项中25项版本与`requirements.lock`不同。为避免无依据升级锁文件，另建不继承site-packages的隔离环境，先解算、再离线安装原40项锁，文件摘要、安装报告与版本核对均通过，`pip check`退出0。152项契约／解析与4项真实本地MCP stdio专项通过；这不是完整应用验收，原开发环境未改变。

40份依赖wheel共10682196字节，按官方PyPI大小／SHA-256认证；部分经TUNA HTTPS镜像传输，保留原始JSON与6份明确标注的web派生描述符。早期16份完整／24项网络失败的PARTIAL结果和全部部分文件保留，不改写为成功。依赖材料v2仅修正首份README漏写`install`子命令的错误，wheel／锁不变，首份原件保留。

固定SDK／stdx原始缓存归档按预设摘要核对后，由原安装脚本在新目录解包，未链接已有安装树；core重新编译、module doctor均退出0。新二进制摘要`0e08b05f081b26a36a76d92fa79c3c97afc0b028b15b9bb8fdf2e05d8bc279cc`，真实IPC完成边界轴、合法Allow和越界Deny。仍依赖宿主MacOSX15.4 SDK；不证明SDK官方网络下载或另一台机器可用。首次准备遗漏未改动安装脚本、直接doctor入口依赖PYTHONPATH两项失败均记录，未改产品代码。详情与完整缺口见[第5项预检](next-phase-5-preflight.md)。

## 证据位置

本阶段目录为仓库根下`.superpowers/sdd/2026-10-30-bounded-packages/`，其中：

- `task7-history-results.json`及8份历史回放日志。
- `task7-v5-rebuild.json`、`task7-task4-own-source-rebuild.json`。
- `task7-service-gates-all.json`及`task7-service-gates-initial.txt`；重建程序为`task7_rebuild_service_gates.py`。
- `task7-finite-artifact-scan.json`及扫描程序`task7_scan_archives.py`。
- `task7-short-string-preliminary-repro.json`，仅解析层初步复现。
- `task7-string-feedback-originals.zip`及清单，1882条原件，SHA-256为`8e22ad7910725a60834cd605480dd6fd83cda322f1d3596156f437d0f1013634`；含全部6次调查／修正尝试与对应源码，逐条重读核验。
- `task7-string-own-source-rebuild.json`／日志／重建程序；先重建源／计划／完整XML的FAIL，再验证原版本字段解析结果；29次均只读，原始绝对坐标保留。
- `task7-full-execution-manifest.json`及`task7-full-execution-inputs.zip`；2301份输入的摘要为`ef45905ba1f88d6895a87897b223810ce1feb5d1c1c81fdbfee9466b70ee8e9c`。
- `task7-full-python-owner.json`／原始日志／exit记录为首次中断运行；`task7-full-python-retry1-*`为3236通过／2失败的完整运行，均保留。订单测试RED／GREEN及进程清理审计另存。
- `task7-full-python-retry2-owner.json`／日志／exit记录为当前3238项Python通过证据；`task7-full-node-retry2-exit.json`及日志为187项Node通过证据。`task7-full-retry2-execution-manifest.json`含2302份输入，摘要`59215b1e66f8035e5951bf3e7c2532ac632b1ed94e58b929c914ad59604c8138`。
- `task7-regression-20261103.zip`含36条当前／历史完整回归材料，逐条重读核验；摘要`259ddb93e4ea2253cba618ab2100f88e59d10e71c5afc824e8bc7c044af6634f`，封存时再次验证2302份输入未变。它不代表独立审阅或主站切换通过。
- `task7-finite-artifact-scan-regression-20261103.json`为最新52份ZIP及59份内嵌ZIP的有限扫描。
- `task7-review-corrected-v2.diff`和清单为当前109个路径的待审阅材料，较早审阅包均保留。
- `task7-independent-review-20261103.md`为完成的独立审阅与作者分级／范围裁定；审阅版本为9eb...，修正不再复审。
- `task7-review-backtick-red.json`／日志／独立运行库为修正前真实SDK失败；`task7-review-typed-delimiters-unit-red-corrected.txt`为2失败／1正常控制，最初单测样例未采用公开Unicode字面量的错误也保留。
- `task7-review-fix-source-freeze.json`／源码ZIP与`task7-full-reviewfix-execution-manifest.json`／执行输入ZIP绑定当前d953...；`task7-review-fix-sdk-*`、Node记录及运行中的Python记录使用不同日志，不覆盖旧结果。
- `task7-reviewfix-feedback-originals.zip`668条原件摘要`7c50aaf78133fdafd17839b5c409e1f769edabcfe57243869f616e89bf48a78b`，`task7-reviewfix-own-source-rebuild.json`为10个运行禁执行同版本重建证据；最新有限扫描为`task7-finite-artifact-scan-reviewfix-20261103.json`。
- `task7-deployment5-environment-preflight.json`、`task7-deployment5-pip-check.txt`。
- `deployment5-download-preflight-result.json`及原始pip／curl记录、公开元数据和完整／部分下载文件，保留早期失败。
- `deployment5-declared-lock-wheelhouse/manifest-range-attempt3.json`为早期16份完整包／24项未完成结果；后续40份完整包见`manifest-mirror-retry1-complete.json`。
- `deployment5-clean-venv-baseline.json`、`deployment5-install-binding.json`、安装报告／版本清单及152项／4项专项日志，分别证明空环境、锁定依赖安装和限定兼容结果。
- `deployment5-fresh-sdk-retry1-result.json`、安装／构建／doctor日志及`deployment5-fresh-sdk-native-ipc.json`绑定新SDK目录与core，原始准备失败另存。

前序功能、阶段测试和浏览器交付证据见[Task5—6阶段验证](next-phase-4D-task5-6-verification.md)。本记录不勾选最终验收、部署或总体目标完成项。
