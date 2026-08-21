# 第 32 课：最终评测与部署

前面的课程已经完成了研究助手的主要能力：资料检索、工作流、证据核验、引用报告、任务历史和人工审批。本课不再增加一个新的 Agent 能力，而是回答一个工程问题：

> 我们怎么知道这个系统真的可靠，并且可以交给别人运行？

## 一、本课目标

```text
固定评测集
  → 回归测试
  → 运行监控
  → 配置检查
  → 部署验收
```

完成本课后，你应该能解释：

1. 为什么 Agent 不能只靠手工体验判断质量；
2. 如何使用固定问题集检测回归；
3. 如何区分状态正确、来源召回和引用有效；
4. 如何记录耗时、Token、成本和失败节点；
5. 为什么健康检查不能泄漏 API Key；
6. Demo、测试、LLM 和生产部署之间有什么差异。

## 二、为什么需要固定评测集

一次运行成功不能证明系统稳定：

```text
今天检索正确
  ≠
明天修改 Chunk 后仍然正确
```

因此本课把问题写成固定的 `EvalCase`：

```python
EvalCase(
    case_id="state-recovery",
    query="状态如何在节点之间流转",
    expected_sources=("agent-state.md",),
    require_citation=True,
    expected_status="completed",
)
```

每个用例明确规定输入问题、期望来源、是否必须带引用和期望最终状态。

## 三、评测器检查什么

文件：`projects/32-final-evaluation-deployment/evaluation.py`。

评测器依赖一个很小的应用接口：

```python
class ResearchApp(Protocol):
    def run(self, query: str) -> dict[str, Any]: ...
```

它不关心应用内部是 DemoRuntime、LLMRuntime、关键词检索、向量检索还是 LangGraph，只检查最终输出。

### 1. 状态检查

```python
output["status"] == "completed"
```

### 2. 来源检查

例如评测要求：

```python
expected_sources = ("agent-state.md",)
```

实际返回：

```python
["agent-state.md#agent-state-2"]
```

评测器会把 `#` 后面的 Chunk ID 去掉，只比较来源文件名。

### 3. 引用检查

当 `require_citation=True` 时，报告必须出现 `[1]` 形式的引用，并包含期望来源的 Chunk 标识：

```markdown
状态可以通过检查点保存。[1]

[1] agent-state.md#agent-state-2
```

## 四、评测结果

`Evaluator.evaluate()` 返回：

```python
{
    "total": 3,
    "passed": 3,
    "failed": 0,
    "pass_rate": 1.0,
    "results": [...],
}
```

单个用例还会记录：

```python
{
    "case_id": "state-recovery",
    "passed": True,
    "status_ok": True,
    "source_hit": True,
    "citation_ok": True,
    "duration_ms": 6.2,
    "error": "",
}
```

失败时可以区分是状态、召回、引用还是运行异常。

## 五、监控器 `Monitor`

文件：`projects/32-final-evaluation-deployment/monitoring.py`。

监控器使用 span 记录一次操作：

```text
start_span
  ↓
执行操作
  ↓
finish_span
```

每个 `Span` 记录名称、类型、耗时、成功/失败、错误信息、输入 Token、输出 Token 和成本。

### Token 和成本

教学版使用简单 Token 估算：

```python
ceil(len(text) / 4)
```

成本计算为：

```python
cost = (
    input_tokens / 1_000_000 * input_price
    + output_tokens / 1_000_000 * output_price
)
```

真实项目应该使用对应模型和网关的实际价格配置。

### 预算控制

```python
Monitor(budget_usd=0.05)
```

如果下一次模型调用会超过预算，就抛出 `BudgetExceededError`，避免评测脚本或异常重试持续消耗费用。

## 六、部署配置检查

文件：`projects/32-final-evaluation-deployment/deployment.py`。

Demo 模式不需要模型凭据。LLM 模式需要：

```text
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_BASE_URL
```

配置检查会拒绝空 API Key、占位符、空模型名和非法 Base URL。

健康检查只返回脱敏摘要：

```python
{
    "mode": "llm",
    "ready": True,
    "api_key_configured": True,
    "model": "test-model",
    "base_url": "https://example.com/v1",
    "problems": [],
}
```

它不会返回真正的 API Key。

## 七、复用前面课程的最终应用

文件：`app_adapter.py`。

第 32 课没有重新实现研究助手，而是复用第 30 课：

```text
第30课研究助手
  → 第29课工作流
  → 第28课检索器
  → 带引用报告
  → 第32课评测器
```

适配器统一输出：

```python
{
    "status": "completed",
    "events": [...],
    "sources": ["agent-state.md#agent-state-2"],
    "report": "# 研究报告...",
    "evidence_count": 1,
}
```

## 八、运行方式

### 离线固定评测

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --demo \
  --evaluate \
  --retriever keyword
```

### 健康检查

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --demo \
  --health
```

### 单次 Demo 运行

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --demo \
  --query "状态如何在节点之间流转"
```

### 真实 LLM 评测

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --llm \
  --evaluate \
  --budget-usd 0.05
```

真实 LLM 模式会产生模型调用和费用，应该先运行 Demo 和 FakeClient 测试。

## 九、最终系统验收清单

```text
□ 固定评测集可重复执行
□ 期望来源可以召回
□ 报告保留引用
□ 资料不足时有明确失败结果
□ 高风险操作经过人工审批
□ 任务历史可以查询
□ 失败节点和耗时可定位
□ 模型成本受预算控制
□ 健康检查不泄漏密钥
□ .env、SQLite、向量索引不会提交
```

## 十、最终架构

```text
用户问题
  ↓
研究规划
  ↓
资料检索
  ↓
证据提取与核验
  ↓
带引用报告
  ↓
任务持久化
  ↓
人工确认
  ↓
发布或拒绝
  ↓
评测、监控和部署
```

本课核心结论：

> Agent 项目不是“能跑一次”就完成，而是要能被评测、被监控、被安全配置，并且能稳定交给别人运行。
