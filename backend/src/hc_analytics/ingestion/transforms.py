from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable

import pandas as pd

from hc_analytics.ingestion.constants import (
    BENEFICIARY_COLUMNS,
    CLAIM_OUTPUT_COLUMNS,
    DATE_COLUMNS,
    PRESCRIPTION_COLUMNS,
)
from hc_analytics.ingestion.io import parse_cms_dates, read_pipe_csv


def _reference_year_from_name(path: Path) -> int:
    match = re.search(r"beneficiary_(\d{4})\.csv$", path.name)
    if not match:
        raise ValueError(f"Could not infer reference year from {path.name}")
    return int(match.group(1))


def normalize_beneficiary_frame(frame: pd.DataFrame, reference_year: int) -> pd.DataFrame:
    renamed = frame.rename(columns={column: column.lower() for column in frame.columns})
    renamed["reference_year"] = reference_year
    renamed = parse_cms_dates(renamed, DATE_COLUMNS["beneficiaries"])
    for column in ("bene_id", "state_code", "sex_ident_cd", "bene_race_cd", "esrd_ind"):
        if column in renamed.columns:
            renamed[column] = renamed[column].astype("string").str.strip()
    if "age_at_end_ref_yr" in renamed.columns:
        renamed["age_at_end_ref_yr"] = pd.to_numeric(
            renamed["age_at_end_ref_yr"],
            errors="coerce",
        )
    return renamed


def load_beneficiaries(raw_dir: Path) -> pd.DataFrame:
    beneficiary_dir = raw_dir / "beneficiary"
    files = sorted(beneficiary_dir.glob("beneficiary_*.csv"))
    if not files:
        raise FileNotFoundError(f"No beneficiary files found in {beneficiary_dir}")

    frames = []
    for path in files:
        frame = read_pipe_csv(path, usecols=BENEFICIARY_COLUMNS)
        frames.append(normalize_beneficiary_frame(frame, _reference_year_from_name(path)))
    return pd.concat(frames, ignore_index=True)


def normalize_claim_chunk(
    frame: pd.DataFrame,
    claim_setting: str,
    column_map: Dict[str, str],
) -> pd.DataFrame:
    renamed = frame.rename(columns=column_map)
    renamed["claim_setting"] = claim_setting
    renamed = parse_cms_dates(renamed, DATE_COLUMNS["claims"])
    if "payment_amt" in renamed.columns:
        renamed["payment_amt"] = pd.to_numeric(renamed["payment_amt"], errors="coerce")
    string_columns = (
        "bene_id",
        "claim_id",
        "claim_setting",
        "provider_state_cd",
        "principal_diagnosis_cd",
        "clm_freq_cd",
        "hcpcs_cd",
    )
    for column in string_columns:
        if column not in renamed.columns:
            renamed[column] = pd.NA
        renamed[column] = renamed[column].astype("string").str.strip()
    return renamed[CLAIM_OUTPUT_COLUMNS]


def claim_chunk_iterator(
    path: Path,
    claim_setting: str,
    column_map: Dict[str, str],
    *,
    chunksize: int,
) -> Iterable[pd.DataFrame]:
    reader = read_pipe_csv(path, usecols=column_map.keys(), chunksize=chunksize)
    for chunk in reader:
        yield normalize_claim_chunk(chunk, claim_setting, column_map)


def normalize_prescription_frame(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(columns=PRESCRIPTION_COLUMNS)
    renamed = parse_cms_dates(renamed, DATE_COLUMNS["prescription_events"])
    for column in ("quantity_dispensed", "days_supply", "fill_number"):
        if column in renamed.columns:
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
    for column in ("pde_id", "bene_id", "product_service_id", "drug_coverage_status_cd"):
        if column in renamed.columns:
            renamed[column] = renamed[column].astype("string").str.strip()
    return renamed
