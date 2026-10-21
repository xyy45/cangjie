# 来源、第三方与 AI 使用记录

本工程独立创建，未将旧工程源码、.env、密钥、数据库或历史用户文件整包迁移。原始目录仅用于只读审阅；文件摘要清单保存在 docs/evidence/original-source-sha256.json。2026-10-18已从用户指定GitHub仓库核实固定commit；V1.1新增少量网关派生代码，具体范围如下，不能再笼统宣称当前全部源码未直接复用。

V1.1实际来源：nuptpisa/CangSight@5db0c7eeeb6a62812fc04e9e88497339fed5e11f，Sympas-Nexus/nexus/gateway/app.py；派生文件nexus/integrations/sympas_runtime.py。复用递归响应脱敏函数、运行查询路由结构及通用_execute_run分派生命周期/create_run入队与线程流程；修改为仅仓颉能力的受保护Blueprint，注入现有RepairLoop及同一事实库，分派状态只作事件投影，异常仅记录类型。没有复用整个旧create_app、旧领域执行器或旧审批路由。按用户许可处理指令采用根Apache-2.0，原文、文件哈希、修改说明及插件MIT元数据差异见docs/third-party/sympas/SOURCE.md和同目录LICENSE。这是最小派生网关，不宣称已启动完整原始网关应用。

审阅了旧 cang_sight_server/server.py 与 skills/sympas_mcp_skills.json 的职责和候选工具声明，未直接复用其代码。原有全工具注册/旧网关不进入新主线；这不宣称旧框架已经仓颉语义适配。可选工具当前排除，理由见progress。

运行依赖：官方 MCP Python SDK 1.26.0、Pydantic 2.12.5、Flask 3.1.3、httpx 0.28.1及固定传递依赖（requirements.lock）。发布前需随实际分发核对各包LICENSE；本项目尚未选择对外开源许可证。

Cangjie SDK 1.0.5 / stdx 1.0.5.1 从官方渠道下载，许可证和第三方notice随本地 .runtime 包保留，不进入源码或工程导出包。SDK摘要与stdx本地下载摘要见progress；后者不宣称官方签名验证。源码fixtures为本次自产订单示例。

Codex参与本工程代码、测试、文档生成。确定性测试使用的替身/合成检查明确标为TEST或单元fixture，不能当作LIVE模型成功。产品Provider的真实origin/model_id由适配器记录；没有DeepSeek配置时不生成假候选、不预造PASS。手写候选的SDK交付测试与LIVE模型验收分开。

当前已有LIVE A成功、连续三次复演、实际页面操作视频与浏览器下载证据；第三人复现和正式比赛提交证据仍缺失。不得将本开发版本描述为通用仓颉分析系统、全算法集成或生产级恶意代码沙箱。

操作视频编码使用独立开发工具环境中的imageio-ffmpeg 0.6.0，未加入应用运行依赖或源码包中的虚拟环境；所有画面来自实际本机页面帧采集，帧摘要可追溯，片段间长等待已缩短。
