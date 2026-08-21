# 14 - 混合检索：向量 + BM25

本课同时使用两种检索方式：

- 向量检索：理解语义相似和改写表达；
- BM25 关键词检索：匹配专业词、函数名、错误码和精确术语。

默认模式使用 Reciprocal Rank Fusion（RRF）融合两路排名。

## 安装依赖

```powershell
pip install -r .\projects\14-hybrid-retrieval\requirements.txt
```

## 构建索引并运行混合检索评测

```powershell
python .\projects\14-hybrid-retrieval\main.py --rebuild
```

之后直接运行：

```powershell
python .\projects\14-hybrid-retrieval\main.py
```

## 比较不同检索方式

```powershell
python .\projects\14-hybrid-retrieval\main.py --vector-only
python .\projects\14-hybrid-retrieval\main.py --bm25-only
```

三种模式都会输出 Hit@3、Precision@3、Recall@3 和 MRR。

