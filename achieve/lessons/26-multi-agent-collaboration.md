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

## 十、把固定函数替换成真实 Agent

扩展版还提供 `llm_workflow.py`。基础版中的角色函数只是离线占位：

```python
def researcher(state):
    return {"research": ["固定字符串"]}
```

真实模式中，`LLMCollaborationRuntime` 为每个角色调用 OpenAI-compatible Chat Completions：

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=[
        {"role": "system", "content": role_instructions},
        {"role": "user", "content": task},
    ],
    temperature=0.2,
)
```

因此一条任务的实际调用链变成：

```text
协调者 Agent：选择 researcher / critic / fact_checker
        ↓
多个专家 Agent 并行调用模型
        ↓
汇总 Agent：综合专家结果和失败记录
```

### 协调者 Agent

协调者只能从白名单选择：

```python
ALLOWED_ROLES = (
    "researcher",
    "critic",
    "fact_checker",
)
```

模型被要求只返回 JSON 数组：

```json
["researcher", "critic", "fact_checker"]
```

`parse_roles()` 会处理代码块、提取 JSON、去重并过滤未知角色。即使模型返回非法角色，也不会让它直接访问任意 Python 节点。

### 专家 Agent

每个专家拥有独立的 system instruction：

```text
researcher：寻找事实和可验证方向
critic：寻找风险和逻辑漏洞
fact_checker：标记需要独立来源核验的结论
```

它们共享总任务，但不共享彼此的中间回答，因此可以保持角色独立性。返回结果会包装成：

```python
{
    "role": "researcher",
    "ok": True,
    "output": "模型返回的研究结果",
}
```

### 汇总 Agent

汇总 Agent 会收到：

- 总任务；
- 所有成功专家的结果；
- 所有失败专家的记录。

它被明确要求区分事实、推断和不确定性，并且不能隐藏失败。这样汇总 Agent 不会把“事实核验失败”误写成“事实已经确认”。

### 调用次数和成本

如果协调者选择三个专家，一次任务至少产生：

```text
1 次协调调用
3 次专家调用
1 次汇总调用
= 5 次模型调用
```

因此多 Agent 的成本和延迟都可能高于单 Agent。生产环境需要记录每个角色的 token、耗时和失败率，并设置总预算。

### 真实模式的边界

当前真实模式已经是真正的 LLM Agent，但专家暂时只接收文本任务，没有连接搜索、RAG 或业务工具。下一步可以把工具加入专家内部：

```text
researcher Agent
  → search tool
  → RAG retriever
  → evidence result
```

也可以把 `researcher` 换成第 24 课的 `smolagents ToolCallingAgent`，再由第 26 课的 LangGraph 负责多个 Agent 的编排。

本课的核心结论是：

> 多 Agent 协作的本质不是堆叠模型，而是把任务拆成清晰职责，并用共享状态和明确路由管理角色之间的协作。

## 九、扩展：动态角色选择与 `Send`

基础版的图是固定的：协调者永远调用 `researcher` 和 `critic`。扩展版增加了 `advanced_workflow.py`，把角色选择和图路径分开：

```text
coordinator
  ↓ 根据任务选择角色
Send(researcher)
Send(critic)
Send(fact_checker)
  ↓
synthesizer
```

### 为什么需要 `Send`

普通边适合固定拓扑：

```python
builder.add_edge("coordinator", "researcher")
builder.add_edge("coordinator", "critic")
```

如果角色数量和角色类型在运行时才确定，就应该使用 `Send`：

```python
return [
    Send(
        "specialist_worker",
        {"task": state["task"], "role": role},
    )
    for role in state["requested_roles"]
]
```

每个 `Send` 都会创建一次 `specialist_worker` 执行，并传入独立的局部状态。所有 worker 的返回结果通过 `worker_results` reducer 汇总到主图状态。

LangGraph 官方把这种模式用于 map-reduce 和 orchestrator-worker 工作流：协调者动态创建 worker，worker 结果写入共享状态，最后由协调者或汇总节点统一处理。[官方 `Send` 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)

### 动态角色选择

扩展版的 `choose_roles` 默认选择：

```python
["researcher", "critic"]
```

当任务包含以下词语时增加事实核验：

```text
生产、上线、风险、安全、production、deploy
```

结果变成：

```python
["researcher", "critic", "fact_checker"]
```

这里仍然使用关键词规则，是为了让 Demo 离线、稳定、可测试。真实系统可以把 `choose_roles` 替换成结构化 LLM 路由器，但必须限制可选角色白名单，不能让模型随意调用任意节点。

### 统一 worker 与角色配置

扩展版没有为每个角色创建独立的图节点，而是使用一个通用节点：

```python
builder.add_node("specialist_worker", specialist_worker)
```

具体角色通过输入状态传入：

```python
{
    "task": "...",
    "role": "researcher",
}
```

这让图结构保持稳定，而角色数量可以动态变化。`specialist_worker` 根据 `role` 选择对应的执行逻辑。

### 失败隔离

扩展版模拟 `fact_checker` 超时：

```python
if state.get("simulate_failure") and role == "fact_checker":
    raise TimeoutError("事实核验服务超时")
```

异常被 worker 自己捕获，转换为结构化失败记录：

```python
{
    "failures": [
        {
            "role": "fact_checker",
            "error": "事实核验服务超时",
        }
    ]
}
```

汇总节点仍然可以使用研究员和审查员的结果，并把最终状态设置为：

```text
completed_with_warnings
```

这体现了生产系统常见的“部分成功”策略：一个非关键专家失败时，不一定要让整条任务完全失败，但必须显式告诉下游和用户哪些核验没有完成。

### 什么时候使用动态分发

适合：

- 用户问题类型不固定；
- 专家数量运行时才确定；
- 需要对多个文档、章节或数据项并行处理；
- 每个 worker 使用不同输入；
- 需要 map-reduce 或 orchestrator-worker 结构。

不适合：

- 只有一个简单工具调用；
- 角色集合始终固定且很少；
- 任务结果不需要汇总；
- 并发带来的成本超过收益。

### 扩展实验

1. 增加 `security_reviewer` 角色，仅在任务包含“权限”或“注入”时启用；
2. 为每个 worker 增加 `confidence` 字段；
3. 让汇总者按照置信度而不是字符串顺序整理结果；
4. 让 `fact_checker` 失败时触发人工审核，而不是直接完成；
5. 将 `_role_output` 替换为真实 LLM 调用，并为每个角色设置不同模型；
6. 使用第 25 课的 checkpointer 保存动态 worker 的执行历史；
7. 为每个 `Send` 增加超时和重试策略。
