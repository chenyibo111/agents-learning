# 24 - 用 smolagents 重写 Agent

这一课把第 23 课手写的 Agent 决策循环交给 `smolagents`，重点观察框架替我们隐藏了什么。

## 安装依赖

```bash
python3 -m pip install -r projects/24-smolagents-agent/requirements.txt
```

如果只运行离线 Demo 和单元测试，不安装 `smolagents` 也可以。

## 离线 Demo

离线 Demo 直接运行工具函数，不访问模型：

```bash
python3 projects/24-smolagents-agent/main.py --demo
```

## 运行真实 Agent

配置 `.env`：

```text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
# DeepSeek Thinking 模式与 smolagents 的 tool_choice=required 不兼容
OPENAI_TOOL_CHOICE=auto
```

然后运行：

```bash
python3 projects/24-smolagents-agent/main.py --interactive
```

程序会创建：

```python
ToolCallingAgent(
    tools=[add_numbers, mul_numbers, search_notes, read_resource],
    model=model,
    max_steps=6,
)
```

模型负责选择工具，`smolagents` 负责工具调用循环，工具函数负责业务执行。

适配器默认使用 `tool_choice=auto`。部分模型或兼容网关（尤其是 Thinking 模式）不接受
`tool_choice=required`；如网关有特殊要求，可以通过 `OPENAI_TOOL_CHOICE` 覆盖默认值。

## 与第 23 课的区别

第 23 课需要手写：

```text
模型请求
→ 解析 tool_call
→ 解析 JSON 参数
→ 调用工具
→ 拼接 tool message
→ 再次请求模型
```

本课主要写：

```python
agent = ToolCallingAgent(tools=tools, model=model)
agent.run(user_input)
```

但工具安全、参数校验、权限和预算仍然需要开发者负责。

## 测试

```bash
python3 -m unittest tests/test_smolagents_agent.py -v
```

测试不访问真实模型。当前环境没有安装 `smolagents` 时，测试会验证适配器能给出可执行的安装提示。
