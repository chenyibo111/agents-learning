# 第 23 课：Agent 通信与工具协议设计

## 1. 目标与范围

本课通过一个纯 Python 标准库项目，演示 Agent 与工具服务之间如何通过稳定的协议交换信息。重点不是实现完整 MCP，而是把协议边界讲清楚：

```text
Agent Client
    ↓ JSON-RPC 风格请求
Protocol Server
    ↓ 校验、路由、统一错误
Tool/Resource Registry
    ↓ 调用已注册的处理函数
Business Handlers
```

项目需要支持四类协议操作：

| 方法 | 作用 |
|---|---|
| `tools/list` | 查询可用工具及其参数描述 |
| `tools/call` | 按工具名称和参数调用工具 |
| `resources/list` | 查询可读取的资源 |
| `resources/read` | 按 URI 读取资源内容 |

项目只模拟本地进程内通信，不连接真实模型、不启动网络服务，也不依赖 API Key。协议消息通过 Python 字典序列化为 JSON，再反序列化处理，以模拟真实客户端/服务端边界。

## 2. 方案选择

### 方案 A：在 Agent 代码里直接调用 Python 函数

实现最简单，但 Agent 与业务函数强耦合。工具描述、参数校验和错误格式容易散落在调用方，无法体现跨进程协议的边界。

### 方案 B：使用第三方 MCP SDK

更接近生产协议，能减少底层协议代码，但会把学习重点转移到 SDK API，且不容易看清“描述、请求、分发、返回”的基本机制。

### 方案 C：实现一个 MCP 风格的最小 JSON 协议（采用）

使用标准库定义请求、响应、工具描述、资源描述和错误结构；通过注册表连接协议层与业务层。这样代码量可控，同时能直接观察协议边界，后续再把处理函数替换成真实 MCP 或 HTTP 适配器。

## 3. 模块设计

项目路径为 `projects/23-agent-protocol/`，包含以下模块：

### `protocol.py`

只定义协议数据结构和校验，不执行任何业务：

- `ToolDefinition`：工具名、描述、输入 JSON Schema；
- `ResourceDefinition`：资源 URI、名称、媒体类型；
- `ProtocolRequest` / `ProtocolResponse`：请求 ID、方法、参数、结果或错误；
- `ProtocolError`：错误码、消息和可选详情；
- JSON 编码/解码函数，拒绝缺少 `id`、`method` 或非对象 `params` 的请求。

请求采用 JSON-RPC 风格的最小结构：

```json
{
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "add_numbers",
    "arguments": {"a": 2, "b": 3}
  }
}
```

成功响应包含 `id` 和 `result`；失败响应包含 `id` 和统一的 `error` 对象，不把 Python 异常堆栈直接暴露给协议调用方。

### `registry.py`

负责注册和分发，不关心请求如何传输：

- 注册工具定义与 handler；
- 注册资源定义与 reader；
- 根据名称/URI 查找处理器；
- 调用前做工具参数的最小类型和必填字段校验；
- 将确定性错误转换为协议层可识别的错误。

注册表是协议层和业务层的唯一连接点，因此可以替换业务实现而不改变客户端协议。

### `server.py`

负责把协议方法映射到注册表：

- `tools/list` 返回工具定义；
- `tools/call` 校验 `name` 与 `arguments` 后调用注册表；
- `resources/list` 返回资源定义；
- `resources/read` 校验 URI 后读取资源；
- 未知方法、缺失参数、未知工具、未知资源都返回统一错误。

该层不包含加法、搜索或文件读取的业务细节。

### `business.py`

提供可观察的教学处理器：

- `add_numbers(a, b)`：演示结构化参数和结构化结果；
- `search_notes(query)`：在内置笔记列表中做简单关键词检索；
- `read_note(uri)`：只读取白名单 URI 对应的内置笔记内容，不接受任意文件路径。

内置数据让 Demo 和测试完全离线，也避免课程运行时读取用户文件或接触凭据。

### `main.py`

提供 Demo 客户端和命令行入口：

1. 创建注册表并注册工具、资源；
2. 通过 JSON 编码/解码模拟客户端发请求；
3. 先发现工具和资源，再调用工具、读取资源；
4. 展示一个未知工具和一个错误参数请求，观察统一错误响应。

## 4. 数据流

正常工具调用：

```text
Agent 发现工具
  → tools/list
  → 服务端返回名称、描述、input_schema
  → Agent 选择 add_numbers
  → tools/call + arguments
  → 协议层校验
  → 注册表找到 handler
  → business.add_numbers
  → 结果包装成 result
  → Agent 收到协议响应
```

资源读取与工具调用的差异是：工具通常表示“执行一个动作”，资源表示“读取一个有 URI 的对象”。两者都经过同一个协议服务，但分别使用名称和 URI 定位，避免把文件读取能力伪装成任意 shell 工具。

## 5. 错误处理与边界

定义稳定的错误码：

- `-32600`：请求结构无效；
- `-32601`：方法不存在；
- `-32602`：参数无效；
- `-32001`：工具或资源执行失败。

错误处理规则：

1. 协议结构错误在进入业务层前拦截；
2. 未知工具、资源和方法不调用任何 handler；
3. 参数类型错误不调用业务 handler；
4. 业务异常转换成简洁错误消息，不返回堆栈；
5. 资源 URI 必须匹配已注册 URI，不能把用户输入直接交给文件系统；
6. 协议层不负责重试、权限和模型决策，这些属于后续课程或上层编排职责。

## 6. 测试与验收标准

使用 `unittest`，新增 `tests/test_agent_protocol.py`，至少覆盖：

- 工具列表包含名称、描述和输入 Schema；
- 资源列表包含 URI 和媒体类型；
- 合法工具调用返回正确结果；
- 合法资源读取返回内容；
- 缺少必填参数时返回 `-32602` 且 handler 未被调用；
- 未知工具、未知资源和未知方法返回对应错误；
- 业务异常被包装成 `-32001`，不泄露堆栈；
- 非法资源 URI 不会读取任意本地路径；
- JSON 编码/解码后请求响应仍保持协议字段。

验收命令：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 projects/23-agent-protocol/main.py --demo
```

## 7. 非目标

- 不实现完整 MCP 生命周期、传输层或 SDK 兼容性；
- 不接入真实 LLM、HTTP、WebSocket 或外部搜索服务；
- 不实现认证、权限审批、重试和持久化；
- 不把任意本地文件系统暴露成资源服务。

这些内容分别在工具可靠性、工作流、安全和后续框架课程中继续展开。

## 8. 预期学习结果

完成后应能用自己的话解释：

1. 工具描述为什么必须包含参数 Schema；
2. Agent 为什么不应该直接依赖业务函数；
3. 协议错误和业务错误有什么区别；
4. 工具与资源为什么使用不同的定位方式；
5. 为什么“协议层负责通信，业务层负责执行”是可替换和可测试的边界。

## 9. 本课代码如何分层

项目位于 `projects/23-agent-protocol/`，建议按下面顺序阅读：

1. `protocol.py`：先看消息长什么样。`ProtocolRequest` 把 `id`、`method`、`params` 固定下来，`ProtocolResponse` 把成功和失败统一成 `result` 或 `error`。
2. `registry.py`：再看工具如何注册。工具描述和 handler 被放在一起，但调用前一定先经过 Schema 校验。
3. `business.py`：最后看业务函数。它只做计算、搜索和内置笔记读取，不知道请求来自哪里。
4. `server.py`：服务端把协议方法路由到注册表，并把内部异常转换成稳定错误，不把 traceback 返回给 Agent。
5. `main.py`：客户端通过 JSON 编码和解码发送请求，模拟协议跨越进程边界。

核心调用链是：

```text
main.request(payload)
  → encode_message
  → decode_message
  → ProtocolServer.handle
  → decode_request
  → _dispatch
  → ToolResourceRegistry
  → business handler
  → ProtocolResponse
```

## 10. 工具和资源的区别

工具是“请服务端执行一个动作”，例如：

```json
{
  "method": "tools/call",
  "params": {
    "name": "add_numbers",
    "arguments": {"a": 2, "b": 3}
  }
}
```

资源是“请服务端读取一个有稳定 URI 的对象”，例如：

```json
{
  "method": "resources/read",
  "params": {"uri": "note://agent-basics"}
}
```

资源 URI 必须先在注册表中存在，所以 `file:///etc/passwd` 不会被当作路径直接读取。这是协议边界带来的安全收益：业务层暴露的是明确能力，而不是任意文件系统。

## 11. 建议学习顺序

运行 Demo：

```bash
python3 projects/23-agent-protocol/main.py --demo
```

然后运行测试：

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

学习时重点观察三件事：

- 修改 `business.py` 的返回值时，协议格式不需要改变；
- 修改 `server.py` 的路由时，业务 handler 不需要知道协议细节；
- 把 `arguments` 中的 `b` 删除时，handler 不会执行，而是先返回 `-32602`。

## 12. 动手实验

完成下面三个小实验，并记录输入、输出和观察结果：

1. 添加 `multiply(a, b)` 工具，要求两个参数都是整数，并为它增加成功和缺少参数测试；
2. 添加 `note://workflow` 资源，验证它会出现在 `resources/list`，且只能通过精确 URI 读取；
3. 给一个测试 handler 增加调用计数器，证明非法参数在进入业务层之前就被拦截。

本课暂时不接入 MCP SDK。先掌握“描述 → 请求 → 校验 → 路由 → 执行 → 响应”这条链路，下一课再比较框架如何替我们封装这些边界。

## 13. 两种 Agent 模式

当前项目同时提供本地规则 Agent 和真正的 LLM Agent：

```bash
# 原有固定协议 Demo，保留用于回归和观察完整请求
python3 projects/23-agent-protocol/main.py --demo

# 本地规则 Agent，不需要 API Key
python3 projects/23-agent-protocol/main.py --interactive --agent local

# LLM Agent，需要 .env 中的兼容接口配置
python3 projects/23-agent-protocol/main.py --interactive --agent llm
```

### 本地规则 Agent

本地规则 Agent 的决策过程是确定性的：

```text
“计算 12 加 30”
  → 正则匹配数字和“加”
  → 生成 add_numbers 工具动作
  → 发送 tools/call
```

它适合学习协议和写测试，因为不需要网络，也不会因为模型随机性导致结果变化。它的局限是只能理解预先写好的输入模式。

### LLM Agent

LLM Agent 的决策由 OpenAI 兼容模型完成：

```text
用户问题
  → tools/list 和 resources/list
  → 模型查看工具描述
  → 模型返回普通文本或 tool_call
  → Agent 将 tool_call 转成协议请求
  → 工具结果反馈给模型
  → 模型生成最终答案
```

LLM Agent 使用 `agent.py` 中的 `LLMToolAgent`。它会把协议工具描述转换成 Chat Completions 的 `tools` 格式，但真正执行时仍然调用：

```text
ProtocolServer.handle()
  → ToolResourceRegistry.call_tool()
```

因此模型只能“决定调用什么”，不能越过协议层直接执行 Python 函数。

资源通过一个受控的 `read_resource` Agent 工具暴露给模型：

```text
模型调用 read_resource(uri)
  → Agent 转换为 resources/read
  → 注册表进行 URI 白名单校验
  → 返回资源内容
```

LLM Agent 还有两个重要边界：

- 模型返回的工具参数必须是合法 JSON；
- 工具调用最多进行 4 轮，避免无限循环。

## 14. 两种 Agent 的共同底座

两种 Agent 的区别只在“如何产生动作”：

| 项目 | 本地规则 Agent | LLM Agent |
|---|---|---|
| 决策方式 | 正则和关键词 | 模型 tool calling |
| 是否需要 API Key | 不需要 | 需要 |
| 是否经过协议层 | 是 | 是 |
| 是否直接调用业务函数 | 否 | 否 |
| 是否适合自动化测试 | 非常适合 | 使用 fake client 测试 |
| 灵活性 | 较低 | 较高 |

这说明 Agent 的核心可以拆成两部分：

```text
决策层：下一步做什么？
执行层：如何安全地执行？
```

本地规则和大模型可以替换决策层，但执行层仍然应该保留协议、参数校验、权限检查和错误处理。

## 15. LLM 模式配置

项目使用根目录已有的 OpenAI 兼容配置：

```text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
```

`OPENAI_API_KEY` 只在选择 `--agent llm` 时读取。本地规则模式和 Demo 模式不会读取或打印 API Key。
