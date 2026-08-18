# 第 26 课：多 Agent 协作

## 一、什么是多 Agent 协作

多 Agent 不是简单地“多开几个模型”。它的核心是把一个复杂任务拆成多个职责明确的角色：

```text
协调者：决定谁做什么
研究员：收集事实和候选方案
审查员：寻找风险、缺口和反例
汇总者：把不同结果合成为最终答案
```

每个角色可以是：

- 一个普通 Python 函数；
- 一次 LLM 调用；
- 一个 `smolagents` Agent；
- 一个 LangGraph 子图；
- 一个远程服务。

因此，“Agent”首先是职责和执行边界，不一定必须是一个独立模型。

## 二、本课图结构

项目位于 `projects/26-multi-agent-collaboration/`：

```text
START
  ↓
coordinator
  ├────────→ researcher ────┐
  └────────→ critic ────────┤
                            ↓
                        synthesizer
                            ↓
                           END
```

这包含两个重要结构：

- fan-out：一个协调者把任务分发给多个 Agent；
- fan-in：多个 Agent 的结果汇入汇总者。

LangGraph 支持多个出边的并行执行。并行节点属于同一个 super-step，所有分支完成后，汇总节点才会运行。[官方 Graph API 文档](https://docs.langchain.com/oss/python/langgraph/use-graph-api)

## 三、`CollaborationState`

```python
class CollaborationState(TypedDict, total=False):
    task: str
    assignments: list[str]
    research: list[str]
    critiques: list[str]
    final_answer: str
    status: str
    events: Annotated[list[str], operator.add]
```

状态字段的职责：

- `task`：总任务；
- `assignments`：协调者分配的角色；
- `research`：研究员输出；
- `critiques`：审查员输出；
- `final_answer`：汇总结果；
- `status`：当前流程状态；
- `events`：所有角色产生的执行记录。

## 四、为什么 `events` 需要 reducer

`coordinator`、`researcher` 和 `critic` 都会更新 `events`。

其中 `researcher` 和 `critic` 会并行运行。如果没有 reducer，LangGraph 不知道两个列表应该覆盖还是合并，可能抛出 `INVALID_CONCURRENT_GRAPH_UPDATE`。

本课声明：

```python
events: Annotated[list[str], operator.add]
```

意思是：当多个节点返回事件列表时，用 `operator.add` 拼接列表。

例如：

```python
["coordinator 完成"] + ["researcher 完成"]
```

结果是：

```python
[
    "coordinator 完成",
    "researcher 完成",
]
```

官方文档说明，并行节点共同更新同一个字段时，需要使用 reducer，例如 `Annotated[list, operator.add]`。[并发更新错误说明](https://docs.langchain.com/oss/python/langgraph/errors/INVALID_CONCURRENT_GRAPH_UPDATE)

注意：并行分支完成的先后顺序不应作为业务逻辑依据。事件列表的顺序可能不稳定，重要结果应放在独立字段中或附带显式排序键。

## 五、四个角色

### `coordinator`

协调者不负责完成全部任务，而是返回：

```python
{"assignments": ["researcher", "critic"]}
```

这代表任务委派。

真实实现中，协调者可以由 LLM 根据任务动态选择角色；本课为了离线可重复，使用固定委派。

### `researcher`

研究员负责提供背景资料、事实和候选结论。

真实实现可以调用：

- 搜索工具；
- RAG 检索器；
- 数据库；
- 外部 API；
- `smolagents` 工具 Agent。

### `critic`

审查员不重复研究，而是专门寻找：

- 证据缺口；
- 逻辑漏洞；
- 风险；
- 成本；
- 失败场景；
- 不适合上线的条件。

独立审查可以降低“所有 Agent 都沿着同一个错误假设执行”的风险。

### `synthesizer`

汇总者等两个分支都完成后才运行：

```python
research = "；".join(state.get("research", []))
critiques = "；".join(state.get("critiques", []))
```

然后生成统一答案。

真实系统中，汇总者还应该负责：

- 解决结果冲突；
- 判断证据强弱；
- 保留引用；
- 明确不确定性；
- 拒绝没有证据的结论。

## 六、图的执行过程

第一次调用：

```python
graph.invoke(
    {"task": "...", "events": []},
    config,
)
```

执行顺序：

```text
1. coordinator
2. researcher 和 critic 并行执行
3. 等待两个分支完成
4. synthesizer 汇总结果
5. END
```

LangGraph 采用 super-step 执行模型。`researcher` 和 `critic` 处于同一个并行 super-step，`synthesizer` 会等两者都完成后再执行。

## 七、和“一个大 Agent”的区别

一个大 Agent：

```text
一个模型自己决定搜索、分析、批评、写答案
```

多 Agent：

```text
协调者 → 研究员
       → 审查员
       → 汇总者
```

多 Agent 的优势：

- 角色职责清晰；
- 可以并行，提高吞吐；
- 研究和审查相互独立；
- 每个角色可以使用不同模型；
- 每个角色可以独立测试和监控。

代价也很明显：

- 调用次数增加；
- 成本增加；
- 延迟可能增加；
- 角色之间可能互相误导；
- 需要处理结果冲突；
- 需要设计超时、重试和失败降级。

多 Agent 不是越多越好。任务简单时，一个模型加几个工具通常更可靠。

## 八、下一步改造方向

1. 把 `researcher` 替换为真实 RAG Agent；
2. 把 `critic` 替换为结构化评审 Agent；
3. 让 `coordinator` 根据任务动态选择角色；
4. 给每个角色配置不同模型；
5. 给并行节点增加超时和重试策略；
6. 为汇总结果增加引用检查；
7. 使用第 25 课的 `InMemorySaver` 保存协作过程；
8. 使用人工审核节点确认最终结果。

本课的核心结论是：

> 多 Agent 协作的本质不是堆叠模型，而是把任务拆成清晰职责，并用共享状态和明确路由管理角色之间的协作。

