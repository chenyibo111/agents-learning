# 第 10 课 Agent Protocols 工程实现设计

## 目标

把第 10 课的固定 task envelope Demo 扩展为一个依赖轻量、可测试的本地协议边界：用 JSON-RPC 实现 MCP 风格的工具/资源发现与调用，用 A2A 风格任务 envelope 管理 Agent 委派任务的生命周期；同时保留原有 `make_task()`、`--demo` 和 `--llm`。

## 核心边界

- `contracts.py` 只定义 JSON-RPC、工具、资源和任务的数据契约，所有对象都能安全转换为 JSON。
- `registry.py` 只负责显式注册能力；工具参数按有限 JSON Schema 校验，资源只能读取注册的 URI，不接受任意文件路径或 URL。
- `auth.py` 负责 token 到 scope 的映射和能力授权；协议错误不回显 token、原始凭证或内部异常堆栈。
- `server.py` 是统一 JSON-RPC 入口，处理版本协商、认证、权限、幂等和重放，再分发到 MCP/A2A 方法。
- `tasks.py` 管理 `submitted → working → completed/failed/cancelled/expired` 状态转换。超时会结束调用方等待并把任务标记为 `expired`；Python 线程不能被强制杀死，因此长任务应使用协作式取消。
- `mcp_adapter.py` 暴露本地 MCP 风格 JSON-RPC 适配器，并可选地构造官方 `mcp.server.fastmcp.FastMCP` 实例；官方 SDK 不作为离线 Demo 的硬依赖。
- `a2a_adapter.py` 提供任务提交、查询、取消的客户端薄适配器。

## 数据流

```text
JSON 请求
  ↓ decode + 契约校验
版本协商 → 重放检查 → 幂等缓存 → token 认证/授权
  ↓
tools/list | tools/call | resources/list | resources/read
  或 tasks/submit | tasks/get | tasks/cancel
  ↓
JSON-RPC 响应 / A2A task envelope
```

## 错误和安全规则

- 使用 JSON-RPC 基础错误码 `-32600/-32601/-32602/-32603`，业务错误使用稳定的 `-320xx` 码。
- 同一 `idempotency_key` 搭配相同请求返回第一次响应；搭配不同请求拒绝，避免把幂等键误当成可复用凭证。
- 没有幂等键时，同一 JSON-RPC request id 在 TTL 内重复提交视为重放。
- 工具和资源默认需要显式 scope；列表发现可公开，实际调用必须授权。
- 版本只接受服务端声明的版本；不匹配返回可诊断但不泄漏内部信息的错误。
- 资源采用精确 URI 白名单，禁止通过 `file://`、任意 HTTP URL 或路径穿越读取数据。

## 非目标

- 不在本课伪造完整的 A2A/ANP 网络传输协议，不引入外网服务或真实凭证。
- 不把线程取消描述成强制终止；生产环境应替换为支持协作取消的任务执行器。
- 不要求安装官方 `mcp` SDK 才能运行测试和离线 Demo。

## 验收标准

1. 原有 `make_task()`、`--demo`、`--llm` 仍可运行。
2. MCP 风格 JSON-RPC 能发现并调用工具、发现并读取白名单资源。
3. 参数错误、未知方法、未授权能力、未知资源和版本不匹配返回稳定错误码。
4. A2A 任务能查询状态、完成、失败、取消和超时，非法状态转换被拒绝。
5. 幂等键、request id 重放保护和认证 scope 有契约测试。
6. 不依赖网络即可运行课程测试；官方 MCP SDK 存在时有可选适配入口。
