# 05 - 持久化记忆

第四课的 `messages` 只存在于内存中，程序关闭后就会消失。本课把消息保存到当前目录的 `session.json`，让 Agent 在重新启动后恢复对话。

## 运行

```powershell
python .\projects\05-persistent-memory\main.py
```

先输入：

```text
请计算 8 加 4
```

输入 `exit` 退出程序，再重新运行程序，然后输入：

```text
把刚才的结果乘以 3
```

## 本课目标

- 理解 Python 对象和 JSON 文本之间的转换；
- 学习保存和恢复 `messages`；
- 区分短期记忆和持久化记忆；
- 认识本地会话文件中的隐私和安全问题。

## 注意

`session.json` 可能包含用户问题和模型回答，已经通过 `.gitignore` 排除，不应提交到公开仓库。

