"""Local, auditable cache for Module II faculty publication sources."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

DEFAULT_CACHE_ROOT = Path("module2/ingestion/raw_sources")


def faculty_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "unknown_faculty").lower()).strip("_")
    return slug or "unknown_faculty"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def save_source_snapshot(
    faculty_name: str,
    source_url: str,
    content: bytes,
    content_type: str = "",
    final_url: str | None = None,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
) -> dict[str, Any]:
    """Save an original HTML/PDF source without overwriting another format."""
    root = Path(cache_root) / faculty_slug(faculty_name)
    root.mkdir(parents=True, exist_ok=True)
    effective_url = final_url or source_url
    path_suffix = Path(urlsplit(effective_url).path).suffix.lower()
    is_pdf = (
        "pdf" in (content_type or "").lower()
        or path_suffix == ".pdf"
        or content.startswith(b"%PDF")
    )
    filename = "publications.pdf" if is_pdf else "publication_page.html"
    source_path = root / filename
    source_path.write_bytes(content)

    metadata = {
        "faculty_name": faculty_name,
        "requested_url": source_url,
        "final_url": effective_url,
        "content_type": content_type,
        "saved_file": filename,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "cached_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = root / "source_metadata.json"
    try:
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        sources = previous.get("sources", {}) if isinstance(previous, dict) else {}
    except (OSError, json.JSONDecodeError):
        sources = {}
    sources[filename] = metadata
    metadata_path.write_text(
        json.dumps({"faculty_name": faculty_name, "sources": sources}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"directory": str(root), "source_path": str(source_path), **metadata}


def save_extraction_artifacts(
    faculty_name: str,
    source_metadata: dict[str, Any],
    records: list[Any],
    warnings: list[str] | None = None,
    cache_root: str | Path = DEFAULT_CACHE_ROOT,
) -> dict[str, str]:
    """Save extracted records and a concise quality report as JSON."""
    root = Path(cache_root) / faculty_slug(faculty_name)
    root.mkdir(parents=True, exist_ok=True)
    serialized = [_jsonable(record) for record in records]
    records_path = root / "extracted_records.json"
    records_path.write_text(
        json.dumps(serialized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    oversized = sum(
        len(str((item.get("raw_metadata") or {}).get("raw_text") or item.get("title") or "")) > 1800
        for item in serialized if isinstance(item, dict)
    )
    warning_list = warnings or []
    report = {
        "faculty_name": faculty_name,
        "source_url": source_metadata.get("final_url") or source_metadata.get("requested_url"),
        "source_file": source_metadata.get("saved_file"),
        "source_sha256": source_metadata.get("sha256"),
        "record_count": len(serialized),
        "oversized_record_count": oversized,
        "warnings": warning_list,
        "review_required": bool(warning_list) or oversized > 0 or len(serialized) == 0,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    report_path = root / "extraction_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"records_path": str(records_path), "report_path": str(report_path)}
