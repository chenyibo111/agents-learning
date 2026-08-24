# 04 - Agent 经典范式

对应课程：[04-agent-patterns](../../lessons/04-agent-patterns.md)，状态：🔁；回顾 `achieve` 第 3、17、20 课。

运行：`python projects/04-agent-patterns/main.py --demo`；`--llm` 请求模型比较范式。Demo 使用结构化 `TraceEvent` 轨迹对比 ReAct、Plan-and-Solve 与 Reflection，不记录隐藏思考文本。

离线实验入口：

```powershell
python projects/04-agent-patterns/main.py --demo --invalidate-plan
python projects/04-agent-patterns/main.py --demo --repeat-react
python projects/04-agent-patterns/main.py --demo --valid-citation
python projects/04-agent-patterns/main.py --demo --json
```

代码已经预置本章实验：计划中途失效时重规划，ReAct 重复行动检测，以及基于规则的 Reflection 引用检查。重点阅读 `run_react()`、`run_plan_and_solve()`、`run_reflection()` 和 `TraceEvent`。

测试：

```powershell
python -m unittest hello-agents/tests/test_agent_patterns.py -v
```
