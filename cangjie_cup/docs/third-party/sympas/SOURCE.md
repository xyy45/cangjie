# Sympas 网关派生代码来源

来源仓库：https://github.com/nuptpisa/CangSight

固定提交：5db0c7eeeb6a62812fc04e9e88497339fed5e11f

原文件：Sympas-Nexus/nexus/gateway/app.py

原文件 SHA256：420b78df711af7f2e4e7de2437736460bb37bb1312da81a396051ee6a98ab89c

派生文件：nexus/integrations/sympas_runtime.py。

实际复用：`_is_sensitive_field`、`_public_value`、运行查询路由结构，以及通用`_execute_run`分派生命周期和`create_run`入队/线程启动顺序。修改：提取为仅仓颉能力的Blueprint，注入当前RepairLoop和原生RunStore投影，不复用旧领域执行器、旧审批路由或第二套运行库；基座分派completed不等于任务已交付。异常内容仅记录类型以免泄露凭据。不是原样导入上游完整网关。原分派函数逐字节摘录在upstream-execute-run.py.txt（与原文件共用本目录Apache-2.0许可），原文件/函数及派生代码摘要、完整修改diff见docs/evidence/v1.1/m1-upstream/dispatcher-source-provenance.json与dispatcher-source-diff.patch。

按照用户已明确的许可处理指令及仓库根Apache-2.0，原始LICENSE原文保存在同目录。网关源码未发现独立许可证、版权例外或具体版权人声明；未增造版权人。插件MIT元数据差异和完整核查范围见docs/v1.1/m1-reuse-review.md。仓库未发现NOTICE，故不存在可附带的上游NOTICE；本文件是新增来源记录。

不得将这一最小派生范围描述为已完整复用上游编排平台。真实MCP/Policy/cjpm验证、独立成员复现及M1基座范围验收分别记录。
