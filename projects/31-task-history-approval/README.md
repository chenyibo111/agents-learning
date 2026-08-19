# 31 - 历史任务与人工确认

本课在第30课带引用报告的基础上，增加任务历史和人工审批门：

```text
生成草稿 → 保存任务 → interrupt 暂停 → 人工决定 → 发布或拒绝
```

## 运行

在 PowerShell 中执行：

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

默认会在项目目录创建 `task_history.sqlite3`，该文件已加入忽略规则，不应提交到 Git。

## 代码结构

```text
store.py     # SQLite 任务和审批历史
workflow.py  # LangGraph 草稿、审批、发布/拒绝流程
main.py      # 用 Command(resume=...) 模拟人工审批
```

## 核心概念

- checkpoint 保存工作流如何恢复；
- SQLite 保存用户可见的任务历史；
- `interrupt()` 暂停流程并等待外部决定；
- `Command(resume=...)` 使用同一个 thread_id 恢复流程；
- 发布节点位于审批之后，避免未确认的外部副作用。

## 测试

```powershell
python -m unittest tests/test_task_history_approval.py -v
```
