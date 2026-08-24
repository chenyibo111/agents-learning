# 15 - 赛博小镇 Agent

对应课程：[15-cyber-town](../../lessons/15-cyber-town.md)。本项目把三层目标收敛为一个标准库离线模拟：商人、研究员和信使在共享环境中按 tick 观察、决策并产生事件。

## 运行

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe hello-agents\projects\15-cyber-town\main.py --demo --ticks 1
.\.venv\Scripts\python.exe hello-agents\projects\15-cyber-town\main.py --demo --json --seed 7 --ticks 3 --output-dir .tmp\cyber-town
```

`--llm` 仍保留为课程概念说明模式；默认运行不联网、不调用真实模型。`--output-dir` 会生成 `checkpoint.json`、`events.jsonl` 和 `report.json`。

## 工程结构

- `schemas.py`：Agent、World、Observation、Action、Event 和 SimulationState。
- `world.py`：初始世界及交易、消息、拒绝规则；资源变更只能从环境入口发生。
- `visibility.py`：把全局状态投影为单个 Agent 可见的 Observation，隔离其他 Agent 的私有记忆。
- `policies.py`：`Policy` 接口与三个确定性规则 NPC；未来 LLM Policy 只能替换决策器，不能绕过环境规则。
- `engine.py`：按 Agent 顺序推进 tick，记录事件，保存 seed，并支持 checkpoint 恢复。
- `storage.py`：原子写入 checkpoint、事件 JSONL 和评测报告。
- `evaluation.py`：事件统计、资源守恒、隐私泄露和可重放检查。

## 实验

1. 在 `world.py` 增加冲突规则，例如信使只能在天气晴朗时发送消息，并为拒绝分支添加测试。
2. 用同一个 `--seed` 分别运行连续模拟和 checkpoint 恢复，比较两个 `state` JSON。
3. 新增一个实现 `Policy` 的模型策略，统计每 tick 的调用次数和成本；环境规则仍然负责校验交易。

## 验收对应关系

- 一 tick：输出 `offer -> trade_completed -> message` 事件链。
- 状态边界：Observation 只包含公共事实、公共事件和自己的私有状态。
- 可重放：同 seed、相同 Policy 和相同 tick 数得到相同状态。
- 可解释：每个事件含 `rule` 字段，非法交易会生成 `action_rejected`。
- 可恢复：checkpoint 从已完成 tick 继续，不重复旧事件。
