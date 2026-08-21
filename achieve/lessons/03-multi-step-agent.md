# 第三课：多步 Agent 与错误处理

## 1. 多步任务是什么

例如用户提出：

```text
请先计算 8 加 4，再把结果乘以 3。
```

理想执行过程是：

```text
第 1 轮：调用 add_numbers(8, 4) → 得到 12
第 2 轮：调用 multiply_numbers(12, 3) → 得到 36
第 3 轮：生成最终答案
```

第二步依赖第一步的结果，这就是多步 Agent 任务。

## 2. 为什么要把错误返回给模型

除法工具遇到除数为 0 时不会让整个程序崩溃，而是返回：

```text
工具执行失败：除数不能为 0
```

这个错误会被追加到 `messages`，模型就可以向用户解释问题。

## 3. 重点阅读代码

重点查看这三处：

```python
max_steps = 5
```

```python
for step in range(max_steps):
```

```python
try:
    result = call_tool(name, arguments)
except Exception as error:
    result = f"工具执行失败：{error}"
```

## 4. 思考题

1. 如果 `max_steps` 设置成 1，多步任务会发生什么？
2. 如果模型一直重复调用同一个工具，当前程序如何停止？
3. 工具错误直接抛出和返回给模型，用户体验有什么区别？

