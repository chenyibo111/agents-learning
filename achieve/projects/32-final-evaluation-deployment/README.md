# 32 - 最终评测与部署

本课把第 27～31 课的研究助手做最终验收，增加：

- 固定评测集和回归通过率；
- 运行耗时、Token、成本和失败监控；
- Demo/LLM 部署配置检查；
- 脱敏健康检查。

## 离线评测

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --demo \
  --evaluate \
  --retriever keyword
```

评测不调用真实 LLM，默认检查状态恢复、工作流安全、关键词/向量检索差异三个问题。

## 健康检查

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --demo \
  --health
```

健康检查只输出模式、模型名、Base URL、配置是否存在和问题列表，不输出 API Key。

## LLM 评测

确认 `.env` 已配置后运行：

```bash
.venv311/bin/python \
  projects/32-final-evaluation-deployment/main.py \
  --llm \
  --evaluate \
  --retriever keyword \
  --budget-usd 0.05
```

这会真实调用模型并产生费用，测试代码不会调用真实网络。

## 文件结构

```text
evaluation.py   # 固定评测集、来源/引用/状态检查
monitoring.py   # span、耗时、Token、成本、预算
deployment.py   # 配置校验和健康检查
app_adapter.py  # 复用第30课研究助手
main.py         # 最终 CLI
```

本项目不会自动创建 `.env`，不会自动安装依赖，也不会把 SQLite、向量索引或模型缓存提交到 Git。

## 测试

```bash
.venv311/bin/python -m unittest tests/test_final_evaluation_deployment.py -v
.venv311/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```
