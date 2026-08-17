# 13 - RAG 检索评测

本课使用一组带有“期望来源”的问题测试 RAG 检索质量，并计算：

- Hit@K：Top-K 中是否命中至少一个正确来源；
- Precision@K：Top-K 中有多少结果是相关来源；
- Recall@K：期望来源有多少被找出来；
- MRR：第一个正确结果的排名倒数。

本项目只测试检索，不调用 DeepSeek。

## 安装依赖

```powershell
pip install -r .\projects\13-rag-evaluation\requirements.txt
```

## 构建索引并评测

```powershell
python .\projects\13-rag-evaluation\main.py --rebuild
```

之后再次评测可以直接运行：

```powershell
python .\projects\13-rag-evaluation\main.py
```

## 比较只用向量检索

```powershell
python .\projects\13-rag-evaluation\main.py --vector-only
```

