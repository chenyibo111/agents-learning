# 第十四课：混合检索与 RRF

## 1. 为什么需要混合检索

向量检索擅长理解语义，例如：

```text
程序重启后如何找回过去的信息？
```

和：

```text
应用再次启动时怎样恢复历史记忆？
```

两句话没有完全相同的关键词，但语义接近。

关键词检索擅长精确匹配，例如：

- `tool_call_id`；
- `ValueError`；
- 产品型号；
- API 参数名；
- 专业缩写。

本课同时使用向量检索和 BM25，然后通过 RRF 合并两个排序结果。

## 2. 安装和运行

```powershell
cd D:\AI\hello-agents-learning
.\.venv\Scripts\Activate.ps1
pip install -r .\projects\14-hybrid-retrieval\requirements.txt
python .\projects\14-hybrid-retrieval\main.py --rebuild
```

默认运行混合检索：

```powershell
python .\projects\14-hybrid-retrieval\main.py
```

只用向量检索：

```powershell
python .\projects\14-hybrid-retrieval\main.py --vector-only
```

只用 BM25：

```powershell
python .\projects\14-hybrid-retrieval\main.py --bm25-only
```

## 3. BM25 的作用

BM25 是一种经典的关键词检索算法，它会考虑：

- 查询词是否出现在文档中；
- 查询词在整个语料中是否稀有；
- 文档长度；
- 词频是否已经足够高。

它比简单的“关键词出现次数”更合理。

本课使用 `rank-bm25` 实现 BM25，并把中文文本按字符、英文文本按单词做了简单切分。

## 4. RRF 融合

两个检索器的分数通常不能直接相加：

```text
向量距离：0.42
BM25 分数：3.17
```

它们的数值范围和含义不同。

RRF 不直接比较原始分数，而是比较排名：

```text
RRF 分数 = 1 / (k + 向量排名)
          + 1 / (k + BM25 排名)
```

本课设置：

```python
RRF_K = 60
```

如果一个片段在两种检索中都排名靠前，它的融合分数就会较高。

## 5. 三种模式

```text
仅向量检索：适合语义改写
仅 BM25：适合精确术语
混合检索：综合两种信号
```

使用第 13 课的指标比较三种模式：

- Hit@3；
- Precision@3；
- Recall@3；
- MRR。

## 6. 局限

本课的中文分词只是教学实现：中文按单字切分，真实项目可以使用更合适的分词器或搜索引擎分析器。

RRF 也不是唯一融合方法。生产系统还可能使用加权 RRF、归一化分数融合或学习排序模型。

## 7. 思考题

1. 为什么代码不直接把向量分数和 BM25 分数相加？
2. 什么类型的问题更适合 BM25？
3. 如果一个结果在向量检索中排名第 1、BM25 中没有出现，它还可能排进最终 Top-K 吗？
4. 混合检索的 Recall 提高了，但延迟和成本可能发生什么变化？

