# 23 - Agent 通信与工具协议

这一课用纯 Python 标准库实现一个 MCP 风格的最小协议 Demo，重点观察四层边界：

```text
Agent Client
    ↓ JSON 请求/响应
Protocol Server
    ↓ 方法路由与错误格式化
Tool/Resource Registry
    ↓ 查找 handler
Business Handlers
```

## 运行

本课完全离线，不需要 API Key：

```bash
python3 projects/23-agent-protocol/main.py --demo
```

Demo 依次演示：

1. `tools/list`：发现工具及其输入 Schema；
2. `resources/list`：发现可读资源及 URI；
3. `tools/call`：调用 `add_numbers`；
4. `resources/read`：读取白名单 URI 的内置笔记；
5. 未知工具错误；
6. 错误参数错误。

## 文件职责

- `protocol.py`：定义 JSON 消息、请求、响应和错误码；
- `registry.py`：注册工具/资源，校验参数并调用 handler；
- `server.py`：路由四个协议方法，隐藏 Python 异常细节；
- `business.py`：提供内存中的计算、搜索和笔记读取；
- `main.py`：模拟客户端经过 JSON 编码/解码边界调用服务端。

## 协议示例

请求：

```json
{
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "add_numbers",
    "arguments": {"a": 2, "b": 3}
  }
}
```

成功响应：

```json
{
  "id": 3,
  "result": {"a": 2, "b": 3, "sum": 5}
}
```

错误响应：

```json
{
  "id": 6,
  "error": {"code": -32602, "message": "缺少必填参数：b"}
}
```

## 测试

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

## 两种 Agent 模式

原有固定 Demo 保持不变：

```bash
python3 projects/23-agent-protocol/main.py --demo
```

本地规则 Agent 不需要 API Key：

```bash
python3 projects/23-agent-protocol/main.py \
  --interactive \
  --agent local
```

可以尝试：

```text
计算 12 加 30
计算 6 乘 7
搜索 工具 协议
读取 Agent 基础
```

LLM Agent 使用 OpenAI 兼容接口：

```bash
python3 projects/23-agent-protocol/main.py \
  --interactive \
  --agent llm
```

需要在 `.env` 中配置 `OPENAI_API_KEY`、可选的 `OPENAI_BASE_URL` 和 `OPENAI_MODEL`。LLM 只能通过协议返回的工具描述选择工具，工具结果会再次作为消息反馈给模型；它不会直接调用业务 handler。

LLM Agent 的循环是：

```text
用户输入
  → 模型
  → tool_call
  → ProtocolServer
  → 工具结果
  → 模型
  → 最终回答
```

代码中的最大工具调用轮数为 4，避免模型陷入无限调用循环。

## 学习实验

1. 在 `business.py` 增加一个 `multiply` 工具，并为它写参数 Schema 和测试；
2. 增加一个 `note://workflow` 资源，观察 `resources/list` 与 `resources/read` 的变化；
3. 给一个 handler 增加调用计数器，验证参数校验失败时 handler 不会被调用；
4. 在 `server.py` 中临时打印请求的 method，观察协议层收到的内容，再删除日志。

本课不是完整 MCP 实现，而是用最小代码理解“协议描述、请求、路由、业务执行、统一响应”的关系。
