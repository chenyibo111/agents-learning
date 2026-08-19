# 第 29 课：研究任务工作流

第 28 课解决的是“从哪里找到资料”。本课继续解决“如何把一次研究任务可靠地跑完”：先规划，再检索，再从资料中提取证据，最后核验证据。

## 一、本课目标

```text
研究问题
  → 研究计划
  → 检索片段
  → 证据记录
  → 已核验证据
```

完成本课后，你应该能解释：

1. 为什么研究任务需要中间状态；
2. 为什么检索器不应该隐藏在 LLM 里；
3. `plan`、`retrieve`、`extract`、`verify` 四个节点分别负责什么；
4. DemoRuntime 和 LLMRuntime 如何共享同一套工作流；
5. 为什么模型返回的结构化结果必须经过校验。

## 二、为什么不能只调用一次模型

下面这种方式很容易产生不可追踪的回答：

```text
用户问题 → LLM → 一段结论
```

问题在于：

- 没有明确研究范围；
- 不知道模型依据了哪些资料；
- 无法区分“原文事实”和“模型推断”；
- 失败时无法知道是规划、检索还是核验出了问题；
- 很难恢复中断的任务。

因此本课把任务拆成多个有明确输入和输出的节点。

## 三、ResearchState：节点之间的共享状态

文件：`projects/29-research-task-workflow/state.py`。

状态示意如下：

```python
{
    "topic": "Agent 如何保存状态并恢复工作流？",
    "plan": ["定义问题", "检索资料", "核验证据"],
    "retrieved_chunks": [
        {
            "source": "agent-state.md",
            "chunk_id": "agent-state-2",
            "text": "...",
            "score": 0.9,
        }
    ],
    "evidence": [
        {
            "claim": "状态可以通过检查点保存",
            "source": "agent-state.md",
            "chunk_id": "agent-state-2",
            "quote": "...",
        }
    ],
    "verified_evidence": [],
    "status": "extracted",
    "events": ["plan 完成", "retrieve 完成", "extract 完成"],
}
```

这里的 `state` 不是某一个节点的局部变量，而是整个工作流的共享数据结构。LangGraph 在调用节点时传入当前状态，节点返回局部更新，框架再把更新合并回状态。

## 四、四个节点的职责

### 1. `plan`

输入：`topic`。

输出：`plan` 和状态 `planned`。

它回答“为了研究这个问题，需要做哪些步骤”。Demo 模式返回固定计划，LLM 模式让模型生成字符串数组。

### 2. `retrieve`

输入：`topic` 和外部注入的 `retriever`。

输出：`retrieved_chunks` 和状态 `retrieved`。

这个节点直接调用第 28 课的检索器：

```python
retriever.search(state["topic"], top_k=top_k)
```

重要边界是：LLMRuntime 没有 `search` 方法。模型不能绕过检索器自行编造来源。

### 3. `extract`

输入：`topic` 和 `retrieved_chunks`。

输出：`evidence` 和状态 `extracted`。

证据至少保留：

```python
{
    "claim": "可验证的事实",
    "source": "来源文件",
    "chunk_id": "来源片段编号",
    "quote": "支持该事实的原文",
}
```

`source` 和 `chunk_id` 让后续报告可以追溯到具体资料片段。

### 4. `verify`

输入：`evidence`。

输出：`verified_evidence` 和状态 `completed`。

核验结果增加：

```python
{
    "verified": True,
    "note": "核验说明",
}
```

本课的 Demo 核验是确定性的：因为证据直接来自检索片段原文，所以标记为已核验。真实生产系统还可以接入第二来源、规则校验或人工审核。

## 五、为什么运行时和检索器要分离

本课使用两个不同的抽象：

```text
ResearchRuntime
  ├── plan()
  ├── extract_evidence()
  └── verify_evidence()

Retriever
  └── search()
```

这样可以独立替换：

- 关键词检索换成向量检索，不影响工作流节点；
- DemoRuntime 换成 LLMRuntime，不影响状态流转；
- 未来加入网页检索，也只需要实现相同的 `search` 接口。

这就是依赖注入：工作流不创建具体的模型和检索器，而是接收它们。

## 六、模型输出为什么要校验

LLM 模式要求模型返回 JSON，例如计划：

```json
["定义问题", "检索资料", "核验证据"]
```

证据：

```json
[
  {
    "claim": "状态可以恢复工作流",
    "source": "agent-state.md",
    "chunk_id": "agent-state-2",
    "quote": "状态可以通过检查点保存"
  }
]
```

代码会检查：

- 返回内容是否是合法 JSON；
- 顶层类型是否正确；
- 必填字段是否存在；
- 字段是否是非空字符串；
- `verified` 是否确实是布尔值。

除此之外，代码还会建立召回结果白名单，要求证据的 `source + chunk_id` 必须来自实际检索结果。仅靠 Prompt 要求模型“不要编造来源”是不够的，边界必须由程序再次校验。

模型输出是外部不可信输入，不能因为它“看起来像 JSON”就直接写入工作流状态。

## 七、运行和测试

离线 Demo：

```bash
.venv311/bin/python projects/29-research-task-workflow/main.py \
  --demo \
  --retriever keyword \
  --query "状态如何在节点之间流转"
```

真实 LLM：

```bash
.venv311/bin/python projects/29-research-task-workflow/main.py \
  --llm \
  --retriever keyword \
  --query "关键词检索和向量检索有什么区别"
```

测试：

```bash
.venv311/bin/python -m unittest tests/test_research_task_workflow.py -v
```

测试中的 `FakeClient` 只模拟模型返回，`FakeRetriever` 只模拟检索结果，因此不会产生网络调用或 API 费用。

## 八、本课与第 30 课的关系

本课输出的是结构化证据：

```text
verified_evidence
```

第 30 课再负责把它转换成：

```text
Markdown 报告
  ├── 结论
  ├── 证据链
  ├── [1]、[2] 引用
  └── 不确定性说明
```

把“研究过程”和“报告渲染”分开，可以避免报告格式变化影响检索、提取和核验逻辑。

## 九、实验题

1. 把 `--retriever keyword` 改成 `--retriever both`，比较召回结果；
2. 让 FakeRetriever 返回空列表，观察四个节点的状态如何变化；
3. 修改 FakeClient 的 JSON，使 `verified` 变成字符串，观察校验错误；
4. 给 `EvidenceRecord` 增加 `confidence` 字段，并让核验节点输出置信度；
5. 思考：如果两个来源对同一个事实结论相反，`verify` 节点应该怎样表示冲突？

本课核心结论：

> 一个可靠的研究 Agent，不是一次生成答案，而是让计划、资料、证据和核验结果在明确状态中逐节点流转。
