from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from module2.ingestion.faculty_directory import discover_faculty
from module2.ingestion.faculty_profile import discover_profile_components
from module2.ingestion.faculty_publications import (
    fetch_publication_source,
    parse_publication_html,
    _find_embedded_pdf_url,
)
from module2.ingestion.faculty_publications_final import parse_publication_pdf
from module2.ingestion.publication_persistence import persist_publications
from module2.ingestion.publication_source_cache import (
    DEFAULT_CACHE_ROOT,
    save_extraction_artifacts,
    save_source_snapshot,
)


def normalize_publication_url(url: str) -> str:
    """Resolve relative URLs and encode spaces in URL paths."""
    absolute_url = urljoin("https://mnnit.ac.in/", url.strip())
    parts = urlsplit(absolute_url)
    encoded_path = quote(parts.path, safe="/:@!$&'()*+,;=-._~%")
    return urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))


def looks_like_pdf(content: bytes, content_type: str, url: str) -> bool:
    return (
        content.startswith(b"%PDF-")
        or "application/pdf" in (content_type or "").lower()
        or urlsplit(url).path.lower().endswith(".pdf")
    )


def _raw_text(record) -> str:
    metadata = getattr(record, "raw_metadata", {}) or {}
    return str(metadata.get("raw_text") or getattr(record, "title", "") or "")


def assess_records(records: list, source_type: str, source_text: str = "") -> list[str]:
    """Conservative checks; warnings prevent accidental database writes."""
    warnings: list[str] = []
    if not records:
        return [f"{source_type} parser returned no publication records"]

    oversized = [record for record in records if len(_raw_text(record)) > 1800]
    if oversized:
        warnings.append(f"{len(oversized)} record(s) exceed 1800 characters")

    suspicious_title = re.compile(
        r"(?i)^(?:source software|new[- ]delhi|june\s+\d{1,2}|"
        r"research contributions at a glance|published journals?\b|"
        r"conference proceedings\b|journal papers?\b|book chapters?\b|"
        r"google scholar\b|patents?\b|sponsored projects?\b)"
    )
    junk = []
    for record in records:
        title = (getattr(record, "title", "") or "").strip()
        raw = _raw_text(record)
        if suspicious_title.search(title) or re.search(r"(?i)book chapters?\s+\[bch1\]", raw):
            junk.append(title[:100] or raw[:100])
        if len(title) > 600:
            warnings.append("At least one title exceeds 600 characters; possible merged records")
            break
    if junk:
        warnings.append("Possible table/header artefact in title: " + junk[0])

    if source_type == "html" and len(records) <= 2:
        longest = max((len(_raw_text(record)) for record in records), default=0)
        numbered_markers = len(re.findall(r"(?m)(?:^|[\s>])\d{1,3}[.)]\s+", source_text))
        if longest > 1000 or numbered_markers >= 4 and len(records) == 1:
            warnings.append("HTML output may contain merged publication entries")

    suspicious = re.compile(
        r"^(?:curriculum vitae|vitae|patents?\b|research project(?:s)?\b|project grants?\b|"
        r"consultancy\b|thesis supervised\b|invited talks?\b|professional experience\b)",
        re.IGNORECASE,
    )
    for record in records:
        if suspicious.search((getattr(record, "title", "") or "").strip()):
            warnings.append(f"Possible non-publication content classified as a publication: {record.title[:100]}")
            break

    return list(dict.fromkeys(warnings))


def _faculty_tokens(value: str) -> set[str]:
    """Normalize faculty/folder names for matching locally cached PDFs."""
    tokens = set(re.findall(r"[a-z0-9]+", (value or "").lower()))
    tokens -= {"dr", "prof", "professor", "mr", "mrs", "ms", "miss", "lt", "lieutenant", "col", "colonel", "faculty", "publications"}
    return tokens


def _find_cached_faculty_pdf(faculty_name: str, cache_dir: Path) -> Path | None:
    """Find an already downloaded publications.pdf without guessing a URL."""
    roots = [cache_dir / "raw_sources", cache_dir]
    candidates: list[Path] = []
    seen_paths: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*/publications.pdf"):
            resolved = str(path.resolve()).lower()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                candidates.append(path)
    if not candidates:
        return None

    wanted = _faculty_tokens(faculty_name)
    if not wanted:
        return None
    folder_tokens = {p: _faculty_tokens(p.parent.name) for p in candidates}

    # Prefer exact token matches. This handles names with honorifics and initials.
    exact = [p for p, tokens in folder_tokens.items() if tokens == wanted]
    if len(exact) == 1:
        return exact[0]

    # Some cache folders intentionally contain only a distinctive first/last name
    # (e.g. dr_kapil). Accept a subset match only when it is unique.
    subset = [p for p, tokens in folder_tokens.items() if tokens and tokens <= wanted and any(len(t) >= 4 for t in tokens)]
    if len(subset) == 1:
        return subset[0]

    # A unique high-overlap match is a final conservative option.
    scored = []
    for path, tokens in folder_tokens.items():
        overlap = len(wanted & tokens)
        score = overlap / max(1, len(wanted | tokens))
        if overlap and score >= 0.6:
            scored.append((score, path))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def discover_publication_records(
    faculty_name: str,
    publication_url: str,
    cache_dir: Path = DEFAULT_CACHE_ROOT,
) -> tuple[list, str, str, list[str], dict]:
    """Fetch/cache HTML or PDF, falling back to an official linked PDF when needed."""
    if not publication_url:
        return [], "missing_publication_url", "", ["No publication URL found"], {}

    publication_url = normalize_publication_url(publication_url)
    content, content_type, final_url = fetch_publication_source(publication_url)
    final_url = normalize_publication_url(final_url)
    source_metadata = save_source_snapshot(
        faculty_name, publication_url, content, content_type, final_url, cache_dir
    )

    if looks_like_pdf(content, content_type, final_url):
        records = parse_publication_pdf(
            pdf_path=source_metadata["source_path"],
            faculty_name=faculty_name,
            source_url=final_url,
        )
        warnings = assess_records(records, "pdf")
        return records, "pdf", final_url, warnings, source_metadata

    html = content.decode("utf-8", errors="replace")
    records = parse_publication_html(
        html=html,
        faculty_name=faculty_name,
        source_url=final_url,
        source_document=final_url,
    )
    html_warnings = assess_records(records, "html", html)
    if records and not html_warnings:
        return records, "html", final_url, [], source_metadata

    # A poor HTML result is not accepted just because it is non-empty.
    pdf_url = _find_embedded_pdf_url(html, final_url)
    if pdf_url:
        pdf_url = normalize_publication_url(pdf_url)
        try:
            pdf_bytes, pdf_content_type, pdf_final_url = fetch_publication_source(pdf_url)
            pdf_final_url = normalize_publication_url(pdf_final_url)
            if looks_like_pdf(pdf_bytes, pdf_content_type, pdf_final_url):
                pdf_metadata = save_source_snapshot(
                    faculty_name, pdf_url, pdf_bytes, pdf_content_type, pdf_final_url, cache_dir
                )
                pdf_records = parse_publication_pdf(
                    pdf_path=pdf_metadata["source_path"],
                    faculty_name=faculty_name,
                    source_url=pdf_final_url,
                )
                pdf_warnings = assess_records(pdf_records, "pdf")
                if pdf_records and not pdf_warnings:
                    return pdf_records, "pdf_fallback_after_html_review", pdf_final_url, [], pdf_metadata
                if pdf_records and len(pdf_records) > len(records) and len(pdf_warnings) <= len(html_warnings):
                    return pdf_records, "pdf_fallback_needs_review", pdf_final_url, pdf_warnings, pdf_metadata
                html_warnings.extend(pdf_warnings or ["Linked PDF did not improve extraction quality"])
            else:
                html_warnings.append("Linked publication source was not a PDF")
        except Exception as exc:
            html_warnings.append(f"Linked PDF fallback failed: {type(exc).__name__}: {exc}")
    else:
        html_warnings.append("No linked PDF found for fallback")

    # If the live page/embedded PDF did not yield records, reuse an already
    # cached official publication PDF for this faculty before giving up.
    if not records or html_warnings:
        cached_pdf = _find_cached_faculty_pdf(faculty_name, cache_dir)
        if cached_pdf:
            try:
                cached_records = parse_publication_pdf(
                    pdf_path=cached_pdf,
                    faculty_name=faculty_name,
                    source_url=final_url,
                )
                cached_warnings = assess_records(cached_records, "pdf")
                if cached_records and (not records or len(cached_records) > len(records)):
                    print(f"  Using cached publication PDF fallback: {cached_pdf}")
                    return cached_records, "cached_pdf_fallback", final_url, cached_warnings, {}
            except Exception as exc:
                html_warnings.append(f"Cached PDF fallback failed: {type(exc).__name__}: {exc}")

    # Preserve the best available extraction for review, but mark it for review.
    return records, "html_needs_review", final_url, list(dict.fromkeys(html_warnings)), source_metadata


def run_bulk_ingestion(dry_run: bool = True) -> None:
    faculty_records = discover_faculty()
    print(f"Faculty discovered: {len(faculty_records)}")
    print(f"Mode: {'DRY RUN — no database writes' if dry_run else 'PERSIST'}")
    print("=" * 88)

    cache_dir = DEFAULT_CACHE_ROOT
    summary = {
        "discovered": len(faculty_records), "processed": 0, "with_records": 0,
        "empty": 0, "failed": 0, "needs_review": 0, "parsed_records": 0,
        "inserted": 0, "reused": 0, "links_created": 0, "links_existing": 0,
    }
    failures: list[dict[str, str]] = []

    for index, faculty in enumerate(faculty_records, start=1):
        print(f"[{index}/{len(faculty_records)}] {faculty.name}")
        try:
            components = discover_profile_components(
                faculty_name=faculty.name, profile_url=faculty.profile_url
            )
            if not components.publications_url:
                summary["empty"] += 1
                print("  SKIPPED: publication URL not found")
                continue

            records, source_type, source_url, warnings, source_metadata = discover_publication_records(
                faculty_name=faculty.name,
                publication_url=components.publications_url,
                cache_dir=cache_dir,
            )
            summary["processed"] += 1
            summary["parsed_records"] += len(records)
            artifacts = save_extraction_artifacts(
                faculty_name=faculty.name,
                source_metadata=source_metadata,
                records=records,
                warnings=warnings,
                cache_root=cache_dir,
            ) if source_metadata else {}

            print(f"  Source: {source_type}")
            print(f"  URL: {source_url}")
            print(f"  Parsed records: {len(records)}")
            if warnings:
                summary["needs_review"] += 1
                print("  REVIEW REQUIRED:")
                for warning in warnings:
                    print(f"    - {warning}")
            if artifacts:
                print(f"  Records: {artifacts['records_path']}")
                print(f"  Report:  {artifacts['report_path']}")

            if not records:
                summary["empty"] += 1
                continue
            summary["with_records"] += 1

            for record in records[:3]:
                print(f"  - [{record.publication_type}] {record.title[:180]}")

            # Records flagged by quality checks are never persisted automatically.
            if warnings:
                if not dry_run:
                    print("  NOT PERSISTED: extraction requires manual review")
                continue
            if dry_run:
                continue

            result = persist_publications(faculty.name, records, profile_url=faculty.profile_url)
            summary["inserted"] += result["publications_inserted"]
            summary["reused"] += result["publications_reused"]
            summary["links_created"] += result["relationships_created"]
            summary["links_existing"] += result["relationships_existing"]
            print(
                "  Persisted: "
                f"inserted={result['publications_inserted']}, reused={result['publications_reused']}, "
                f"links_created={result['relationships_created']}, links_existing={result['relationships_existing']}"
            )
        except Exception as exc:
            summary["failed"] += 1
            failures.append({"faculty": faculty.name, "error": f"{type(exc).__name__}: {exc}"})
            print(f"  FAILED: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 88)
    print("PUBLICATION INGESTION SUMMARY")
    print("=" * 88)
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').title():22}: {value}")

    failure_path = Path("module2/ingestion/publication_ingestion_failures.json")
    if failures:
        failure_path.write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Failure details saved to: {failure_path}")
    elif failure_path.exists():
        failure_path.unlink()
    if dry_run:
        print("\nDRY RUN COMPLETE: no publication database writes were attempted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover and ingest faculty publication records.")
    parser.add_argument("--persist", action="store_true", help="Write validated publication records to PostgreSQL. Default is dry run.")
    args = parser.parse_args()
    run_bulk_ingestion(dry_run=not args.persist)
