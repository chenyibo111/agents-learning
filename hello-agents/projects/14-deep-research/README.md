# 14 - DeepResearch Agent

对应课程：[14-deep-research](../../lessons/14-deep-research.md)，回顾 `achieve` 第 27～32 课。本项目把归档研究助手能力整理为可恢复、可审计的离线研究引擎。

运行：

```powershell
python projects/14-deep-research/main.py --demo
python projects/14-deep-research/main.py --demo --json
python projects/14-deep-research/main.py --demo --conflict
python projects/14-deep-research/main.py --demo --retrieval-failure
python projects/14-deep-research/main.py --demo --interrupt-after-round 1 --output-dir .tmp\research
python projects/14-deep-research/main.py --resume .tmp\research\checkpoint.json --json
```

实验：加入来源去重；制造冲突证据并标记不确定性；模拟检索失败降级；保存中断状态后继续第二轮检索。

## 工程分层

- `schemas.py`：Query、Source、Evidence、Claim、Citation 和 ResearchState。
- `corpus.py`、`retriever.py`：本地资料库、可替换 Retriever 和来源去重。
- `planner.py`、`engine.py`：问题拆解、多轮预算、研究状态机和检查点恢复。
- `evidence.py`：证据提取、结论生成和冲突识别。
- `audit.py`、`report.py`：引用支持关系审计和带引用 Markdown 报告。
- `storage.py`：检查点和研究报告的原子 JSON 持久化。
- `experiment.py`：离线研究实验编排。

系统明确区分来源、证据和结论；搜索结果摘要不能直接成为证据，引用也必须通过支持关系审计。本课默认不访问互联网或真实模型 API。

## 三层实现状态

- 概念层：已覆盖拆题、来源、证据、矛盾核对和引用。
- 最小实践层：当前 Demo 已用本地来源和 claims 演示引用链。
- 工程实现层：已加入 Retriever 适配、来源去重、证据 Schema、引用审计、多轮预算、抓取失败降级、检查点恢复和回归测试。

测试：

```powershell
python -m unittest hello-agents/tests/test_deep_research.py -v
```
