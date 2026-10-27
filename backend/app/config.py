"""Application settings, read from environment variables (and an optional backend/.env file).

Nothing secret is hardcoded here. On EC2, AWS credentials come from the IAM role attached
to the instance (boto3 finds them automatically through the instance metadata service).
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "local"))
    cors_origins: list = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        ]
    )

    # --- AWS ---
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    s3_bucket_name: str = field(default_factory=lambda: os.getenv("S3_BUCKET_NAME", "").strip())
    s3_prefix: str = field(default_factory=lambda: os.getenv("S3_PREFIX", "jobs").strip("/"))
    presigned_url_expiry_seconds: int = field(
        default_factory=lambda: _int("PRESIGNED_URL_EXPIRY_SECONDS", 900)
    )
    # auto = use S3 when S3_BUCKET_NAME is set, otherwise local disk
    storage_backend: str = field(default_factory=lambda: os.getenv("STORAGE_BACKEND", "auto").lower())
    # Optional: point boto3 at an S3-compatible emulator (used only for testing)
    s3_endpoint_url: str = field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL", "").strip())

    # --- Structure prediction engine ---
    # esmatlas = Meta ESM Atlas public ESMFold API (no key)
    # nvidia   = NVIDIA-hosted ESMFold (needs NVIDIA_API_KEY)
    # none     = no 3D prediction; the app says so clearly
    prediction_engine: str = field(default_factory=lambda: os.getenv("PREDICTION_ENGINE", "esmatlas").lower())
    esmatlas_url: str = field(
        default_factory=lambda: os.getenv("ESMATLAS_URL", "https://api.esmatlas.com/foldSequence/v1/pdb/")
    )
    nvidia_esmfold_url: str = field(
        default_factory=lambda: os.getenv(
            "NVIDIA_ESMFOLD_URL", "https://health.api.nvidia.com/v1/biology/nvidia/esmfold"
        )
    )
    nvidia_api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_API_KEY", "").strip())
    prediction_timeout_seconds: float = field(default_factory=lambda: _float("PREDICTION_TIMEOUT_SECONDS", 120))

    # --- Workflow ---
    max_sequence_length: int = field(default_factory=lambda: _int("MAX_SEQUENCE_LENGTH", 400))
    min_sequence_length: int = field(default_factory=lambda: _int("MIN_SEQUENCE_LENGTH", 10))
    parallel_workers: int = field(default_factory=lambda: _int("PARALLEL_WORKERS", 6))
    max_concurrent_jobs: int = field(default_factory=lambda: _int("MAX_CONCURRENT_JOBS", 2))
    # ARTIFICIAL delay added to each analysis task so the parallel speed-up is visible on screen.
    default_demo_delay_seconds: float = field(default_factory=lambda: _float("DEMO_TASK_DELAY_SECONDS", 0))

    # --- Local paths ---
    database_path: Path = field(
        default_factory=lambda: Path(os.getenv("DATABASE_PATH", str(BACKEND_DIR / "data" / "predictions.db")))
    )
    local_storage_dir: Path = field(
        default_factory=lambda: Path(os.getenv("LOCAL_STORAGE_DIR", str(BACKEND_DIR / "data" / "files")))
    )

    @property
    def use_s3(self) -> bool:
        if self.storage_backend == "s3":
            return True
        if self.storage_backend == "local":
            return False
        return bool(self.s3_bucket_name)


settings = Settings()
