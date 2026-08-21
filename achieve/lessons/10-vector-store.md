# 第十课：向量数据库与持久化索引

## 1. 为什么需要向量数据库

第九课每次启动都会：

```text
加载文档
→ 加载 Embedding 模型
→ 重新编码所有片段
→ 在内存中搜索
```

本课把向量、文档和元数据写入 Chroma 的本地持久化目录：

```text
projects/10-vector-store/vector_store/
```

后续启动可以直接加载已有索引。

## 2. 一条向量记录包含什么

```text
id：片段唯一 ID
embedding：向量
document：原始片段文本
metadata：来源文件、chunk_id 等信息
```

## 3. Chroma 的基本对象

```text
PersistentClient：连接本地数据库
Collection：一组向量记录
upsert：新增或更新记录
query：查询最近邻向量
```

## 4. 为什么更换模型要重建

不同 Embedding 模型可能产生不同维度、不同语义空间的向量。查询向量和数据库中的文档向量必须由兼容的模型生成，否则无法正确比较。

## 5. 思考题

1. 为什么 id 必须稳定？
2. 为什么不能只保存 embedding，不保存原文和 metadata？
3. 如果增加一篇文档，索引应该如何更新？
4. 如果更换 Embedding 模型，为什么要使用 `--rebuild`？

