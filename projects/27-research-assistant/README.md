# 27 - 研究助手需求与双运行时架构

本课开始把前面学到的 Agent、RAG、LangGraph 和多 Agent 能力组合成一个完整的个人研究助手架构。

同一套工作流支持两种运行模式：

- `--demo`：固定数据、离线、可重复，不访问模型；
- `--llm`：使用 OpenAI-compatible Chat Completions 运行真实模型。

## 安装依赖

在 macOS/zsh 中执行：

`bash
source .venv311/bin/activate
python -m pip install -r projects/27-research-assistant/requirements.txt
`

## 离线 Demo

`bash
python projects/27-research-assistant/main.py --demo
python projects/27-research-assistant/main.py --demo --topic "评估多 Agent 是否适合生产环境"
`

Demo 使用 `DemoRuntime`，不会读取 API Key，也不会调用网络。

## 真实 LLM

在仓库根目录 `.env` 中配置：

`text
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://你的兼容网关
OPENAI_MODEL=你的模型名称
`

运行：

`bash
python projects/27-research-assistant/main.py --llm --topic "评估多 Agent 是否适合生产环境"
`

真实模式会调用模型完成规划、候选资料生成、证据提取、证据核验和报告生成。当前课程中的“资料收集”仍是模型生成候选资料；第 28 课再接入真实文件、网页或搜索工具。

## 共享工作流

`text
plan
  → collect_sources
  → extract_evidence
  → verify_evidence
  → write_report
`

节点只依赖 `ResearchRuntime` 接口，因此工作流不需要知道当前使用的是 Demo 还是 LLM。

## 测试

`bash
python -m unittest tests.test_research_assistant -v
`

真实模型测试使用 fake client，不访问真实网关。不要把 `.env` 或 API Key 提交到 Git。
