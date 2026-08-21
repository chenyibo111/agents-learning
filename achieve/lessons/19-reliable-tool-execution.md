# 第十九课：可靠工具执行

## 1. 为什么工具调用不能直接执行

前面的 Agent 可以根据模型返回的工具调用，直接执行 Python 函数：

```text
模型请求工具
  ↓
解析参数
  ↓
调用函数
  ↓
把结果返回模型
```

但真实工具可能遇到很多问题：

- 参数类型错误；
- 网络暂时不可用；
- 服务响应太慢；
- 工具执行成功，但响应丢失；
- Agent 重试时重复创建订单或扣款。

因此，工具调用需要经过一个可靠执行层，而不是让模型直接控制函数。

## 2. 运行项目

本课不需要 API Key：

```bash
source .venv/bin/activate
python3 projects/19-reliable-tool-execution/main.py --demo
```

运行测试：

```bash
python3 -m unittest tests/test_reliable_tool_execution.py -v
```

## 3. ToolSpec

每个工具使用 `ToolSpec` 描述：

```python
ToolSpec(
    name="add_numbers",
    description="计算两个数字的和",
    parameters={...},
    handler=add_numbers,
    max_attempts=3,
    base_delay=1.0,
    timeout_seconds=2.0,
)
```

它把工具的几个重要属性集中起来：

- 工具名称和描述；
- 参数契约；
- 实际处理函数；
- 最大尝试次数；
- 重试退避时间；
- 单次执行超时时间；
- 哪些异常可以重试。

这样执行器不需要知道每个工具的业务细节，只需要读取 `ToolSpec`。

## 4. 参数校验必须先于执行

`validate_arguments()` 会根据工具的参数定义检查输入：

```json
{
  "type": "object",
  "properties": {
    "a": {"type": "number"},
    "b": {"type": "number"}
  },
  "required": ["a", "b"],
  "additionalProperties": false
}
```

如果传入：

```json
{"a": "not-a-number", "b": 2}
```

工具不会被调用，而是直接返回：

```json
{
  "ok": false,
  "error_type": "validation_error",
  "attempts": 0
}
```

这有两个好处：

1. 避免把错误参数传给外部系统；
2. 避免对确定性错误进行无意义重试。

## 5. 只重试临时错误

项目定义了：

```python
class TransientToolError(RuntimeError):
    pass
```

工具只有在明确抛出这个异常时，才会进入重试流程：

```text
第 1 次失败
  ↓ 等待 1 秒
第 2 次失败
  ↓ 等待 2 秒
第 3 次执行
```

普通的 `ValueError`、参数错误和业务拒绝不会重试。

重试次数是“总尝试次数”，不是“额外重试次数”：

```python
max_attempts = 3
```

表示最多执行三次，包括第一次调用。

## 6. 为什么使用指数退避

如果服务暂时过载，立即连续发送请求可能让问题更严重。

指数退避通常是：

```text
1 秒 → 2 秒 → 4 秒 → 8 秒
```

当前 Demo 为了快速演示，把等待函数替换成了打印函数，不会真的等待 3 秒；生产环境应使用真实的 `time.sleep()`，并通常加一点随机抖动，避免大量客户端同时重试。

## 7. 超时控制

`ToolExecutor._run_with_timeout()` 使用线程池执行工具：

```python
future = executor.submit(spec.handler, arguments)
future.result(timeout=spec.timeout_seconds)
```

如果工具超过时间，就返回：

```json
{
  "ok": false,
  "error_type": "timeout",
  "attempts": 1
}
```

当前实现默认不重试超时。原因是：

```text
超时 ≠ 工具一定没有执行
```

例如写入订单的请求已经在服务端成功，但客户端没有及时收到响应。此时再次重试可能产生重复订单。

## 8. 幂等性

幂等性表示同一个请求执行一次或多次，最终效果相同。

项目通过 `idempotency_key` 实现简单的内存缓存：

```python
executor.execute(
    "write_record",
    {"value": "hello"},
    idempotency_key="request-1",
)
```

第一次调用：

```json
{
  "result": "record-1",
  "cached": false
}
```

相同 key 第二次调用：

```json
{
  "result": "record-1",
  "attempts": 0,
  "cached": true
}
```

工具函数只执行了一次，因此不会重复产生副作用。

## 9. 统一错误结果

执行器不会把所有异常都直接抛给上层，而是转换成统一结构：

```text
unknown_tool       工具不存在
validation_error   参数不合法
tool_error         普通业务错误
retry_exhausted    临时错误重试耗尽
timeout            超时
```

这样的结果可以直接返回给 Agent，让模型知道工具调用失败的原因，同时避免模型接触复杂的 Python 异常栈。

## 10. 和前面课程的关系

第 17 课关注任务整体状态：

```text
任务执行到哪一步？失败后如何恢复？
```

第 18 课关注模型输出格式：

```text
模型返回的 JSON 是否符合契约？
```

第 19 课关注工具执行安全：

```text
参数是否合法？是否应该重试？是否超时？会不会重复执行？
```

三者组合后，Agent 才逐渐具备可靠工作流的基础。

## 11. 可靠性边界

当前项目是教学版：

- 幂等缓存只存在内存中，程序重启后丢失；
- 没有并发锁；
- Python 线程超时不能强制终止已经运行的函数；
- 没有将幂等状态保存到数据库；
- 没有接入真实模型的工具调用协议。

真实支付、订单等系统通常需要服务端幂等键、数据库唯一约束和事务，而不能只依赖客户端缓存。

## 12. 思考题

1. 为什么参数错误不应该重试？
2. 为什么超时默认不应该重试？
3. 如果工具执行成功但缓存保存失败，重试会发生什么？
4. 内存中的幂等缓存重启后消失，如何改成数据库？
5. 如何把第 19 课的工具结果保存到第 17 课的 `AgentState.results` 中？
