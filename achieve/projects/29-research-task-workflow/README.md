# 29 - 研究任务工作流

本课把第 28 课的“检索资料”放入一个完整研究流程：规划研究问题、召回资料、提取证据、核验证据。

## 运行环境

```bash
source .venv311/bin/activate
python -m pip install -r projects/29-research-task-workflow/requirements.txt
```

关键词模式会复用第 28 课的本地 Markdown 知识库，不需要 API Key 或向量模型：

```bash
python projects/29-research-task-workflow/main.py \
  --demo \
  --retriever keyword \
  --query "Agent 如何保存状态并恢复工作流？"
```

向量模式和 `both` 模式还需要安装第 28 课的 `chromadb`、`sentence-transformers` 依赖。

真实 LLM 模式使用仓库根目录 `.env` 中的 OpenAI-compatible 配置：

```bash
python projects/29-research-task-workflow/main.py \
  --llm \
  --retriever keyword \
  --query "关键词检索和向量检索有什么区别"
```

检索仍然由本地检索器完成，LLM 只负责规划、提取和核验，不负责自行访问网页。

## 工作流

```text
topic
  → plan
  → retrieve
  → extract
  → verify
  → verified_evidence
```

每个节点返回局部状态更新，LangGraph 将其合并进 `ResearchState`。本课不生成最终 Markdown 报告，第 30 课会使用 `verified_evidence` 生成带引用报告。

## 文件结构

```text
state.py              # ResearchState、SearchResult、EvidenceRecord
runtime.py            # DemoRuntime、LLMRuntime、配置校验
workflow.py           # 四个节点和 LangGraph 图
retrieval_source.py   # 复用第28课检索器的适配层
main.py               # CLI
```

## 测试

```bash
.venv311/bin/python -m unittest tests/test_research_task_workflow.py -v
```

测试使用 FakeRetriever 和 FakeClient，不会调用真实模型，也不会下载向量模型。
