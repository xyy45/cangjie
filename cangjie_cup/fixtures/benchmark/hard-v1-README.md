# 组合业务规则难例

10类规则，每类3种逻辑缺陷；hard-v1-10为首批，hard-v1-30为扩展，旧v1与v1-30未覆盖。仅Int64/Bool、最多4参数、同包最多3生产文件。

`private/`用于本地独立搜索和封存验收，禁止作为LLM上下文；公开材料只经public_material导出。holdout输入也从搜索和缩减中排除。

缺陷审阅、实际SDK质量与重放原件见docs/demo/validation/next-phase-2/。合格语料不等于模型修复成功。
