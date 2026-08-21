# 第 31 课：历史任务与人工确认

第 30 课已经可以把已核验证据生成带引用的 Markdown 报告。本课继续解决两个生产问题：

```text
报告生成
  → 保存任务历史
  → 等待人工确认
  → 批准发布或拒绝发布
```

## 一、本课目标

完成本课后，你应该能解释：

1. 为什么 LangGraph checkpoint 不能完全替代业务任务数据库；
2. 如何保存任务、报告、状态和审批历史；
3. `interrupt()` 如何暂停工作流；
4. `Command(resume=...)` 如何在同一个 `thread_id` 上恢复工作流；
5. 为什么高风险副作用必须放在人工确认之后；
6. 为什么发布节点需要幂等设计。

## 二、Checkpoint 和任务历史不是一回事

LangGraph checkpoint 主要保存“工作流如何继续执行”，例如当前节点和图状态。业务任务历史则面向用户和审计，至少需要保存：

```text
task_id
query
status
draft_report
created_at
updated_at
approval_history
```

因此本课同时使用：

```text
LangGraph InMemorySaver：恢复当前工作流
SQLite TaskStore：保存任务和审批历史
```

`InMemorySaver` 仍然是易失的；SQLite 文件则可以在程序重启后读取历史任务。

## 三、本课工作流

```text
START
  ↓
draft_report
  ↓ 保存草稿
approval_gate
  ↓ interrupt 暂停
  ├── approved → publish
  └── rejected → reject
```

草稿生成和发布是两个不同阶段。生成草稿可以自动完成，但发布报告可能产生外部影响，因此必须等待人工决定。

## 四、`TaskStore` 的职责

文件：`projects/31-task-history-approval/store.py`。

`TaskStore` 使用 SQLite 保存：

- 任务基本信息；
- 当前状态；
- 草稿报告；
- LangGraph 状态快照；
- 每一次批准或拒绝记录。

它不负责调用模型，也不负责决定工作流下一步。这样数据库层、工作流层和报告层仍然保持分离。

## 五、`interrupt()` 的执行语义

审批节点执行到：

```python
answer = interrupt({
    "type": "approval_required",
    "task_id": state["task_id"],
    "report": state["draft_report"],
})
```

工作流会暂停，并把审批请求交给调用方。初次调用不会执行 `publish` 或 `reject`。

恢复时必须使用相同的线程 ID：

```python
graph.invoke(
    Command(
        resume={
            "decision": "approved",
            "comment": "检查通过",
        }
    ),
    config,
)
```

恢复值会成为 `interrupt()` 的返回值，审批节点继续执行，之后路由到 `publish` 或 `reject`。

## 六、为什么发布必须在确认之后

错误流程：

```text
生成报告 → 发布报告 → 请求人工确认
```

如果用户拒绝，外部系统可能已经被修改。

正确流程：

```text
生成草稿 → 保存草稿 → 人工确认 → 发布
```

本课 Demo 把“写入 published 状态”作为发布副作用。真实系统中，这个节点还可能发送邮件、上传文件、调用发布 API，因此必须：

- 放在审批之后；
- 使用幂等键；
- 记录操作结果；
- 区分批准、拒绝和发布失败。

## 七、运行示例

PowerShell：

```powershell
python .\projects\31-task-history-approval\main.py `
  --decision approved `
  --query "评估报告是否可以发布"
```

拒绝发布：

```powershell
python .\projects\31-task-history-approval\main.py `
  --decision rejected `
  --query "评估报告是否可以发布"
```

程序会先显示暂停的审批请求，随后用 `Command(resume=...)` 模拟人工操作，并输出最终任务记录。

## 八、测试重点

测试文件：`tests/test_task_history_approval.py`。

覆盖内容：

- SQLite 任务创建、更新和历史读取；
- 工作流在审批节点暂停；
- 未批准前不会进入发布节点；
- 批准后状态变为 `published`；
- 拒绝后状态变为 `rejected`；
- 恢复时使用同一个 `thread_id`。

## 九、当前边界

本课使用 SQLite 和内存 checkpoint 完成教学 Demo，暂不处理：

- 多用户权限系统；
- 审批人身份认证；
- 分布式锁；
- 生产级 PostgreSQL checkpointer；
- Web UI；
- 报告质量自动评分。

这些内容将在第 32 课的评测和部署阶段继续完善。

本课核心结论：

> 自动化 Agent 可以生成候选结果，但高风险副作用必须通过可恢复的人工确认门之后才能执行。
