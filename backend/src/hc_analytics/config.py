from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class ExperimentalCondition(str, Enum):
    BASELINE = "baseline"
    XAI = "xai"
    LLM = "llm"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="HC_",
        extra="ignore",
    )

    repo_root: Path = Field(default_factory=lambda: _REPO_ROOT)
    data_raw_dir: Path = Path("data/raw")
    data_processed_dir: Path = Path("data/processed")
    artifacts_dir: Path = Path("artifacts")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    experimental_condition: ExperimentalCondition = ExperimentalCondition.BASELINE

    study_id: str = "pilot-001"
    study_mode: bool = False
    study_cases_path: Path = Path("study/study_cases.json")
    log_events: bool = True

    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: float = 0.0
    llm_max_attempts: int = 8
    llm_retry_base_seconds: float = 1.0
    llm_retry_cap_seconds: float = 30.0

    stability_method: str = "bootstrap"  # bootstrap | margin
    bootstrap_iterations: int = 5
    allow_logistic_fallback: bool = False

    # local compatibility versus the production Azure runtime.
    environment: str = "local"
    storage_backend: str = "sqlite"
    database_url: Optional[str] = None
    session_secret: Optional[str] = None
    integration_secret: Optional[str] = None
    admin_token: Optional[str] = None
    entra_tenant_id: Optional[str] = None
    entra_audience: Optional[str] = None
    entra_admin_role: str = "MedAstraX.ResearchAdmin"
    enrollment_namespace: str = "test"
    recruitment_enabled: bool = False
    allow_synthetic_launch: bool = True
    enforce_progression: bool = False
    require_admin_for_research: bool = False
    cors_origins: Optional[str] = None
    session_ttl_seconds: int = 8 * 60 * 60
    launch_ttl_seconds: int = 600
    enrollment_cap_per_study: int = 60
    enrollment_cap_total: int = 120
    frontend_dist: Path = Path("frontend/dist")
    asset_root: Optional[Path] = None
    release_manifest_path: Path = Path("release/release-manifest.json")
    retention_policy: str = "unresolved"
    # Left unset on purpose. Tutorial-complete / comprehension-fail payment is unresolved.
    payment_tutorial_fail_cents: Optional[int] = None

    @property
    def strict_sessions(self) -> bool:
        return self.environment == "production" or self.enforce_progression

    @property
    def research_admin_required(self) -> bool:
        return self.environment == "production" or self.require_admin_for_research

    def allowed_origins(self) -> list[str]:
        if self.cors_origins is None:
            if self.environment == "production":
                return []
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def infrastructure_blockers(self) -> list[str]:
        if self.environment != "production":
            return []
        blockers: list[str] = []
        if self.storage_backend != "postgres" or not self.database_url:
            blockers.append("PostgreSQL is not configured.")
        if not self.session_secret or not self.integration_secret:
            blockers.append("Session or integration secret is missing.")
        return blockers

    def production_blockers(self) -> list[str]:
        blockers = self.infrastructure_blockers()
        if self.environment != "production":
            return blockers
        if self.recruitment_enabled and self.enrollment_namespace != "pilot":
            blockers.append("Recruitment is enabled outside the pilot namespace.")
        if self.retention_policy == "unresolved":
            blockers.append("Retention lifecycle is unresolved.")
        if self.payment_tutorial_fail_cents is None:
            blockers.append("Payment after comprehension failure is unresolved.")
        return blockers

    @property
    def raw_data_path(self) -> Path:
        return self.repo_root / self.data_raw_dir

    @property
    def processed_data_path(self) -> Path:
        return self.repo_root / self.data_processed_dir

    @property
    def artifacts_path(self) -> Path:
        return self.repo_root / self.artifacts_dir

    @property
    def frontend_dist_path(self) -> Path:
        return self.repo_root / self.frontend_dist

    @property
    def immutable_asset_root(self) -> Path:
        if self.asset_root is not None:
            return self.repo_root / self.asset_root
        return self.repo_root / "study"

    @property
    def release_manifest(self) -> Path:
        return self.repo_root / self.release_manifest_path


def get_settings() -> Settings:
    return Settings()
