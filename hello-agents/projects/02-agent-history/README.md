# 02 - Agent 发展史

对应课程：[02-agent-history](../../lessons/02-agent-history.md)，状态：🆕。

运行：`python projects/02-agent-history/main.py --demo`；配置 `.env` 后可运行 `--llm` 做概念总结。Demo 输出从符号主义到 LLM Agent 的时间线、表示方式、反馈信号和限制。

也可以查看失败案例或结构化时间线：

```powershell
python projects/02-agent-history/main.py --failures
python projects/02-agent-history/main.py --json
```

实验代码已经预置：历史阶段、失败案例和时间线数据结构都可以直接运行；学习时重点阅读 `Stage`、`timeline_data()`、`render_timeline()` 和 `render_failures()`，并解释“表示方式”和“反馈信号”为什么会改变 Agent 能力。

测试：

```powershell
python -m unittest hello-agents/tests/test_agent_history.py -v
```
