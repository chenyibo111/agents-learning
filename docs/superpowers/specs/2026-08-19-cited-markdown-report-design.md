# 第 30 课：带引用的 Markdown 报告设计

## 目标

把第 29 课输出的 `verified_evidence` 转换为带稳定引用编号的 Markdown 研究报告，同时保留离线 Demo 和真实 LLM 两种模式。

## 范围

- 新增 `projects/30-cited-markdown-report/`。
- 复用第 29 课的研究工作流和第 28 课检索器，不修改前两课代码。
- 新增引用映射：按 `source + chunk_id` 去重并从 1 开始编号。
- 新增 `DemoReportWriter`：使用确定性模板生成报告。
- 新增 `LLMReportWriter`：把已核验证据和引用编号交给 OpenAI-compatible 模型组织语言。
- 对 LLM 返回的 Markdown 做引用编号校验，禁止引用不存在的编号。
- 本课只生成 Markdown 字符串，不做文件持久化；历史任务保存留到第 31 课。

## 数据流

```text
第29课 verified_evidence
  → build_citations
  → DemoReportWriter / LLMReportWriter
  → validate_report_citations
  → Markdown 报告
```

每条引用包含：

- `number`
- `source`
- `chunk_id`
- `quote`

引用编号按首次出现顺序稳定生成，同一个 `source + chunk_id` 只保留一个编号。

## LLM 安全边界

LLM 只能组织报告内容，不能自行决定引用编号或来源。程序生成引用目录，并在模型返回后检查：

- 报告非空；
- 所有 `[n]` 都是合法整数；
- `n` 必须存在于程序生成的引用目录；
- 有证据时报告至少包含一个引用。

## CLI

```bash
python projects/30-cited-markdown-report/main.py --demo --retriever keyword
python projects/30-cited-markdown-report/main.py --llm --retriever keyword
```

报告直接输出到标准输出，不创建报告文件，避免本课引入持久化和文件覆盖问题。

## 验收标准

- Demo 模式无需 API Key 即可输出带 `[1]` 引用的 Markdown。
- 引用编号与 `source#chunk_id` 映射稳定且去重。
- LLM 模式通过 FakeClient 测试，不进行真实网络请求。
- 非法引用编号会被拒绝。
- 第 29 课工作流和全量测试不回归。
