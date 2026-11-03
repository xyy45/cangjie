# 第3A项验收：单次调用业务属性

2026-10-26。**3A已验收；第3项整体、3B关系、3C序列及后续语法／部署仍未完成。** 本阶段真实模型请求0、远程分析MCP请求0。模型HTTP响应是夹具；仓颉SDK、原生策略、实际函数返回与本地MCP传输分别按原件标识。

## 已实现的闭环

上传单文件或受限同包工程后，可填写／导入独立的`properties_json`。用户核对并确认，系统将其冻结为`verification/properties.json`，记录摘要与`USER_CONFIRMED`来源；模型不能修改它。旧流程留空时不改变原确认哈希。

公开测试通过后，先执行已配置的旧oracle检查；旧检查失败／未知时不启动属性检查。随后由原生核生成参数轴，在独立副本中运行固定SDK，逐个采集真实返回值，再用受限解释器判断已确认属性。SDK用例执行完成与属性满足是两个结论。

属性FAIL生成`business_property`反馈：输入、实际返回、违反的属性、断言false及其原件位置；不存在唯一数值答案时不补造expected。反例进入下一轮，后续候选回归先前已验证反例。公开测试、旧规则及属性等必需检查全部通过，才可进入审阅与交付。审批、导出和证据归档重新核验同一报告。

## 契约与边界

- v1、kind=single；Int64／Bool、0至4参数；复用现有同包和最多3个允许修改的生产文件范围。
- 原始字段为version、kind、function、domains、properties、seed、max_cases、excluded_inputs，JSON最多16KiB。每份1至8条属性，均有id、text、precondition、assertion。
- 输入别名arg0…arg3，实际返回别名result；条件和断言静态类型均为Bool。白名单AST解释，无eval或任意源码执行。
- 初始最多128次调用，最多2批缩减、每批32次；总deadline至多90秒、单批至多60秒、输出2MiB。每条属性必须有实际适用观测，不能空通过。
- 缩减保持原失败属性的前置条件，并实际重跑；不保证全局最小。初始全属性覆盖与缩减单属性覆盖分别绑定，后者不能成为整个候选PASS的依据。
- 搜索、累计与缩减均排除封存输入。与旧oracle同时配置时，不得通过新契约缩小旧排除集合。
- STARTED／中断不自动重跑。缺失、重复、错误token／类型、溢出、错误树／工具身份、日志不全或解释失败为UNKNOWN。

这些是有限输入验证，不证明任意输入正确；尚未验证成对调用、操作序列、并发、数据库、网络或外部状态。

## 真实SDK证据

四组完整运行保存于[SDK原件绑定](validation/next-phase-3A/sdk-runs-binding.json)，共7份属性报告：

| 场景 | 真实结果 |
|---|---|
| 退款标量状态 | 公开测试PASS，漏扣历史额度的候选属性FAIL；参考候选属性PASS，累计回归8组输入 |
| 两轮修复与交付 | 实际SDK反例进入第二次模拟HTTP模型请求；原生策略／本地MCP和交付归档通过；接受后篡改日志会阻断再次导出 |
| 同包跨文件计费 | 观测目标调用另一生产文件；首候选FAIL，修复只改允许文件后PASS；原测试、配置、签名和属性保持冻结 |
| 计费阈值 | 初始失败输入41，经两批真实SDK缩减到39，仍返回-1并违反非负属性；8个缩减执行，未声称39是全局最小值 |

退款首轮已经找到当前评分下不可再缩减的反例，实际缩减计数0，未为展示伪造迭代。另有真实SDK用例覆盖Bool、Int64最小值、零参数和128输入上限。

## 回归与审阅

在工程目录执行：

```bash
../.venv/bin/python -m pytest tests -m 'not live' -q --tb=short
node --test tests/*.test.cjs
git diff --check
```

完整Python结果为**874通过／1 live未运行，1082.27秒**；全部Node最终**121通过／0失败，244.059917毫秒**；diff检查退出0。见[Python原始输出](validation/next-phase-3A/final-full-regression.txt)及[Node原始输出](validation/next-phase-3A/final-node-tests.txt)。

浏览器最后发现最小UNKNOWN响应显示undefined统计。补了1项Node失败再修正提示，仅改properties.js；其后的全部Node121通过。完整Python执行对应的**全部81份Python产品源码哈希与当前一致**，见[源码对应证明](validation/next-phase-3A/python-regression-source-binding.json)，没有把展示文字调整冒充新一轮SDK执行。最终封存源摘要为`2af05ce93b95c1132f7b9be2e21ae31eab295e173d4b961a20e4e54ea7cfbf69`。

一次fresh-context整体审阅发现并修复：大Int64在浏览器中舍入、徽标沿用历史PASS、非字符串表达式触发HTTP500。精确展示文本不改内部类型／原件；候选摘要和当前详情重新verify；非法表达式在缓存前拒绝。修复前后证据见[独立审阅记录](validation/next-phase-3A/final-review.md)。未追加逐任务审阅或修改旧评测成绩。

## 浏览器验收

使用独立localhost夹具，明确禁用新模型、分析、修复与审批操作；没有用它替代真实SDK结果。

1. 通过系统文件选择器导入测试JSON与属性JSON，核对arg别名；导入不自动勾选许可。
2. 用户确认后进入上传工作台；再次打开时测试和属性不可编辑。数据库与冻结文件摘要一致，模型／工具请求均0，见[确认原件](validation/next-phase-3A/browser-confirmation.json)。
3. 查看真实SDK两轮记录：首轮公开PASS／属性FAIL，输入`[900,800,101]`实际返回901；第二轮属性PASS、回归8组。
4. 仅在派生浏览器副本中改动日志，当前报告变UNKNOWN、第二轮变待验证，下载入口失效；原始SDK归档未变。

浏览器记录从实际SDK运行复制。该测试在接受后故意改坏日志；派生展示副本曾只用原接受归档恢复该日志以展示PASS，再进行独立篡改控制。来源及摘要见[browser-results-fixture.json](validation/next-phase-3A/browser-results-fixture.json)。浏览器历史是测试入口导入，未声称是新模型运行。

![属性失败实景](validation/next-phase-3A/browser-property-fail.jpg)

![证据失效后保持未知](validation/next-phase-3A/browser-property-unknown.jpg)

## 封存与离线重放

```bash
../.venv/bin/python docs/demo/validation/next-phase-3A/replay_offline.py
../.venv/bin/python docs/demo/validation/next-phase-2/replay_offline.py
```

新归档独立保存源码、本项目原生核和4组SDK运行原件。重放重建7份属性报告，验证1个故意篡改的负控制，再从原接受归档恢复正确日志以核对原PASS。重放期间禁止网络、模型、SDK及原生IPC执行；仅借用固定SDK字节和现有Python依赖做身份核验。结果见[新报告重放](validation/next-phase-3A/archived-replay.json)。

第2项旧源码、6个真实评测轨迹、完整报告哈希仍可离线重放，见[历史阶段重放](validation/next-phase-3A/phase2-archived-replay.json)。这不构成干净机器部署验收。

归档排除.env、会话／操作凭据和SDK发行包；内部扫描没有发现当前配置模型或分析凭据的字节，不输出凭据。见[有限范围扫描记录](validation/next-phase-3A/artifact-privacy-check.json)。

## 试用与下一步

可用[退款缺陷源码](validation/next-phase-3A/examples/refund-defect.cj)、[预期行为](validation/next-phase-3A/examples/refund-goal.txt)、[公开测试](validation/next-phase-3A/examples/refund-tests.json)和[属性JSON](validation/next-phase-3A/examples/refund-properties.json)测试。选择refundState，分别导入测试与业务属性，核对后确认。

接下来按总目标实施3B成对调用关系；3C、语法扩展及干净环境部署继续保留未完成状态。新真实模型请求仍需独立数量预算。本阶段没有自动提交、推送或云部署。8877本地实例已在确认无在途操作后加载新版，原44个历史任务保留；实际入口与静态脚本核验见[激活记录](validation/next-phase-3A/activation.json)。

为继续开发3B而保持当前演示版本，8877现从`.runtime/active-stage-3A`冻结快照运行，同一持久数据／会话目录继续复用，SDK与原生核在该目录实际冒烟通过。配置只引用本机原私有文件，未加入发布归档；该运行隔离不是第5项干净安装验收，见[快照激活记录](validation/next-phase-3A/active-snapshot.json)。
