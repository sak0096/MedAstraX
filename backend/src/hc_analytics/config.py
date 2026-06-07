from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExperimentalCondition(str, Enum):
    BASELINE = "baseline"
    XAI = "xai"
    LLM = "llm"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HC_",
        extra="ignore",
    )

    repo_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3],
    )
    data_raw_dir: Path = Path("data/raw")
    data_processed_dir: Path = Path("data/processed")
    artifacts_dir: Path = Path("artifacts")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    experimental_condition: ExperimentalCondition = ExperimentalCondition.BASELINE

    study_id: str = "pilot-001"
    log_events: bool = True

    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None

    @property
    def raw_data_path(self) -> Path:
        return self.repo_root / self.data_raw_dir

    @property
    def processed_data_path(self) -> Path:
        return self.repo_root / self.data_processed_dir

    @property
    def artifacts_path(self) -> Path:
        return self.repo_root / self.artifacts_dir


def get_settings() -> Settings:
    return Settings()
