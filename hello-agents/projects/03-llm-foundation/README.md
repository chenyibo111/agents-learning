# 03 - LLM 基础

对应课程：[03-llm-foundation](../../lessons/03-llm-foundation.md)，状态：🔁；回顾 `achieve` 第 1 课的网关配置。

运行：`python projects/03-llm-foundation/main.py --demo`；`--llm` 调用 OpenAI 兼容接口。Demo 展示消息拼接和粗略 token 预算，不代表具体模型 tokenizer 的精确计费。

实验：加入历史消息；设置上下文预算并截断；把模型输出改成 JSON 后在程序中校验。
