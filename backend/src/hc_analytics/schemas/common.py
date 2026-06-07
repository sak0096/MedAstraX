from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, Field


class VersionRecord(BaseModel):
    component: str
    version: str
    git_commit: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceRecord(BaseModel):
    source_name: str
    source_url: Optional[str] = None
    extracted_at: datetime
    schema_version: str
    transformation_version: str
    file_checksums: Dict[str, str] = Field(default_factory=dict)
