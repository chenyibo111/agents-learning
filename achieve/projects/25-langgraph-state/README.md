# 25 - 用 LangGraph 管理状态

本课使用 LangGraph 把一个可暂停、可恢复的 Agent 工作流表达成图：

```text
collect_notes → draft_summary → human_review
                                  ↓ approved
                                publish
                                  ↓
                                END

                                  ↓ rejected
                                revise
                                  ↓
                            human_review
```

## 安装依赖

```powershell
pip install -r .\projects\25-langgraph-state\requirements.txt
```

## 离线 Demo

Demo 不访问模型或网络，但需要安装 LangGraph：

```powershell
python .\projects\25-langgraph-state\main.py --demo
```

它会执行以下过程：

1. 创建一个带 `thread_id` 的工作流；
2. 运行资料收集和草稿生成节点；
3. 在人工审核节点暂停；
4. 使用 `Command(resume=...)` 恢复；
5. 完成发布并打印最终状态。

也可以演示“第一次拒绝、修改后再次批准”：

```powershell
python .\projects\25-langgraph-state\main.py --demo --reject-once
```

## 核心代码

```python
builder = StateGraph(ResearchState)
builder.add_node("collect_notes", collect_notes)
builder.add_node("draft_summary", draft_summary)
builder.add_node("human_review", human_review)
builder.add_node("revise", revise)
builder.add_node("publish", publish)
```

节点函数只返回需要更新的状态字段：

```python
return {"draft": "...", "status": "drafted"}
```

工作流通过检查点保存状态：

```python
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "lesson-25"}}
```

生产环境不应依赖 `InMemorySaver`，应替换为数据库检查点，例如 SQLite 或 PostgreSQL。

## 测试

```powershell
python -m unittest tests/test_langgraph_state.py -v
```

