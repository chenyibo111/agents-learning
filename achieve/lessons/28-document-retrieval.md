# 第 28 课：资料采集与双检索器知识库

第 27 课的研究助手已经有了工作流，但资料仍然是 Demo 固定值或模型生成的候选值。本课接入本地 Markdown 知识库，并一次实现关键词检索和向量检索。

## 一、本课目标

`text
Markdown 文件
  → 文档切分
  → 带来源的 Chunk
  → 建立检索器
  → Top-K 检索
  → 上下文拼接
  → Demo 或 LLM 回答
`

本课重点是让检索层先找到证据，再交给回答层，而不是让模型自己猜测资料。

## 二、为什么需要两种检索器

关键词检索和向量检索擅长的内容不同：

| 检索器 | 擅长内容 | 局限 |
|---|---|---|
| KeywordRetriever | 函数名、错误码、专业术语、精确表达 | 不理解同义改写 |
| VectorRetriever | 语义相近、不同表达方式的问题 | 依赖 Embedding，可能忽略精确术语 |

关键词适合 `tool_call_id`、错误码和函数名；向量检索适合“怎样找回任务状态”与“从检查点恢复工作流”这类不同措辞但语义相近的问题。

## 三、文档切分

文件：`projects/28-document-retrieval/ingest.py`。

`load_chunks` 读取目录下的 Markdown 文件，按空行切分段落，并为每个 Chunk 保存：

`python
{
    "source": "agent-state.md",
    "chunk_id": "agent-state-1",
    "text": "Agent 的状态保存任务主题...",
    "content_hash": "..."
}
`

来源信息决定了最终能否生成可追踪引用。如果只保存纯文本，回答层无法知道证据来自哪个文件。

## 四、关键词检索

`KeywordRetriever` 不依赖模型和数据库，流程是：

1. 对 Chunk 分词；
2. 对查询分词；
3. 计算词语重叠；
4. 按分数排序；
5. 返回 Top-K。

教学版的核心分数是：

`python
query_terms = set(tokenize(query))
document_terms = set(tokenize(document))
score = len(query_terms & document_terms) / len(query_terms)
`

它速度快、结果透明，对精确术语很有效。第 14 课已经学习过 BM25，之后可以只替换内部实现，不改变检索器接口。

## 五、向量检索

`VectorRetriever` 使用 SentenceTransformers 和 Chroma：

`text
文档 Chunk
  → SentenceTransformer 编码
  → 写入 Chroma
  → 查询编码成向量
  → Chroma 返回最近邻
`

向量索引保存：

`text
id          → chunk_id
embedding   → 文本向量
document    → 原始文本
metadata    → source、chunk_id、content_hash
`

更换 Embedding 模型后，旧向量和新向量不在同一个向量空间，必须重建索引：

`bash
python projects/28-document-retrieval/main.py --demo --retriever vector --rebuild
`

索引默认位于项目的 `vector_store/` 目录。

## 六、统一 Retriever 接口

两种检索器都实现：

`python
class Retriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        ...
`

返回结果统一包含：

`python
{
    "source": "retrieval.md",
    "chunk_id": "retrieval-1",
    "text": "检索增强生成...",
    "score": 0.8,
    "retriever": "keyword",
}
`

因此回答层不需要知道底层使用的是关键词还是向量。

## 七、同时使用两种检索器

`both` 模式会分别查询两种检索器，再按 `chunk_id` 去重，选择分数更高的结果：

`bash
python projects/28-document-retrieval/main.py --demo --retriever both
`

这还不是完整的 RRF。第 14 课已经实现过 RRF，本课先把两个检索器放进同一个完整项目，后续可以把简单合并替换为：

`text
关键词排名 + 向量排名
  → RRF
  → 最终 Top-K
`

## 八、回答层和检索层分离

文件：`answer.py`。

`DemoAnswerer` 直接展示检索结果；`LLMAnswerer` 把检索片段放入上下文后调用模型。

真实 LLM 看到的是：

`text
问题：用户问题

资料：
[1] retrieval.md#retrieval-1
检索到的文本

请只能依据资料回答，并保留引用。
`

检索器负责找证据，LLM 负责组织语言，回答必须保留来源。

## 九、向量检索如何测试

真实向量检索依赖 Chroma、SentenceTransformers、Embedding 模型和缓存。测试直接启动真实模型会很慢，也会受到网络影响。

本课测试使用 `FakeEmbeddingModel` 和 `FakeCollection`，重点验证：

- 正确调用 Embedding；
- 正确调用 Chroma；
- 正确读取 documents、metadatas、distances；
- 返回统一 SearchResult；
- 保留 source 和 chunk_id。

## 十、两种运行模式

完全不需要向量依赖的关键词 Demo：

`bash
python projects/28-document-retrieval/main.py --demo --retriever keyword --query "状态 如何恢复"
`

向量 Demo：

`bash
python projects/28-document-retrieval/main.py --demo --retriever vector
`

真实 LLM：

`bash
python projects/28-document-retrieval/main.py --llm --retriever both --query "关键词检索和向量检索有什么区别"
`

向量模式虽然不调用 LLM，但第一次运行可能需要下载 Embedding 模型；关键词模式才是完全不需要额外模型的离线基线。

## 十一、安全边界

当前项目只读取配置的知识库目录。未来接入用户指定文件或网页时，必须考虑任意路径读取、符号链接逃逸、URL 白名单、SSRF、下载大小限制、超时重试和文档中的 Prompt Injection。

检索到的文本是不可信资料，不是系统指令。

## 十二、实验

1. 增加包含专业错误码的 Markdown 文件，比较两种检索器；
2. 分别运行 `keyword`、`vector` 和 `both`；
3. 修改文档但不重建索引，观察向量结果；
4. 加入 RRF，比较简单合并和 RRF；
5. 让 LLM 在没有检索结果时明确拒答。

本课核心结论是：

> 检索器应该是可替换的基础设施。关键词检索提供透明基线，向量检索提供语义能力，回答层只消费统一的检索结果。
