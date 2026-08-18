# 19 - 可靠工具执行

这一课实现一个与模型服务无关的 `ToolExecutor`，把普通函数调用包装成更可靠的工具执行流程：

```text
工具请求
  ↓
参数校验
  ↓
幂等缓存检查
  ↓
带超时执行
  ↓
临时错误才重试
  ↓
返回统一结果
```

## 运行

本课只使用 Python 标准库，不需要安装额外依赖：

```bash
source .venv/bin/activate
python3 projects/19-reliable-tool-execution/main.py --demo
```

## Demo 内容

Demo 会依次演示：

1. 参数类型错误在调用工具前被拒绝；
2. 临时错误按 1 秒、2 秒退避重试；
3. 慢工具超过超时时间后返回 `timeout`；
4. 相同幂等键只产生一次副作用，第二次直接返回缓存结果。

## 统一结果

成功结果：

```json
{
  "ok": true,
  "tool": "add_numbers",
  "result": 5.0,
  "attempts": 3,
  "cached": false
}
```

失败结果：

```json
{
  "ok": false,
  "tool": "add_numbers",
  "error_type": "validation_error",
  "message": "参数 a 必须是 number",
  "attempts": 0,
  "cached": false
}
```

## 测试

```bash
python3 -m unittest tests/test_reliable_tool_execution.py -v
```

本课暂时只实现工具执行器，没有接入模型工具调用。这样可以先独立观察可靠性规则，再在后续工作流课程中接入 Agent。
