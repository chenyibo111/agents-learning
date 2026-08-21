# 第十三课：RAG 检索评测与指标

## 1. 为什么需要评测

只运行几个问题并凭感觉判断“结果不错”，不能说明检索器真的可靠。

本课为每个测试问题标注期望来源，然后计算多个指标：

- Hit@K：前 K 个结果中是否至少命中一个正确来源；
- Precision@K：前 K 个结果中有多少是相关来源；
- Recall@K：期望来源有多少被召回；
- MRR：第一个正确结果排名越靠前，分数越高。

## 2. 运行

```powershell
cd D:\AI\hello-agents-learning
.\.venv\Scripts\Activate.ps1
pip install -r .\projects\13-rag-evaluation\requirements.txt
python .\projects\13-rag-evaluation\main.py --rebuild
```

之后直接运行：

```powershell
python .\projects\13-rag-evaluation\main.py
```

只使用向量检索，不进行 Rerank：

```powershell
python .\projects\13-rag-evaluation\main.py --vector-only
```

## 3. Hit@K

假设问题的正确来源是 `memory.md`，Top-3 结果为：

```text
tool-calling.md
memory.md
grounding.md
```

因为 Top-3 中出现了 `memory.md`，所以：

```text
Hit@3 = 1
```

如果完全没有正确来源：

```text
Hit@3 = 0
```

## 4. Precision@K

Precision 关注“找出来的结果有多准”：

```text
Precision@K = Top-K 中相关结果数 / K
```

如果 Top-3 中有 1 个相关结果：

```text
Precision@3 = 1 / 3 = 0.333
```

## 5. Recall@K

Recall 关注“应该找到的内容找到了多少”。

本课每个问题暂时只设置一个期望来源，因此命中时 Recall@3 通常是 1，未命中时是 0。

如果一个问题有两个正确来源，但 Top-3 只找到其中一个：

```text
Recall@3 = 1 / 2 = 0.5
```

## 6. MRR

MRR 关注第一个正确结果排在第几位：

```text
第 1 位命中：MRR = 1
第 2 位命中：MRR = 1/2 = 0.5
第 3 位命中：MRR = 1/3 ≈ 0.333
没有命中：MRR = 0
```

MRR 很适合衡量“正确答案是否排在前面”。

## 7. 向量检索和 Rerank 的比较

默认运行：

```text
向量检索 → 召回候选 → Rerank → 返回 Top-K
```

使用 `--vector-only` 时：

```text
向量检索 → 直接返回 Top-K
```

比较两次输出，观察 Rerank 是否改善了 Hit@K、Precision@K 或 MRR。

## 8. 评测的局限

本课只评测检索结果，没有评测 DeepSeek 最终回答是否正确。

真实项目还需要增加：

- 答案正确性评测；
- 引用有效性评测；
- 资料不足时的拒答评测；
- 延迟、成本和上下文长度评测；
- 更大的测试集和人工标注。

## 9. 思考题

1. 为什么 Hit@3 很高，但 Precision@3 仍然可能很低？
2. 为什么 MRR 比单纯的 Hit@3 更能反映排序质量？
3. 如果一个问题有多个正确来源，如何修改评测数据？
4. Rerank 后 MRR 提高但 Recall 不变，说明了什么？

