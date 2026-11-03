# 有限结构体／类设计（第4C项）

状态：一次builder检查完成，作者接口裁定已补齐；既有持续授权覆盖常规阶段，不重复八节确认。尚无4C产品修改。基线为已验收4B的310冻结源87a61970010d98f471d8b81a2af7723af255b874636522e5de5458c29486dc47；8877独立4B及自有core31f1...保持。

## 意图与验收目标

支持仓颉订单／退款等具有有限字段的struct和class，通过普通顶层入口调用已声明的实例方法，传入和返回结构化对象。贯通源码／工程上传、公开测试、用户确认的独立规则／属性／关系／状态序列、实际SDK观测、反例／缩减／历史、CEGIS、人工审阅与交付。不是仅接受class关键字或把对象转成字符串修复。

SDK调研3case实际PASS：struct数值字段复制、class引用别名、struct内Array仍共享引用。原件在.superpowers/sdd/2026-10-29-bounded-objects/sdk-recon-originals.zip。调研允许var／mut用于观察语言事实，不表示产品子集开放这些写入。

## 方案与取舍

1. 仅平铺为多个Int64参数：不满足对象入出参及方法调用，排除。
2. 沿现有受限解析器增加声明注册表、明确构造与纯实例方法，对象在验证边界按字段快照：采用。复用现有服务，不引入新进程／库。
3. 全编译器AST／一般可变对象图：当前未验证稳定SDK解析集成；继承、循环引用、共享身份会扩大验证契约，本阶段不采用，不声称任意面向对象程序已支持。

作者裁定：同时支持有限struct及class，字段为public let；构造仅绑定参数到字段，方法只能读取字段和返回新对象。禁止字段写入、mut、可变class API和数组元素写入，故允许的class引用身份不可被修改操作观察。验证比较是声明类型＋字段值的结构比较，不冒充仓颉默认class的==语义。代价：原地修改对象的程序须改写为显式返回新状态；后续若支持共享身份，必须新设计而不能静默放宽本契约。

## 有界声明与语法

- 延续单文件64KiB／1000行／4000 token，工程2MiB／100文件、最多3个允许修改的已有生产文件、同包与固定SDK1.0.5。顶层函数与实例方法共享每文件16／工程128个函数体预算，参数0—4；构造体另受4类型上限及闭合赋值语法约束；不增下载／网络／文件／进程权限。
- 一个同包工程至多4个具名对象类型；类型、字段、方法名为ASCII普通标识符，最多64字符，拒绝内置／预留名及跨命名空间歧义、重载。每类型1—4字段、0—4纯实例方法。
- 字段仅Int64／Bool／String／Array<Int64>，沿用严格Int64、String≤256 UTF-8字节及Array≤16个Int64；不含对象字段／对象数组／Option／泛型／继承／接口／静态成员／属性／宏／扩展／顶层初始化。
- `public struct Name { public let field: Type ... public init(field: Type,...) { this.field = field ... } public func method(...): Return { ... } }`；class同形。一个public普通init，参数名称／类型／声明顺序与字段完全一致，且函数体仅按顺序一次赋值全部字段，不含调用、分支、运算或初始化副作用。
- 允许构造Name(args)、obj.field读取、obj.method(args)、this.field／this.method、普通同包调用、局部变量／if／while／for／返回，沿已有表达式子集。实例方法参数0—4、返回既有值或已声明对象；不支持直接选择方法作为上传修复入口，使用顶层包装函数。
- 所有生产文件、方法体、构造体都验证，不能把未选择的方法当漏洞出口。对象==／!=不开放；可逐字段比较。拒绝对象／字段／方法名称遮蔽以及对象一般成员访问。禁止实例字段赋值及数组元素赋值；局部整值重新绑定仍允许。
- 类型声明、字段顺序／类型、构造体、方法与顶层函数签名在上传确认和候选比较中冻结，允许修改范围内的方法体／顶层函数体可修复。不能修改测试、模型、域、类型身份或额外新增文件。原工程TestParser增加闭合构造字面量，仍保留原测试ID／原文和全部配置。

## 注册表、JSON及类型身份

- 新的`nexus/repair/object_values.py`提供闭合注册表校验和值工具；源码声明解析放`nexus/uploads/object_types.py`，避免通用values依赖上传服务。注册表形式：`{Name:{kind:'struct'|'class',fields:[{name,type}],methods:[{name,params,return_type}],constructor:[{name,type}]}}`，仅上述键；规范化时类型／方法按名字排序，字段与构造保留声明顺序。
- `inspect_source`／同包项目索引增加可选types注册表；只有签名入出参包含对象时，所选signature增加types。无对象签名保持原字节／模型版本；源码里存在对象但顶层入口只收返普通值，可使用原协议验证实际返回。生产声明门禁仍生效。
- JSON对象值必须恰为`{"$type":"OrderState","fields":{"amount":100,"refunded":0}}`；字段集合精确匹配声明，拒绝漏／多／错类型／null／嵌套对象及Bool冒充Int64。类型tag不可省，字段JSON输入顺序不改变语义，规范输出按声明顺序；每个对象边界返回新dict及新Array。
- object_values接口：registry(raw)、is_object_type(kind,types)、value(raw,kind,types)、typed_key(raw,types)、weight(raw,types)、literal(raw,kind,types)、has_objects(signature)。typed key含声明类型名和逐字段带类型的值，不能依赖Python True==1／共享dict／JSON顺序；weight为字段值既有权重之和，名字固定不计权。
- 现有primitive(value,kind)增加可选types=None；无types保持旧行为。oracle.input_key及共享键工具在明确object tag情况下使用严格对象工具，业务契约在接纳前始终用完整registry校验，不由tag自行授予类型。域为1—16个不同完整对象，非法／重复拒绝，原顺序保持；组合空间仍按既有预算采样，不穷举。

## 模型与实际执行协议

- 签名含对象时Oracle version5，single／relation／sequence version4；优先于Array与String。算法分别boundary-object-v5、single-properties-object-v4、paired-relations-object-v4、state-sequences-object-v4。无对象的版本及正常harness字节保持。types来自冻结源码，不允许模型JSON另给声明注册表。
- AST以独立allow_objects／types环境扩展，不开放Python Attribute／eval／任意dict。新增object_get(value,"field")、object_with(value,"field",replacement)、object_new("Type",fieldValue1,...)。类型名／字段名须为编译期String常量，参数数目和结果类型按registry检查；普通String长度、Array helper仍可嵌套。所有对象结果独立复制，字段级溢出／越界／超限在实际计划及缩减前检查。
- typed模型对象==／!=比较相同名义类型的字段结构；不同对象类型拒绝，而不是把默认SDK对象身份比较当业务规则。构造参考状态可用object_with／object_new；状态类型必须与入口返回相同，初态和参考后态在确认域内，真实下一步使用上一步实际返回。
- 新V4保留头覆盖ORACLE／PROPERTY／RELATION／SEQUENCE／SEQUENCE_END／VALUE_ERROR，V1—V3遇错版本头均UNKNOWN。普通值沿V3编码；对象为`o:Type:fieldCount:`后逐声明字段拼接`length:fieldWire`。length为ASCII wire字符数、无前导零；字段按schema解码，不递归对象。类型名≤64、字段最多4，每字段String最大514字符，整个对象最大2141字符；超限／尾随／错tag／错字段数／非规范长度均拒绝。
- SDK编码器逐字段读取实际对象，逐字段String／Array guard；任一不合法则整批VALUE_LIMIT／UNKNOWN，不截断、不用模型预期补值。命名与构造器／字段／方法冲突测试覆盖；生成器不能调用用户一般toString／equals／getter，字段为直接public let。
- 原生boundary.axes对声明对象域及每个字段完整typed验证，返回原顺序对象轴；Python独立对照。新core身份进入所有服务和交付绑定；IPC证明不称数字签名。公开测试及四服务实际SDK一律新独立候选副本，旧阶段按各自冻结源/core重放。
- 预算不增：Oracle≤256，single≤128，relation原上限，sequence≤16轨迹／8步／128计划调用，缩减／历史并集原上限。所有inputs／左右调用／初态／实际前态／参考后态／失败摘要与观测须独立深复制；先修复4B已知失败摘要数组alias，并新增双向修改否定控制。

## 服务、定位与页面

- 上传／草案schema、显式应用与用户确认冻结；公开测试、规则、属性、关系、状态模型互相绑定。四服务完整检查版本、声明registry、core、harness、日志、源树和全历史；fresh-hash类型篡改、过期core、未结束STARTED、未知结果均不交付。
- DeepSeek上下文明确对象格式、冻结声明、允许纯方法和不可修改测试；canonical JSON反例保留对象字段值及完整前缀。对象定位只识别闭合构造字面量和受限方法位置，能绑定才标确认，图不覆盖则如实降级；不捏造MCP对象分析能力。
- 页面给出具名对象脚手架（按字段类型生成初值），expected继续null待核对；导入保留原JSON text，服务端提供对象／嵌套Array／Int64精确显示，缺canonical文本不得舍入。确认只读、epoch、跨会话、当前summary/detail冲突及拒绝路径复用。
- 新付费模型／远程6240预算0；模型HTTP与图均明确fixture，SDK／native／stdio真实执行分别记账。不能把自建参考修复／HTTP fixture当模型能力。主站4B不作fixture或中途升级，4C最终完整验收后才切换。

## 验收证据与下一步

1. 值／registry／源码／工程／公开测试：同名错tag、字段遗漏／多余、Bool混入、String／Array边界、构造器副作用、隐藏可变方法、签名变化拒绝；跨文件type/method调用和原测试保护。
2. 模型／native／搜索／缩减：相同字段不同具名类型、Unicode字段值、极值Array字段、反例深复制、实际计划预检与不可达／矛盾状态；原生对象域及篡改证明。
3. V4真实SDK：struct／class参数返回、方法修复、对象字段异常UNKNOWN、构造与生成名碰撞、非首对象状态＋固定String或Array上下文＋跨候选完整历史组合一条整链，不只分层拼接证据。
4. 四服务公开PASS→独立FAIL→参考修复PASS，真实缩减及全历史；显式HTTP模型／图夹具的两轮循环与UNKNOWN停止、实际接受／导出／下载200、原件篡改400→恢复200。
5. 浏览器真实导入／冻结／只读／FAIL／更小对象前缀／PASS／篡改UNKNOWN及拒绝／恢复；隔离副本、外部执行禁用、审计0；不用主站用户数据。
6. 一次fresh最终审阅与重要修复，冻结源/helper/core后完整not-live Python／全部Node／diff检查通过；所有新自建原件封存并提取独立重建，旧2／3A／3B／3C／4A／4B均用自己的版本重放；有限密钥／私有成员／路径检查，空闲切换并比对原任务／session。只标4C，4D／5仍待实现。

留给builder：检查现有API衔接、registry传播／循环导入、wire上界及完整验收是否可实施，提出影响真实行为的缺口；普通实现细节由作者裁定，已批准阶段不重复向用户征询。


## Builder检查后的作者接口裁定

一次只读检查完成，无需用户决定的问题。wire最大2141经检查成立。重要接口缺口为对象公开测试表示，按以下一致协议落实后写计划，不二次审阅设计。

### 对象公开测试与字段观测

- 上传生成测试：每case先将入口返回保存在不可冲突的生成名局部中，只调用一次。对象按声明字段依次断言；Int64／Bool／String直接比较，Array字段先比较size，再仅在size等于预期时比较每项。禁止用class默认==实现结构比较；harness保留字集合覆盖全部类型／字段／方法／函数及参数。
- 工程原测试允许闭合`@Expect(entry(Constructor(literals...),...).field, literal)`，仅单层已声明字段；仍可保留既有普通返回值调用形式。直接`@Expect(objectExpression, Constructor(...))`拒绝并提示字段投影，禁止一般表达式、任意getter、方法链、对象比较、变量测试或循环测试。未修改原测试内容和SDK case ID。已有普通值项目case metadata不增字段。
- 新投影case在原`function/args/expected/id/path/line`之外添加`projection:[fieldName]`与`expected_type:fieldType`，完整返回类型从冻结signature读取；expected仅为投影字段值，不能伪造成完整对象。TestParser和候选索引对照这些冻结字段。
- 上传生成对象测试的可信case metadata来自确认对象示例；日志映射可生成更细路径`[fieldName]`／`[fieldName,"$size"]`／`[fieldName,index]`（index0—15），分别标定真实叶值与预期叶值。仅识别与冻结生成模板或原项目字段投影完全匹配的断言，不由任意字符串猜函数／字段。
- 新公共反馈`kind=public_field`携带function、完整typed args、projection、expected_type、expected_value、actual_field_value、SDK case与原日志坐标；不填actual_return为整对象，不补造其他字段。FocusService.confirmed_cases与localization按投影预期及typed叶值重新匹配，标注FIELD_OBSERVATION，未知投影保持UNMAPPED。实际完整对象返回仅来自V4独立验证观测。
- 所有新对象参数／预期值经冻结registry验证后规范复制；保留用户原JSON文本及source hash。global input_key／typed_key可对带tag的闭合字段结构生成稳定排序键，但这种无registry键计算绝不视为类型验证；primitive对象入口必须显式给registry。

### 原生、字节预算和兼容性

对象轴请求仅在has_objects时为`{domains,types}`，types为冻结registry的值语义投影（kind、fields），不含方法body／任意模型声明；普通请求严格保持`{domains}`原形。native与消费方同时校验确切键、具名tag／字段及原顺序。原JSON／IPC总字节限制保持，超出则明确拒绝或UNKNOWN，不自动扩大预算。

已有4B失败摘要数组共享列为本阶段Task1首个TDD缺陷修复，不作历史4B原件重写；活跃4B仍使用自己的原冻结源。
