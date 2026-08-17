# 11 - RAG 两阶段检索与评测

本课在向量数据库召回之后增加一个简单的重排序阶段：

```text
向量数据库召回候选片段
        ↓
关键词重排序
        ↓
返回最终 Top-K
```

## 安装依赖

```powershell
pip install -r .\projects\11-rag-rerank\requirements.txt
```

## 普通运行

```powershell
python .\projects\11-rag-rerank\main.py
```

## 第一次运行或知识库变化后

```powershell
python .\projects\11-rag-rerank\main.py --rebuild
```

## 运行检索评测

```powershell
python .\projects\11-rag-rerank\main.py --eval
```

评测模式不会调用 DeepSeek，只测试检索结果是否包含预期来源。

## 本课目标

- 理解召回（Recall）和重排序（Rerank）的区别；
- 理解为什么第一名不一定是最终最优结果；
- 学习用简单测试集评测检索器；
- 认识检索质量和答案质量是两个不同问题。

