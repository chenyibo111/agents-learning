# 30 - 带引用的 Markdown 报告

本课把第 29 课的 `verified_evidence` 转换成带稳定引用编号的 Markdown 研究报告。

## 运行环境

```bash
source .venv311/bin/activate
python -m pip install -r projects/30-cited-markdown-report/requirements.txt
```

离线 Demo：

```bash
python projects/30-cited-markdown-report/main.py \
  --demo \
  --retriever keyword \
  --query "状态如何在节点之间流转"
```

真实 LLM：

```bash
python projects/30-cited-markdown-report/main.py \
  --llm \
  --retriever keyword \
  --query "关键词检索和向量检索有什么区别"
```

报告只输出到终端，不会自动创建或覆盖文件。向量模式和 `both` 模式继续使用第 28 课的向量依赖。

## 报告结构

```markdown
# 研究报告

## 结论

状态可以通过检查点保存。[1]

## 来源

[1] agent-state.md#agent-state-2
> 状态可以通过检查点保存。
```

引用编号由程序根据 `source + chunk_id` 生成。同一个片段重复出现时只分配一个编号。

## 文件结构

```text
report.py          # 引用映射、报告渲染、LLM 引用校验
research_source.py # 复用第29课工作流
main.py            # CLI
```

## 测试

```bash
.venv311/bin/python -m unittest tests/test_cited_markdown_report.py -v
```

测试不会访问真实模型，也不会产生 API 费用。
