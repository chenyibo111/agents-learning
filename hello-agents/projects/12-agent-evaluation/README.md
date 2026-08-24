# 12 - Agent 性能评估

对应课程：[12-agent-evaluation](../../lessons/12-agent-evaluation.md)。本项目实现一个确定性、离线、可回放的 Agent 评测引擎，重点是让失败样本可以定位、复现并阻止回归。

## 运行

```powershell
python projects/12-agent-evaluation/main.py --demo
python projects/12-agent-evaluation/main.py --demo --json
python projects/12-agent-evaluation/main.py --demo --json --output-dir .tmp\agent-evaluation
python projects/12-agent-evaluation/main.py --replay-case injection-01 --strategy guarded
```

`--output-dir` 会保存：

- `manifest.json`：评测集版本、策略、case 清单和随机种子；
- `trajectories.jsonl`：完整 Agent 轨迹、工具调用、延迟、token、成本和安全事件；
- `report.json`：硬指标、Judge 结果、策略比较、Pareto 前沿和发布门禁。

## 工程分层

- `schemas.py`：评测 case、轨迹、指标、Judge 和门禁的数据契约；
- `dataset.py`：版本化评测集，覆盖正常、边界、工具失败、提示注入和证据不足；
- `runner.py`：确定性 `guarded`、`fast`、`unsafe` 策略，支持轨迹回放；
- `metrics.py`：只根据轨迹计算硬指标；
- `judges.py`：独立记录 rubric、Judge 分数和人工校准；
- `comparison.py`：策略指标比较和 Pareto 前沿；
- `gate.py`：成功率、安全违规率、证据完整率和成本回归门禁；
- `storage.py`：原子 JSON/JSONL 实验产物存储；
- `experiment.py`：完整实验编排。

默认发布门禁要求成功率至少 75%、安全违规率为 0、证据完整率至少 75%。本课不调用真实模型 API，避免网络、模型版本和随机性影响评测教学结果。

## 测试

```powershell
python -m unittest hello-agents/tests/test_agent_evaluation.py -v
python -m unittest hello-agents/tests/test_projects.py -v
```
