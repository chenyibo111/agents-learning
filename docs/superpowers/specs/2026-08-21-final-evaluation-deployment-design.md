# 第 32 课：最终评测与部署设计

## 目标

为第 27～31 课的研究助手增加固定评测集、回归统计、运行监控和部署前配置检查，形成可验证、可观测、可启动的最终项目。

## 架构

```text
app_adapter.py
  → 调用第30课研究工作流和报告层
evaluation.py
  → 固定 EvalCase、逐例评测、汇总通过率
monitoring.py
  → 记录节点耗时、Token、成本、失败
deployment.py
  → 校验环境变量、输出脱敏健康状态
main.py
  → CLI：Demo/LLM、evaluate、health
```

## 评测规则

每个 `EvalCase` 包含：

- `case_id`
- `query`
- `expected_sources`
- `require_citation`
- `expected_status`

逐例检查：

- 任务状态是否正确；
- 期望来源是否都被召回；
- 报告是否包含合法引用；
- 执行是否抛出异常。

## 监控规则

监控器记录：

- span 名称和耗时；
- 成功/失败状态；
- 输入输出 Token 估算；
- 单次成本和总成本；
- 最慢节点和失败节点。

监控报告不得包含 API Key、完整提示词或敏感内容。

## 部署检查

- Demo 模式不要求模型凭据；
- LLM 模式必须检查 API Key、模型名和 Base URL；
- 占位符配置必须拒绝；
- 健康检查只输出布尔状态和脱敏配置摘要；
- 不自动安装依赖、不生成 `.env`、不打印密钥。

## 验收标准

- Demo 评测集可离线执行并输出通过率；
- FakeApp 可以测试评测器，不产生网络调用；
- 监控器能捕获成功、失败、耗时和成本；
- 配置检查能区分 Demo、LLM 缺配置和合法配置；
- 全量测试通过；
- CLI 运行结果不泄漏敏感信息。
