# 第 24 课：用 smolagents 重写 Agent

## 一、为什么需要 Agent 框架

第 23 课中，我们手写了完整的 Agent 循环：

```text
用户输入
  → 模型
  → tool_call
  → 参数解析
  → 工具执行
  → 工具结果反馈给模型
  → 最终答案
```

手写的好处是透明，每一行都能看到；缺点是通用代码很多：

- 工具描述转换；
- 模型请求；
- tool call 解析；
- JSON 参数解析；
- 工具结果拼接；
- 最大步骤数控制；
- 最终答案提取。

`smolagents` 的作用就是把这些通用 Agent 循环封装起来，让我们主要关注工具和业务能力。

## 二、本课项目

项目位于 `projects/24-smolagents-agent/`，工具定义在 [tools.py](../projects/24-smolagents-agent/tools.py)，框架适配在 [agent_runner.py](../projects/24-smolagents-agent/agent_runner.py)。

工具能力与第 23 课对应：

```text
add_numbers
mul_numbers
search_notes
read_resource
```

但工具不再通过自定义 `ToolDefinition` 注册，而是使用框架装饰器：

```python
from smolagents import tool


@tool
def add_numbers(a: int, b: int) -> int:
    """计算两个整数的和。"""
    return a + b
```

这里的函数签名和 docstring 很重要。框架会根据它们生成工具描述，让模型知道：

- 工具叫什么；
- 工具做什么；
- 参数叫什么；
- 参数是什么类型。

## 三、`ToolCallingAgent`

本课选择 `ToolCallingAgent`：

```python
agent = ToolCallingAgent(
    tools=all_tools(),
    model=model,
    max_steps=6,
)
```

它适合当前课程，因为第 23 课刚学习了 Tool Calling。我们暂时不使用 `CodeAgent`，原因是 `CodeAgent` 会让模型生成并执行 Python 代码，安全边界更复杂。

`max_steps=6` 是框架层的循环上限，作用类似第 23 课手写 Agent 的 `max_rounds`。

## 四、模型适配

`agent_runner.py` 中的 `build_model()` 使用：

```python
from smolagents import OpenAIServerModel
```

它可以连接 OpenAI 兼容服务：

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
```

例如：

```text
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
# 与 DeepSeek Thinking 模式兼容
OPENAI_TOOL_CHOICE=auto
```

API Key 只从环境变量读取，不写入源码，也不打印到日志。

`smolagents` 某些版本默认会发送 `tool_choice=required`。部分 DeepSeek Thinking
接口不接受这个值，因此本课适配器默认改为 `tool_choice=auto`，并允许通过
`OPENAI_TOOL_CHOICE` 覆盖。`auto` 的含义是让模型自行决定是否调用工具。

## 五、框架隐藏了什么

第 23 课需要手写：

```python
response = client.chat.completions.create(...)
tool_calls = response.choices[0].message.tool_calls
arguments = json.loads(tool_call.function.arguments)
result = execute_tool(name, arguments)
messages.append({"role": "tool", "content": result})
```

本课通过：

```python
answer = agent.run(user_input)
```

把这些细节隐藏起来。

但隐藏不等于消失。框架内部仍然需要完成：

```text
读取工具 Schema
  → 请求模型
  → 接收 tool_call
  → 找到对应工具
  → 调用工具
  → 反馈结果
  → 继续循环
```

所以学习框架之前先手写一遍非常重要，否则只能知道 API 怎么调用，却不知道框架到底在帮你做什么。

## 六、工具安全仍然存在

即使使用框架，也不能认为工具天然安全。

例如：

```python
@tool
def read_resource(uri: str) -> str:
    if uri not in NOTES_BY_URI:
        raise ValueError("未知资源 URI")
    return NOTES_BY_URI[uri]["content"]
```

这个白名单仍然必须由开发者编写。

如果直接实现成：

```python
return open(uri).read()
```

那么模型就可能间接读取任意本地文件。

框架负责调用循环，不会自动替你完成业务权限设计。

## 七、运行方式

离线 Demo：

```bash
python3 projects/24-smolagents-agent/main.py --demo
```

真实 Agent：

```bash
python3 -m pip install -r projects/24-smolagents-agent/requirements.txt
python3 projects/24-smolagents-agent/main.py --interactive
```

如果没有安装 `smolagents`，交互模式会返回安装提示；离线 Demo 和测试不依赖真实模型。

## 八、测试重点

测试文件是 [tests/test_smolagents_agent.py](../tests/test_smolagents_agent.py)，覆盖：

- 加法工具；
- 乘法工具；
- 笔记搜索；
- 注册资源读取；
- 非法 URI 拦截；
- 占位 API Key 拒绝；
- 缺少 smolagents 时的可执行提示；
- 离线 Demo。

真实模型调用不放入自动化测试，避免测试依赖网络、账号和模型输出的随机性。

## 九、与第 23 课的核心对比

| 问题 | 第 23 课 | 第 24 课 |
|---|---|---|
| 工具如何描述 | 手写 Schema | `@tool` + 类型提示 + docstring |
| Agent 如何循环 | 手写 `while` | `ToolCallingAgent` |
| 如何解析 tool call | 手写 JSON 解析 | 框架处理 |
| 如何限制步骤 | 自己维护轮数 | `max_steps` |
| 工具安全 | 自己负责 | 仍然自己负责 |
| 参数可信度 | 自己校验 | 仍需校验 |

结论是：

> 框架减少了通用代码，但没有消除 Agent 系统的安全、可靠性和业务设计责任。

## 十、动手实验

1. 给 `tools.py` 增加一个 `divide_numbers` 工具，处理除数为零；
2. 把 `max_steps` 从 6 改成 2，观察复杂任务是否提前结束；
3. 删除某个工具的 docstring，观察框架是否还能生成有效描述；
4. 比较第 23 课的 `LLMToolAgent` 和本课的 `ToolCallingAgent`，分别记录调用循环由谁负责。
