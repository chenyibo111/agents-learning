# 第十七课：Agent 状态管理与可恢复工作流

## 1. 为什么需要状态

一次性 Agent 通常是：

```text
问题 → 模型 → 答案
```

复杂任务更像：

```text
规划 → 执行步骤 1 → 执行步骤 2 → 检查 → 完成
```

如果只依赖内存中的变量，程序中断后就会丢失：

- 当前执行到哪一步；
- 哪些步骤已经完成；
- 每一步产生了什么结果；
- 最终答案是否已经生成。

本课把这些信息保存成结构化状态，并在每一步后写入检查点。

## 2. 运行

离线演示：

```powershell
cd D:\AI\hello-agents-learning
.\.venv\Scripts\Activate.ps1
pip install -r .\projects\17-agent-state\requirements.txt
python .\projects\17-agent-state\main.py --demo
```

使用 DeepSeek：

```powershell
python .\projects\17-agent-state\main.py --task "整理 Agent 工具调用的学习要点"
```

恢复任务：

```powershell
python .\projects\17-agent-state\main.py --resume
```

## 3. AgentState

状态包含：

```python
task
status
steps
current_step
results
final_answer
updated_at
```

这比只保存 messages 更清晰，因为它直接表达了业务进度。

## 4. 状态流转

本课使用以下状态：

```text
planning → executing → reviewing → completed
                           ↓
                         failed
```

状态机的价值是限制合法流程，避免程序在不清楚当前阶段时继续执行。

## 5. 检查点

每完成一个步骤，程序执行：

```python
state.current_step += 1
save_state(state)
```

如果程序之后中断，重新运行：

```powershell
python .\projects\17-agent-state\main.py --resume
```

就可以读取 JSON 状态并从未完成步骤继续。

## 6. 可靠性边界

当前检查点是本地 JSON 文件，适合学习和单机实验。真实系统还需要考虑：

- 并发写入；
- 原子保存；
- 文件损坏恢复；
- 数据库事务；
- 状态版本升级；
- 敏感信息加密。

## 7. 思考题

1. 为什么状态不应该只保存在 messages 中？
2. 如果步骤执行成功但保存检查点失败，恢复时会发生什么？
3. `failed` 状态和“可以继续恢复”之间是什么关系？
4. 如何给每个步骤增加重试次数和超时？

