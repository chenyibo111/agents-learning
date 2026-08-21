# 第二十课：工作流编排

## 1. 为什么需要工作流编排

前面的 Agent 通常把流程写成一个循环：

```text
调用模型 → 执行工具 → 再调用模型
```

当任务变复杂后，程序需要明确表达：

- 哪些步骤必须按顺序执行；
- 哪些步骤可以并行执行；
- 哪些结果会决定下一条路径；
- 哪些操作必须等待人工确认。

这就是工作流编排。

本课的流程是：

```text
prepare
  ↓
collect_local ─┐
               ├─ 并行收集
collect_catalog┘
  ↓
merge
  ↓
风险判断
  ├─ low  → publish → completed
  └─ high → waiting_approval
                    ↓
             approve → publish
             reject  → rejected
```

## 2. 运行项目

```bash
source .venv/bin/activate
python3 projects/20-workflow-orchestration/main.py --demo
```

运行高风险分支：

```bash
python3 projects/20-workflow-orchestration/main.py --demo --high-risk
```

此时程序会保存状态并停在：

```text
状态：waiting_approval
当前节点：approval
```

批准：

```bash
python3 projects/20-workflow-orchestration/main.py --approve
```

拒绝：

```bash
python3 projects/20-workflow-orchestration/main.py --reject
```

## 3. WorkflowState

源码中的 `WorkflowState` 保存：

```text
task
status
current_node
data
history
approval_reason
updated_at
```

其中：

- `status` 表示工作流处于运行、等待审批还是完成状态；
- `current_node` 表示下一步从哪个节点继续；
- `data` 保存节点之间传递的业务数据；
- `history` 保存已经执行过的节点；
- `approval_reason` 解释为什么需要人工确认。

这和第 17 课的状态思想一致，但第 20 课增加了节点编排和分支。

## 4. 顺序节点

`WorkflowRunner.run()` 使用 `current_node` 决定下一步。

每个节点执行后都会：

1. 更新 `data`；
2. 向 `history` 追加记录；
3. 设置下一个 `current_node`；
4. 保存状态。

因此程序中断后，不需要从头执行，只要读取当前节点即可继续。

## 5. 并行节点

两个资料收集分支使用线程池：

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    futures = {
        name: executor.submit(handler, dict(state.data))
        for name, handler in branches.items()
    }
```

两个分支分别是：

```text
collect_local
collect_catalog
```

它们互相独立，因此可以同时执行。等两个 Future 都完成后，工作流才进入 `merge`。

适合并行的任务通常满足：

- 分支之间没有数据依赖；
- 分支不会同时修改同一个共享资源；
- 最终可以合并各自结果。

如果第二个节点必须使用第一个节点的结果，就不能简单地并行。

## 6. 条件分支

`merge` 节点会读取：

```python
risk_level = state.data.get("risk_level", "low")
```

然后决定下一步：

```text
risk_level == low
  → publish

risk_level == high
  → approval
```

条件应该由程序明确判断，而不是只存在于模型的自然语言中。

## 7. 人工审批节点

高风险任务会进入：

```python
state.status = "waiting_approval"
state.current_node = "approval"
```

并保存状态后退出。此时程序不会继续发布。

之后使用：

```bash
python3 projects/20-workflow-orchestration/main.py --approve
```

程序读取状态后，把当前节点切换到 `publish`。

如果使用：

```bash
python3 projects/20-workflow-orchestration/main.py --reject
```

工作流进入 `rejected` 状态。

人工审批的关键点是：

```text
等待审批不是异常，而是工作流的一种正常状态。
```

它应该被持久化，而不是通过 `input()` 阻塞线程等待用户。

## 8. 工作流状态和节点状态

两种状态解决不同问题。

工作流状态：

```text
pending
running
waiting_approval
completed
rejected
failed
```

回答“整个任务现在处于什么阶段”。

当前节点：

```text
prepare
parallel_collect
merge
approval
publish
done
```

回答“恢复时从哪个节点继续”。

不能只保存一个 `status`，否则程序知道任务在运行，却不知道具体从哪个步骤继续。

## 9. 和前面课程的关系

第 17 课保存任务状态和检查点；第 18 课校验模型返回的结构化结果；第 19 课可靠执行工具；第 20 课编排多个节点、分支和人工确认。

组合起来就是：

```text
工作流节点
  ↓
可靠工具执行
  ↓
结构化结果校验
  ↓
状态持久化和恢复
```

## 10. 可靠性边界

当前项目是教学版：

- 状态使用本地 JSON 文件；
- 没有原子写入；
- 没有多进程锁；
- 并行分支异常时会让整个工作流失败；
- 没有动态注册节点；
- 审批身份和权限尚未验证；
- 没有把超时和 retry 策略接入每个节点。

真实系统还需要考虑审批人身份、权限、审计日志、并发修改和状态版本升级。

## 11. 思考题

1. 为什么人工审批应该是状态，而不是 `input()` 阻塞？
2. 两个并行节点同时写同一个文件会有什么问题？
3. 如果并行分支 A 成功、分支 B 失败，应该全部重跑还是只重跑 B？
4. 如何给每个节点增加超时和 retry？
5. 如何把第 20 课改成通用的 DAG，而不是写死节点名称？
