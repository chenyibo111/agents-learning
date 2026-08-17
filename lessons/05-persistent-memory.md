# 第五课：持久化记忆

## 1. 短期记忆和持久化记忆

第四课的消息只保存在 Python 变量中：

```python
messages = [...]
```

程序退出后，变量就消失了。

本课使用 JSON 文件保存消息：

```python
SESSION_FILE.write_text(
    json.dumps(messages, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

重新运行时再读取：

```python
data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
```

## 2. 运行实验

1. 启动程序；
2. 输入“请计算 8 加 4”；
3. 输入 `exit`；
4. 再次启动程序；
5. 输入“把刚才的结果乘以 3”；
6. 查看 `session.json` 的内容。

## 3. 本课限制

JSON 文件适合学习和小规模实验，但生产系统还需要考虑：

- 文件并发写入；
- 会话 ID；
- 数据库；
- 消息数量和 Token 长度；
- 隐私保护和加密；
- 用户删除数据。

