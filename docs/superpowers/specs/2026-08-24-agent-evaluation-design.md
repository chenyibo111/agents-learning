# 第 12 课 Agent 性能评估工程设计

## 目标

构建一个完全离线、确定性、可回放的 Agent 评测引擎，覆盖版本化评测集、轨迹记录、硬规则指标、独立 Judge 结果、策略对比、Pareto 分析、失败样本定位和发布门禁。

## 范围

本课实现评测与回归工程，不实现真实大模型训练、在线监控或外部模型 API。默认运行两个确定性 Agent 策略，模拟正确回答、工具失败、证据缺失和提示注入等评测场景。

## 架构

`dataset.py` 提供带版本和场景标签的评测集；`runner.py` 执行策略并记录完整轨迹；`metrics.py` 只计算可验证的硬指标；`judges.py` 独立记录 Judge 与人工校准结果，不覆盖硬指标；`comparison.py` 计算策略指标和 Pareto 前沿；`gate.py` 根据明确阈值决定是否允许发布；`storage.py` 以 JSONL 和 JSON 原子保存实验产物；`experiment.py` 编排一次完整实验。

## 数据契约

- 评测集版本固定为 `agent-eval-v1`。
- 每个 case 必须有 `case_id`、`split`、`scenario`、`prompt`、`expected_answer`、`required_tool` 和 `requires_evidence`。
- 每条轨迹必须记录策略、case、最终输出、工具调用、步骤数、延迟、token、估算成本、安全违规和失败原因。
- 规则指标和 Judge 结果必须使用不同字段保存。
- 产物必须包含 manifest、轨迹 JSONL 和 report JSON。

## 指标与门禁

硬指标包括成功率、平均步数、平均延迟、平均 token、平均成本、安全违规率、工具参数正确率和引用/证据完整率。Judge 结果只作为补充维度，必须保留 rubric、分数和人工校准标记。

默认发布门禁要求：成功率不低于 0.75，安全违规率为 0，证据完整率不低于 0.75，平均成本不能超过基线的 1.5 倍。门禁报告必须列出失败指标和失败 case id。

## 验收标准

1. 能运行离线 Demo 并生成训练/评测报告。
2. 能按 case id 回放失败轨迹。
3. 能区分硬规则失败与 Judge 失败。
4. 能比较两个策略并输出 Pareto 前沿。
5. 安全失败样例可以阻断发布。
6. 轨迹、manifest、报告可以保存并重新加载。
7. 专属测试覆盖数据版本、指标计算、Judge 分离、回放、Pareto 和门禁。
