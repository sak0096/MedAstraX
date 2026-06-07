from __future__ import annotations

SOURCE_NAME = "CMS Synthetic Medicare Enrollment, FFS Claims, and PDE"
SOURCE_URL = (
    "https://data.cms.gov/collection/"
    "synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event"
)
SCHEMA_VERSION = "1.0"

BENEFICIARY_COLUMNS = [
    "BENE_ID",
    "STATE_CODE",
    "COUNTY_CD",
    "ZIP_CD",
    "BENE_BIRTH_DT",
    "SEX_IDENT_CD",
    "BENE_RACE_CD",
    "ESRD_IND",
    "BENE_DEATH_DT",
    "BENE_ENROLLMT_REF_YR",
    "AGE_AT_END_REF_YR",
    "BENE_HI_CVRAGE_TOT_MONS",
    "BENE_SMI_CVRAGE_TOT_MONS",
    "BENE_PTA_TRMNTN_CD",
    "BENE_PTB_TRMNTN_CD",
]

CLAIM_SETTINGS = {
    "inpatient": {
        "relative_path": "inpatient/inpatient.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "ICD9_DGNS_CD_1": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
    "outpatient": {
        "relative_path": "outpatient/outpatient.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "ICD9_DGNS_CD_1": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
    "carrier": {
        "relative_path": "carrier/carrier.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "PRNCPAL_DGNS_CD": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
            "HCPCS_CD": "hcpcs_cd",
        },
    },
    "snf": {
        "relative_path": "snf/snf.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "ICD9_DGNS_CD_1": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
    "dme": {
        "relative_path": "dme/dme.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "PRNCPAL_DGNS_CD": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
    "hha": {
        "relative_path": "hha/hha.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "ICD9_DGNS_CD_1": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
    "hospice": {
        "relative_path": "hospice/hospice.csv",
        "columns": {
            "BENE_ID": "bene_id",
            "CLM_ID": "claim_id",
            "CLM_FROM_DT": "service_from_dt",
            "CLM_THRU_DT": "service_thru_dt",
            "CLM_PMT_AMT": "payment_amt",
            "PRVDR_STATE_CD": "provider_state_cd",
            "ICD9_DGNS_CD_1": "principal_diagnosis_cd",
            "CLM_FREQ_CD": "clm_freq_cd",
        },
    },
}

PRESCRIPTION_COLUMNS = {
    "PDE_ID": "pde_id",
    "BENE_ID": "bene_id",
    "SRVC_DT": "service_dt",
    "PD_DT": "paid_dt",
    "PROD_SRVC_ID": "product_service_id",
    "QTY_DSPNSD_NUM": "quantity_dispensed",
    "DAYS_SUPLY_NUM": "days_supply",
    "FILL_NUM": "fill_number",
    "DRUG_CVRG_STUS_CD": "drug_coverage_status_cd",
}

DATE_COLUMNS = {
    "beneficiaries": ["bene_birth_dt", "bene_death_dt"],
    "claims": ["service_from_dt", "service_thru_dt"],
    "prescription_events": ["service_dt", "paid_dt"],
}

CHUNK_SIZE = 100_000

CLAIM_OUTPUT_COLUMNS = [
    "bene_id",
    "claim_id",
    "claim_setting",
    "service_from_dt",
    "service_thru_dt",
    "payment_amt",
    "provider_state_cd",
    "principal_diagnosis_cd",
    "clm_freq_cd",
    "hcpcs_cd",
]
