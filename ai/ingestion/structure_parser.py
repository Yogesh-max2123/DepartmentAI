from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

# DepartmentAI/
# ├── ai/ingestion/structure_parser.py  <-- this file
# └── documents/ug/processed/ug_ordinance_pages.json
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_JSON = BASE_DIR / "documents" / "ug" / "processed" / "ug_ordinance_pages.json"
OUTPUT_JSON = BASE_DIR / "documents" / "ug" / "processed" / "ug_ordinance_structure.json"

BODY_START, BODY_END = 9, 27
FORM_START, FORM_END = 28, 44
NOTES_START = 45

SECTION_RE = re.compile(r"^\s*(\d{1,2})\.\s*$")
CLAUSE_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d+){1,2})\.?\s+(.+?)\s*$")
FORM_RE = re.compile(r"\bForm\s*:\s*BP-(\d{2})\b", re.I)
CLAUSE_REF_RE = re.compile(
    r"\bClause\s+([0-9]+(?:\.[0-9]+)*(?:\([ivxIVX]+\))?(?:\([ivxIVX]+\))?)",
    re.I,
)

SECTION_TITLES = {
    "1": "INTRODUCTION",
    "2": "ACADEMIC SESSION",
    "3": "ADMISSION",
    "4": "CURRICULUM (B. Tech. Programme)",
    "5": "REGISTRATION",
    "6": "TEACHING AND EVALUATION",
    "7": "ACADEMIC PERFORMANCE REQUIREMENT",
    "8": "HOLIDAYS, VACATION, AND SEMESTER LEAVE",
    "9": "PROGRAMME REQUIREMENTS",
    "10": "DEGREES",
    "11": "SCHOLARSHIPS, PRIZES, AND MEDALS",
    "12": "CONDUCT AND DISCIPLINE",
    "13": "AMENDMENTS",
}


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def load_pages() -> list[dict]:
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_JSON}")

    obj = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        pages = obj.get("pages")
    else:
        pages = obj

    if not isinstance(pages, list):
        raise ValueError("Expected JSON object containing a 'pages' list.")

    return pages


def detect_sections(pages: list[dict]) -> list[dict]:
    """Detect Sections 1-13 only in the ordinance body, excluding TOC/front matter."""
    found = []

    for page in pages:
        page_no = page["page_number"]
        if not (BODY_START <= page_no <= BODY_END):
            continue

        lines = clean_lines(page["text"])

        for i, line in enumerate(lines):
            match = SECTION_RE.fullmatch(line)
            if not match:
                continue

            number = match.group(1)
            if number not in SECTION_TITLES:
                continue

            title = (
                lines[i + 1].strip()
                if i + 1 < len(lines)
                else SECTION_TITLES[number]
            )

            found.append(
                {
                    "number": number,
                    "title": SECTION_TITLES[number],
                    "start_page": page_no,
                    "source_title": title,
                }
            )

    # Keep the first real occurrence of each section.
    unique = {}
    for section in found:
        unique.setdefault(section["number"], section)

    sections = [
        unique[str(i)]
        for i in range(1, 14)
        if str(i) in unique
    ]

    # Same-page section starts are valid, e.g. Sections 4 and 5.
    for i, section in enumerate(sections):
        next_section = sections[i + 1] if i + 1 < len(sections) else None
        section["end_page"] = (
            next_section["start_page"] if next_section else BODY_END
        )
        section["page_count"] = (
            section["end_page"] - section["start_page"] + 1
        )

    return sections


def detect_clauses(pages: list[dict], sections: list[dict]) -> list[dict]:
    """
    Detect numbered clauses/subclauses using document order.

    Important:
    Section context is tracked by heading position rather than by page number.
    This handles pages containing the end of one section and the beginning of
    another, such as PDF page 12 and page 25.
    """
    clauses = []
    current_section = None

    for page in pages:
        page_no = page["page_number"]

        if not (BODY_START <= page_no <= BODY_END):
            continue

        lines = clean_lines(page["text"])

        for i, line in enumerate(lines):
            section_match = SECTION_RE.fullmatch(line)

            if section_match and section_match.group(1) in SECTION_TITLES:
                current_section = section_match.group(1)
                continue

            # Case 1: number and title are on the same line.
            clause_match = CLAUSE_RE.match(line)

            if clause_match:
                number = clause_match.group(1).rstrip(".")
                title = clause_match.group(2).strip()

            else:
                # Case 2: clause number is on one line and title is next line.
                standalone = re.fullmatch(
                    r"\s*(\d{1,2}(?:\.\d+){1,2})\.?\s*",
                    line,
                )

                if not standalone:
                    continue

                number = standalone.group(1).rstrip(".")
                next_line = (
                    lines[i + 1].strip()
                    if i + 1 < len(lines)
                    else ""
                )

                # A cross-reference such as "5.4." followed by prose must
                # not become a clause.
                if (
                    not next_line
                    or re.match(
                        r"^\d{1,2}(?:\.\d+){1,2}\.?\s",
                        next_line,
                    )
                ):
                    continue

                title = next_line

            top_level = number.split(".")[0]

            # Clause must belong to the currently active section.
            if current_section != top_level:
                continue

            # A clause has at least one decimal component: 1.1, 5.2.1, etc.
            if len(number.split(".")) < 2:
                continue

            clauses.append(
                {
                    "number": number,
                    "title": title,
                    "section": current_section,
                    "start_page": page_no,
                }
            )

    # De-duplicate clause numbers while preserving first occurrence.
    unique = {}
    for clause in clauses:
        unique.setdefault(clause["number"], clause)

    def clause_sort_key(clause: dict):
        return tuple(int(part) for part in clause["number"].split("."))

    clauses = sorted(unique.values(), key=clause_sort_key)

    # Page ranges are intentionally inclusive and may overlap when two clauses
    # begin on the same page. Exact text boundaries are line-based and can be
    # added later during intelligent chunking.
    for i, clause in enumerate(clauses):
        next_clause = clauses[i + 1] if i + 1 < len(clauses) else None

        clause["end_page"] = (
            next_clause["start_page"] if next_clause else BODY_END
        )
        clause["page_count"] = (
            clause["end_page"] - clause["start_page"] + 1
        )

    return clauses


def extract_form_clause_refs(text: str) -> list[str]:
    return sorted(
        set(CLAUSE_REF_RE.findall(text)),
        key=lambda value: tuple(
            int(x) for x in re.findall(r"\d+", value)
        ),
    )


def detect_forms(pages: list[dict]) -> list[dict]:
    """
    Detect actual annexure forms, not ordinary ordinance references.

    BP-12 is special: its page does not contain the literal "Form: BP-12",
    but its title is "Medical/ Semester/Study Leave Application".
    BP-11 intentionally appears twice as two distinct form records.
    """
    starts = []

    for page in pages:
        page_no = page["page_number"]

        if not (FORM_START <= page_no <= FORM_END):
            continue

        text = page["text"]
        match = FORM_RE.search(text)

        if match:
            starts.append((page_no, f"BP-{match.group(1)}"))

        elif (
            page_no == 41
            and "Medical/ Semester/Study Leave Application" in text
        ):
            starts.append((page_no, "BP-12"))

    starts.sort()

    forms = []

    for i, (start_page, form_id) in enumerate(starts):
        next_start = (
            starts[i + 1][0]
            if i + 1 < len(starts)
            else FORM_END + 1
        )
        end_page = min(next_start - 1, FORM_END)

        page = next(
            p for p in pages if p["page_number"] == start_page
        )
        lines = clean_lines(page["text"])

        title = ""
        for line in lines:
            upper = line.upper()

            if (
                upper.startswith("FORM FOR")
                or upper.startswith("FEED BACK FORM")
                or "LEAVE APPLICATION" in upper
            ):
                title = line
                break

        forms.append(
            {
                "form_id": form_id,
                "start_page": start_page,
                "end_page": end_page,
                "page_count": end_page - start_page + 1,
                "title": title,
                "clauses": extract_form_clause_refs(page["text"]),
            }
        )

    return forms


def detect_form_references(pages: list[dict]) -> dict:
    """
    Find references such as [Form: BP-13] inside the ordinance body.

    These are kept separate from actual form-page detection.
    """
    references = defaultdict(list)

    for page in pages:
        page_no = page["page_number"]

        if not (BODY_START <= page_no <= BODY_END):
            continue

        lines = clean_lines(page["text"])
        current_clause = None

        for line in lines:
            clause_match = CLAUSE_RE.match(line)

            if clause_match:
                current_clause = clause_match.group(1).rstrip(".")

            for form_match in FORM_RE.finditer(line):
                form_id = f"BP-{form_match.group(1)}"

                references[form_id].append(
                    {
                        "page": page_no,
                        "clause_context": current_clause,
                        "text": line,
                    }
                )

    return dict(references)


def detect_page_types(pages: list[dict], forms: list[dict]) -> list[dict]:
    form_pages = set()

    for form in forms:
        form_pages.update(
            range(form["start_page"], form["end_page"] + 1)
        )

    result = []

    for page in pages:
        page_no = page["page_number"]

        if page_no < BODY_START:
            if page_no <= 2:
                page_type = "front_matter"
            elif page_no <= 6:
                page_type = "table_of_contents"
            else:
                page_type = "preamble_or_nomenclature"

        elif BODY_START <= page_no <= BODY_END:
            page_type = "ordinance_body"

        elif page_no in form_pages:
            page_type = "form"

        elif page_no >= NOTES_START:
            page_type = "notes"

        else:
            page_type = "annexure"

        result.append(
            {
                "page": page_no,
                "page_type": page_type,
            }
        )

    return result


def validate(
    pages: list[dict],
    sections: list[dict],
    clauses: list[dict],
    forms: list[dict],
    form_references: dict,
) -> dict:
    errors = []
    warnings = []

    expected_sections = [str(i) for i in range(1, 14)]
    actual_sections = [s["number"] for s in sections]

    missing_sections = [
        s for s in expected_sections if s not in actual_sections
    ]

    if missing_sections:
        errors.append(f"Missing sections: {missing_sections}")

    if len(sections) != 13:
        errors.append(
            f"Expected 13 sections, detected {len(sections)}"
        )

    unique_form_ids = sorted(
        set(f["form_id"] for f in forms)
    )
    expected_forms = [f"BP-{i:02d}" for i in range(1, 14)]

    missing_forms = [
        f for f in expected_forms if f not in unique_form_ids
    ]

    if missing_forms:
        errors.append(f"Missing forms: {missing_forms}")

    if len(unique_form_ids) != 13:
        errors.append(
            "Expected 13 unique form IDs, "
            f"detected {len(unique_form_ids)}"
        )

    for section in sections:
        if section["start_page"] > section["end_page"]:
            errors.append(
                f"Invalid section range: {section['number']}"
            )

    for clause in clauses:
        if clause["start_page"] > clause["end_page"]:
            errors.append(
                f"Invalid clause range: {clause['number']}"
            )

    for form in forms:
        if form["start_page"] > form["end_page"]:
            errors.append(
                f"Invalid form range: {form['form_id']}"
            )

    if len(pages) != 50:
        warnings.append(
            f"Expected 50 pages for this source, got {len(pages)}"
        )

    if len(forms) != 14:
        warnings.append(
            "There are 14 physical form records because BP-11 occurs "
            "twice (Clauses 6.2.5 and 7.5)."
        )

    if not form_references:
        warnings.append(
            "No form references found in the ordinance body."
        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def build_structure(pages: list[dict]) -> dict:
    sections = detect_sections(pages)
    clauses = detect_clauses(pages, sections)
    forms = detect_forms(pages)
    form_references = detect_form_references(pages)
    page_types = detect_page_types(pages, forms)

    for section in sections:
        section["clauses"] = [
            clause["number"]
            for clause in clauses
            if clause["section"] == section["number"]
        ]

    validation = validate(
        pages,
        sections,
        clauses,
        forms,
        form_references,
    )

    return {
        "document": {
            "name": "MNNIT UG Ordinance",
            "source_file": "UG Ordinance.pdf",
            "total_pages": len(pages),
            "body_pages": [BODY_START, BODY_END],
            "form_pages": [FORM_START, FORM_END],
            "notes_pages": [NOTES_START, len(pages)],
        },
        "sections": sections,
        "clauses": clauses,
        "forms": forms,
        "form_references": form_references,
        "pages": page_types,
        "validation": validation,
    }


def main():
    pages = load_pages()
    structure = build_structure(pages)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(structure, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nMNNIT UG ORDINANCE - STRUCTURE PARSER")
    print(f"PDF pages          : {len(pages)}")
    print(f"Sections detected  : {len(structure['sections'])}")
    print(f"Clauses detected   : {len(structure['clauses'])}")
    print(f"Form records       : {len(structure['forms'])}")
    print(
        f"Unique form IDs    : "
        f"{len(set(f['form_id'] for f in structure['forms']))}"
    )
    print(
        f"Form references    : "
        f"{len(structure['form_references'])}"
    )
    print(
        f"Validation         : "
        f"{'PASS' if structure['validation']['valid'] else 'FAIL'}"
    )

    if structure["validation"]["errors"]:
        print("\nERRORS")
        for error in structure["validation"]["errors"]:
            print(" -", error)

    if structure["validation"]["warnings"]:
        print("\nWARNINGS")
        for warning in structure["validation"]["warnings"]:
            print(" -", warning)

    print("\nSECTIONS")
    for section in structure["sections"]:
        print(
            f"{section['number']}. {section['title']} "
            f"pages {section['start_page']}-{section['end_page']} "
            f"clauses: {', '.join(section['clauses']) or 'none'}"
        )

    print("\nFORMS")
    for form in structure["forms"]:
        print(
            f"{form['form_id']} "
            f"pages {form['start_page']}-{form['end_page']} "
            f"clauses: {', '.join(form['clauses']) or 'none'}"
        )


if __name__ == "__main__":
    main()
