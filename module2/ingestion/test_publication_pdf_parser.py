from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from module2.ingestion.faculty_publications_final import parse_publication_pdf

ROOT = Path("module2/ingestion/raw_sources")
JUNK_TITLE = re.compile(
    r"(?i)^(?:source software|new[- ]delhi|june\s+\d{1,2}|"
    r"research contributions at a glance|published journals?\b|"
    r"conference proceedings\b|journal papers?\b|book chapters?\b|"
    r"google scholar\b|patents?\b|sponsored projects?\b)"
)


def main() -> int:
    if not ROOT.exists():
        print(f"Cached PDF folder not found: {ROOT}")
        return 2

    pdfs = sorted(ROOT.rglob("publications.pdf"))
    print(f"Cached publication PDFs found: {len(pdfs)}")
    errors: list[str] = []
    total_records = 0
    per_faculty: dict[str, list] = {}

    for pdf in pdfs:
        faculty_key = pdf.parent.name
        try:
            records = parse_publication_pdf(pdf, faculty_name=faculty_key.replace("_", " "))
            per_faculty[faculty_key] = records
            types = Counter(record.publication_type for record in records)
            total_records += len(records)
            print(f"{faculty_key}: {len(records)} records | {dict(types)}")

            if not records:
                errors.append(f"{faculty_key}: parser returned no records")
            for record in records:
                title = (record.title or "").strip()
                raw = str((record.raw_metadata or {}).get("raw_text", ""))
                if not title:
                    errors.append(f"{faculty_key}: empty title")
                if JUNK_TITLE.search(title):
                    errors.append(f"{faculty_key}: suspicious title: {title[:120]}")
                if len(raw) > 1800:
                    errors.append(f"{faculty_key}: merged/oversized raw record ({len(raw)} chars): {title[:100]}")

        except Exception as exc:
            errors.append(f"{faculty_key}: {type(exc).__name__}: {exc}")
            print(f"{faculty_key}: ERROR {type(exc).__name__}: {exc}")

    # Regression checks for the observed layout-specific failures.
    if "dr_abhinav_kumar" in per_faculty:
        records = per_faculty["dr_abhinav_kumar"]
        chapters = [r for r in records if r.publication_type == "BOOK_CHAPTER"]
        if len(chapters) < 7:
            errors.append(f"Abhinav Kumar: expected at least 7 separate book chapters; got {len(chapters)}")
        if any("[BCh1]" in (r.title or "") for r in records):
            errors.append("Abhinav Kumar: book-chapter section was merged into a publication title")

    if "mr_rajesh_tripathi" in per_faculty:
        records = per_faculty["mr_rajesh_tripathi"]
        if len(records) != 3:
            errors.append(f"Rajesh Tripathi: expected 3 table rows; got {len(records)}")
        if any(re.search(r"(?i)^(?:new[- ]delhi|june\s+12\s+2019|source software)", r.title or "") for r in records):
            errors.append("Rajesh Tripathi: table column data leaked into a title")

    if "dr_k_sowjanya" in per_faculty:
        records = per_faculty["dr_k_sowjanya"]
        if len(records) != 18:
            errors.append(f"K. Sowjanya: expected 18 publication records (patents excluded); got {len(records)}")
        if any(r.publication_type == "PATENT" or re.search(r"(?i)^patents?\b", r.title or "") for r in records):
            errors.append("K. Sowjanya: patent data was incorrectly classified as a publication")
        repeated_titles = [r for r in records if "standardization aspects of authentication relay attack" in (r.title or "").lower()]
        if len(repeated_titles) != 2:
            errors.append("K. Sowjanya: same-title records from distinct venues were incorrectly merged")

    if "dr_kapil" in per_faculty and len(per_faculty["dr_kapil"]) < 40:
        errors.append(f"Kapil Gupta: expected at least 40 Google Scholar rows; got {len(per_faculty['dr_kapil'])}")

    print("\nPARSER VALIDATION SUMMARY")
    print(f"PDFs tested: {len(pdfs)}")
    print(f"PDFs producing records: {sum(bool(v) for v in per_faculty.values())}")
    print(f"Total parsed records: {total_records}")
    print(f"Validation errors: {len(errors)}")
    for error in errors[:100]:
        print(f"  - {error}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
