"""
Abstracted file storage backend.

If S3_BUCKET env var is set → use AWS S3.
Otherwise → use local disk (UPLOAD_DIR).

All callers go through save_file() / get_local_path() / delete_file() so
switching backends requires no changes outside this module.
"""
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _cfg():
    """Lazy import of config to avoid circular imports at module load."""
    from app.config import UPLOAD_DIR, S3_BUCKET, AWS_REGION
    return UPLOAD_DIR, S3_BUCKET, AWS_REGION


def is_s3() -> bool:
    """Return True when S3 storage is active (S3_BUCKET is set)."""
    _, S3_BUCKET, _ = _cfg()
    return bool(S3_BUCKET)


def _s3_client():
    import boto3
    _, S3_BUCKET, AWS_REGION = _cfg()
    return boto3.client("s3", region_name=AWS_REGION), S3_BUCKET


def storage_key(project_id: int, filename: str) -> str:
    """Build the S3 object key for a project file."""
    return f"projects/{project_id}/{filename}"


def save_file(project_id: int, filename: str, src_path: str) -> str:
    """
    Persist src_path to storage and return the stored_path.

    - Local mode: atomically moves src_path → UPLOAD_DIR/filename
      returns 'UPLOAD_DIR/filename'
    - S3 mode: uploads src_path to S3, deletes the local temp file,
      returns the S3 key ('projects/{project_id}/{filename}')
    """
    UPLOAD_DIR, S3_BUCKET, _ = _cfg()

    if is_s3():
        key = storage_key(project_id, filename)
        client, bucket = _s3_client()
        client.upload_file(src_path, bucket, key)
        try:
            os.unlink(src_path)
        except OSError:
            pass
        logger.info(f"Uploaded project {project_id} file to s3://{bucket}/{key}")
        return key

    # Local: atomic rename
    dest = os.path.join(UPLOAD_DIR, filename)
    os.replace(src_path, dest)
    logger.info(f"Saved project {project_id} file to {dest}")
    return dest


def get_local_path(stored_path: str) -> str | None:
    """
    Return a local filesystem path that can be read by pandas.

    - Local mode: returns stored_path if it exists (handles both absolute and
      relative paths, plus bare filenames joined to UPLOAD_DIR).
    - S3 mode: downloads the object to a temp file and returns that path.
      Returns None if the object doesn't exist.
    """
    UPLOAD_DIR, _, _ = _cfg()

    if is_s3():
        suffix = os.path.splitext(stored_path)[-1] or ".tmp"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        try:
            client, bucket = _s3_client()
            client.download_file(bucket, stored_path, tmp.name)
            logger.debug(f"Downloaded s3 object {stored_path} → {tmp.name}")
            return tmp.name
        except Exception as e:
            logger.warning(f"S3 download failed for {stored_path}: {e}")
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            return None

    # Local mode: try as-is first (handles absolute paths and
    # paths like 'uploads/project_1_file.csv' from legacy rows)
    if Path(stored_path).exists():
        return stored_path

    # Bare filename joined to UPLOAD_DIR
    joined = os.path.join(UPLOAD_DIR, stored_path)
    if Path(joined).exists():
        return joined

    return None


def delete_file(stored_path: str) -> None:
    """Remove the file from whichever backend is active."""
    UPLOAD_DIR, _, _ = _cfg()

    if is_s3():
        try:
            client, bucket = _s3_client()
            client.delete_object(Bucket=bucket, Key=stored_path)
            logger.info(f"Deleted s3://{bucket}/{stored_path}")
        except Exception as e:
            logger.warning(f"S3 delete failed for {stored_path}: {e}")
        return

    # Local
    # Handle both stored forms (absolute, relative, or bare filename)
    candidates = [
        stored_path,
        os.path.join(UPLOAD_DIR, stored_path),
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                os.remove(path)
                logger.info(f"Deleted local file {path}")
            except OSError as e:
                logger.warning(f"Could not delete {path}: {e}")
            return
