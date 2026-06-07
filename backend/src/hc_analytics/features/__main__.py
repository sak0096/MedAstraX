from __future__ import annotations

from hc_analytics.features.pipeline import run_feature_engineering


def main() -> None:
    result = run_feature_engineering()
    print("Feature engineering complete.")
    print(f"Rows: {result['feature_rows']}")
    print(f"Feature store: {result['feature_store']}")
    print(f"Cohort summary: {result['cohort_summary']}")


if __name__ == "__main__":
    main()
