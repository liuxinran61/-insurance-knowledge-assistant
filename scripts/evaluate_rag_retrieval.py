"""保险售后 RAG 评测脚本。

默认执行不调用聊天模型的离线评测：检索召回、引用准确性代理指标、
以及风险规则拦截效果。添加 --with-agent 后，会额外调用真实的
KnowledgeAgent，验证最终答案引用与关键事实覆盖情况。
"""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Optional

from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.knowledge_tools import assess_service_risk
from app.db.session import SessionLocal
from app.services.rag_service import RAGService


DEFAULT_DATASET = Path("docs/rag-evals/insurance-after-sales-v1.jsonl")
DEFAULT_RISK_DATASET = Path("docs/rag-evals/risk-interception-v1.jsonl")
SAFETY_MARKERS = ("不能确认", "不能承诺", "人工", "专员", "无法", "核实")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """读取每行一题的金标准数据集，并尽早报出格式错误。"""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} 不是合法 JSON：{error}") from error
    return cases


def percentage(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def unique_names(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def summarize_distances(values: list[float]) -> dict[str, Any]:
    """汇总最佳余弦距离；数值越小，问题与知识片段越相关。"""
    if not values:
        return {"count": 0}

    return {
        "count": len(values),
        "min": round(min(values), 4),
        "median": round(median(values), 4),
        "max": round(max(values), 4),
    }


async def evaluate_retrieval(
    service: RAGService,
    cases: list[dict[str, Any]],
    *,
    owner_id: int,
    top_k: int,
) -> dict[str, Any]:
    """评估向量检索及其返回引用的准确性，不调用聊天模型。"""
    expected_source_count = 0
    expected_source_hit_count = 0
    cited_source_count = 0
    correct_citation_count = 0
    strict_case_total = 0
    strict_case_hit_count = 0
    unsupported_case_total = 0
    unsupported_case_blocked_count = 0
    supported_best_distances: list[float] = []
    unsupported_best_distances: list[float] = []
    case_results: list[dict[str, Any]] = []

    for case in cases:
        scored_chunks = await service.retrieve_relevant_chunks(
            query=case["query"],
            owner_id=owner_id,
            top_k=top_k,
            include_distances=True,
        )
        chunks = [chunk for chunk, _ in scored_chunks]
        distances = [distance for _, distance in scored_chunks]
        best_distance = min(distances, default=None)
        retrieved_sources = unique_names(chunk.document.filename for chunk in chunks)
        expected_sources = set(case.get("expected_sources", []))
        retrieved_set = set(retrieved_sources)
        hit_sources = sorted(expected_sources & retrieved_set)

        if expected_sources:
            if best_distance is not None:
                supported_best_distances.append(best_distance)
            expected_source_count += len(expected_sources)
            expected_source_hit_count += len(hit_sources)
            cited_source_count += len(retrieved_sources)
            correct_citation_count += len(hit_sources)
            strict_case_total += 1
            strict_case_hit_count += int(expected_sources.issubset(retrieved_set))
            strict_hit: Optional[bool] = expected_sources.issubset(retrieved_set)
        else:
            if best_distance is not None:
                unsupported_best_distances.append(best_distance)
            unsupported_case_total += 1
            unsupported_case_blocked_count += int(not retrieved_sources)
            strict_hit = None

        case_results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_sources": sorted(expected_sources),
                "retrieved_sources": retrieved_sources,
                "hit_sources": hit_sources,
                "strict_hit": strict_hit,
                "best_cosine_distance": (
                    round(best_distance, 4)
                    if best_distance is not None
                    else None
                ),
            }
        )

    return {
        "metrics": {
            "source_recall_at_k": percentage(
                expected_source_hit_count, expected_source_count
            ),
            "strict_query_recall_at_k": percentage(
                strict_case_hit_count, strict_case_total
            ),
            "citation_precision_at_k": percentage(
                correct_citation_count, cited_source_count
            ),
            "unsupported_query_abstention_rate": percentage(
                unsupported_case_blocked_count, unsupported_case_total
            ),
            "evaluated_cases": len(cases),
            "top_k": top_k,
        },
        "distance_diagnostics": {
            "supported_queries": summarize_distances(
                supported_best_distances
            ),
            "unsupported_queries": summarize_distances(
                unsupported_best_distances
            ),
        },
        "cases": case_results,
    }


def evaluate_risk_interception(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """评估确定性风险工具的风险等级与人工升级判断。"""
    level_hit_count = 0
    handoff_expected_count = 0
    handoff_hit_count = 0
    handoff_actual_count = 0
    case_results: list[dict[str, Any]] = []

    for case in cases:
        result = assess_service_risk(case["query"])
        expected_level = case["expected_risk_level"]
        expected_handoff = case["requires_human_handoff"]
        actual_handoff = result["requires_human_handoff"]

        level_hit_count += int(result["risk_level"] == expected_level)
        handoff_expected_count += int(expected_handoff)
        handoff_hit_count += int(expected_handoff and actual_handoff)
        handoff_actual_count += int(actual_handoff)
        case_results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_risk_level": expected_level,
                "actual_risk_level": result["risk_level"],
                "expected_handoff": expected_handoff,
                "actual_handoff": actual_handoff,
                "matched_signals": result["matched_signals"],
                "passed": (
                    result["risk_level"] == expected_level
                    and actual_handoff == expected_handoff
                ),
            }
        )

    return {
        "metrics": {
            "risk_level_accuracy": percentage(level_hit_count, len(cases)),
            "human_handoff_recall": percentage(
                handoff_hit_count, handoff_expected_count
            ),
            "human_handoff_precision": percentage(
                handoff_hit_count, handoff_actual_count
            ),
            "evaluated_cases": len(cases),
        },
        "cases": case_results,
    }


async def evaluate_agent(
    service: RAGService,
    cases: list[dict[str, Any]],
    *,
    owner_id: int,
) -> dict[str, Any]:
    """调用真实 Agent，评估最终答案的来源引用与关键事实覆盖。

    这一步会使用配置中的 LLM Key，适合发布前或调优后执行，
    不建议在每次本地保存代码时都运行。
    """
    agent = KnowledgeAgent(service)
    citation_total = 0
    citation_hit_count = 0
    expected_total = 0
    expected_hit_count = 0
    fact_total = 0
    fact_hit_count = 0
    refusal_total = 0
    refusal_hit_count = 0
    failed_case_count = 0
    case_results: list[dict[str, Any]] = []

    for case in cases:
        try:
            result = await agent.run(query=case["query"], owner_id=owner_id)
        except Exception as error:
            # 单题的网络/限流失败不应让整轮评测没有任何产出。
            failed_case_count += 1
            case_results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "error": str(error),
                }
            )
            print(f"[Agent 评测失败] {case['id']}: {error}")
            continue

        cited_sources = unique_names(source["filename"] for source in result.sources)
        expected_sources = set(case.get("expected_sources", []))
        cited_set = set(cited_sources)
        source_hits = expected_sources & cited_set
        must_include = case.get("must_include", [])
        answer = result.answer or ""
        fact_hits = [term for term in must_include if term in answer]
        needs_refusal = bool(case.get("should_refuse"))
        has_safe_response = any(marker in answer for marker in SAFETY_MARKERS)

        if expected_sources:
            citation_total += len(cited_sources)
            citation_hit_count += len(source_hits)
            expected_total += len(expected_sources)
            expected_hit_count += len(source_hits)
        fact_total += len(must_include)
        fact_hit_count += len(fact_hits)
        refusal_total += int(needs_refusal)
        refusal_hit_count += int(needs_refusal and has_safe_response)

        case_results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "cited_sources": cited_sources,
                "expected_sources": sorted(expected_sources),
                "fact_hits": fact_hits,
                "must_include": must_include,
                "requires_refusal": needs_refusal,
                "safe_response": has_safe_response,
                "tool_calls": result.tool_calls,
            }
        )

    return {
        "metrics": {
            "answer_citation_precision": percentage(citation_hit_count, citation_total),
            "answer_citation_recall": percentage(expected_hit_count, expected_total),
            "key_fact_keyword_coverage": percentage(fact_hit_count, fact_total),
            "safe_answer_rate_for_refusal_cases": percentage(
                refusal_hit_count, refusal_total
            ),
            "successful_cases": len(cases) - failed_case_count,
            "failed_cases": failed_case_count,
        },
        "cases": case_results,
    }


def print_metrics(title: str, metrics: dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    for name, value in metrics.items():
        formatted = f"{value:.1%}" if isinstance(value, float) else value
        print(f"{name}: {formatted}")


async def run(args: argparse.Namespace) -> dict[str, Any]:
    retrieval_cases = load_jsonl(args.dataset)[: args.limit]
    risk_cases = load_jsonl(args.risk_dataset)
    db = SessionLocal()
    service = RAGService(db)

    try:
        report: dict[str, Any] = {
            "dataset": str(args.dataset),
            "owner_id": args.owner_id,
            "retrieval": await evaluate_retrieval(
                service, retrieval_cases, owner_id=args.owner_id, top_k=args.top_k
            ),
            "risk_interception": evaluate_risk_interception(risk_cases),
        }
        if args.with_agent:
            report["agent"] = await evaluate_agent(
                service, retrieval_cases, owner_id=args.owner_id
            )
        return report
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="评测保知通的 RAG 与风险拦截效果")
    parser.add_argument("--owner-id", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--limit", type=int, default=None, help="仅跑前 N 道知识题")
    parser.add_argument("--with-agent", action="store_true", help="调用真实 LLM 评估答案")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--risk-dataset", type=Path, default=DEFAULT_RISK_DATASET)
    parser.add_argument("--report", type=Path, help="可选：将完整结果保存为 JSON")
    args = parser.parse_args()

    report = asyncio.run(run(args))
    print_metrics("检索与引用", report["retrieval"]["metrics"])
    print("\n=== 向量距离诊断（越小越相关） ===")
    for group, summary in report["retrieval"]["distance_diagnostics"].items():
        print(f"{group}: {summary}")
    print_metrics("风险拦截", report["risk_interception"]["metrics"])
    if "agent" in report:
        print_metrics("Agent 最终回答", report["agent"]["metrics"])

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n完整结果已保存到：{args.report}")


if __name__ == "__main__":
    main()
