# 22 - 可观测性与成本控制

这一课实现一个纯 Python 的 Agent 运行观测器，记录：

```text
Trace
  ├─ Span：planner
  ├─ Span：retrieval
  └─ Span：reviewer
```

每个 Span 包含耗时、状态、Token、成本和父子关系。

## 运行

本课不需要 API Key：

```bash
source .venv/bin/activate
python3 projects/22-observability-cost-control/main.py --demo
```

模拟审查节点失败：

```bash
python3 projects/22-observability-cost-control/main.py \
  --demo \
  --fail-review
```

设置预算上限：

```bash
python3 projects/22-observability-cost-control/main.py \
  --demo \
  --budget 0.000001
```

## 报告内容

运行后会输出：

- `trace_id`：本次工作流运行 ID；
- `total_duration_ms`：总耗时；
- `total_input_tokens`：输入 Token 估算；
- `total_output_tokens`：输出 Token 估算；
- `total_cost_usd`：估算成本；
- `failed_spans`：失败节点；
- `slowest_span`：最慢节点；
- `spans`：每个节点的详细信息。

## 测试

```bash
python3 -m unittest tests/test_observability_cost.py -v
```

本课使用字符数近似 Token，仅用于学习观测和预算控制流程，生产环境应使用模型服务返回的真实 Token 用量。
