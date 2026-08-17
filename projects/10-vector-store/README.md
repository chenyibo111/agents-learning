# 10 - 向量数据库与持久化索引

第九课每次启动都会重新编码所有文档。本课使用 Chroma 将向量、文本和来源元数据保存到本地，后续启动时直接加载索引。

## 安装本课依赖

在学习工程根目录执行：

```powershell
pip install -r .\projects\10-vector-store\requirements.txt
```

## 第一次运行

```powershell
python .\projects\10-vector-store\main.py
```

第一次运行会加载 Embedding 模型、编码文档并建立本地索引。索引保存在：

```text
projects/10-vector-store/vector_store/
```

## 后续运行

再次启动时，如果索引已经存在，程序会直接读取 Chroma 中的向量，不重复编码文档。

如果修改了知识库或更换了 Embedding 模型，重建索引：

```powershell
python .\projects\10-vector-store\main.py --rebuild
```

## 本课目标

- 理解向量数据库保存的是什么；
- 理解 collection、id、embedding、document、metadata；
- 学习 `PersistentClient` 的本地持久化；
- 学习 `upsert` 建立索引和 `query` 查询近邻；
- 理解为什么更换 Embedding 模型后必须重建索引。

