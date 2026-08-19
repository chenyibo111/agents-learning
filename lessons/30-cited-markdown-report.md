# 第 30 课：带引用的 Markdown 报告

第 29 课已经完成了计划、检索、证据提取和核验。本课把 `verified_evidence` 转换成用户可以阅读、检查和分享的 Markdown 报告。

## 一、本课目标

```text
已核验证据
  → 引用编号映射
  → 报告模板或 LLM 写作
  → 引用校验
  → Markdown 报告
```

完成本课后，你应该能解释：

1. 为什么引用编号应该由程序生成，而不是完全交给模型；
2. `source`、`chunk_id`、`quote` 如何组成证据链；
3. DemoReportWriter 和 LLMReportWriter 的职责差异；
4. 如何拒绝模型返回的非法引用编号；
5. 为什么报告层应该和检索层、工作流层分离。

## 二、报告不是证据

第 29 课的结果是结构化证据：

```python
{
    "claim": "状态可以通过检查点保存",
    "source": "agent-state.md",
    "chunk_id": "agent-state-2",
    "quote": "状态可以通过检查点保存",
    "verified": True,
}
```

报告只是这些证据的表达形式：

```text
证据 → 结论句子 → [1] → 来源目录 → 原文片段
```

因此，报告不能成为新的事实来源。它应该能够回溯到之前已经核验过的证据。

## 三、`Citation`：引用目录

文件：`projects/30-cited-markdown-report/report.py`。

引用结构是：

```python
{
    "number": 1,
    "source": "agent-state.md",
    "chunk_id": "agent-state-2",
    "quote": "状态可以通过检查点保存",
}
```

`build_citations` 按证据第一次出现的顺序编号：

```text
第一个 source + chunk_id → [1]
第二个 source + chunk_id → [2]
重复的 source + chunk_id → 复用原编号
```

去重键是：

```python
(source, chunk_id)
```

不能只用 `source` 去重，因为同一个文件可能包含多个不同 Chunk。

## 四、Demo 报告生成

`DemoReportWriter` 不调用模型，直接使用模板：

```python
report = DemoReportWriter().write_report(
    "Agent 状态管理",
    verified_evidence,
)
```

它生成四类内容：

1. 报告标题；
2. 基于证据的结论；
3. `[1]`、`[2]` 引用标记；
4. 来源和原文引用目录。

它适合：

- 离线 Demo；
- 单元测试；
- 没有 API Key 的环境；
- 检查引用链路是否正确。

## 五、LLM 报告生成

`LLMReportWriter` 会把两部分内容发送给模型：

```text
已核验证据
  ├── claim
  ├── source
  └── chunk_id

程序生成的引用目录
  ├── [1] agent-state.md#agent-state-2
  └── [2] workflow.md#workflow-1
```

模型只负责：

- 组织语言；
- 安排报告结构；
- 把事实写成自然语言段落。

模型不能负责：

- 自己创建来源；
- 自己决定不存在的引用编号；
- 访问知识库之外的资料。

## 六、为什么要校验引用

模型可能返回：

```markdown
# 研究报告

结论。[9]
```

但程序只生成了 `[1]` 和 `[2]`。这时 `[9]` 是无效引用，必须拒绝。

`validate_report_citations` 会：

1. 检查报告不能为空；
2. 提取 Markdown 中的 `[数字]`；
3. 检查每个数字是否存在于引用目录；
4. 有证据时，要求报告至少出现一个引用。

核心原则是：

> 模型可以写文字，但引用目录由程序掌握。

## 七、从第 29 课连接到第 30 课

文件：`research_source.py`。

第 30 课不重新实现研究工作流，而是复用第 29 课：

```text
第29课 run_workflow()
  ↓
verified_evidence
  ↓
第30课 ReportWriter
  ↓
Markdown
```

入口函数 `run_report` 的流程是：

```python
result = run_workflow(...)
report = writer.write_report(
    query,
    result.get("verified_evidence", []),
)
```

这样报告层不需要知道检索器和 LangGraph 的内部实现。

## 八、运行示例

```bash
.venv311/bin/python projects/30-cited-markdown-report/main.py \
  --demo \
  --retriever keyword \
  --query "状态如何在节点之间流转"
```

输出分成两部分：

第一行是工作流元信息：

```json
{
  "status": "completed",
  "retrieved_count": 2,
  "evidence_count": 2
}
```

后面是 Markdown 报告：

```markdown
## 结论

状态可以在节点之间传递。[1]

## 来源

[1] agent-state.md#agent-state-2
```

## 九、测试设计

测试文件：`tests/test_cited_markdown_report.py`。

测试覆盖：

- 引用编号稳定；
- 相同 Chunk 去重；
- Demo 报告包含结论、引用和来源；
- 缺少引用时报告被拒绝；
- 不存在的引用编号被拒绝；
- LLM 能收到引用目录；
- 第 29 课工作流能连接到第 30 课报告层。

使用 `FakeClient` 的好处是：

```text
测试模型交互格式
而不是测试真实网络
```

## 十、当前边界

本课暂不负责：

- 把报告写入文件；
- 保存历史任务；
- 版本化报告；
- 人工确认后再发布；
- 跨任务恢复。

这些内容属于第 31 课“历史任务与人工确认”。

本课核心结论：

> 高质量报告不仅要写得通顺，还必须让每个重要结论都能沿着引用编号回到具体证据。
