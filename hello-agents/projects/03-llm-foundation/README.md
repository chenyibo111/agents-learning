# 03 - LLM 基础

对应课程：[03-llm-foundation](../../lessons/03-llm-foundation.md)，状态：🔁；回顾 `achieve` 第 1 课的网关配置。

运行：`python projects/03-llm-foundation/main.py --demo`；`--llm` 调用 OpenAI 兼容接口。Demo 展示消息协议、历史消息、上下文截断、粗略 token 预算和结构化输出校验；token 估算不代表具体模型 tokenizer 的精确计费。

离线练习：

```powershell
python projects/03-llm-foundation/main.py --demo --history
python projects/03-llm-foundation/main.py --demo --max-tokens 20
python projects/03-llm-foundation/main.py --demo --response-format json
python projects/03-llm-foundation/main.py --demo --system "只输出 JSON，不要解释"
```

代码已经预置上述实验对应的实现：`build_messages()` 负责消息协议，`truncate_messages()` 负责上下文预算，`validate_structured_response()` 负责 JSON 校验。真实模型输出仍然是不可信的建议，不能把 `source=\"model-generated\"` 当作外部证据。

测试：

```powershell
python -m unittest hello-agents/tests/test_llm_foundation.py -v
```
