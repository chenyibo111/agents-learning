# 26 - 多 Agent 协作

本课在第 25 课的 LangGraph 状态图基础上，演示一个最小的多 Agent 工作流：

```text
coordinator
    ↓ 委派
researcher  ─┐
             ├─→ synthesizer → END
critic      ─┘
```

三个角色分别负责：

- `coordinator`：理解任务并分配角色；
- `researcher`：提供事实和背景资料；
- `critic`：从风险、缺口和反例角度审查；
- `synthesizer`：汇总不同 Agent 的结果。

## 安装依赖

本课复用 LangGraph：

```powershell
pip install -r .\projects\26-multi-agent-collaboration\requirements.txt
```

## 离线 Demo

```powershell
python .\projects\26-multi-agent-collaboration\main.py --demo
```

也可以指定任务：

```powershell
python .\projects\26-multi-agent-collaboration\main.py --demo --task "评估 Agent 是否适合生产环境"
```

Demo 不调用真实模型。每个角色是一个确定性的 Python 函数，先学习协作拓扑，再把角色函数替换为真实 LLM 调用。

## 关键知识点

- 一个 Agent 不等于一个模型实例，也可以是一个有明确职责的节点；
- 从一个节点连向多个节点，会形成 fan-out 并行分支；
- 多个分支汇入一个节点，会形成 fan-in 汇总；
- 并行节点共同更新同一个状态字段时，需要 reducer；
- `Annotated[list[str], operator.add]` 会把并行分支的列表结果合并起来；
- 并行分支的完成顺序不应作为业务逻辑依据。

## 测试

```powershell
python -m unittest tests/test_multi_agent_collaboration.py -v
```

