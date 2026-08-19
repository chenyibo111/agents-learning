# 28 - 资料采集与双检索器知识库

本课把第 27 课的候选资料替换为本地 Markdown 知识库，并一次实现两种检索器：

- `KeywordRetriever`：关键词检索，零模型、可解释、启动快；
- `VectorRetriever`：Embedding + Chroma 向量检索，适合语义相似问题。

两者返回相同的结果结构，因此可以替换而不修改回答层。

## 安装依赖

关键词模式不需要额外依赖。向量模式需要：

`bash
source .venv311/bin/activate
python -m pip install -r projects/28-document-retrieval/requirements.txt
`

首次使用向量检索时，SentenceTransformers 可能需要下载并缓存 Embedding 模型。

## 关键词 Demo

`bash
python projects/28-document-retrieval/main.py \
  --demo \
  --retriever keyword \
  --query "状态 如何恢复"
`

这个模式不访问模型或网络。

## 向量 Demo

`bash
python projects/28-document-retrieval/main.py \
  --demo \
  --retriever vector \
  --query "怎样找回之前的任务状态"
`

如果知识库内容或 Embedding 模型发生变化，可以重建索引：

`bash
python projects/28-document-retrieval/main.py \
  --demo \
  --retriever vector \
  --rebuild
`

索引默认保存在项目目录的 `vector_store/`，该目录不应提交到 Git。

## 同时比较两种检索器

`bash
python projects/28-document-retrieval/main.py \
  --demo \
  --retriever both \
  --query "Agent 如何恢复工作流"
`

`both` 会分别查询关键词和向量检索，再按结果分数合并相同 chunk。

## 真实 LLM 回答

配置仓库根目录的 `.env`：

`text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://你的兼容网关
OPENAI_MODEL=你的模型名称
`

运行：

`bash
python projects/28-document-retrieval/main.py \
  --llm \
  --retriever both \
  --query "关键词检索和向量检索有什么区别"
`

检索先在本地完成，LLM 只负责根据检索片段生成回答。模型不会自动访问任意网页。

## 文件结构

`text
knowledge/
  ├── agent-state.md
  ├── retrieval.md
  └── workflow.md
ingest.py       # Markdown → source-traceable chunks
retrievers.py   # keyword/vector retrievers
answer.py       # Demo/LLM answerer
main.py         # CLI
`

## 测试

`bash
python -m unittest tests.test_document_retrieval -v
`

向量检索测试使用 fake embedding 和 fake collection，不需要下载模型或启动 Chroma。
