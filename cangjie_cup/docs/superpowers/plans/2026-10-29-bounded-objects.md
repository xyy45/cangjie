# 有限结构体／类 Implementation Plan

> REQUIRED: superpowers:executing-plans，作者inline逐任务实施；一个最终fresh审阅。持续授权已存在，不重复八节／阶段确认；无Git写入、推送或历史台账清理。预算真实模型／远程分析0。

**Goal:** 4C有限具名struct／class对象从声明、JSON、纯方法、实际SDK观测贯通独立验证、反例修复、页面和交付。

**Architecture:** 在既有Parser／shared values／四模型／四服务上增加闭合types registry、名义对象值和显式V4；保持旧普通值协议。所有对象字段只读、构造冻结，实际状态由返回对象字段决定。主站独立4B不作fixture。

**Tech:** Python3.12／Flask／SQLite／JS／pytest／Node、固定SDK1.0.5／stdx、仓颉core，无新依赖。

**Spec:** `docs/superpowers/specs/2026-10-29-bounded-objects-design.md`，含一次builder后的全部作者接口裁定。基线310源87a619...在`.superpowers/sdd/2026-10-29-bounded-objects/baseline/`。

## Review Focus

1. 未带registry的键计算不得变成类型授权；同字段不同$type、field bool/int、JSON顺序和可变dict／Array不得串用证据。Task1／3／5覆盖。
2. class身份、struct内Array别名、隐藏方法／构造器／跨文件helper不得绕过readonly；方法receiver和类型／函数命名冲突精确。Task2／4覆盖。
3. 公开字段投影不能冒充完整对象实际返回；生成测试单次调用、Array长度错误不越界继续、原测试meta／Focus重建都绑定。Task2／5覆盖。
4. V4值错误、旧协议保留头、最大2141 wire、nonce／TCS／CASE／summary／stderr和生成名碰撞；方法名／字段名不能遮蔽生成器。Task4覆盖。
5. 非首对象状态＋固定String／Array上下文＋跨候选缩减历史的真实SDK一条整链，不用分层测试代替；未知停止和原件篡改禁止交付。Task5／6覆盖。

## Task1：失败摘要快照修复与对象值契约

**Files:** Modify `nexus/repair/exploration.py`、`sequence_trace.py`、`values.py`；Create `nexus/repair/object_values.py`、`tests/test_failure_snapshot_aliases.py`、`tests/test_object_values.py`。

**Interfaces:** object_values.registry(raw)->新规范registry；is_object_type(kind,types)->bool；value(raw,kind,types)->深复制tag对象；typed_key(raw,types=None)->名义类型与排序字段typed tuple（无types仅作闭合结构key，绝不validate）；weight(raw,types=None)->字段既有权重和；literal(raw,kind,types)->可信构造字面量；has_objects(signature)->bool。values.primitive(value,kind,types=None)、typed_key(value,types=None)、primitive_weight(value,types=None)，旧调用语义保持。

- [x] 先写alias RED：Oracle structured失败args／actual_return与observations相互修改均不影响另一侧；Sequence失败顶层before／actual／expected与observations末步／复制steps双向独立。保留caller输入完整与原日志重建断言。执行 `../.venv/bin/python -m pytest tests/test_failure_snapshot_aliases.py -q --tb=short`，Expected真实当前alias FAIL。
- [x] 仅在形成摘要处deepcopy这些值，运行该文件及`tests/test_array_feedback.py tests/test_array_trace.py tests/test_string_final_review.py`，Expected全PASS；不改历史4B执行源／原件。
- [x] 对象values RED：恰为$type／fields、tag／registry／类与结构体、字段顺序、同字段不同类型、缺／多键、bool/int、0／4／5类型与字段、String256／257、Array16／17、嵌套对象拒绝、输入和key快照。Expected缺模块／功能失败后最小实现，不新增依赖。
- [x] `../.venv/bin/python -m pytest tests/test_object_values.py tests/test_array_values.py tests/test_string_values.py -q --tb=short`全PASS；保存RED/GREEN／ruling，更新台账。

## Task2：声明注册、纯方法、上传／工程及公开字段测试

**Files:** Create `nexus/uploads/object_types.py`、`tests/test_object_language.py`、`tests/test_object_projects.py`、`tests/test_object_uploads.py`、`tests/sdk/test_object_public_sdk.py`；Create `nexus/uploads/public_tests.py`；Modify `nexus/repair/focus_service.py`的公开case类名衔接；Modify `nexus/uploads/language.py`、`service.py`、`nexus/projects/index.py`、`nexus/requirements/service.py`、`nexus/execution/workspace.py`的实际缺口，保持既有入口。

**Interfaces:** object_types.collect(source)->registry与声明坐标／方法索引；Parser可选types／receiver_type并保留原constructor；program()/inspect_source仅对象出现时增types，params／return为对象时函数signature附types。language.literal(value,types=None)对对象必须明确registry；声明解析先同包收集后验证所有body。项目index含canonical types、qualified方法位置／calls，候选比较冻结这些接口。

- [x] RED覆盖4类型／每类4字段4方法、public let、完全匹配构造赋值、类型／函数／方法命名、参数0—4及16／128体预算、同包跨文件声明／调用、this.field／this.method、字段／返回类型追踪、局部重绑定。拒绝var／mut／继承／静态／getter／重载／对象字段／隐藏可变方法／数组写／一般成员／构造副作用；非选中方法也验证。
- [x] 实现声明收集和受限Parser，旧无对象source／signature输出保持；方法解析以receiver名义类型，定位calls保留qualified name和原坐标，不把方法加入顶层入口下拉。
- [x] 工程TestParser RED闭合构造字面量与`@Expect(entry(...).field,literal)`；新增projection／expected_type仅用于新投影case。拒绝直接对象@Expect；candidate冻结registry／constructor／signature／原测试ID／源码配置，3允许生产路径边界保持。
- [x] 上传生成对象公开test：单次入口调用局部结果，逐字段Expect；Array先size，size相等才逐项Expect。冻结raw JSON／types并保留跨会话、幂等、旧响应／CSRF控制；不生成草案自动确认。
- [x] 运行新增三文件及旧`tests/test_upload_language.py tests/test_project_index.py tests/test_project_archive.py tests/test_upload_service.py tests/test_array_uploads.py tests/test_string_uploads.py`全PASS。
- [x] 固定SDK公开缺陷→参考修复：struct／class退款边界、class方法计算错误、两文件冻结投影原测试。空String／Array及极值字段、完整对象返回按字段断言、原件及源清单一致。先冻结源码，执行 `../.venv/bin/python -m pytest tests/sdk/test_object_public_sdk.py -q --tb=short --basetemp=/private/tmp/cangsight-4C-task2-sdk`；Expected测试全PASS，业务bad FAIL→fixed PASS，原件归档并纯重建。

## Task3：对象模型、搜索／缩减和原生轴

**Files:** Modify `nexus/repair/oracle.py`、`properties.py`、`relations.py`、`sequences.py`、`cangjie/core/src/main.cj`；Create `tests/test_object_contracts.py`、`tests/test_object_search.py`、`tests/test_object_core.py`。

**Interfaces:** expression_tree(...,allow_objects=False,types=None)、evaluate(...,allow_objects=False,types=None)、expression_type(...,types=None)，新增三个object helper，Type/field须常量；先registry类型推断后执行，不开放Python Attribute/dict AST。所有object模型version优先Oracle5／其余4，types仅冻结signature携带。native boundary_payload对象为{domains,types(值投影)}，旧仅domains。

- [x] RED合法／错版本、typed domain1—16唯一完整对象、helper构造／取字段／替换字段、错误tag／字段／值／中间溢出／索引／超限，旧版本拒绝object helper。
- [x] 采样顺序／seed／评分、域内缩减与保留输入、所有临时对象深复制；模型只对实际计划／缩减预检，不声称穷举。对象初态／后态在域、非首state、context复用、矛盾转移、累计历史上限覆盖。
- [x] 原生实现精确registry／对象字段校验，旧轴正常包络字节保持；Python完整typed对照Bool/int和名义类型。构建新开发core，记录source／compiler／core；主站4B core不改。
- [x] 新三文件及旧Array／String／数值模型、native policy／binding回归全PASS；原生合法／拒绝原件与自有core封存，禁止执行提取重建一致。

## Task4：V4对象真实观测

**Files:** Create `nexus/repair/object_trace.py`、`tests/test_object_trace.py`、`tests/sdk/test_objects_sdk.py`；Modify `primitive_trace.py`、`property_trace.py`、`relation_trace.py`、`sequence_trace.py`、旧保留头集合。

**Interfaces:** object_trace.encode(value,kind,types)、decode(text,kind,types)、header(signature,package,token,cls,sequence=False)、wire／limit_guard；primitive_trace显式version4，原default1及V1—V3正常渲染保持。flat对象o:Type:fieldCount:length:fieldWire，最大2141，真实读取字段，旧primitive/Array/String codecs复用。

- [x] RED错tag／字段count／length／前导0／尾随／超2141／bool/int／Unicode／Array16／17，V1—V4混头、nonce／重复／错case／TCS／stderr／summary后／伪标记均UNKNOWN；新旧generated name黄金与所有声明名字碰撞覆盖。
- [x] 生成object参数构造、实际字段编码与逐字段limits；state下一调用直接使用真实上次返回，错误值整批UNKNOWN，未执行尾部不计验证。所有Host结果copy，不能把class==当结构模型比较。
- [x] 执行新／旧全trace兼容测试全PASS。实际SDK`tests/sdk/test_objects_sdk.py`覆盖struct/class、0参返回、混合普通值、最大2141 wire、String控制Unicode／Array极值、超限对象字段返回、真实溢出／下标UNKNOWN和命名碰撞。超限返回独立防御fixture明确标记，不放宽正常source gate。
- [x] SDK前源冻结，命令／日志／typed值／harness／source／case清单封存并禁止SDK／native／网络提取重建。

## Task5：四服务、草案／CEGIS、公开字段定位、交付与页面

**Files:** Modify `nexus/uploads/rule_contract.py`、`nexus/demo/rule_draft_provider.py`、`deepseek.py`、四服务、`cegis_loop.py`、`focus_service.py`、`localization.py`、`nexus/execution/delivery.py`实际缺口；Modify `nexus/web/property_view.py`、`app.py`、`nexus/demo/static/{upload,feedback,exploration,properties,relations,sequences,localization,demo}.js`、`templates/demo.html`实际缺口；Create `tests/test_object_services.py`、`test_object_feedback.py`、`test_object_gates.py`、`test_object_web.py`、`tests/objects-ui.test.cjs`、`tests/sdk/test_object_loop_sdk.py`、`test_object_cegis_loop.py`、`docs/demo/validation/next-phase-4C/browser_fixture.py`。

**Interfaces:** 沿用prepare／confirm／run／verify／feedback／accept／export；public_field反馈按spec字段，不产生whole actual_return；Focus精确typed投影重建，真正完整对象仅来自V4。每服务identity绑定object_values／object_types／object_trace及完整模型依赖／registry／core，旧档案独立重放。对象精确JSON的文本字段不改typed事实。

- [x] 先RED上传schema／draft版本5／显式preview apply、确认／registry冻结／跨会话；mock transport origin=TEST，prepare不得发送。四服务public原件和前置依赖、全历史、值深复制、fresh-hash false/int／tag／字段顺序篡改、过期core、STARTED／unknown、预检不得消费SDK或留下孤立批次。
- [x] 先RED生成与原工程projection确认／SDK日志映射，public_field不整对象冒充；限定源码方法／构造字面量，真实源码坐标与qualified method链，MCP无图时如实UNAVAILABLE。模型ctx保留真实字段／对象／完整prefix，禁止修改registry／测试／域。
- [x] 实现四服务、依赖、locator、schema／提示；跑新增和旧Array／String服务／上传／反馈／门禁／交付／userreview／race回归全PASS。
- [x] 实际SDK公开PASS→独立FAIL→参考修复PASS，覆盖Oracle＋属性／两文件method关系／对象状态；非首state＋String或Array固定context＋全历史整链一例，真实更小失败前缀。HTTP模型与图明确fixture，两轮REVIEW_PENDING、首轮UNKNOWN停止不重发；实际接受／导出／下载200，wire／public／model／registry原件篡改400→恢复200。原件source冻结封存／禁止执行重建。
- [x] UI／Flask RED对象脚手架、expected null、raw JSON导入、64位Int精确字段、Array嵌套安全回退、public_field标注、当前summary/detail UNKNOWN压过历史PASS且拒绝可用。最小实现，不改无关布局；`node --test tests/*.test.cjs`及新旧相关页面接口全PASS。
- [x] 隔离复制自建SDK原件，禁SDK／native／模型／网络；实际浏览器导入→确认只读→FAIL／更小对象前缀→PASS→仅副本篡改UNKNOWN禁止接受／允许拒绝→恢复PASS，截图／AX／零执行审计，关闭自有服务与tab。

## Task6：最终独立审阅、完整回归、封存与激活

**Files:** Create `docs/demo/next-phase-4C-verification.md`、`docs/demo/validation/next-phase-4C/{capture_evidence,replay_offline}.py`；Update本计划、spec、总目标；自有工作台账及snapshots保留。

- [x] 一次fresh最终审阅对比accepted4B310源，含完整Review Focus；Critical／Important集中真实RED→GREEN修复，Minor记录，所有declined判断形成ruling；不第二次审阅，不Git写入。
- [x] 冻结完整执行源／helper／core；`../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short`、`node --test tests/*.test.cjs`、`git diff --check`全部通过，期间不编辑冻结源。保留失败／未知整轮，不因超时放宽断言或改写原件。
- [x] 全部自建SDK／HTTP与图fixture／native／public-field／审批交付原件、实际command／harness／source封存。独立提取禁止SDK／IPC／网络按自己的冻结源/core重建；旧2／3A／3B／3C／4A／4B也各自版本全重放。
- [x] 有限配置密钥／私有成员／ZIP路径／嵌套归档扫描，明确保留已检查SDK／自建运行路径，不称普遍匿名化或干净安装。
- [x] 准备独立4C自有core副本并smoke；主站无在途才切换，表／全部记录／session／HTTP资产比对一致，旧4B可回退。4C验收后重读路线图推进4D跨包，部署5仍待实现，预算0。

## 自检与作者裁定

规格各部分对应Tasks1—6；builder重要投影缺口由Task2／5明确闭环，wire2141及registry值／签名一致。对象fields只读及constructor闭合、无registry键非授权、native新旧payload、预算与函数数均按spec执行。所有动作限CangSight，不启动无关medical Autopilot。常规阶段沿用已批准inline方式直接继续。
