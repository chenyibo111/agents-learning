# 01 - 初识智能体：最小 Agent

本项目对应 [Hello-Agents 第 1 章](../../lessons/01-agent-basics.md)，是 `hello-agents/` 的第一 个完整实践。它不导入 `achieve/`，但会对照旧项目第 1～3 课重新实现相同的递进：模型建议 → 工具调用 → 多步状态 → 错误和终止。

## 文件结构

```text
01-agent-basics/
├── agent.py       # 工具、schema、离线策略、安全执行和结果状态
├── llm_agent.py   # OpenAI 兼容 tool-calling 循环
├── main.py        # --demo / --llm 命令行入口
└── README.md
```

## 运行离线 Demo

从仓库根目录执行：

```bash
cd /Users/yibo.chen/project/agents-learning
.venv311/bin/python hello-agents/projects/01-agent-basics/main.py --demo
.venv311/bin/python hello-agents/projects/01-agent-basics/main.py --demo \
  --task "先计算 8 加 4，再把结果乘以 3"

# 查看结构化工具事件
.venv311/bin/python hello-agents/projects/01-agent-basics/main.py --demo \
  --task "先计算 8 加 4，再把结果乘以 3" --events
```

预期可以看到类似结果：

```text
answer=36.0; steps=2; tools=['add_numbers', 'multiply_numbers']
```

离线模式使用规则策略，不访问模型接口；它的价值是让工具注册、状态依赖和终止条件可以确定性复现。

## 运行真实 LLM Agent

```bash
cd /Users/yibo.chen/project/agents-learning/hello-agents
cp .env.example .env
# 编辑 .env，填写 OPENAI_BASE_URL、OPENAI_API_KEY、OPENAI_MODEL
.venv311/bin/python projects/01-agent-basics/main.py --llm \
  --task "请计算 23 加 19，并说明调用了什么工具"
```

真实模式中的职责边界：

```text
LLM：决定是否调用工具、调用哪个工具、传入什么参数
Python：校验工具名和参数、执行工具、回传 observation、限制步数
```

如果没有配置或不希望产生费用，使用 `--demo`。不要把 `.env`、API Key 或完整响应中的敏感字段提交到 Git。

## 建议阅读顺序

1. 先读课程笔记第 4～7 节，理解组件和数据流；
2. 阅读 `agent.py` 的 `TOOLS`、`call_tool()`、`execute_tool_safely()`；
3. 阅读 `run_offline()`，观察两步任务如何依赖第一步结果；
4. 最后阅读 `llm_agent.py`，比较模型循环和规则循环的相同点与不同点。

## 第一课实验

- 增加 `subtract_numbers` 工具，并补齐 schema、注册表、离线解析和测试；
- 把 `max_steps` 改成 1，观察多步任务如何被拒绝；
- 让除法工具接收 `b=0`，确认错误作为 observation 返回；
- 为每一步增加不含密钥的结构化事件日志；
- 用一句话记录：为什么“模型会调用工具”不等于“模型拥有工具权限”？

## 测试

```bash
.venv311/bin/python -m unittest hello-agents/tests/test_agent_basics.py -v
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v
```

完成标准：第一条命令的 7 个第一课测试通过，第二条命令的全部课程测试通过，并且你能解释一次两步任务中 state、tool observation、events 和 max_steps 的作用。
