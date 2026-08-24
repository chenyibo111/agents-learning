# 05 - 低代码平台：节点、状态与审批工作流

对应课程：[05-low-code-platforms](../../lessons/05-low-code-platforms.md)，状态：🔁；回顾 Dify 节点与状态的讨论。

本课把低代码平台拆成可以阅读和测试的 Python 组件：节点负责局部业务，State 在节点间流转，Runner 负责调度、暂停、恢复和终止，Store 负责持久化。

## 三层实现

### 第一层：概念

理解 Coze、Dify、n8n 的定位，以及输入节点、LLM 节点、知识库节点、工具节点、条件节点、审批节点和输出节点如何组成有向图。

### 第二层：最小 Demo

`main.py` 的 `run_workflow()` 保留了最小字典状态流程：

```text
normalize → route → answer
```

运行：

```bash
cd /Users/yibo.chen/project/agents-learning
.venv311/bin/python hello-agents/projects/05-low-code-platforms/main.py --demo
```

### 第三层：工程实现

工程代码位于 `workflow.py`，包含：

- `WorkflowState`：结构化状态、事件、审批 ID 和已完成动作；
- `NodeSpec`：节点输入字段、输出字段和执行函数；
- `WorkflowRunner`：节点调度、最大步数、路由和终止；
- `SQLiteStateStore`：把暂停状态、审批信息和 outbox 保存到 SQLite；
- `tools.py`：注册带 `send_email` 权限的本地 outbox 工具节点；
- `resume()`：批准或拒绝人工审批；
- `completed_actions`：避免审批重复提交导致 answer 动作重复执行。

低风险问题走知识库回答，高风险词（发送、付款、删除、发布、下单）会暂停：

```bash
# 运行并保存待审批状态
.venv311/bin/python hello-agents/projects/05-low-code-platforms/main.py \
  --demo \
  --question "请发送邮件给客户" \
  --state-file /tmp/hello-agents-workflow.sqlite3

# 通过审批并恢复
.venv311/bin/python hello-agents/projects/05-low-code-platforms/main.py \
  --demo \
  --question "请发送邮件给客户" \
  --resume --approve \
  --state-file /tmp/hello-agents-workflow.sqlite3
```

当前高风险动作只写入本地 SQLite outbox，不会真的发送邮件或调用外部系统；真实副作用必须再接入带权限、幂等和审计的工具适配器。

## 实验

- 增加一个新的低风险路由，并为它写状态测试；
- 模拟节点内部异常，区分 `failed`、`rejected` 和 `waiting_approval`；
- 用 SQLite 查询某个 workflow 的事件和 outbox 记录；
- 把审批超时从固定秒数改成配置，并用 fake clock 测试边界；
- 为工具增加第二个权限，验证未经授权的状态永远不能执行。

## 测试

```bash
.venv311/bin/python -m unittest hello-agents/tests/test_low_code_workflow.py -v
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v
```

完成标准：能解释平台节点和代码 NodeSpec 的对应关系，能让低风险流程完成、高风险流程暂停并恢复，能证明状态被持久化且重复审批不会重复执行动作。
