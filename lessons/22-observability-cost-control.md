# 第二十二课：可观测性与成本控制

## 1. 为什么需要可观测性

Agent 出现问题时，单看最终答案通常不够：

- 哪个节点最慢？
- 哪次模型调用最贵？
- 是规划失败还是工具失败？
- 输入和输出 Token 是否突然增长？
- 工作流失败前已经执行了哪些步骤？

可观测性就是给一次运行建立完整的执行记录，让我们能够回答这些问题。

本课使用两层结构：

```text
一次工作流运行 = Trace
Trace 中的每个节点 = Span
```

## 2. 运行项目

```bash
source .venv/bin/activate
python3 projects/22-observability-cost-control/main.py --demo
```

模拟失败：

```bash
python3 projects/22-observability-cost-control/main.py --demo --fail-review
```

预算过低：

```bash
python3 projects/22-observability-cost-control/main.py --demo --budget 0.000001
```

## 3. Trace 和 Span

一次运行首先创建根 Span：

```text
workflow
  ├─ planner
  ├─ retrieval
  └─ reviewer
```

每个 Span 都有：

```text
trace_id
span_id
parent_id
name
kind
status
started_at
ended_at
duration_ms
error
```

`parent_id` 让程序可以重建节点之间的调用关系，而不仅仅是得到一串平面日志。

## 4. 记录耗时

`TraceRecorder.start_span()` 记录开始时间，`finish_span()` 记录结束时间：

```python
span.duration_ms = (end_tick - start_tick) * 1000
```

报告会找出最慢节点：

```python
slowest_span = max(spans, key=lambda span: span.duration_ms)
```

Demo 中的 `retrieval` 节点故意等待了一小段时间，可以用来观察性能瓶颈。

## 5. Token 估算

本课使用简单估算：

```python
estimate_tokens(text) = ceil(len(text) / 4)
```

例如：

```text
8 个字符 ≈ 2 个 Token
```

这不是模型真实 Tokenizer，只是一个不依赖外部库的教学近似。不同模型的 Tokenizer 不同，中文、英文、代码和 JSON 的 Token 比例也不同。

生产环境应该优先使用 API 返回的真实用量：

```text
prompt_tokens
completion_tokens
total_tokens
```

## 6. 成本计算

项目使用：

```python
ModelPricing(
    input_per_million=0.15,
    output_per_million=0.60,
)
```

成本公式是：

```text
输入成本 = 输入 Token / 1,000,000 × 输入单价
输出成本 = 输出 Token / 1,000,000 × 输出单价
总成本 = 输入成本 + 输出成本
```

不同模型需要使用不同价格配置，不能把一个模型的价格套到另一个模型上。

## 7. 预算门禁

`BudgetTracker.reserve()` 会检查：

```text
已使用成本 + 本次预计成本 > 预算上限？
```

如果超过预算，就抛出 `BudgetExceededError`，并且不再记录本次调用成本。

这可以防止：

- 无限循环持续消耗 Token；
- 查询改写导致调用次数爆炸；
- 上下文异常膨胀；
- 单个任务消耗超过预期。

当前 Demo 在模拟调用后计算成本。真实系统应该在请求前根据最大输出 Token 做预估，在请求后用 API 返回的真实用量结算。

## 8. 失败和报告

如果 `reviewer` 抛出异常，程序会：

1. 将 `reviewer` 标记为 `error`；
2. 将根工作流 Span 标记为 `error`；
3. 把错误信息保存到 Span；
4. 报告中列出 `failed_spans`。

报告还会列出：

```text
总 Span 数
总耗时
总输入/输出 Token
总成本
最慢节点
失败节点
剩余预算
```

这比只打印一句“任务失败”更容易定位问题。

## 9. 日志、指标和 Trace 的区别

### 日志 Log

记录单条事件：

```text
reviewer failed: timeout
```

### 指标 Metric

聚合后的数字：

```text
失败率：3.2%
平均延迟：820ms
```

### Trace

描述一次完整请求经过了哪些节点：

```text
workflow → planner → retrieval → reviewer
```

三者通常需要一起使用。

## 10. 和前面课程的关系

第 17 课保存工作流状态；第 18 课校验结构化输出；第 19 课保证工具执行；第 20 课编排节点；第 21 课控制安全边界；第 22 课观察运行过程并控制成本。

可以把一次 Agent 运行看成：

```text
状态 State
  +
安全 Security
  +
可靠执行 Reliability
  +
可观测性 Observability
```

## 11. 可靠性边界

当前项目是教学版：

- Token 只是近似估算；
- 价格是手动配置；
- Trace 只保存在内存中；
- 没有接入 OpenTelemetry；
- 没有跨进程上报指标；
- 预算没有处理并发竞态；
- 没有区分缓存 Token、批处理价格和不同计费层级。

生产系统通常会把 Trace 上报到观测平台，把指标发送到监控系统，并将预算记录持久化。

## 12. 思考题

1. 为什么只记录最终答案无法定位 Agent 问题？
2. Token 估算和真实 Token 统计有什么差异？
3. 如果两个并发节点同时预留预算，如何避免超支？
4. 哪些输入字段应该脱敏后再写入 Trace？
5. 如何把第 22 课的 Span 和第 20 课的工作流节点关联起来？
