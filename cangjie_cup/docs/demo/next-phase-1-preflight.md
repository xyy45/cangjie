# 业务规则辅助生成：实施前基线

日期：2026-10-25。状态：准备核验完成；本轮一次性产品实施提示尚待明确确认。本文不是功能实现或验收报告。

## 当前工作树证据

- 分支：codex/upgrade-counterexamples-20261023。工作树包含上一轮大量未提交内容，保留，不清理或覆盖。
- 实际执行身份：67d93b9c38e0eab172ff6cd2bbf695895e9cefd28b9267f3cd60a39bfd5930b1，与上一轮已重放的真实试评测一致。本轮尚无产品源码修改。
- 实际依赖：Flask3.1.3、httpx0.28.1、Pydantic2.13.4、MCP1.28.1；这些是当前安装版本，不表示已验证干净安装。

## 已运行的既有基线

使用仅在该命令中生效的placeholder模型环境；不读取／输出密钥，不调用真实模型或MCP。

```bash
DEEPSEEK_API_KEY=upgrade-test-placeholder DEEPSEEK_BASE_URL=https://fixture.invalid DEEPSEEK_MODEL=test-model ../.venv/bin/python -m pytest tests/test_upload_service.py tests/test_upload_routes.py tests/test_upload_oracle.py tests/test_oracle.py -q --tb=short
node --test tests/upload-ui.test.cjs tests/project-upload-ui.test.cjs
```

结果：Python18通过，1.80s；Node16通过，96.266459ms，0失败。原始输出见validation/next-phase-1/baseline-{python,node}.txt。只证明现有上传／例子／规则及相关前端基线，没有验证未来草案生成能力；不代替实施后的专项和完整回归。

## 已核对的接入点

1. `nexus/uploads/routes.py`实际前缀是`/api/uploads/repair`；新草案路由沿用该前缀，现有准备／确认路由仍保持不调用模型。
2. `UploadService._read/get`按actor隔离，校验单文件源摘要或工程original_manifest；不能只相信浏览器传来的摘要。
3. `UploadService.confirm`已有例子、oracle校验与冻结；新功能只在用户选择应用后接入，可选来源字段不能改变手动路径语义。
4. `nexus/projects/index.py`函数索引含path、params、return_type和public，可绑定用户选择函数及生产路径。
5. `nexus/demo/static/upload.js`已有generation／readEpoch防晚到覆盖；新轮询须同时校验上传、函数、路径和当前generation。
6. `nexus/execution/ownership.py`持有运行锁才可写；现有RuntimeOwner.reconcile主要覆盖tasks和tool_requests，不覆盖尚未实现的草案请求。实施时必须新增明确恢复入口，不能假设现有恢复自动覆盖草案。

## 下一步与授权边界

用户确认本轮八节实施提示后，开始第1项Task1的失败测试及产品代码。自动目标续跑消息不当作该明确确认。确认前仅完成文档与既有基线核验；本轮真实模型请求0，上一轮剩余上限不转入新批次。
