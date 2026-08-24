# 10 - Agent 通信协议

对应课程：[10-agent-protocols](../../lessons/10-agent-protocols.md)，状态：✅ 工程实现完成；回顾 `achieve` 第 23 课。

运行离线工程 Demo：

```bash
python projects/10-agent-protocols/main.py --demo
```

保留旧的最小 envelope：不带参数运行仍输出 `make_task()`；真实模型模式只在需要时调用配置好的 OpenAI-compatible 网关：

```bash
python projects/10-agent-protocols/main.py
python projects/10-agent-protocols/main.py --llm
```

也可以直接发送一条 JSON-RPC 请求：

```bash
python projects/10-agent-protocols/main.py --request '{"jsonrpc":"2.0","id":"cli-1","method":"tools/call","params":{"name":"add_numbers","arguments":{"a":2,"b":3}}}'
```

离线 Demo 内置 `demo-token`，只用于本地课程演示；不要把真实 API Key 写进参数、测试或 Git。`read-only-token` 可以读取资源，但不能调用数学工具。

工程实现包含：

- MCP 风格 JSON-RPC：`tools/list`、`tools/call`、`resources/list`、`resources/read`；
- A2A 风格 task envelope：`tasks/submit`、`tasks/get`、`tasks/run`、`tasks/cancel`；
- `1.0` 版本协商、稳定 JSON-RPC/业务错误码、参数 Schema 校验；
- token → scope 的认证授权，资源精确 URI 白名单；
- 幂等键缓存和 request id TTL 重放保护；
- `submitted`、`working`、`completed`、`failed`、`cancelled`、`expired` 状态转换；
- 可选官方 `mcp.server.fastmcp.FastMCP` 工厂：`mcp_adapter.build_official_mcp_server()`。

## 三层实现状态

- 概念层：已区分 MCP、A2A、ANP 的通信边界。
- 最小实践层：保留带版本和 task id 的本地 envelope，并新增可运行的本地 JSON-RPC 请求。
- 工程实现层：已完成 `protocol_engine`、MCP/A2A 适配器、认证授权、超时取消、幂等/重放保护和 21 个协议契约测试。

## 工程目录

```text
10-agent-protocols/
├── protocol_engine/
│   ├── contracts.py       # JSON-RPC、工具、资源、任务契约
│   ├── errors.py          # 稳定错误码
│   ├── registry.py        # 能力注册表和 Schema 校验
│   ├── auth.py            # token 与 scope
│   ├── idempotency.py     # 幂等键
│   ├── replay.py          # request id TTL 重放保护
│   ├── tasks.py           # A2A 任务状态机
│   └── server.py          # 统一 JSON-RPC 分发边界
├── mcp_adapter.py         # 本地/官方 MCP 适配器
├── a2a_adapter.py         # A2A 风格客户端
└── main.py                # 离线 Demo、请求 CLI、LLM 讲解
```
