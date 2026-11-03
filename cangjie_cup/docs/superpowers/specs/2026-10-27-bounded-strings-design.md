# 第4A项：有界字符串全链支持设计

状态：Task1—6已完成，完整回归／归档重放通过且8877已激活独立4A。详细证据见docs/demo/next-phase-4A-verification.md。后续数组等子阶段单独实施，新增真实模型／远程分析预算0。

## 意图、目标和不做的内容

让仓颉业务函数的字符串输入／输出能够经过上传、用户确认、公开测试、独立规则、属性／关系／状态序列、反例反馈、修复、人工审阅与交付。用空值、Unicode长度及精确令牌拼接缺陷验证能力，不用模型自评作PASS。

仍为同包受限普通函数，最多4个参数（普通函数保留零参数，序列至少一个显式状态参数），16函数，允许修改1—3个已有生产文件；String与Int64／Bool可混合。不开数组参数／返回、类／结构体、跨包、导入、任意成员或脚本。`.toRuneArray().size`是专用长度操作，不开放Rune／Array值。

## 方案取舍（作者按持续授权选择）

1. 仅放宽String上传与公开测试：改动少，但独立规则及反例链断开，不满足本阶段。
2. 在现有受限解析、类型化契约、原生轴和日志验证中兼容扩展：复用权限／存储／交付；需要逐项处理旧协议兼容。选择此方案。
3. 改为通用编译器AST或任意执行：尚无已核实的SDK/MCP AST接口，会扩大执行权限并引入不同工程，本阶段不采用。

## 固定语义与资源

固定macOS ARM64／SDK1.0.5／macOS15.4 SDK，依赖版本不变。独立真实SDK实验的1个case／16断言已通过，原件见 `docs/demo/validation/next-phase-4A-preflight/`；不是已实现支持。

- 每个输入、输出、源字面量及规则中间String最多256 UTF-8字节（空串允许）；合法Unicode标量序列，拒绝单独代理字符。不自动规范化Unicode或去空白。
- 源码 `s.size` 等于UTF-8字节数；`s.toRuneArray().size`等于Unicode码点数；均为Int64。组合重音不是字素。String只支持 `+`、`==`、`!=`，不开放排序、下标或一般方法调用。
- 普通双引号字面量允许已验证的换行／回车／tab／引号／反斜杠及 `\u{...}` 转义。上传源码不接受插值、原始／多行字符串；不能用包含括号或注释标记的文字伪造函数调用。
- JSONString允许NUL／控制字符但必须按JSON转义，和256字节限制同时检查。源文件本身的控制字符限制不放宽；解码后的字面量按字符串值检查。
- JSON→Cangjie源码统一逐Unicode码点转义，包含美元、反斜杠、引号和换行时仍不能插入表达式。旧Bool／Int64字面量字节保持不变。
- 保持64KiB／1000行源文件、2MiB／100文件工程、公开2—12例且target／regression均有、1—4参数及已有验证预算。不得因String引入无界笛卡尔积、循环或自动请求。

## 分层接口

### 共享值语义与解析

新增小模块 `nexus/repair/values.py` 承担 primitive(value,kind)、string(value)、UTF-8字节／码点长度、typed_key、primitive_weight与源码String字面量编码，不做执行。返回原typed值，不把Int64变浮点。类型严格区分Bool／Int64／String。数值旧路径的值、顺序、得分及序列化保持golden。

`nexus/uploads/language.py` 扩展受限token／类型推导。词法必须完整扫描字符串，不用去注释后再正则；两遍解析中字符串里的括号／大括号／注释不影响结构。String字面量、String参数/返回、同包函数调用、赋值、if／while及上述专用长度链均检查类型。拼接仅String+String；比较不允许混合类型。拒绝任意字段、方法、函数值、导入、宏、插值、overload及新I/O入口。编译器仍最终决定实际编译。

项目索引／上传测试解析（`nexus/projects/`）同样复用安全String字面量解码，不只更新单文件路径。声明和原测试被保护；参考修复不进入模型上下文。

### 域、规则与版本

String域严格 `{"values":[...]}`，1—16个唯一、有序、合法有界String；这是明确枚举域，不代表所有256字节以内的字符串。Bool域仍{}；Int64仍min/max/points。公开示例可位于域外但必须类型和长度有效；旧各契约是否要求示例在域内的规则不改变。字符串保留输入沿用当前精确typed排除及128总量上限。

含String的独立规则只允许version3（含excluded_inputs，允许空列表），algorithm `boundary-string-v3`；单次属性version2／kind single／algorithm `single-properties-string-v2`；关系version2／原kind／algorithm `paired-relations-string-v2`；序列version2／kind sequence／algorithm `state-sequences-string-v2`。字段集合除version与由签名决定的域外保持既有结构。String签名不得提交旧版；纯数值／布尔继续既有版本，不悄悄改写旧契约和harness。

表达式语法增加有界String常量、String+String、同类型==/!=及 `byte_len(x)`／`rune_len(x)`（String→Int64）；不支持String排序、格式化、索引、属性访问或其他调用。条件仍严格Bool；min/max/ceil_div仍仅Int64，分支两侧同类型。数值旧版本不获得String能力或新辅助调用，避免旧语义静默扩张。

需要重用安全AST检查、类型检查与求值，在显式String版本上下文启用。现有 oracle.expression_tree(text,names) 为旧调用保留默认旧语义；扩展可选类型／版本上下文，不用eval或exec，不通过“看见字符串字面量”自动选择新版。验证新模型预检的是预算内即将执行的生成／缩减／历史回归输入，以及原契约要求检查的公开示例；不是整个Int64域或其笛卡尔积。关系双方与序列实际规划可达前缀均逐项预检，所有匹配操作模板仍须一致。保持现有结构化4096／随机4096等原候选尝试上限和各验证条数上限，不能为了“预检全部”无限枚举。矛盾／溢出／中间值超限属于模型错误，待执行批次在SDK前失败；未采样语义不作保证。

### 搜索、缩减与仓颉核心

原生 `boundary.axes` 增加String分支，严格验证values字段／类型／唯一性／256字节／16值，并按确认顺序返回JsonString轴；Int64/Bool输出和拒绝规则保持。Python独立重建全typed轴并检查原生proof／组件身份，不将空或错误包络当PASS，也不绕过原生核。

新String版本搜索以枚举值为轴，随机阶段使用同一seed的有限选择；历史有效反例优先，保留输入不得执行。缩减只使用已确认域内的更短String值，不从任意中间状态启动序列，不声称全局最小。混合值权重：Int64绝对值、Bool0/1、String UTF-8字节数；平局按严格typed规范key决定。序列首先比较步数，再权重，再规范key。旧numeric算法、顺序和score保持原样。

关系左右调用可含String，只有实际观测才能证明关系。序列允许String显式状态或上下文，但状态返回同类型且参考后态必须属于状态域；Markov转移只依赖可见state/arg，匹配同完整输入的多个操作参考结果必须一致。初始状态、16轨迹／8步／128调用、两批8轨迹缩减、8保留失败前缀与全历史并集约束保持3C；超预算／未知立即停止。

### SDK观测协议与独立重建

纯Int64/Bool契约维持原V1 harness字节和解码。任何String签名使用独立V2协议：`NEXUS_ORACLE_V2|`、`NEXUS_PROPERTY_V2|`、`NEXUS_RELATION_V2|`、`NEXUS_SEQUENCE_V2|`、`NEXUS_SEQUENCE_END_V2|`。所有类型值作为独立token：Int64／Bool沿canonical原表示，String使用 `s:` 加小写UTF-8十六进制（空串为 `s:`）。不把String原文直接放入日志控制字段。

harness中String输出编码使用已验证toArray字节遍历，固定十六进制字典／无外部依赖；返回超过256字节时输出保留的 `NEXUS_VALUE_ERROR_V2|token|caseI|VALUE_LIMIT` 标记后结束，整个批次UNKNOWN，不能截断为PASS/业务FAIL。编码辅助函数／变量名要与上传函数和参数避名。

decoder验证当前expected的完整SDK case集合和success summary；值必须canonical、偶数小写hex、不超512hex字符、严格UTF-8、无代理、不允许非法或过长编码。String中的伪造协议、换行、Summary文本没有解析权限。V1/V2所有保留前缀在错误kind／STDERR／汇总后／重复／错误token／错误case或step中都UNKNOWN。实际序列前态必须严格等于上步实际返回，首次模型偏离停止尾部；完整SDK协议检查先于业务解释。每条观测绑定实际case／step及完整日志字符坐标。

独立规则version3同样使用oracle-kind的V2观测（NexusOracleV2+token的实际SDK类/case），Python将typed实际返回与已确认expected比较；不再依赖SDK失败消息中String的引号／换行格式。旧oracle v1/v2仍保持BoundaryTests和原harness字节。新版batch保存token、观测及完整日志绑定；失败记录沿用kind independent_rule及真实test_id/args/oracle_hash，expected/actual为规范JSON文本，另保留expected_value/actual_return typed值和source。通用SDK报告解析只负责执行状态和完整case集合，String业务失败必须来自受控编码观测，不能用字符串内伪造的Summary/CASE作依据。公开测试仍用受信任@Expect，但必须验证原expected case完整集合；恶意控制字符诊断导致无法归属时UNKNOWN，不放宽parser来接受。

### 服务、模型、门禁与UI

UploadService／Requirements／WorkspaceStore冻结新typed公开测试与契约，原始String JSON不先eval或规范化；草案仍需用户确认。DeepSeek上下文携带确认的String规则、完整typed反例和实际SDK失败；模型无权改测试／配置／契约。草案模型protocol和修复JSONschema保持结构兼容，提示根据签名说明String界限和新版本，全部真实联调使用显式HTTP夹具，预算0。

原有服务绑定所有新value/encoding/contract源码依赖及新core组件身份；search／shrink／累计回归／超时／取消／恢复／原件篡改的复验门禁沿用，不新增跳过前置项。String配置后的顺序仍公开→oracle→property→relation→sequence；无配置项跳过。接受／导出／归档／下载必须当前证据有效。

前端上传String参数初值为 `""`，Int64／Bool保持旧默认，expected仍由用户核对。导入文件、epoch、确认只读逻辑复用；canonical JSON text字段增加String并以带引号转义形式显示空串／控制字符／Unicode，textContent渲染，不用innerHTML。候选摘要/详情不一致UNKNOWN，接受禁用；已知当前待审候选仍可拒绝。无新增执行或许可接口。

### 兼容、原件与主站

构建新core只修改开发目录 `.runtime/core` 及构建metadata；8877的独立3C快照含自有core和源码，不覆盖。新core会改变当前引擎绑定，旧开发报告可能失效；旧第2项/3A/3B/3C均保留自有源码/core/原件复验，不承诺透明迁移。

各任务先真实RED再最小实现与对应兼容测试。最后一次fresh全阶段审阅；集中修复Important，Minor记录不顺便扩展。最终冻结源码后全量非live Python／Node、真实SDKString公开测试／观测／四种可选验证／CEGIS及审批交付门禁，封存禁SDK/IPC/联网重放；旧阶段仍用各自原件重放。

无真实DeepSeek/远程分析质量声明；真实预算另行明确授权。用户真实数据不作为测试夹具，不读写凭据或上传原文到外部。有限归档扫描允许保留已说明的SDK/core路径，不能修改日志／core字节冒充脱敏。

## 验收例子与失败界限

1. UTF-8长度门槛：中文令牌按码点限制，错误实现用size字节；公开正常ASCII通过，String规则／属性发现中文边界。
2. 两文件精确凭证：helper拼接缺分隔符造成两个不同输入相同票据；String关系实际双调用发现，修复后回归。
3. String显式状态：从空串依次追加许可的短操作码，参考转移与状态域有限，错误拼接两次漏字符；前缀实际链与缩减均SDK证明。
4. 空串、引号、反斜杠、美元插值形状、NUL、换行、协议形状、组合Unicode及256/257字节、非法hex/UTF-8和单代理字符控制；非法模型不能消费候选运行。
5. 身份/权限/范围、保留输入、原件改动、未知停止、无真实请求、旧数值输出golden都通过。有限枚举域和有限测试不等于任意字符串业务或全语义证明。

## 留给实现者的常规选择

小函数命名／测试fixture组织和必要的安全辅助模块拆分可自行决定；不得扩大上述操作／类型／权限。若实际固定SDK不支持所需编码或编译语法，应保留真实失败证据并缩小方案，经设计更新，不伪造返回。重要业务语义变更才需要用户澄清；常规阶段不重新询问确认。

## Builder检查结论

唯一重要问题为“有限输入”是否要求穷举完整Int64域，现已明确仅预算内实际计划和既定公开示例，逐输入预检、超限失败、不扩大验证保证；是作者按原有限验证范围作出的澄清，不改变用户业务要求。没有需用户决定的新增事项，不进行第二次builder检查。

执行范围澄清：256字节约束覆盖确认输入／预期输出／字面量和模型中间值，V2观测将检查候选返回；不声称给候选函数全部中间分配施加硬堆内存上限。候选仍使用既有沙箱、超时与输出限额，不引入未验证的进程资源保证。

Task3接口澄清：primitive_trace保留read名称并显式version=1默认；case_ids新增可选signature来匹配同名测试类的实际Value后缀。Oracle-kind仅V2允许且保持现有256 case预算；single／relation仍最多128实际case，sequence仍16轨迹／128计划调用，不把String接入缩小已有规则预算。V2成功属性观测增加source，V1报告字段与正常harness字节保持。
