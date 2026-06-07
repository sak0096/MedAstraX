from __future__ import annotations

import argparse

from hc_analytics.explainability.pipeline import run_explainability


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SHAP explanations (Phase 4).")
    parser.add_argument("--top-k", type=int, default=5, help="Top contributors per beneficiary.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap for faster local prototyping.",
    )
    args = parser.parse_args()

    result = run_explainability(top_k=args.top_k, max_rows=args.max_rows)
    print("Explainability pipeline complete.")
    print(f"Model family: {result['model_family']}")
    print(f"Rows explained: {result['row_count']}")
    print(f"Bundles written: {result['bundle_count']}")
    print(f"Manifest: {result['manifest']}")


if __name__ == "__main__":
    main()
