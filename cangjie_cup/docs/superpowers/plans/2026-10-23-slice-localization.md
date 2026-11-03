# 切片驱动修复定位 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans，按已确认目标连续实施；保持TDD与最后独立审阅，不因阶段切换再次请求授权。

**Goal:** 把真实失败用例关联到确认需求、冻结源码函数／语句和原件绑定的MCP依赖切片，为各轮修复提供可检查的定位上下文。
**Architecture:** 复用RepairAnalysis的基线分析、point.py已校验PDG和既有反馈原件；新增聚焦定位模块，不新增服务或数据库。解析器提供函数跨度与同包调用线索；可信失败记录决定映射，MCP切片只作为静态定位假设。保留现有完整源码和基线摘要作为提案依据，不通过裁剪上下文改变候选校验规则。
**Tech Stack:** Python现有语法门禁／记录／MCP分析、Flask、原生JavaScript、固定仓颉SDK。
**Spec:** ../../升级改进开发计划.md（阶段3）

## Global Constraints

- 复用同一3轮／480秒／候选及输出预算，不能为了定位暗中增加模型请求。
- 模型仍对IMMUTABLE_BASELINE返回累计编辑；定位使用的源版本必须明确，候选失败版本和基线坐标分别绑定。
- 输入／实际／预期来自校验过的公开测试或独立规则报告，不执行模型生成的表达式，也不猜测业务预期。
- 没有有效PDG、语句节点或可靠函数映射时明确UNAVAILABLE／UNMAPPED；不能制造依赖节点、跨文件MCP图或缺陷证明。
- 定位中的跨文件函数关系只能标为本地受限语法索引来源，不能混入MCP逐文件图冒充原生跨文件分析。
- 所有定位证据、工具原件、源码／树／日志摘要与需求版本关联；仅复制原件或写新派生记录，不覆盖已有分析／验证结果。
- 未识别的生产语法保持旧行为，不通过放宽门禁实现定位支持；原单文件和阶段1、2回归保持。

## Review Focus

- 候选新增／删减行后，不能将基线行号渲染为候选当前行号；引用明确显示坐标版本。
- 同名变量／多个return／递归调用不得导致无限遍历、串函数高亮或将整文件当作精准定位。
- 不可信日志／源码注释中的函数名、工具失败或空结果不能成为已验证事实；缺少确认用例映射必须保持未知。
- 定位报告或原MCP结果被篡改、跨任务套用、非同一基线时，模型读取／前端／归档都应拒绝该定位证据。
- 可选定位失败不能伪造普通测试／独立搜索成功；界面说明静态假设与实际失败证据各自的来源。

## Task 1: 函数位置与失败映射

Files: extend nexus/uploads/language.py／projects/index.py with deterministic source spans as needed; create nexus/repair/localization.py; tests/test_localization.py.
Interface: build_focus(source_files,confirmed_cases,failures,analysis_reports,binding)->有界定位报告。binding至少包含task_id、baseline_id/hash、spec_hash、失败subject_id/tree_hash；每个引用保留文件SHA与坐标subject。
- [x] RED：确认用例映射到指定函数；原工程跨文件调用线索标为LOCAL_SOURCE_INDEX；重复变量、未知函数、循环调用、错误摘要与无法映射用例不产生虚假精准结果。
- [x] GREEN：使用现有受限token解析函数声明／结束位置和调用关系；只有已有确认映射允许关联测试到函数。输出最多8个定位项、每项最多4个锚点和40行上下文；所有截断明确记录。
- [x] 测试基线源码换行、注释、多return与候选行号变化，断言坐标始终绑定实际原件。

## Task 2: 原件验证与PDG切片

Files: localization.py, analysis/repair.py, tests/analysis/test_repair_localization.py.
- [x] RED：真实格式的源绑定PDG经attach_point_graph及point_slice得到相关节点／边；改原始响应／源码／日志摘要会拒绝；空PDG保留UNAVAILABLE。
- [x] GREEN：仅从已验证分析原件重建PDG；选择函数内可解释的返回／结果语句作静态切片锚点，保留锚点选择依据。源码索引只补充调用线索，不宣称动态路径或精确根因。
- [x] 写入独立LOCALIZATION_CONTEXT事件及不可变记录，摘要覆盖完整定位报告和原件引用；verify函数重建并比对，不只相信JSON里的状态。

## Task 3: 各轮模型反馈与证据归档

Files: repair/cegis_loop.py, analysis/repair.py, execution/archive.py, demo/deepseek.py as needed; tests/sdk/test_localization_repair.py.
- [x] RED：有真实失败的下一轮收到正确定位和已有反馈；定位对应基线坐标／失败候选双绑定；不存在定位时原循环仍可用。
- [x] GREEN：在各轮propose前调用明确的定位钩子，复用已验证基线分析结果，不重新付费、不增加模型次数；限制定位上下文16KiB，超预算显式降级。
- [x] 真实SDK与模型HTTP夹具：两文件缺陷／独立新反例进入下一轮，模型输入含可信定位，普通测试／规则全部通过；交付原件与定位可复核，篡改定位不被归档接受。

## Task 4: 前端定位链与阶段验收

Files: demo/static/localization.js, demo/templates/demo.html, static/evidence.js／demo.js as needed; tests/localization-ui.test.cjs; docs/demo/upgrade-phase3-verification.md.
- [x] RED：展示失败用例→确认需求→函数／语句／静态切片，明确坐标版本和工具状态；不同候选切换不混用定位，空结果有明确状态。
- [x] GREEN：复用现有浅色样式与证据面板；代码选中／原件入口必须对应已绑定文件，不添加无来源高亮。
- [x] 全量Python（not live）、Node、差异检查、必要浏览器验证、独立审阅和证据归档；不以模型夹具结果声明真实模型修复率。
- [x] 更新主计划、重新读取后进入阶段4评测集。

## Execution Ledger

2026-10-23：阶段2最终461 Python通过／1未运行、87 Node通过、独立审阅重要问题关闭；主服务8877空闲时已重启加载工程导入，主界面三种导入方式确认存在。已更新并重新读取主计划，开始阶段3设计和代码路径核对。尚未实现本阶段定位模块，不声明阶段3能力已可用。

Ruling: 首版定位沿用模型编辑所依据的冻结基线坐标，并单独标明实际失败候选／树摘要 — 现有模型提案始终累计基于基线，避免把候选行号误套基线图 — 后续如需候选专属分析，必须单独产生该版本工具原件，不复用基线图冒充。

Pre-flight: Task1输出函数跨度和确认映射供Task2选择锚点；Task2输出原件绑定报告供Task3模型和归档校验；Task4只读取Task3验证后的报告。失败记录来源必须在Task3从原有check／exploration原件重建，不能直接相信前端或模型传入的failure字典。

2026-10-24：Task 1–4 complete。最终486 Python通过／1未运行（487.97s）、93 Node通过、差异检查通过；真实静态MCP＋SDK浏览器定位／PDG跳转／交付下载200，提案为测试提供器，未调用付费模型。日志调用核对Important已修复且独立复核通过；超长UNMAPPED预算健壮性Minor记录阶段6。详见docs/demo/upgrade-phase3-verification.md。重读总计划，继续阶段4。
