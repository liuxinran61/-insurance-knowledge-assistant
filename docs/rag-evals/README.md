# 保险售后 RAG 评测集

`insurance-after-sales-v1.jsonl` 是一组人工维护的知识问答金标准问题。每行是一道题，字段含义如下：

- `query`：模拟新人客服的真实提问；
- `expected_sources`：正确答案应命中的资料文件；
- `must_include`：回答中必须覆盖的关键事实；
- `should_refuse`：为 `true` 时，系统应明确说明无法确认或需要转人工，而不能编造结论。

数据集同时包含两类拒答题：有边界资料可引用的高风险保险问题，以及
`expected_sources` 为空的无依据问题。后者包含完全无关的问题和保险领域
但当前知识库未覆盖的问题，用于校准相关性阈值与测试“无依据不作答”。

先用该集合记录当前检索效果，再调整切块、检索和 Prompt。这样才能说明优化带来了什么变化。

`risk-interception-v1.jsonl` 专门评测风险工具，字段包括：

- `expected_risk_level`：预期为 `low` / `medium` / `high`；
- `requires_human_handoff`：是否必须提示人工升级。

## 指标定义

默认评测不调用聊天模型，只测可重复、低成本的底层能力：

- `source_recall_at_k`：金标准来源文件中，有多少被 Top-K 检索结果召回；
- `strict_query_recall_at_k`：一道多来源题中，所有预期文件都被召回的比例；
- `citation_precision_at_k`：检索结果中属于金标准来源的文件占比。它是“回答引用准确性”的离线代理指标；
- `unsupported_query_abstention_rate`：没有标准资料的问题，没有返回任意资料的比例；
- `risk_level_accuracy`：风险等级判断准确率；
- `human_handoff_recall`：应升级的问题中，实际触发人工升级的比例；
- `human_handoff_precision`：实际触发人工升级的问题中，确实应该升级的比例。

添加 `--with-agent` 后，脚本会实际调用配置好的 LLM，额外测最终回答的引用准确率、引用召回率、关键事实关键词覆盖率和拒答场景的安全答复率。该模式会消耗 API 用量，适合发布前或调优后运行。

## 运行方式

在 API 容器中运行，保证可以访问同一份数据库和 Embedding 配置：

```bash
docker compose exec api python scripts/evaluate_rag_retrieval.py --owner-id 1 --top-k 3
```

保存完整结果（用于前后版本对比）：

```bash
docker compose exec api python scripts/evaluate_rag_retrieval.py \
  --owner-id 1 \
  --top-k 3 \
  --report docs/rag-evals/reports/baseline.json
```

端到端 Agent 验收（会调用真实模型）：

```bash
docker compose exec api python scripts/evaluate_rag_retrieval.py \
  --owner-id 1 \
  --top-k 3 \
  --with-agent \
  --report docs/rag-evals/reports/agent-baseline.json
```
