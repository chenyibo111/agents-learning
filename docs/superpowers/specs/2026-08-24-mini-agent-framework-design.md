# 第 7 课 Mini Agent Framework 设计

## 目标

在保留第 7 课原有 `--demo` 和 `--llm` 的前提下，新增一个不依赖第三方 Agent SDK 的工程化教学实现，将 Agent 拆成 Model、Tool、Memory、Policy 和 Runner 五个可替换边界，并支持离线规则模型、真实 OpenAI-compatible 文本模型、工具校验、权限、事件、重试和 SQLite checkpoint。

## 边界

`Model` 只生成结构化或文本响应；`Policy` 只解析响应并生成 final/tool_call 动作；`ToolRegistry` 负责工具注册、schema 校验和权限；`Memory` 负责消息与 checkpoint；`Runner` 负责有限循环、事件、失败和恢复。工具执行不进入 Model，模型不能绕过 Registry 直接产生副作用。

旧版 `main.py --demo` 继续使用共享 `run_loop`，新增 `--framework-demo` 运行 Mini Framework 离线实现，新增 `--llm-agent` 运行真实 LLM Agent。真实 LLM 只复用现有 `common.llm` 配置，不引入新的必选第三方依赖。

## 数据流

```text
task → Runner → Memory → Model → Policy
                         ↓ final
                       Result
                         ↓ tool_call
                   ToolRegistry → Tool → Observation → Memory
```

## 安全和恢复

- 未知工具、非法参数和未授权工具调用不得执行；
- 默认最多执行有限步数；
- 只有明确的临时工具错误可重试，副作用工具默认不自动重试；
- 每步保存可序列化状态到 SQLite；
- checkpoint 和事件对常见 credential 字段脱敏；
-真实 smoke test 不纳入默认测试，避免费用和网络不稳定。
