# 第十五课：查询改写与多路召回

## 1. 为什么要改写查询

用户问题通常是面向人的自然语言，不一定适合直接搜索知识库：

```text
程序重启后怎么找回以前的东西？
```

模型可以把它改写成多个搜索表达：

```text
程序重新启动后如何恢复历史消息？
Agent 如何实现持久化记忆？
应用重启后如何读取持久化对话？
```

不同表达可能召回不同片段，再把多路结果融合起来，可以减少单一查询表达造成的漏召回。

## 2. 运行

```powershell
cd D:\AI\hello-agents-learning
.\.venv\Scripts\Activate.ps1
pip install -r .\projects\15-query-rewriting\requirements.txt
python .\projects\15-query-rewriting\main.py --rebuild
```

离线评测：

```powershell
python .\projects\15-query-rewriting\main.py --eval
```

对比不使用多查询：

```powershell
python .\projects\15-query-rewriting\main.py --eval --no-rewrite
```

交互式运行需要 DeepSeek 配置：

```powershell
python .\projects\15-query-rewriting\main.py
```

## 3. 查询改写流程

```text
原始问题
  ↓
DeepSeek 生成最多 3 个搜索表达
  ↓
原始问题和改写问题分别进行混合检索
  ↓
使用 RRF 融合多路结果
  ↓
把证据交给 DeepSeek 回答
```

本课保留原始问题，是为了避免模型改写错误导致原始意图丢失。

## 4. 解析模型输出

模型被要求返回 JSON 数组：

```json
["查询表达一", "查询表达二"]
```

`parse_query_variants()` 会处理：

- 正常 JSON 数组；
- Markdown 代码块包裹的 JSON；
- 模型没有遵守 JSON 格式时的逐行回退解析。

如果解析失败，程序继续使用原始问题，不让一次改写失败导致整个检索失败。

## 5. 多路融合

每个查询表达都会经过：

```text
向量检索 + BM25 → 一路混合结果
```

多个混合结果再经过一次 RRF：

```text
查询 1 的结果
查询 2 的结果
查询 3 的结果
        ↓
      RRF 融合
```

如果一个片段被多个查询表达同时召回，它会获得更多排名贡献。

## 6. 成本和风险

查询改写不是免费功能：

- 多一次或多次 LLM 调用；
- 需要执行更多检索；
- 延迟和成本增加；
- 错误改写可能改变用户原意；
- 改写结果可能引入知识库中不存在的术语。

因此需要保留原始查询，并用评测集确认改写是否真正提升了 Recall 或 MRR。

## 7. 思考题

1. 为什么多查询检索要保留原始问题？
2. 如果改写结果之间互相矛盾，应该怎么处理？
3. 查询改写让 Recall 提高，但延迟增加，是否值得使用？
4. 如何限制模型不要改变用户问题的时间、数字和专有名词？

