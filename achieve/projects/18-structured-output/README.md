# 18 - 结构化输出与结果校验

这一课让模型不再返回任意格式的自然语言，而是返回符合固定 JSON 契约的结果。

项目演示三个环节：

```text
模型生成 JSON
      ↓
Python 解析并校验字段
      ↓
格式错误？把错误反馈给模型自动修复
```

## 运行环境

在项目根目录执行：

```bash
source .venv/bin/activate
python3 -m pip install -r projects/18-structured-output/requirements.txt
```

## 离线演示

离线演示不调用模型，模拟一次错误输出和一次修复后的输出：

```bash
python3 projects/18-structured-output/main.py --demo
```

## 使用模型

确保 `.env` 中已经配置模型服务：

```env
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的 API Key
OPENAI_MODEL=deepseek-v4-flash
```

如果终端里已经设置了同名环境变量，它们会覆盖 `.env`。需要使用 `.env` 时先执行：

```bash
unset OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL
```

启动：

```bash
python3 projects/18-structured-output/main.py \
  --task "整理 Agent 工具调用的学习要点"
```

## 输出契约

模型必须返回以下 JSON 对象：

```json
{
  "title": "主题标题",
  "summary": "主题摘要",
  "key_points": ["要点一", "要点二"],
  "confidence": "high",
  "sources": ["来源文件或链接"]
}
```

代码会检查：

- 必填字段是否存在；
- 字段类型是否正确；
- 字符串是否为空；
- `key_points` 是否包含 1～5 项；
- `confidence` 是否为 `high`、`medium` 或 `low`；
- 是否出现契约之外的字段。

## 运行测试

```bash
python3 -m unittest tests/test_structured_output.py -v
```

本课没有使用 provider 专属的 Structured Outputs 参数，因此可以同时用于官方 DeepSeek API 和 OpenAI 兼容网关。
