# 第四课：对话记忆

## 1. 本课目标

让 Agent 在一次程序运行期间记住之前的消息。

这不是“模型自己记住了”，而是程序一直维护同一个 `messages` 列表：

```python
messages.append({"role": "user", "content": user_task})
run_agent(client, model, messages)
```

## 2. 观察对话历史

依次输入：

```text
请计算 8 加 4
把刚才的结果乘以 3
再除以 2
```

第二个问题没有直接给出数字，Agent 需要从历史消息中找到上一次结果。

## 3. `clear` 做了什么

```python
messages = messages[:1]
```

它保留第一条 system 消息，删除之前所有用户、助手和工具消息。

## 4. 重要限制

当前记忆只存在于内存中：

```text
程序运行期间：有记忆
程序退出后重新运行：记忆消失
```

以后学习会话持久化时，才会把 `messages` 保存到文件或数据库。

