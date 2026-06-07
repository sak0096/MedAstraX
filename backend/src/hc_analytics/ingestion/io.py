from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit_hash(repo_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


def read_pipe_csv_header(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readline().strip().split("|")


def read_pipe_csv(
    path: Path,
    *,
    usecols: Optional[Iterable[str]] = None,
    chunksize: Optional[int] = None,
) -> pd.DataFrame | Iterable[pd.DataFrame]:
    available = set(read_pipe_csv_header(path))
    selected = [column for column in usecols or available if column in available]
    if not selected:
        raise ValueError(f"No requested columns found in {path}")

    return pd.read_csv(
        path,
        sep="|",
        usecols=selected,
        dtype=str,
        chunksize=chunksize,
        low_memory=False,
    )


def parse_cms_dates(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    parsed = frame.copy()
    for column in columns:
        if column in parsed.columns:
            parsed[column] = pd.to_datetime(
                parsed[column].astype(str).str.strip(),
                format="%Y%m%d",
                errors="coerce",
            )
    return parsed


def write_parquet_chunks(
    chunks: Iterable[pd.DataFrame],
    output_path: Path,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer: Optional[pq.ParquetWriter] = None
    row_count = 0
    try:
        for chunk in chunks:
            if chunk.empty:
                continue
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output_path, table.schema)
            writer.write_table(table)
            row_count += len(chunk)
    finally:
        if writer is not None:
            writer.close()
    return row_count


def checksums_for_files(paths: Dict[str, Path]) -> Dict[str, str]:
    return {name: file_sha256(path) for name, path in sorted(paths.items()) if path.exists()}
