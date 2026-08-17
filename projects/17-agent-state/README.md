# 17 - Agent 状态管理与可恢复工作流

本课把一次性 Agent 改造成有状态的工作流：

- 用结构化状态保存任务、步骤和结果；
- 每完成一步就写入检查点；
- 程序中断后可以从上次进度恢复；
- 用明确的状态流转代替无限循环。

## 安装依赖

```powershell
pip install -r .\projects\17-agent-state\requirements.txt
```

## 离线演示

```powershell
python .\projects\17-agent-state\main.py --demo
```

## 使用 DeepSeek 创建任务

```powershell
python .\projects\17-agent-state\main.py --task "整理 Agent 工具调用的学习要点"
```

## 恢复中断的任务

```powershell
python .\projects\17-agent-state\main.py --resume
```

状态默认保存在：

```text
projects/17-agent-state/session-state.json
```

