# 09 - 神经网络 Embedding 语义检索

第八课使用 TF-IDF 向量。本课使用 `sentence-transformers` 的多语言 Embedding 模型，把文本编码成包含语义信息的向量。

## 安装本课依赖

在学习工程根目录执行：

```powershell
pip install -r .\projects\09-embedding-retrieval\requirements.txt
```

## 运行

```powershell
python .\projects\09-embedding-retrieval\main.py
```

第一次运行时会下载 Embedding 模型，可能需要几分钟；模型会被缓存，后续运行不需要重复下载。

## 建议输入

```text
如何让模型使用外部能力？
```

```text
重新启动程序后，Agent 如何找回之前的信息？
```

```text
RAG 如何从资料中生成答案？
```

## 本课目标

- 理解神经网络 Embedding 和 TF-IDF 的区别；
- 观察语义相近但用词不同的问题能否检索到相关片段；
- 理解向量归一化和点积相似度；
- 了解 Embedding 模型缓存和本地部署成本。

