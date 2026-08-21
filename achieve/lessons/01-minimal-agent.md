# 第一课：手写最小 Agent

## 本课目标

- 使用 Python 调用兼容 OpenAI SDK 的模型接口；
- 理解 `messages`、system、user 和 assistant 消息；
- 搭建一个最小的 Agent 请求循环；
- 为后续工具调用和多步 Agent 打基础。

## 对应项目

```text
projects/01-minimal-agent/
```

## 学习重点

先理解一次完整的模型请求：

```text
用户输入 → messages → LLM → assistant 回复
```

后续课程会在这个基础上增加工具、循环、记忆和状态管理。

