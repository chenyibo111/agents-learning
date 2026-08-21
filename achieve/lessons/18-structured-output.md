# 第十八课：结构化输出与结果校验

## 1. 为什么不能直接相信模型输出

如果让模型回答：

```text
请整理 Agent 工具调用的要点。
```

模型可能返回 Markdown、自然语言、代码围栏或格式不完整的 JSON。

这对人来说通常可以阅读，但程序无法稳定地读取：

```python
result["key_points"]
```

因此，可靠的 Agent 需要把模型输出当成“不可信输入”，经过解析和校验之后才能进入后续业务流程。

本课的流程是：

```text
任务
  ↓
模型输出 JSON
  ↓
JSON 解析
  ↓
字段和类型校验
  ↓
通过：交给程序
失败：反馈错误并让模型修复
```

## 2. 运行项目

在 macOS 或 Linux 的 zsh 中：

```bash
source .venv/bin/activate
python3 -m pip install -r projects/18-structured-output/requirements.txt
python3 projects/18-structured-output/main.py --demo
```

`--demo` 会模拟：

1. 模型返回错误的 `key_points` 类型和 `confidence` 值；
2. 校验器列出具体错误；
3. 修复器返回符合契约的 JSON；
4. 程序再次校验并输出结果。

使用真实模型：

```bash
python3 projects/18-structured-output/main.py \
  --task "整理 Agent 工具调用的学习要点"
```

## 3. 输出契约

项目中的 `OUTPUT_SCHEMA` 是本课的输出契约：

```python
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["title", "summary", "key_points", "confidence", "sources"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "key_points": {"type": "array"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "sources": {"type": "array"},
    },
}
```

它表达了程序期望的形状：顶层必须是对象，并且包含五个字段。

本项目把契约写成 JSON Schema 风格的字典，但没有依赖第三方 `jsonschema` 库，而是手动实现校验逻辑。这样可以更清楚地看到每一条规则如何工作，也能最大程度兼容不同的模型服务商。

## 4. JSON 解析和代码围栏

模型有时会返回：

````text
```json
{"title": "..."}
```
````

这不是纯 JSON，因为首尾多了 Markdown 代码围栏。

`strip_code_fence()` 会先去除围栏，然后 `parse_json_object()` 调用：

```python
json.loads(cleaned)
```

解析失败时，程序会抛出 `StructuredOutputError`，而不是让更底层的 `JSONDecodeError` 直接泄漏给调用方。

## 5. 字段校验

`collect_validation_errors()` 负责收集错误，而不是发现一个错误就立即停止。

例如下面的结果：

```json
{
  "title": "",
  "summary": "有内容",
  "key_points": "不是数组",
  "confidence": "unknown"
}
```

会同时发现：

```text
title 为空
缺少 sources
key_points 不是数组
confidence 不是允许的枚举值
```

一次收集多个错误的好处是：模型下一次修复时可以同时处理全部问题，减少来回请求。

## 6. 自动修复

`validate_with_repair()` 的核心逻辑是：

```text
尝试解析和校验
  ↓
成功 → 返回结构化结果
  ↓
失败 → 调用 repair(content, errors)
  ↓
再次解析和校验
```

默认最多修复两次：

```python
MAX_REPAIR_ATTEMPTS = 2
```

修复提示会同时包含：

- 输出契约；
- 校验错误列表；
- 模型原始输出。

这比简单地告诉模型“请重新输出 JSON”更有效，因为模型知道具体违反了哪些规则。

## 7. 为什么不使用原生 Structured Outputs

OpenAI 的部分模型和接口支持直接传入 JSON Schema，让服务端保证格式。但当前项目需要兼容：

- DeepSeek 官方 OpenAI 兼容接口；
- Mihoyo 内部 OpenAI 兼容网关；
- 不同模型对 `response_format` 或 JSON Schema 的支持差异。

因此本课选择更通用的方案：

```text
提示约束 + json.loads + Python 校验 + 自动修复
```

它不能保证模型第一次就返回正确结果，但程序可以可靠地拒绝错误结果，并给模型一次修复机会。

## 8. 和第 17 课的关系

第 17 课解决的是“任务进度是否可靠”：

```text
当前执行到哪一步？
失败后从哪里恢复？
```

第 18 课解决的是“模型结果是否可靠”：

```text
模型返回的内容能不能被程序安全读取？
```

组合起来就是：

```text
Agent 状态管理
  + 结构化结果校验
  = 更可靠的可恢复工作流
```

## 9. 可靠性边界

当前实现仍然是学习版：

- 手动校验规则还比较简单；
- 自动修复次数固定为 2 次；
- 修复请求本身没有加入网络重试；
- 没有保存每次原始输出和修复输出；
- 没有使用正式的 JSON Schema 校验库。

后续可以把校验失败信息保存到第 17 课的 `AgentState.results` 中，形成完整的可追踪工作流。

## 10. 思考题

1. 为什么模型返回了合法 JSON，仍然可能不能通过业务校验？
2. `sources` 是否应该允许为空？
3. 自动修复两次仍失败时，应该直接失败还是交给人工确认？
4. 如果模型返回了额外字段，应该丢弃还是报错？
5. 如何把本课的校验结果接入第 17 课的 `failed` 和 `--resume` 机制？
