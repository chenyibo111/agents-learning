# 13 - 智能旅行助手

对应课程：[13-travel-assistant](../../lessons/13-travel-assistant.md)。本项目将最小预算过滤 Demo 扩展为规划与执行分离的旅行 Agent 工程骨架。

运行：

```powershell
python projects/13-travel-assistant/main.py --demo
python projects/13-travel-assistant/main.py --demo --json
python projects/13-travel-assistant/main.py --demo --json --approve --output-dir .tmp\travel-assistant
python projects/13-travel-assistant/main.py --demo --weather-failure
python projects/13-travel-assistant/main.py --demo --inventory-expired
```

实验：加入日期和天气约束；模拟库存过期和天气工具失败；把预订动作设计成幂等且必须人工确认的工具。

## 工程分层

- `schemas.py`：旅行需求、航班、酒店、天气、行程和预订状态。
- `normalization.py`：日期、时区、币种校验和隐私字段处理。
- `providers.py`：可替换的航班、酒店、天气 Provider，默认使用离线 Fixture。
- `planner.py`：预算、日期、库存和天气约束过滤，只生成行程草案。
- `booking.py`：`PENDING_APPROVAL` → `CONFIRMED` 状态机和幂等键。
- `storage.py`：预订账本和 JSON 报告的原子持久化。
- `experiment.py`：离线 Demo 编排。

规划阶段不会确认预订；只有显式传入 `--approve` 才会进入确认状态。默认不会调用真实支付、航班或酒店 API。

## 三层实现状态

- 概念层：已覆盖需求结构化、约束、预算和预订审批。
- 最小实践层：当前 Demo 已用固定候选行程做预算过滤。
- 工程实现层：已接入可替换离线 Provider，处理时区、币种、库存、天气降级、隐私、幂等预订和审批恢复。

测试：

```powershell
python -m unittest hello-agents/tests/test_travel_assistant.py -v
```
