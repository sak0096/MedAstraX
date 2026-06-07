"""Ingestion pipeline entry point (Phase 1)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from hc_analytics.config import Settings, get_settings
from hc_analytics.ingestion.constants import (
    CHUNK_SIZE,
    CLAIM_SETTINGS,
    PRESCRIPTION_COLUMNS,
    SCHEMA_VERSION,
    SOURCE_NAME,
    SOURCE_URL,
)
from hc_analytics.ingestion.io import (
    checksums_for_files,
    git_commit_hash,
    read_pipe_csv,
    write_parquet_chunks,
)
from hc_analytics.ingestion.transforms import (
    claim_chunk_iterator,
    load_beneficiaries,
    normalize_prescription_frame,
)
from hc_analytics.schemas.common import ProvenanceRecord


def _collect_source_files(raw_dir: Path) -> Dict[str, Path]:
    sources: Dict[str, Path] = {}
    for path in sorted((raw_dir / "beneficiary").glob("beneficiary_*.csv")):
        sources[f"beneficiary/{path.name}"] = path
    for claim_setting, config in CLAIM_SETTINGS.items():
        sources[config["relative_path"]] = raw_dir / config["relative_path"]
    sources["prescription/pde.csv"] = raw_dir / "prescription" / "pde.csv"
    return sources


def _ingest_beneficiaries(raw_dir: Path, processed_dir: Path) -> int:
    beneficiaries = load_beneficiaries(raw_dir)
    output_path = processed_dir / "beneficiaries.parquet"
    beneficiaries.to_parquet(output_path, index=False)
    return len(beneficiaries)


def _ingest_claims(raw_dir: Path, processed_dir: Path) -> int:
    output_path = processed_dir / "claims.parquet"
    if output_path.exists():
        output_path.unlink()

    writer: Optional[pq.ParquetWriter] = None
    total_rows = 0
    try:
        for claim_setting, config in CLAIM_SETTINGS.items():
            source_path = raw_dir / config["relative_path"]
            if not source_path.exists():
                continue
            chunks = claim_chunk_iterator(
                source_path,
                claim_setting,
                config["columns"],
                chunksize=CHUNK_SIZE,
            )
            for chunk in chunks:
                if chunk.empty:
                    continue
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(output_path, table.schema)
                writer.write_table(table)
                total_rows += len(chunk)
    finally:
        if writer is not None:
            writer.close()
    return total_rows


def _ingest_prescriptions(raw_dir: Path, processed_dir: Path) -> int:
    source_path = raw_dir / "prescription" / "pde.csv"
    if not source_path.exists():
        return 0

    output_path = processed_dir / "prescription_events.parquet"
    if output_path.exists():
        output_path.unlink()

    chunks = (
        normalize_prescription_frame(chunk)
        for chunk in read_pipe_csv(
            source_path,
            usecols=PRESCRIPTION_COLUMNS.keys(),
            chunksize=CHUNK_SIZE,
        )
    )
    return write_parquet_chunks(chunks, output_path)


def _write_manifest(
    *,
    settings: Settings,
    provenance: ProvenanceRecord,
    row_counts: Dict[str, int],
    source_files: Dict[str, Path],
) -> Path:
    manifest_path = settings.artifacts_path / "ingestion_manifest.json"
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": provenance.model_dump(mode="json"),
        "row_counts": row_counts,
        "outputs": {
            "beneficiaries": str(settings.processed_data_path / "beneficiaries.parquet"),
            "claims": str(settings.processed_data_path / "claims.parquet"),
            "prescription_events": str(
                settings.processed_data_path / "prescription_events.parquet"
            ),
        },
        "source_files": checksums_for_files(source_files),
        "git_commit": git_commit_hash(settings.repo_root),
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def run_ingestion(settings: Optional[Settings] = None) -> ProvenanceRecord:
    """Parse, validate, and stage CMS synthetic data into analysis-ready parquet tables."""
    settings = settings or get_settings()
    raw_dir = settings.raw_data_path
    processed_dir = settings.processed_data_path
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    source_files = _collect_source_files(raw_dir)
    beneficiary_files = [
        path for name, path in source_files.items() if name.startswith("beneficiary/") and path.exists()
    ]
    prescription_file = source_files["prescription/pde.csv"]
    claim_files = [
        path
        for name, path in source_files.items()
        if name.endswith(".csv")
        and not name.startswith("beneficiary/")
        and name != "prescription/pde.csv"
        and path.exists()
    ]
    if not beneficiary_files:
        raise FileNotFoundError("Missing beneficiary files in data/raw/beneficiary/")
    if not prescription_file.exists():
        raise FileNotFoundError("Missing prescription/pde.csv in data/raw/prescription/")
    if not claim_files:
        raise FileNotFoundError("Missing FFS claim files in data/raw/")

    row_counts = {
        "beneficiaries": _ingest_beneficiaries(raw_dir, processed_dir),
        "claims": _ingest_claims(raw_dir, processed_dir),
        "prescription_events": _ingest_prescriptions(raw_dir, processed_dir),
    }

    provenance = ProvenanceRecord(
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        extracted_at=datetime.now(timezone.utc),
        schema_version=SCHEMA_VERSION,
        transformation_version=git_commit_hash(settings.repo_root) or "unknown",
    )
    _write_manifest(
        settings=settings,
        provenance=provenance,
        row_counts=row_counts,
        source_files=source_files,
    )
    return provenance
