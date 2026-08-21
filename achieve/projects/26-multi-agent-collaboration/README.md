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

## 扩展实验：动态角色与失败隔离

基础 Demo 的角色和边是固定的。扩展版使用 LangGraph 的 `Send` API，由协调者根据任务动态选择专家：

```powershell
python .\projects\26-multi-agent-collaboration\advanced_main.py --demo
```

包含“生产、上线、风险或安全”的任务会自动增加 `fact_checker`：

```powershell
python .\projects\26-multi-agent-collaboration\advanced_main.py --demo --task "评估生产上线风险"
```

模拟事实核验服务超时：

```powershell
python .\projects\26-multi-agent-collaboration\advanced_main.py --demo --simulate-failure
```

扩展版不会因为一个专家失败就丢弃其他专家的结果，而是返回 `completed_with_warnings`，并把失败角色和错误记录到 `failures`。

扩展版测试：

```powershell
python -m unittest tests/test_multi_agent_advanced.py -v
```

## 真实 LLM 多 Agent

扩展版的固定角色函数还提供了真实模型实现：

- 协调者 Agent：调用模型选择角色；
- 研究员 Agent：独立调用模型分析任务；
- 审查员 Agent：独立调用模型寻找风险；
- 事实核验 Agent：独立调用模型标记需要核验的结论；
- 汇总 Agent：调用模型综合所有专家结果。

配置仓库根目录的 `.env`：

```text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
```

运行真实模式：

```powershell
python .\projects\26-multi-agent-collaboration\llm_main.py --task "评估多 Agent 协作是否适合生产环境"
```

一次任务通常包含：

```text
1 次协调者调用
N 次专家调用
1 次汇总调用
```

真实模式没有把 API Key 写入代码，也不会打印 API Key。没有配置密钥时请继续使用前面的离线 Demo。
