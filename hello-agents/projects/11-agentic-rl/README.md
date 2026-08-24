# 11 - Agentic-RL

对应课程：[11-agentic-rl](../../lessons/11-agentic-rl.md)。本项目是一个可复现的离线实验引擎，不执行真实的大模型参数更新；它把 Agentic-RL 的关键工程边界完整落在轨迹、奖励、评测和产物审计上。

运行：`python projects/11-agentic-rl/main.py --demo`；`--llm` 获取概念解释。

离线实验：

```powershell
python projects/11-agentic-rl/main.py --demo --reward-version v0
python projects/11-agentic-rl/main.py --demo --reward-version v1 --json
python projects/11-agentic-rl/main.py --demo --save-trajectories .tmp\eval-trajectories.jsonl
python projects/11-agentic-rl/main.py --demo --output-dir .tmp\runs --json
```

`--output-dir` 会生成一个 run 目录，包含：

- `manifest.json`：实验版本、随机种子、奖励版本、训练/评测任务清单。
- `trajectories.jsonl`：可回放的、带 schema 版本的轨迹。
- `report.json`：训练/评测指标、相对优势、奖励排序审计和安全门禁。

## 工程分层

- `agentic_rl/schemas.py`：版本化领域模型。
- `environment.py`、`policies.py`、`runner.py`：环境、策略和轨迹生成。
- `rewards.py`：版本化奖励、奖励分解和 reward-hacking 审计。
- `evaluation.py`：评测、相对优势和发布安全门禁。
- `storage.py`、`experiments.py`：原子产物存储、训练/评测切分和实验编排。

这仍然不是 GPU 训练框架，也没有伪装成 GRPO：真实项目还需要模型服务、数据集版本库、批处理队列、LoRA/训练后端、离线评测集和线上回滚系统；本课先把这些系统的可审计接口和安全约束固定下来。

## 三层实现状态

- 概念层：已覆盖 SFT、轨迹、奖励和 reward hacking。
- 最小实践层：已生成小型确定性轨迹，比较正确答案、步骤惩罚和工具约束。
- 工程实现层：已建立模块化实验引擎、版本化 schema、JSONL 轨迹存储、原子 manifest/report、奖励分解与双排序审计、训练/评测分离、相对优势比较和安全门禁。

测试：

```powershell
python -m unittest hello-agents/tests/test_agentic_rl.py hello-agents/tests/test_agentic_rl_engineering.py -v
```
