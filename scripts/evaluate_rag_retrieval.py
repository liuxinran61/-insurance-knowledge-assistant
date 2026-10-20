import argparse
import asyncio
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.rag_service import RAGService


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


async def evaluate(
    cases: list[dict],
    owner_id: int,
    top_k: int,
) -> None:
    db = SessionLocal()
    service = RAGService(db)

    try:
        evaluable_count = 0
        hit_count = 0

        for case in cases:
            chunks = await service.retrieve_relevant_chunks(
                query=case["query"],
                owner_id=owner_id,
                top_k=top_k,
            )

            retrieved_sources = [
                chunk.document.filename
                for chunk in chunks
            ]
            expected_sources = set(case["expected_sources"])

            if expected_sources:
                evaluable_count += 1
                is_hit = expected_sources.issubset(
                    set(retrieved_sources),
                )
                hit_count += int(is_hit)
            else:
                is_hit = None

            print(f"\n[{case['id']}] {case['query']}")
            print(f"  召回文件: {retrieved_sources}")
            print(f"  命中结果: {is_hit}")

        if evaluable_count:
            hit_rate = hit_count / evaluable_count
            print(
                f"\nRecall@{top_k}: "
                f"{hit_count}/{evaluable_count} "
                f"= {hit_rate:.1%}",
            )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-id", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(
            "docs/rag-evals/insurance-after-sales-v1.jsonl",
        ),
    )
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    asyncio.run(evaluate(cases, args.owner_id, args.top_k))


if __name__ == "__main__":
    main()