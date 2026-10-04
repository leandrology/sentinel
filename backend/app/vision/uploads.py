"""Uploaded-video storage. Validates type/size, stores under a controlled dir."""

from __future__ import annotations

import uuid
from pathlib import Path

ALLOWED_EXTENSIONS = {".mp4", ".webm", ".avi", ".mov"}
ALLOWED_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/x-msvideo",
    "video/quicktime",
    "video/avi",
}


def ensure_upload_dir(upload_dir: str) -> Path:
    path = Path(upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_upload(
    filename: str | None, content_type: str | None, size_bytes: int, max_mb: int
) -> str:
    """Return safe extension or raise ValueError with an operator-safe message."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported file type '{ext or '?'}': use mp4 or webm")
    if size_bytes > max_mb * 1024 * 1024:
        raise ValueError(f"file too large: limit is {max_mb} MB")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        if not content_type.startswith("video/"):
            raise ValueError(f"unsupported content type '{content_type}'")
    return ext


def save_upload(data: bytes, original_name: str, upload_dir: str) -> dict[str, object]:
    ext = Path(original_name).suffix.lower() or ".mp4"
    stored_name = f"{uuid.uuid4().hex[:12]}{ext}"
    dest = ensure_upload_dir(upload_dir) / stored_name
    dest.write_bytes(data)
    return {"id": dest.stem, "filename": stored_name, "path": str(dest), "size_bytes": len(data)}


def list_uploads(upload_dir: str) -> list[dict[str, object]]:
    root = Path(upload_dir)
    if not root.exists():
        return []
    items: list[dict[str, object]] = []
    for f in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
            try:
                items.append(
                    {
                        "id": f.stem,
                        "filename": f.name,
                        "path": str(f),
                        "size_bytes": f.stat().st_size,
                    }
                )
            except OSError:
                continue
    return items


def resolve_upload(upload_dir: str, video_id: str) -> Path | None:
    """Resolve an upload id to a path, confined to the upload dir (no traversal)."""
    safe = "".join(c for c in video_id if c.isalnum() or c in ("-", "_"))[:64]
    if not safe:
        return None
    root = Path(upload_dir)
    for f in root.iterdir():
        if f.is_file() and f.stem == safe and f.suffix.lower() in ALLOWED_EXTENSIONS:
            return f
    return None
