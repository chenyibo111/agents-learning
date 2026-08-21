# 20 - 工作流编排

这一课实现一个纯 Python 的工作流编排器，演示四种常见节点：

```text
顺序节点 → 并行节点 → 条件分支 → 人工审批
```

## 运行

本课不需要 API Key，也不需要额外依赖：

```bash
source .venv/bin/activate
python3 projects/20-workflow-orchestration/main.py --demo
```

低风险任务会自动完成：

```text
prepare
  ↓
collect_local + collect_catalog（并行）
  ↓
merge
  ↓
publish
  ↓
completed
```

运行高风险任务：

```bash
python3 projects/20-workflow-orchestration/main.py --demo --high-risk
```

高风险任务会暂停在审批节点，并保存到：

```text
projects/20-workflow-orchestration/workflow-state.json
```

批准：

```bash
python3 projects/20-workflow-orchestration/main.py --approve
```

拒绝：

```bash
python3 projects/20-workflow-orchestration/main.py --reject
```

也可以直接恢复但保持等待：

```bash
python3 projects/20-workflow-orchestration/main.py --resume
```

## 测试

```bash
python3 -m unittest tests/test_workflow_orchestration.py -v
```

## 当前实现

- `WorkflowState` 保存工作流状态、当前节点、数据和历史；
- `WorkflowRunner` 负责节点调度和状态保存；
- 两个资料收集节点使用线程池并行执行；
- `risk_level` 控制是否进入人工审批；
- 审批结果从 JSON 状态文件恢复后继续执行。
