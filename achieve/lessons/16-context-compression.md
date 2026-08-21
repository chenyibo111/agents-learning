# 第十六课：RAG 上下文压缩、去重与预算

## 1. 为什么要压缩上下文

查询改写和多路召回会带来更多候选片段，但结果可能重复，全部交给模型也会造成：

- 上下文过长；
- 请求成本增加；
- 响应速度变慢；
- 模型注意力被无关内容分散；
- 多段重复证据占用窗口。

本课在交给模型前增加一层上下文处理：

```text
多路检索
  ↓
按 chunk_id 去重
  ↓
按相关性排序
  ↓
按字符预算截断
  ↓
保留引用编号
  ↓
交给模型
```

## 2. 运行

```powershell
cd D:\AI\hello-agents-learning
.\.venv\Scripts\Activate.ps1
pip install -r .\projects\16-context-compression\requirements.txt
python .\projects\16-context-compression\main.py --rebuild
```

运行离线演示：

```powershell
python .\projects\16-context-compression\main.py --demo
```

限制上下文预算：

```powershell
python .\projects\16-context-compression\main.py --demo --max-chars 800
```

启动 Agent：

```powershell
python .\projects\16-context-compression\main.py
```

## 3. 去重

多路查询可能多次召回同一个片段。程序使用 `chunk_id` 识别重复结果，并保留距离最小的那一份：

```python
if item is None or result["distance"] < item["distance"]:
    best_by_id[result["id"]] = result
```

## 4. 字符预算

本课用 `max_chars` 作为简单预算，例如：

```text
max_chars = 1600
```

压缩器不断计算剩余空间，只把能放入预算的证据加入上下文，必要时截断最后一个片段。

字符数不是精确 token 数。生产项目应该使用目标模型对应的 tokenizer 计算 token 数。

## 5. 引用保留

压缩不能只保留文本，还要保留来源：

```text
[C1] 来源：memory.md#memory-2
证据：持久化记忆可以写入 JSON、SQLite 或数据库。
```

否则模型虽然看到了内容，用户却无法验证答案来自哪里。

## 6. 思考题

1. 为什么去重应该使用 `chunk_id`，而不是直接比较文本？
2. 如果最相关的片段很长，应该截断它还是换成下一个片段？
3. 字符预算和 token 预算有什么区别？
4. 上下文压缩后 Precision 不变但答案变差，可能是什么原因？

