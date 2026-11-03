# 仓颉业务缺陷合成基准 v1目录／sealed协议v2

`v1-30/`保存先验收的30种业务上下文，`v1/`保存扩展100任务。100任务覆盖30个family，包含70个明确标记的参数／命名变体，并非100种独立语义缺陷。每个任务由团队编写，不是工业数据集，也不代表模型实际修复率。

每个`tasks/business_NNN/`包含：

- `task.json`：业务族、变体、入口函数和允许修改文件。
- `public/`：原缺陷工程、goal.txt、examples.json，可发给修复模型。
- `private/rule.json`：确定性搜索规则v2，包含严格类型的保留输入排除集合；数据本身不进入模型源码上下文。
- `private/grading-rule.json`：未过滤的v1业务规则，只用于最终验收和数据质量验证。
- `private/holdout.json`：循环结束后的固定验收输入与预期；不进入任何修复反馈。
- `private/reference/`：人工编写参考修复，仅作数据质量验证，不发给修复模型。

搜索规则冻结时保留全部holdout输入，正常搜索、缩减、累计反例和证据重放均禁止使用这些输入。加载器要求排除集合与冻结holdout完全相等；模型得不到保留输入及最终验收结果。最终验收使用单独未过滤规则。holdout与搜索共享业务规格，仍不是独立工业分布或未知语义评测。对照实验比较的是是否增加静态MCP和主动搜索反馈。

对于只有一个失败输入的一元边界缺陷，封存该输入可能使主动搜索没有能揭示该缺陷的剩余输入；这类任务只提供目标业务修复与保留输入验证证据，不证明主动搜索的发现能力。价格、随机种子、模型和预算需要随真实实验保留。

在CangSight-Nexus-Demo目录运行（macOS固定1.0.5 SDK与现有Python环境）：

```bash
# 不请求模型：查看数据及最大请求预算
../.venv/bin/python -m nexus.benchmark list
../.venv/bin/python -m nexus.benchmark plan --tasks business_001,business_030 --modes direct,mcp,cegis --max-model-requests 18

# 不请求模型：真实SDK验证缺陷和参考修复，输出目录必须不存在
../.venv/bin/python -m nexus.benchmark quality --output .runtime/my-quality-run
../.venv/bin/python -m nexus.benchmark verify-quality --output .runtime/my-quality-run

# 会使用本地私有DeepSeek配置并请求真实模型，先明确调用预算
../.venv/bin/python -m nexus.benchmark run --tasks business_001,business_030 --modes direct,mcp,cegis --max-model-requests 18 --output .runtime/my-live-run

# 只重建报告，不请求模型；按最初批次计划逐项核对
../.venv/bin/python -m nexus.benchmark report --batch .runtime/my-live-run --output .runtime/my-report
```

三种流程都使用公开编译／测试反馈，最多3次请求、总修复480秒、每次最多6000输出tokens、temperature0.2。DIRECT无静态MCP，MCP添加基线静态分析与失败定位，CEGIS再添加确认规则的有限搜索。最后统一运行最多60秒的私有验收，费用和耗时不能只统计模型生成部分。`UNKNOWN`和未修复仍留在分母；模型不确定请求不重发，既有运行目录不能覆盖。

报告只有三个流程任务集合、模型、数据集、执行版本及预算一致，且执行本身均已完成时才标记LIVE_COMPARABLE。FIXTURE_ONLY只证明集成，不能作真实模型成绩。无usage或价格时费用UNKNOWN；可用`--prices-json <文件>`输入`input_per_million`、`output_per_million`和`currency`（CNY／USD），估算忽略缓存折扣、税费及网络成本，不内置可能过期的服务价格。

当前批次schema3计划包含实际Python源码、依赖版本、requirements.lock摘要、固定编译器／包管理器与core2身份；统一implementation_hash随STARTED和schema2最终结果绑定。创建运行及重放时重新计算，执行源码／依赖／原生构建变化会拒绝混用；源码目录链接也拒绝。历史schema2计划可只读重建，但无执行身份的结果不能升级为同版本LIVE比较。

批次计划摘要随STARTED和最终结果绑定；报告迭代全部计划项，整个任务缺失也保留在分母。`COMPLETE`表示已有可重建的最终实验结果且任务执行已完成，`MISSING`表示没有该运行目录，`UNFINISHED`表示存在运行材料但无完整结果，或实际任务仍处于活动／IN_DOUBT状态；即使已有result.json，也不会把未决执行标为完成，后者不代表已证实进程终止。未完成请求的已知次数保留，未知usage、耗时或计费不填0。程序遇到异常、BLOCKED／IN_DOUBT、未完成任务或UNKNOWN验证时会停止后续调用，不自动重跑；异常类型留在STOPPED／ERROR记录，避免保存任意异常文本。重建报告不启动任何修复。

旧单独结果仍可用`report --runs <目录...>`读取，其统计范围只是明确提供的行；真实结果标为LIVE_UNPLANNED，不能当作原批次的完整比较。旧schema1计划不能冒充当前摘要绑定计划；历史FIXTURE报告保持可读。

质量门禁把最多10个任务放进同一测试包；任务函数使用唯一名字，生产源码保持原字节，来源和测试分组保留。每任务独立要求：缺陷工程真实可编译、至少一个holdout失败、参考修复的公开及holdout全部通过。组合只缩短编译开销，不等于工程修复范围扩张；实际模型任务仍逐个走上传／冻结／策略／候选／SDK流程。

清单覆盖全部数据字节。加载拒绝链接、路径逃逸、文件或清单摘要变化。运行和报告记录清单摘要；验收日志、测试材料、候选及工具链变化会使重放拒绝。`verify-quality`还校验当前质量验证器版本，代码升级后旧结果只能作为当时快照，需重新验证。

本机验收只覆盖已记录的macOS ARM64／仓颉1.0.5／实际Python依赖组合。原lock与实际安装版本同时纳入快照；不据此宣称在全新机器完成过相同安装，也不宣称整个SDK动态库／标准库的逐字节可复现性。
