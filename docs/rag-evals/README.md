# 保险售后 RAG 评测集

`insurance-after-sales-v1.jsonl` 是一组人工维护的金标准问题。每行是一道题，字段含义如下：

- `query`：模拟新人客服的真实提问；
- `expected_sources`：正确答案应命中的资料文件；
- `must_include`：回答中必须覆盖的关键事实；
- `should_refuse`：为 `true` 时，系统应明确说明无法确认或需要转人工，而不能编造结论。

先用该集合记录当前检索效果，再调整切块、检索和 Prompt。这样才能说明优化带来了什么变化。
