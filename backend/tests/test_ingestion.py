from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hc_analytics.config import Settings
from hc_analytics.ingestion.pipeline import run_ingestion


@pytest.fixture()
def ingestion_settings(tmp_path: Path) -> Settings:
    raw_dir = tmp_path / "data" / "raw"
    beneficiary_dir = raw_dir / "beneficiary"
    beneficiary_dir.mkdir(parents=True)
    (raw_dir / "inpatient").mkdir(parents=True)
    (raw_dir / "prescription").mkdir(parents=True)

    beneficiary = (
        "BENE_ID|STATE_CODE|COUNTY_CD|ZIP_CD|BENE_BIRTH_DT|SEX_IDENT_CD|BENE_RACE_CD|"
        "ESRD_IND|BENE_DEATH_DT|BENE_ENROLLMT_REF_YR|AGE_AT_END_REF_YR|"
        "BENE_HI_CVRAGE_TOT_MONS|BENE_SMI_CVRAGE_TOT_MONS|BENE_PTA_TRMNTN_CD|BENE_PTB_TRMNTN_CD\n"
        "BENE001|01|001|35004|16-Aug-1940|1|1|0||2023|83|12|12|0|0\n"
    )
    (beneficiary_dir / "beneficiary_2023.csv").write_text(beneficiary, encoding="utf-8")

    inpatient = (
        "BENE_ID|CLM_ID|CLM_FROM_DT|CLM_THRU_DT|CLM_PMT_AMT|PRVDR_STATE_CD|"
        "PRNCPAL_DGNS_CD|CLM_FREQ_CD\n"
        "BENE001|CLM001|25-Mar-2023|29-Mar-2023|1200.50|01|I509|1\n"
    )
    (raw_dir / "inpatient" / "inpatient.csv").write_text(inpatient, encoding="utf-8")

    prescription = (
        "PDE_ID|BENE_ID|SRVC_DT|PD_DT|PROD_SRVC_ID|QTY_DSPNSD_NUM|"
        "DAYS_SUPLY_NUM|FILL_NUM|DRUG_CVRG_STUS_CD\n"
        "PDE001|BENE001|10-Jan-2023|11-Jan-2023|00071015523|30|30|1|C\n"
    )
    (raw_dir / "prescription" / "pde.csv").write_text(prescription, encoding="utf-8")

    return Settings(
        repo_root=tmp_path,
        data_raw_dir=Path("data/raw"),
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def test_run_ingestion_writes_processed_tables(ingestion_settings: Settings) -> None:
    provenance = run_ingestion(ingestion_settings)
    processed = ingestion_settings.processed_data_path

    beneficiaries = pd.read_parquet(processed / "beneficiaries.parquet")
    claims = pd.read_parquet(processed / "claims.parquet")
    prescriptions = pd.read_parquet(processed / "prescription_events.parquet")

    assert provenance.source_name.startswith("CMS Synthetic Medicare")
    assert len(beneficiaries) == 1
    assert beneficiaries.iloc[0]["bene_id"] == "BENE001"
    assert len(claims) == 1
    assert claims.iloc[0]["claim_setting"] == "inpatient"
    assert pd.notna(claims.iloc[0]["service_from_dt"])
    assert pd.notna(beneficiaries.iloc[0]["bene_birth_dt"])
    assert len(prescriptions) == 1
    assert (ingestion_settings.artifacts_path / "ingestion_manifest.json").exists()
