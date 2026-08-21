# 21 - Agent 安全与权限控制

这一课实现一个与模型服务无关的安全工具执行器，演示：

```text
不可信文本检测
  ↓
工具白名单
  ↓
角色权限
  ↓
风险等级和人工审批
  ↓
允许或拒绝执行
```

## 运行

本课只使用 Python 标准库：

```bash
source .venv/bin/activate
python3 projects/21-agent-security/main.py --demo
```

Demo 会演示：

1. 低风险读取工具正常执行；
2. Prompt Injection 文本被阻断；
3. 高风险发送消息需要审批；
4. shell 工具即使审批也被硬阻断。

## 安全规则

- 工具必须先注册；
- 当前角色必须拥有工具权限；
- 当前上下文必须把工具放进 allowlist；
- 高风险工具需要显式 `approval_granted=True`；
- `run_shell` 等硬阻断工具永远不能执行；
- 不可信文本中的可疑指令会触发阻断。

## 测试

```bash
python3 -m unittest tests/test_agent_security.py -v
```

Prompt Injection 检测是启发式示例，不是完整的安全防护。生产系统还需要权限服务、审计日志、沙箱和人工审批身份验证。
