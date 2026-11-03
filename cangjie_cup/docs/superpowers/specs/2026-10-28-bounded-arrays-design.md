# 第4B项：有界Int64数组全链支持设计

状态：设计检查及Task1—3完成，数组服务／页面及最终验收尚待实施。持续授权下推进；真实模型／远程分析新预算0。8877运行独立已验收4A快照，后续开发不能编辑该快照。

## 意图与范围

支持Array<Int64>业务函数经过单文件／同包工程上传、确认冻结、公开测试、独立规则、属性、关系、显式状态序列、反例缩减／累计回归、CEGIS反馈、审阅和交付。覆盖空数组、下标、遍历求和、Int64边界和实际异常；不能只放宽类型白名单。

维持单文件64KiB／1000行／4000 token、同包工程原预算、普通函数零至4参数、最多3个可修改生产文件。Array<Int64>可与Int64／Bool／String混合，数组只是一维Int64序列；不支持嵌套、Bool/String数组、一般泛型、类、跨包、依赖下载或新的执行权限。

## 方案选择（作者依持续授权决定）

1. 仅支持JSON数组和公开测试：快，但无法贯通独立验证及修复反馈，不符合路线图。
2. 扩展受限语法、typed值和新版本契约／协议，在原服务／权限／门禁中复用执行：选择此方案，改动集中且能明确兼容边界。
3. 接入通用编译器AST或开放标准Array API：尚未核实稳定AST接口，会扩大执行与别名语义。本阶段不采用。

数组采用**按值的验证语义和只读的候选数组子集**：允许读取、比较、遍历、返回参数或新数组字面量；拒绝数组元素写入、Array构造器、复制／扩容／成员方法。SDK已证明Array存在共享别名，未验证的原地修改不能悄悄视为纯函数。此为作者的范围选择，代价是原地更新类源码须改写为返回新值；不宣称支持任意Array程序。路线图要求的空数组／下标／遍历／求和均完整覆盖，不省略返回数组、状态或验证链。

## 固定SDK调研证据

`/private/tmp/cangsight-4B-sdk-preflight-20261028`保存5组自建工程、配置、原日志与命令。真实固定SDK执行如下：

- 空数组显式注解、直接返回[]、f([])、@Expect数组／空数组，for(value in values)、while／size／index均编译执行PASS。
- 两份独立同值数组使用==为true。别名／函数返回同数组后元素赋值会影响原数组，实际断言PASS。
- HIGH+1真实OverflowException，空数组[0]真实IndexOutOfBoundsException，SDK退出1且ERROR；现有严格报告解析状态为UNKNOWN，不误记为业务FAIL或PASS。调研脚本起初expected_state写FAIL只是预期假设，原件保留，产品未为迁就它降低UNKNOWN边界。
- 无模型、远程6240或主站用户任务执行。固定SDK／stdx／compiler／core身份沿用4A记录；后续改core产生新身份，不能复用旧报告作新引擎证明。

## 值、语法与别名边界

- 类型名规范为`Array<Int64>`，JSON为原始list、长度0—16，每项必须type int且在Int64范围；拒绝bool、float、str、tuple、嵌套list、null及第17项。参数／预期／模型常量及中间数组均检查。值进入边界后复制，key转为typed tuple，不把list放进set或依赖Python的True==1。
- Array权重为`len(value)+sum(abs(item) for item in value)`，空数组0；与String字节权重、数字绝对值共同构成确定缩减顺序，不保证全局最小。评分使用Python整数，不声称其自身是候选Int64算术。
- 候选语法：Array<Int64>参数／返回／局部声明，[]或[expr,...]最多16个Int64表达式；下标array[Int64]返回Int64；`.size`返回Int64；for(name in array){...}只迭代Int64，局部作用域禁止遮蔽。while原语义保留。允许同类型结构相等／不等，不允许排序、数组+、切片、范围／推导式或一般成员。
- 下标负数／越界由SDK判断；语法门禁只检查索引类型，不能声称静态证明边界安全。Int64溢出仍由SDK真实执行；异常产生UNKNOWN并阻止后续修复／交付。
- 不允许任何array[index]=value，不允许Array的一般成员方法；所有允许同包函数也受同一门禁约束，不能经helper绕过。返回别名只在无写入语法下安全；验证输入／expected／before_state仍独立复制，防止宿主层共享list污染。
- 工程测试继续只接受完整字面量@Expect；新增数组字面量与typed比较，原测试内容和测试ID不可修改。生成公开测试使用已验证的[]／[int,...]形式；纯数值／String输出源码字节不变。
- 16元素是确认值／模型／观测返回的边界，不是候选进程所有分配的硬堆限额，继续现有沙箱／超时／输出限制。

## 契约、表达式、搜索与原生轴

- 签名含数组时仅Oracle version4、single property／relation／sequence version3；即使同时有String也使用数组版本。String而无数组维持Oracle3／其余2，纯数值旧版本不变。算法标识为boundary-array-v4、single-properties-array-v3、paired-relations-array-v3、state-sequences-array-v3。
- Array参数域`{"values":[[],[1],[1,2]]}`为1—16个明确数组，逐项typed核对、重复域拒绝、合法轴顺序保留；每个数组≤16。String既有values域、Bool{}、Int64 min/max/points不变。初始数组状态与参考后态须在确认的状态域；不自动把生成草案当已确认的域。
- 新版本表达式使用独立allow_arrays标志，可保留String能力；新增最多16项Int64 AST list字面量以及array_len(x)、array_at(x,i)、array_sum(x)、array_append(x,n)、array_replace(x,i,n)。参数个数严格；所有返回新数组，禁任意对象／属性／Python eval／slice／负下标／生成式。array_sum按顺序逐步Int64 checked加法；array_at/replace下标必须0≤i<len。array_append超过16拒绝；String仍≤256字节。
- 规则比较Array仅结构==／!=；条件严格Bool，算术严格Int64，分支静态同类型。规则中的溢出或越界为模型不可验证，预检时拒绝／重放UNKNOWN，不伪造候选业务错误。
- shared typed_key／input_key保证嵌套输入向量可用于排除、累计、缩减、乱序／重复检测；旧数字／String采样顺序、同seed得分与V1/V2正常harness字节有golden保护。
- 原生仓颉boundary.axes新增Array<Int64>分支：校验values1—16、数组0—16、元素Int64／非Bool、重复域拒绝且合法轴保留次序。Python消费方完整typed重建对照；IPC包络仅绑定请求／组件，不声称密码签名。
- 仅预算内计划、实际缩减、既定公开示例和保留历史输入预检；不枚举完整Int64域。搜索数组只选域内值，缩减只选确认域中更小值；不会把域外元素删除／数值改变隐式当合法样本。所有历史前缀（含先前STARTED／UNKNOWN）维持既有阻断语义。
- Oracle16—256 case、单次16—128、关系既有双调用预算、序列16轨迹／8步／128计划调用／两批8轨迹缩减／8保留失败前缀与历史并集上限不变。状态可为Array，操作参数及上下文可混合，模型必须Markov／同输入转移一致；完整前缀、初态可达和真实上步返回值不能替换成预期状态。

## V3观测与独立复验

- 任何Array签名显式使用NEXUS_ORACLE_V3|／PROPERTY_V3|／RELATION_V3|／SEQUENCE_V3|／SEQUENCE_END_V3|及VALUE_ERROR_V3|；V1/V2解码器也识别这些保留前缀并在错协议／位置时UNKNOWN。
- Int64／Bool沿canonical表示，String沿s:小写UTF-8 hex。Array token为`a:<count>:<canonical signed integer,...>`，例如`a:0:`、`a:2:-1,2`。长度必须和项目数一致，无空格／+号／前导0／-0／尾分隔符，不允许十进制bool或第17项。解析前检查文本长度≤340，逐项严格Int64。
- 固定SDK harness真实遍历返回数组生成token；只检查size不超过16后再编码。越界返回标记VALUE_LIMIT，整批UNKNOWN；不截断、不降级用Python预测代替实际观测。字符串继续guard256。
- 保留已接受V2的nonce、case完整集、执行summary、STDERR／未知前缀／重复／错case／错step／汇总后／TCS混淆等检查。生成名字与上传函数／参数避名，包级函数引用防case0遮蔽。每条观测保留真实完整日志坐标。
- Array状态与返回结构比较，既定输入、参考前后态、实际前后态分别复制；关系左右调用分别提供独立输入。首次状态偏离停止尾部，未执行调用保留计数，不计作已验证。

## 服务、反馈、权限、页面

上传／工程索引／requirements／WorkspaceStore冻结新值和版本；草案schema／提示支持Array，但仍需用户确认。DeepSeek上下文说明数组只读子集、16元素、正确版本和实际typed反例，不能修改测试／域／配置／范围；HTTP模型与图夹具明确标识，真实预算0。

四服务重建绑定新值／协议／表达式依赖和新core身份；规则先于属性／关系／状态，公开测试必须先通过。缩减前预检不可遗漏；异常／未知／重启／取消不自动重发。审阅／导出／归档／下载必须复验当前证据；旧结果因引擎升级失效时明确UNKNOWN，旧冻结版本档案保持可重放，不承诺透明迁移。

页面Array参数初值[]、expected仍null待核对；canonical JSON展示嵌套数组、空数组及大整数，保持原始typed数据；String转义规则不变。导入、显式草案应用、确认只读、epoch／旧响应、候选摘要详情冲突和拒绝路径复用。浏览器需真实导入并复核当前FAIL／PASS／篡改UNKNOWN，保持主站用户数据不作fixture。

## 验收、隔离与未覆盖能力

使用4A冻结288源作为基线，任务逐步RED→GREEN并保留真实SDK／native原件。验收至少包含：漏最后一项求和／空数组；两文件下标边界／重复值属性与关系；Array显式状态交换／重置且真实前态链；数组返回17项、非法编码、空数组越界、Int64溢出UNKNOWN。自建参考修复不算真实LLM能力。

一次fresh全阶段审阅、集中重要修复、冻结后全量not-live Python／Node／diff、最终源／core／原件归档、禁止执行／IPC／联网独立重放；旧2／3A／3B／3C／4A按各自版本复验。有限凭据／成员／路径／嵌套ZIP检查保持原日志，明确路径保留与扫描限度。主站维持独立4A，4B验收后当前无在途时切换新自有core快照，原用户数据／session／记录保持，不改.git／commit／push／reset／clean。

数组API／原地更新、嵌套数组和对象／跨包仍未支持，采样不证明全语义，部署／干净安装仍为第5项。以上范围选择不需要重复产品批准；真实付费请求／外部发布仍需单独授权。

## Builder检查结论

一次只读检查完成，未留需要用户回答的重要问题。最坏wire长度已从初稿326修正为340，并计划16×LOW往返控制；域重复统一为拒绝而非静默去重，合法域维持次序。17项返回控制为绕开候选门禁的独立防御fixture，不放宽产品字面量长度；未执行第二次builder检查。
