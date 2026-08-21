# 第 25 课：用 LangGraph 管理状态

## 一、为什么需要 LangGraph

前面几课逐步遇到了几个问题：

- 第 3 课的 Agent 循环需要自己控制最大步数；
- 第 17 课需要自己定义状态和保存检查点；
- 第 20 课需要自己实现顺序、条件、并行和人工审批；
- 第 24 课虽然由 `smolagents` 接管了工具调用循环，但复杂流程仍然需要额外编排。

LangGraph 的核心思想是：

```text
状态 State + 节点 Node + 边 Edge = 可执行工作流图
```

它不是让模型自由发挥整个流程，而是让开发者明确规定流程可以经过哪些节点、每个节点如何更新状态，以及什么条件下走哪条边。

## 二、本课项目

项目位于 `projects/25-langgraph-state/`，示例是一个带人工审核的研究摘要工作流：

```text
collect_notes
      ↓
draft_summary
      ↓
human_review ──批准──→ publish → END
      ↑
      └────拒绝──── revise
```

这个例子完全离线，不依赖模型。这样可以先把 LangGraph 的运行机制看清楚，再把节点替换成真实的 LLM 调用。

## 三、State：节点之间共享的数据

状态定义在 `workflow.py`：

```python
class ResearchState(TypedDict, total=False):
    topic: str
    notes: list[str]
    draft: str
    approved: bool
    status: str
    published: str
    events: list[str]
```

状态是整个图的共享上下文。每个节点接收完整状态，但通常只返回自己修改的字段：

```python
def draft_summary(state: ResearchState) -> dict[str, Any]:
    draft = "；".join(state.get("notes", []))
    return {
        "draft": f"研究摘要：{draft}",
        "status": "drafted",
    }
```

这里节点不需要手动把整个 `state` 重新复制一遍，只返回增量更新即可。

## 四、Node：一个可执行步骤

节点就是普通 Python 函数：

```python
def collect_notes(state):
    return {"notes": [...], "status": "collected"}
```

通过 `add_node` 注册：

```python
builder.add_node("collect_notes", collect_notes)
```

LangGraph 会在节点运行时把当前状态传给函数，再把返回值合并到图状态中。

## 五、Edge：控制执行顺序

固定顺序使用普通边：

```python
builder.add_edge(START, "collect_notes")
builder.add_edge("collect_notes", "draft_summary")
builder.add_edge("draft_summary", "human_review")
builder.add_edge("publish", END)
```

这表达了：

```text
开始 → 收集资料 → 生成草稿 → 人工审核
```

## 六、条件边：根据状态选择路径

审核之后需要根据 `approved` 决定路径：

```python
def route_after_review(state):
    return "publish" if state.get("approved") else "revise"
```

注册条件边：

```python
builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {"publish": "publish", "revise": "revise"},
)
```

这比在一个巨大 `while` 循环里写很多 `if/else` 更容易阅读和测试。

## 七、`interrupt`：暂停并等待人工输入

人工审核节点调用：

```python
decision = interrupt({
    "type": "human_review",
    "question": "是否批准这份研究摘要？",
    "draft": state["draft"],
})
```

运行到这里时，图不会继续执行，而是返回一个中断信息。调用方可以把这个信息展示给用户。

恢复时要使用同一个 `thread_id`：

```python
config = {"configurable": {"thread_id": "lesson-25-demo"}}
graph.invoke(Command(resume={"approved": True}), config)
```

这里的 `thread_id` 很关键。它告诉 LangGraph：

> 这不是一个全新的任务，而是恢复之前暂停的那条工作流。

## 八、Checkpointer：保存状态

编译时传入检查点保存器：

```python
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

检查点可以支持：

- 多轮对话状态；
- 人工审批后恢复；
- 中断后的故障恢复；
- 查看历史状态；
- 从历史节点重新执行。

本课使用 `InMemorySaver`，进程退出后数据会消失。生产环境应使用数据库后端，例如 SQLite 或 PostgreSQL 检查点。

## 九、和第 17、20 课的区别

第 17 课手动实现了：

```text
AgentState
→ save_state()
→ load_state()
→ while 循环恢复
```

第 20 课手动实现了节点调度和人工审批。

第 25 课则把这些概念交给 LangGraph 表达：

| 手写概念 | LangGraph 概念 |
|---|---|
| `AgentState` | `StateGraph` 的 State |
| 工作步骤 | Node |
| 步骤顺序 | Edge |
| `if/else` 路由 | Conditional Edge |
| 保存状态 | Checkpointer |
| 暂停审批 | `interrupt()` |
| 恢复任务 | `Command(resume=...)` |

框架减少了调度和持久化样板代码，但业务节点本身仍然需要开发者编写。

## 十、运行实验

安装依赖：

```powershell
pip install -r .\projects\25-langgraph-state\requirements.txt
```

运行自动批准：

```powershell
python .\projects\25-langgraph-state\main.py --demo
```

运行拒绝后重新审核：

```powershell
python .\projects\25-langgraph-state\main.py --demo --reject-once
```

重点观察事件序列：

```text
collect_notes
→ draft_summary
→ human_review 拒绝
→ revise
→ human_review 批准
→ publish
```

## 十一、生产设计注意事项

1. `InMemorySaver` 只适合 Demo，生产使用数据库检查点；
2. 有副作用的节点，例如扣款、发邮件、写订单，必须设计幂等键；
3. 恢复工作流时，要避免重复执行已经成功的外部操作；
4. 人工审核数据需要权限控制和审计日志；
5. 每个节点都应有超时、重试和失败状态；
6. 状态中不要直接保存 API Key、密码等敏感信息；
7. 图的边界要明确，不能只依赖模型自己决定关键业务流程。

本课的核心结论是：

> LangGraph 用图结构管理 Agent 的状态和流程，让长任务、人工介入和失败恢复变得可见、可控、可测试。

