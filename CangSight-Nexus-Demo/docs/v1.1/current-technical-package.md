# V1.1 当前团队技术复核交付报告

日期：2026-10-18。此包可交给成员进行源码检查、离线/SDK复现及限定范围验收；不代表V1.1总目标或比赛正式提交完成。

## 建议交给成员的文件

- 技术复核包：`/Users/jadya/Documents/CangSight-Workspace/02-开发工程/CangSight-Nexus/.runtime/releases/CangSight-Nexus-v1.1-团队技术复核包-21eec36.zip`
- 外层ZIP SHA256：`93d760f6821137f44ecf990a455429383a7da54ab0a60cdc80b5e59d0e6d4635`
- 同目录校验文件：`CangSight-Nexus-v1.1-团队技术复核包-21eec36.sha256`；外部完整清单：`CangSight-Nexus-v1.1-团队技术复核包-21eec36.manifest.json`。
- 源码ZIP：`CangSight-Nexus-v1.1-Native-M1-source-21eec36.zip`；SHA256：`607a0a99395ef26ca914378c23a2629d2664117fd6b36da9a04e39d4d747e76f`。
- 固定源码快照：`21eec3604c32c083e72bc93add9538828a07c7d6`；应用实现：`9a41097`。后续交付报告提交只保存测试/归档记录，不改写该固定快照。

成员优先接收外层技术复核包及.sha256。包内source是可启动的CangSight-Nexus平台源码，含用于演示修复的原始故障案例；evidence中的修复工程导出只是验证产物，不能覆盖平台源码。请先阅读README-先读我.md和reports中的启动说明。

## 实际完成的验证

| 验证 | 实际结果 | 原始证据 |
| --- | --- | --- |
| 正式工程默认离线 | 144 passed、12 deselected，27.83秒 | dispatcher-offline-final.txt |
| 真实SDK/HTTP（含M1、MCP/Policy/cjpm、A/D和导出边界） | 11 passed，73.00秒；生成替身/手写提案不计LIVE | dispatcher-sdk-final.txt及对应真实记录 |
| 配对/前端竞态 | Node15 passed | dispatcher-node.txt |
| 无.git/无.env源码解压回归 | 144 passed、12 deselected，27.04秒 | package-no-git-offline.txt、package-no-git-details.json |
| 解压目录Fresh Policy | 实际cjc编译exit0，源码/编译器/新二进制摘要核对 | package-fresh-policy-build.txt/json |
| 固定源码完整性 | ZIP中485文件逐字节对照固定Git blob；许可保留 | package-integrity.json |
| 外层文件与嵌套归档 | 26个载荷摘要全部一致；递归4个ZIP共772条目CRC/路径/符号链接检查通过 | 外层release-manifest.json及package-integrity.json |
| 敏感排除 | 未含.env、运行库、虚拟环境、Git元数据、私有操作者/会话/所有者文件、target；当前实际API/操作者/会话/所有者凭据值精确扫描无命中，未输出值 | 外层manifest的credential_scan/archive_scan |

无Git目录：`/Users/jadya/Documents/CangSight-Workspace/02-开发工程/.cangsight-v11-m1-repro-nir11nl8/CangSight-Nexus`。只复用本机测试解释器与已固定SDK/stdx链接，Policy重新编译，没有复用开发机Policy、.env、数据库或授权凭据。这是同机发布验证，不能冒充另一成员独立复现。

## 证据与视频的版本边界

历史真实模型提案在当前执行器重新验证耗时9.635秒，实际MCP/原生Policy/cjpm检查通过（基线10通过/1失败，候选11通过），旧批准失效，使用新的EXECUTOR_REVALIDATION_OPERATOR批准并导出。新导出SHA256为`9cf9d79d77e95665c2f16006b891155cae1b79a171c4e10016fb349fb94517ea`。本轮新增模型请求0；该操作是人工脚本驱动MCP的重新验证，M1自动分派由单独真实SDK链证明，不混称本次新LIVE或成员本人接受。

视频位于video/historical-only，为既有真实记录的静音页面帧回放，保留来源/帧记录说明；不是当前实时修复录像。旧a19f6d7等技术包及其摘要保持原样。

## 尚未完成

当前整版新LIVE尚未执行，原先一次付费授权已经使用；后续需要新的明确授权。Native一般Mach IPC/进程信息/资源耗尽及所有后代边界仍未证明，强制而未验证项继续NOT_VERIFIED/BLOCKED。独立成员执行人/实际回执、赛事平台、精确截止时刻和正式提交均PENDING。仅支持登记自产案例，不运行任意上传工程，不将独立目录称为安全沙箱；本版不引入Docker。

技术复核包整理与限定范围测试完成，不宣告技术总验收或比赛正式提交完成。真实模型任务仍需成员本人的费用授权和实际人工审阅。
