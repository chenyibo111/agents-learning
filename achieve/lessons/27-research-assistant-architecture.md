# 第 27 课：研究助手需求与双运行时架构

从这一课开始，我们不再只做单个 Agent 实验，而是开始组装一个完整的个人研究助手。

## 一、最终要解决的问题

用户输入一个研究主题后，系统需要完成：

`text
研究主题
  → 制定研究计划
  → 收集候选资料
  → 提取事实
  → 核验事实
  → 生成带引用报告
  → 保存任务历史
`

后续课程会分别实现资料导入、知识库、研究工作流、报告、历史任务和评测。本课先确定边界和接口。

## 二、为什么必须同时支持 Demo 和真实 LLM

如果只有真实 LLM 模式，学习和测试会依赖 API Key、网络、网关可用性、模型随机输出和真实调用成本。

如果只有离线 Demo，又无法验证真实模型是否能理解任务和调用能力。

因此本课采用双运行时：

`text
                    ┌── DemoRuntime：固定、离线、可重复
ResearchRuntime ────┤
                    └── LLMRuntime：真实 OpenAI-compatible 模型
`

工作流只依赖 `ResearchRuntime`，不知道具体实现是哪一种。

## 三、共享状态 ResearchState

状态定义在 `state.py`：

`python
class ResearchState(TypedDict, total=False):
    topic: str
    plan: list[str]
    sources: list[SourceRecord]
    evidence: list[EvidenceRecord]
    verified_evidence: list[EvidenceRecord]
    report: str
    status: str
    events: list[str]
    error: str
`

状态保存任务数据，但不保存 API Key、OpenAI Client 或其他连接对象。

状态应该可以被检查点保存、被测试构造、被日志记录、被后续节点消费，并且可以在不改变运行时的情况下恢复。

## 四、运行时接口

`runtime.py` 定义统一能力：

`python
class ResearchRuntime(Protocol):
    def plan(self, topic: str) -> list[str]: ...
    def collect_sources(self, topic, plan): ...
    def extract_evidence(self, topic, sources): ...
    def verify_evidence(self, topic, evidence): ...
    def write_report(self, topic, evidence): ...
`

`DemoRuntime` 和 `LLMRuntime` 都实现这组方法。

工作流可以统一调用：

`python
plan = runtime.plan(state["topic"])
`

不需要把 `if demo_mode` 和真实模型分支散落在每个节点中。把模式判断放在运行时边界，是本课最重要的架构决策。

## 五、共享 LangGraph 工作流

项目位于 `projects/27-research-assistant/`，工作流节点是：

`text
plan
  ↓
collect_sources
  ↓
extract_evidence
  ↓
verify_evidence
  ↓
write_report
`

每个节点只负责一件事，并返回增量状态：

`python
def plan_node(state, runtime):
    return {
        "plan": runtime.plan(state["topic"]),
        "status": "planned",
        "events": ["plan 完成"],
    }
`

节点不负责解析命令行参数、读取 API Key、判断运行模式或打印最终结果。这些职责分别属于 CLI、运行时和展示层。

## 六、离线 Demo 做了什么

运行：

`bash
python projects/27-research-assistant/main.py --demo
`

离线模式使用确定性资料：

`text
DemoRuntime
  → 固定研究计划
  → 固定候选资料
  → 固定证据
  → 固定核验结果
  → Markdown 报告
`

它仍然经过完整 LangGraph 工作流，所以可以验证状态流转、节点顺序、字段更新和报告中的 `[1]`、`[2]` 引用编号。

“离线”只表示不调用真实模型和网络，不表示完全不需要项目依赖。运行前仍需安装本课的 LangGraph 依赖。

## 七、真实 LLM 做了什么

配置 `.env`：

`text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://你的兼容网关
OPENAI_MODEL=你的模型名称
`

运行：

`bash
python projects/27-research-assistant/main.py --llm --topic "评估多 Agent 是否适合生产环境"
`

真实模式会进行多次模型调用：

`text
1. 生成研究计划 JSON
2. 生成候选资料 JSON
3. 提取证据 JSON
4. 核验证据 JSON
5. 生成 Markdown 报告
`

前四步要求模型返回 JSON，`LLMRuntime` 会做类型和字段校验。模型返回非法 JSON 或缺少字段时，工作流会失败，而不是静默使用错误数据。

当前的候选资料仍然由模型生成，并不等于真实搜索结果。第 28 课会把 `collect_sources` 替换为本地文件、网页或搜索工具。

## 八、为什么真实模型测试使用 fake client

测试文件是 `tests/test_research_assistant.py`。fake client 模拟：

`python
client.chat.completions.create(...)
`

这样可以验证请求次数、JSON 解析、字段校验、状态流转和报告生成，而不需要真实 API Key、真实网关或网络连接。

## 九、本课的架构分层

`text
main.py
  ├── --demo → DemoRuntime
  └── --llm  → LLMRuntime → OpenAI-compatible API
                    ↓
              ResearchRuntime
                    ↓
              LangGraph Workflow
                    ↓
              ResearchState
`

未来接入真实搜索时，只需要替换或扩展 `collect_sources` 能力，不应该把搜索逻辑塞进 CLI 或状态对象。

## 十、运行和实验

`bash
source .venv311/bin/activate
python -m pip install -r projects/27-research-assistant/requirements.txt
python projects/27-research-assistant/main.py --demo
python -m unittest tests.test_research_assistant -v
`

建议实验：

1. 修改 `DemoRuntime` 的资料，观察报告是否变化；
2. 在 `ResearchState` 中增加 `warnings` 字段；
3. 让 DemoRuntime 返回一个未核验事实，观察报告如何处理；
4. 修改 LLMRuntime 的 JSON 校验，比较“严格失败”和“自动修复”的差异；
5. 比较 Demo 和 LLM 模式的 `events` 是否保持相同顺序。

本课核心结论是：

> Demo 和真实 LLM 不应该是两套业务流程，而应该是同一个工作流背后的两种运行时实现。
