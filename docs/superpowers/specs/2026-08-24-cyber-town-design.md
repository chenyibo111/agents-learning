# 第 15 课赛博小镇 Agent：工程设计规范

## 目标

把课程中的三个角色、共享环境、私有记忆和事件循环实现成一个可离线运行的社会模拟内核。实现必须满足：状态转移可重复、规则可审计、Agent 只能看到授权信息、模拟可以检查点恢复，并且规则 Policy 与未来的 LLM Policy 使用同一接口。

## 范围

- 三个固定角色：商人、研究员、信使。
- 共享世界：公开事实、市场状态、角色的公开经济状态。
- Agent 私有状态：自己的目标、私有记忆和关系，不进入其他 Agent 的观察。
- 行动：报价、接受交易、公开消息和空行动。
- 环境规则：库存、余额、交易对象、数量和价格由环境校验。
- 事件日志：每次行动和环境副作用都记录为带规则来源的事件。
- 固定 seed：用于记录模拟配置和支持同配置重放。
- 检查点：JSON 原子写入，支持中断后继续，不重复已经完成的 tick。
- 评测：统计事件、交易、拒绝、消息、资源守恒和隐私泄露。

不在本课范围内：真实联网、真实 LLM 调用、复杂自然语言解析、分布式并行和生产数据库。

## 核心不变量

1. `Observation` 只能含公共事实、公共事件和当前 Agent 自己的私有状态。
2. 余额和库存不能由 Agent 直接修改，必须经过环境规则。
3. 合法交易保持总余额和总库存不变。
4. 公共事件不得携带 `private_memory` 或其他 Agent 的私有字段。
5. 相同初始状态、Policy、seed 和 tick 数量产生相同状态与事件日志。
6. 恢复执行从 checkpoint 的下一个 tick 开始，不重复已完成事件。

## 模块设计

```text
schemas.py     不可变领域对象与 JSON 序列化
world.py       初始世界、行动规则、资源校验
visibility.py  世界到 Agent Observation 的授权投影
policies.py    Policy 协议与离线规则 NPC
engine.py      tick 循环、行动编排、seed、恢复
storage.py     checkpoint、事件日志和报告文件
evaluation.py  守恒、隐私、事件和回放评测
main.py        CLI、demo、JSON 输出和可选 LLM 说明模式
```

## 验收场景

### 正常一 tick

商人公开报价一张地图，研究员接受，信使发送公开问候。输出中可以追踪 `offer -> trade_completed -> message` 的因果链。

### 非法行动

对不存在库存或余额不足的交易请求生成 `action_rejected`，状态不发生资源变化，并记录拒绝规则。

### 可见性

商人的 Observation 不能读取研究员的私有记忆；公共事件仍然可见。

### 重放与恢复

同一 seed 连续运行和 checkpoint 恢复运行的 `world`、`events`、`report` 应一致。

### 规则与模型策略插拔

引擎只依赖 `Policy.decide(observation)`。默认使用规则 Policy；未来的 LLM Policy 只负责从同一 Observation 生成 Action，不能绕过环境规则。
