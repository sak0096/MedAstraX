from __future__ import annotations

from hc_analytics.ingestion.pipeline import run_ingestion


def main() -> None:
    provenance = run_ingestion()
    print("Ingestion complete.")
    print(f"Source: {provenance.source_name}")
    print(f"Schema version: {provenance.schema_version}")
    print(f"Transformation version: {provenance.transformation_version}")


if __name__ == "__main__":
    main()
