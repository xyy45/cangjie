# 4B有界数组语义调研

2026-10-28，实际固定SDK1.0.5／macOS ARM64，使用开发目录现有SDK与stdx。自建临时工程，不使用用户数据、模型、远程6240。原件：[26份文件归档](validation/next-phase-4B/sdk-preflight.zip)及[摘要清单](validation/next-phase-4B/sdk-preflight-manifest.json)。调研本身不是产品完成证明。

| 调研组 | 实际SDK／严格解析结果 | 结论 |
|---|---|---|
| arrays | 退出0，PASS | 空数组、Int64下标、for遍历、size、返回数组可用；赋值给别名或返回引用再写元素会影响原数组 |
| comparison | 退出0，PASS | 两个独立同值数组结构相等 |
| empty_literal | 退出0，PASS | 直接返回[]、f([])、@Expect(f([]),[])及Int64极值数组可编译／执行 |
| overflow | 退出1，ERROR，UNKNOWN | HIGH+1抛OverflowException，不能伪装为通过或确定业务反例 |
| out_of_bounds | 退出1，ERROR，UNKNOWN | 空数组[0]抛IndexOutOfBoundsException |

所有组实际执行cjpm test --no-run，随后--skip-build --show-all-output。初始调研驱动对两种异常的expected_state=FAIL是假设，实际UNKNOWN原件完整保留，产品未修改解析器以迎合预期。

本阶段采用只读Array<Int64>候选子集、JSON按值语义，长度0—16，有限域1—16个明确数组；拒绝元素写入和一般Array API。设计与版本／协议边界见[设计](../superpowers/specs/2026-10-28-bounded-arrays-design.md)，一步步实施见[计划](../superpowers/plans/2026-10-28-bounded-arrays.md)。
