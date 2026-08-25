# Werewolf LLM Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让第 16 课真实 LLM 对局具备明确的行动协议、可靠的降级、可信的运行指标和可控的请求延迟。

**Architecture:** 在 `LLMPolicy` 边界完成模型输出的别名归一化和严格结构校验；规则引擎继续作为最终权威，并允许显式安全无动作。评测从运行入口接收 offline 模式，模型适配器从环境读取价格和输出上限，所有新增行为通过离线单元测试验证。

**Tech Stack:** Python 3.11 标准库、`unittest`、OpenAI Chat Completions 兼容 HTTP 接口。

---

### Task 1: 行动协议、别名和 Schema 校验

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] 先添加测试：每个阶段 Prompt 包含允许枚举；`kill`、`speech`、`night_seer`、`no_action` 归一化为规则枚举；缺字段、错误类型、未知字段和阶段不允许行动安全降级。
- [x] 运行专属测试，确认新断言失败。
- [x] 增加阶段允许行动表、别名表和本地 JSON Schema 校验，不引入额外依赖。
- [x] 让 `LLMPolicy` 在解析后先归一化、再校验，保留服务端 actor_id 和模型指标。
- [x] 运行相关测试，确认通过。

### Task 2: 阶段化安全降级

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/rules.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] 先添加测试：超时、非法 JSON 和 Schema 失败在所有阶段都产生可结算的安全无动作，不增加 `action_rejected`。
- [x] 运行测试确认失败。
- [x] 规则层接受 `noop` 作为显式无动作，并确保查验、发言和投票结算不会凭空产生事实。
- [x] 运行测试确认通过。

### Task 3: 运行模式、Token 费用和输出上限

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/evaluation.py`
- Modify: `hello-agents/projects/16-graduation-project/main.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] 先添加测试：输入/输出价格能计算费用，`evaluate_game(..., offline=False)` 反映真实模式，HTTP payload 在配置时包含输出上限。
- [x] 运行测试确认失败。
- [x] 增加每百万 Token 价格配置、输出 Token 上限配置和费用计算。
- [x] 从 CLI 的 policy 选择传递 offline 标记到评测报告。
- [x] 运行测试确认通过。

### Task 4: Prompt 和文档中的运行参数

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/lessons/16-graduation-project.md`

- [x] 在 Prompt 中明确阶段、允许行动、字段类型和 `noop` 语义。
- [x] 文档记录输出上限、价格配置、别名兼容、Schema 校验和安全降级。
- [x] 删除已经完成事项的过时未完成标记，保留真实 LLM 端到端延迟风险说明。

### Task 5: 验证和问题记录

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/ISSUES.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/FIXES.md`

- [x] 运行第 16 课专属测试。
- [x] 运行 `.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v`，最新结果为 245 passed、4 skipped。
- [x] 将每项已验证修复追加到 `FIXES.md`，同步更新 `ISSUES.md` 状态。
- [x] 检查 `git diff`，确认没有真实 API Key、完整 Prompt 或完整模型响应进入仓库。
