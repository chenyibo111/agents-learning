# 16 - RAG 上下文压缩与去重

多路检索可能返回重复片段，知识库片段过长时还可能超出模型上下文预算。本课实现：

- 按 chunk_id 去重；
- 根据相关性排序；
- 使用字符预算压缩证据；
- 保留稳定的引用编号；
- 检查压缩结果没有超过预算。

## 安装依赖

```powershell
pip install -r .\projects\16-context-compression\requirements.txt
```

## 构建索引

```powershell
python .\projects\16-context-compression\main.py --rebuild
```

## 离线运行压缩演示

```powershell
python .\projects\16-context-compression\main.py --demo
```

调整上下文预算：

```powershell
python .\projects\16-context-compression\main.py --demo --max-chars 800
```

## 启动带压缩上下文的 Agent

需要在 `.env` 中配置 DeepSeek：

```powershell
python .\projects\16-context-compression\main.py
```

