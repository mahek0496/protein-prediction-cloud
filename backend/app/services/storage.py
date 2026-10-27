"""Result storage: Amazon S3 (cloud) or local disk (offline development).

- S3 mode uses boto3 with the default credential chain. On EC2 that is the IAM role attached to
  the instance -- no access keys are stored in code or config files.
- Downloads from S3 use short-lived presigned GET URLs, so the browser never sees AWS credentials.
- If an S3 upload fails, the file is kept on local disk and the error is reported to the UI.
"""
import logging
from pathlib import Path

from ..config import settings

log = logging.getLogger("storage")

CONTENT_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".pdb": "chemical/x-pdb",
    ".cif": "chemical/x-mmcif",
}


class StorageError(Exception):
    pass


def describe_aws_error(exc: Exception) -> str:
    """Turn boto3/botocore exceptions into a beginner-readable message."""
    from botocore.exceptions import (ClientError, EndpointConnectionError, NoCredentialsError,
                                     PartialCredentialsError, ConnectTimeoutError, ReadTimeoutError)
    bucket = settings.s3_bucket_name
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return ("No AWS credentials found. On EC2, attach the IAM role (ProteinAppEC2Role) to the instance. "
                "On your PC, run 'aws configure' or set STORAGE_BACKEND=local.")
    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError)):
        return f"Amazon S3 is unreachable in region {settings.aws_region} (network problem or service outage)."
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("AccessDenied", "403", "AllAccessDisabled", "InvalidAccessKeyId", "SignatureDoesNotMatch"):
            return (f"Access denied by AWS ({code}). Check that the IAM role policy allows s3:PutObject, "
                    f"s3:GetObject and s3:DeleteObject on arn:aws:s3:::{bucket}/{settings.s3_prefix}/* "
                    f"and s3:ListBucket on arn:aws:s3:::{bucket}.")
        if code in ("NoSuchBucket", "404", "NotFound"):
            return f"S3 bucket '{bucket}' was not found. Check S3_BUCKET_NAME and AWS_REGION."
        if code in ("PermanentRedirect", "301", "AuthorizationHeaderMalformed"):
            return f"Bucket '{bucket}' is in a different region than AWS_REGION={settings.aws_region}."
        if code in ("ExpiredToken", "RequestExpired"):
            return "AWS credentials have expired. Restart the app or refresh your credentials."
        return f"AWS error {code}: {exc.response.get('Error', {}).get('Message', str(exc))}"
    return f"Unexpected storage error: {exc}"


class LocalStorage:
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str, filename: str) -> Path:
        p = (self.root / job_id / filename).resolve()
        if self.root.resolve() not in p.parents:
            raise StorageError("Invalid file path.")
        return p

    def save(self, job_id, filename, data: bytes) -> dict:
        p = self._path(job_id, filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return {"filename": filename, "backend": "local", "key": f"{job_id}/{filename}", "size_bytes": len(data)}

    def read(self, job_id, filename) -> bytes:
        p = self._path(job_id, filename)
        if not p.exists():
            raise StorageError(f"File {filename} not found.")
        return p.read_bytes()

    def download_url(self, job_id, filename) -> dict:
        return {"url": f"/api/files/{job_id}/{filename}", "expires_in": None, "backend": "local"}

    def delete(self, job_id, filename):
        p = self._path(job_id, filename)
        if p.exists():
            p.unlink()

    def health(self) -> dict:
        return {"backend": "local", "ok": True, "path": str(self.root),
                "message": "Local disk storage (AWS S3 not configured)."}


class S3Storage:
    name = "s3"

    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket_name
        if not self.bucket:
            raise StorageError("STORAGE_BACKEND=s3 but S3_BUCKET_NAME is empty.")
        cfg = Config(region_name=settings.aws_region, signature_version="s3v4",
                     s3={"addressing_style": "path" if settings.s3_endpoint_url else "virtual"},
                     connect_timeout=5, read_timeout=20,
                     retries={"max_attempts": 3, "mode": "standard"})
        self.session = boto3.session.Session(region_name=settings.aws_region)
        self.client = self.session.client("s3", config=cfg, endpoint_url=settings.s3_endpoint_url or None)

    def key(self, job_id, filename):
        return f"{settings.s3_prefix}/{job_id}/{filename}"

    def save(self, job_id, filename, data: bytes) -> dict:
        ctype = CONTENT_TYPES.get(Path(filename).suffix, "application/octet-stream")
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key(job_id, filename), Body=data,
                                   ContentType=ctype, Metadata={"job-id": job_id})
        except Exception as exc:  # botocore raises several unrelated exception classes
            raise StorageError(describe_aws_error(exc)) from exc
        return {"filename": filename, "backend": "s3", "bucket": self.bucket,
                "key": self.key(job_id, filename), "size_bytes": len(data)}

    def read(self, job_id, filename) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=self.key(job_id, filename))["Body"].read()
        except Exception as exc:
            raise StorageError(describe_aws_error(exc)) from exc

    def download_url(self, job_id, filename) -> dict:
        expiry = settings.presigned_url_expiry_seconds
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": self.key(job_id, filename),
                        "ResponseContentDisposition": f'attachment; filename="{job_id[:8]}_{filename}"'},
                ExpiresIn=expiry,
            )
        except Exception as exc:
            raise StorageError(describe_aws_error(exc)) from exc
        return {"url": url, "expires_in": expiry, "backend": "s3"}

    def delete(self, job_id, filename):
        try:
            self.client.delete_object(Bucket=self.bucket, Key=self.key(job_id, filename))
        except Exception as exc:
            raise StorageError(describe_aws_error(exc)) from exc

    def health(self) -> dict:
        info = {"backend": "s3", "bucket": self.bucket, "region": settings.aws_region, "prefix": settings.s3_prefix}
        creds = self.session.get_credentials()
        # "iam-role" = EC2 instance profile (what we want on EC2); "shared-credentials-file" = aws configure
        info["credential_source"] = getattr(creds, "method", None) if creds else None
        if creds is None:
            info.update(ok=False, message=describe_aws_error(_no_credentials()))
            return info
        try:
            self.client.head_bucket(Bucket=self.bucket)
            info.update(ok=True, message=f"Connected to S3 bucket '{self.bucket}'.")
        except Exception as exc:
            info.update(ok=False, message=describe_aws_error(exc))
        return info


def _no_credentials():
    from botocore.exceptions import NoCredentialsError
    return NoCredentialsError()


class StorageManager:
    """Chooses S3 or local storage, and falls back to local disk if an S3 upload fails."""

    def __init__(self):
        self.local = LocalStorage(settings.local_storage_dir)
        self.s3 = None
        self.init_error = None
        if settings.use_s3:
            try:
                self.s3 = S3Storage()
            except Exception as exc:  # e.g. boto3 missing or bucket name empty
                self.init_error = str(exc)
                log.error("S3 storage could not be initialised: %s", exc)

    @property
    def primary(self):
        return self.s3 or self.local

    def save_files(self, job_id: str, files: dict) -> dict:
        """files = {filename: str|bytes}. Returns {"files": [...], "errors": [...]}."""
        saved, errors = [], []
        for filename, content in files.items():
            data = content.encode("utf-8") if isinstance(content, str) else content
            if self.s3:
                try:
                    saved.append(self.s3.save(job_id, filename, data))
                    continue
                except StorageError as exc:
                    errors.append(f"S3 upload of {filename} failed: {exc}. Saved on server disk instead.")
                    log.warning("S3 upload failed for %s/%s: %s", job_id, filename, exc)
            elif settings.use_s3:
                errors.append(f"S3 not available ({self.init_error}). Saved {filename} on server disk.")
            saved.append(self.local.save(job_id, filename, data))
        return {"files": saved, "errors": errors}

    def _backend_for(self, record: dict):
        if record.get("backend") == "s3":
            if not self.s3:
                raise StorageError("This file is stored in S3, but S3 is not configured on this server.")
            return self.s3
        return self.local

    def read(self, job_id, record) -> bytes:
        return self._backend_for(record).read(job_id, record["filename"])

    def download_url(self, job_id, record) -> dict:
        return self._backend_for(record).download_url(job_id, record["filename"])

    def delete_files(self, job_id, records) -> list:
        errors = []
        for r in records:
            try:
                self._backend_for(r).delete(job_id, r["filename"])
            except StorageError as exc:
                errors.append(f"{r['filename']}: {exc}")
        return errors

    def health(self) -> dict:
        if settings.use_s3 and not self.s3:
            return {"backend": "s3", "ok": False, "message": f"S3 initialisation failed: {self.init_error}"}
        return self.primary.health()


_storage = None


def get_storage() -> StorageManager:
    global _storage
    if _storage is None:
        _storage = StorageManager()
    return _storage


def reset_storage():
    """Re-read settings and rebuild the storage client (used by tests)."""
    global _storage
    _storage = None
