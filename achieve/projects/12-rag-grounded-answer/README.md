# 12 - RAG 可信回答与引用校验

本课在 RAG 检索结果中加入稳定的证据编号，例如 `[R1-1]`，并在模型回答后检查：

- 是否包含引用；
- 引用是否来自本轮检索结果；
- 检索结果是否足够相关。

## 安装依赖

```powershell
pip install -r .\projects\12-rag-grounded-answer\requirements.txt
```

## 第一次运行或知识库变化后

```powershell
python .\projects\12-rag-grounded-answer\main.py --rebuild
```

## 运行检索与引用评测

```powershell
python .\projects\12-rag-grounded-answer\main.py --eval
```

评测模式不会调用 DeepSeek，只测试检索结果和证据编号。

## 启动 Agent

```powershell
python .\projects\12-rag-grounded-answer\main.py
```

回答时要求模型使用类似下面的引用：

```text
记忆可以保存到本地 JSON 文件。[R1-1]
```

