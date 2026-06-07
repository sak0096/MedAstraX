from __future__ import annotations

from hc_analytics.modeling.pipeline import run_training


def main() -> None:
    result = run_training()
    print("Model training complete.")
    print(f"Targets: {', '.join(result['targets'])}")
    print(f"Models dir: {result['models_dir']}")
    print(f"Predictions: {result['predictions']}")
    print(f"Rows scored: {result['prediction_rows']}")
    print(f"Manifest: {result['manifest']}")


if __name__ == "__main__":
    main()
