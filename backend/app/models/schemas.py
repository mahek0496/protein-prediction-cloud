"""Request bodies validated by FastAPI/Pydantic."""
from typing import Literal

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    sequence: str = Field(..., description="Protein sequence in FASTA or plain text", max_length=20000)
    name: str | None = Field(None, max_length=120)
    execution_mode: Literal["parallel", "sequential"] = "parallel"
    demo_delay_seconds: float | None = Field(
        None, ge=0, le=5, description="ARTIFICIAL delay per analysis task (C-G), for demonstrations only"
    )


class BenchmarkRequest(BaseModel):
    sequence: str = Field(..., max_length=20000)
    demo_delay_seconds: float = Field(1.0, ge=0, le=5)
