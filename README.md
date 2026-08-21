# Hello Agents 学习工程

这是我的 AI Agent 实践学习目录，参考 Datawhale 的 [Hello-Agents](https://github.com/datawhalechina/hello-agents) 教程，并通过独立小项目边学边做。

完整课程表请查看：[CURRICULUM.md](CURRICULUM.md)。

## 学习目标

- 理解 Agent 的核心循环：观察、思考、调用工具、读取结果、继续行动。
- 不依赖框架，先手写一个最小 Agent。
- 再学习工具、记忆、RAG、上下文工程、工作流和多 Agent 协作。
- 最终完成一个可以展示的研究助手项目。

当前进度：第 00～32 课全部完成，后续课程见课程表。

## 目录说明

```text
hello-agents-learning/
├─ lessons/                         # 每课学习笔记
├─ projects/                        # 每课可运行的小项目
│  ├─ 01-minimal-agent/
│  ├─ 02-interactive-agent/
│  └─ ...
├─ CURRICULUM.md                    # 完整课程表
├─ ROADMAP.md                       # 阶段目标与当前进度
├─ requirements.txt                 # Python 依赖
├─ .env.example                     # API 配置模板
└─ README.md                        # 本文件
```

## 第一次运行

在 PowerShell 中执行：

```powershell
cd D:\AI\hello-agents-learning
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

然后编辑 `.env`，填入你使用的模型服务商配置。DeepSeek 示例：

```env
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_MODEL=deepseek-v4-flash
```

再运行第一课：

```powershell
python .\projects\01-minimal-agent\main.py
```

不要把 `.env` 提交到 Git，也不要把 API Key 写进代码。

每个项目可能有自己的依赖，请先阅读对应项目的 `README.md`，必要时执行该项目的 `requirements.txt`。

## 学习路线

详细课程、状态和后续计划见 [CURRICULUM.md](CURRICULUM.md)，阶段路线见 [ROADMAP.md](ROADMAP.md)。
