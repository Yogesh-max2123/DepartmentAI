from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

# DepartmentAI-MTech/
# ├── ai/ingestion/structure_parser.py          <-- this file
# └── documents/mtech/processed/mtech_ordinance_pages.json
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_JSON = BASE_DIR / "documents" / "mtech" / "processed" / "mtech_ordinance_pages.json"
OUTPUT_JSON = BASE_DIR / "documents" / "mtech" / "processed" / "mtech_ordinance_structure.json"

# The Masters' Ordinance PDF has 56 physical pages:
#   pages 1-8   : front matter (cover, vision/mission, TOC, preamble, nomenclature)
#   pages 9-38  : ordinance body (Sections 1 to 16)
#   pages 39-50 : annexure forms (MP-01 to MP-10 and GL-1)
#   pages 51-56 : blank "Notes" pages
BODY_START, BODY_END = 9, 38
FORM_START, FORM_END = 39, 50
NOTES_START = 51

# A section heading is a line such as "1. INTRODUCTION" or
# "8. Teaching and Evaluation". The known section titles are used to
# distinguish headings from ordinary numbered list items such as
# "1. Master of Technology (M.Tech.)" that also occur inside a section.
SECTION_RE = re.compile(r"^\s*(\d{1,2})\.?\s+(.+?)\s*$")
CLAUSE_RE = re.compile(r"^\s*(\d{1,2}(?:\.\d+){1,3})\.?\s+(\S.*?)\s*$")
FORM_RE = re.compile(
    r"\b(MP|GL)\s*[-–]?\s*(\d{1,2})(?:\(([abAB])\)|([abAB]))?",
    re.I,
)
CLAUSE_REF_RE = re.compile(
    r"\bClause\s*:?\s*([0-9]+(?:\.[0-9]+)*(?:\([0-9A-Za-z]+\))*)",
    re.I,
)
# Used to locate clause boundaries inside a page whose lines have been
# joined into a single string (so references split across lines are found).
CLAUSE_INLINE_RE = re.compile(
    r"(?:(?<=\s)|^)(\d{1,2}(?:\.\d+){1,3})\.?(?=\s)",
)

SECTION_TITLES = {
    "1": "INTRODUCTION",
    "2": "ACADEMIC SESSION",
    "3": "ADMISSION",
    "4": "REGISTRATION",
    "5": "LEAVE RULES",
    "6": "PROVISION FOR JOINING OTHER ACADEMIC INSTITUTIONS AS A NON-DEGREE STUDENT",
    "7": "PROGRAMME REQUIREMENTS",
    "8": "TEACHING AND EVALUATION",
    "9": "ACADEMIC PERFORMANCE REQUIREMENTS",
    "10": "TERMINATION OF PROGRAMME",
    "11": "APPOINTMENT OF THESIS SUPERVISOR(S) AND CONSTITUTION OF THESIS EXAMINATION BOARD",
    "12": "THESIS SUBMISSION AND EXAMINATION",
    "13": "DEGREE REQUIREMENTS",
    "14": "STIPEND/FELLOWSHIP, SCHOLARSHIPS, PRIZES AND MEDALS",
    "15": "CONDUCT AND DISCIPLINE",
    "16": "WAIVER OF REQUIREMENTS IN SPECIAL CASES",
}

# A short, distinctive prefix used to recognise the real heading line.
# This prevents numbered list items inside a section from being mistaken
# for section headings.
SECTION_HEADING_PREFIXES = {
    "1": "INTRODUCTION",
    "2": "ACADEMIC SESSION",
    "3": "ADMISSION",
    "4": "REGISTRATION",
    "5": "LEAVE RULES",
    "6": "PROVISION FOR JOINING",
    "7": "PROGRAMME REQUIREMENTS",
    "8": "TEACHING AND EVALUATION",
    "9": "ACADEMIC PERFORMANCE REQUIREMENTS",
    "10": "TERMINATION OF PROGRAMME",
    "11": "APPOINTMENT OF THESIS SUPERVISOR",
    "12": "THESIS SUBMISSION AND EXAMINATION",
    "13": "DEGREE REQUIREMENTS",
    "14": "STIPEND",
    "15": "CONDUCT AND DISCIPLINE",
    "16": "WAIVER OF REQUIREMENTS",
}

# Physical annexure form records. The Masters' Ordinance contains twelve
# physical forms: MP-01 to MP-10 (MP-09 appears as two separate forms,
# MP-09a and MP-09b) and the GL-1 thesis submission guideline sheet.
FORM_PAGE_IDS = {
    39: "MP-01",
    40: "MP-02",
    41: "MP-03",
    42: "MP-04",
    43: "MP-05",
    44: "MP-06",
    45: "MP-07",
    46: "MP-08",
    47: "MP-09a",
    48: "MP-09b",
    49: "MP-10",
    50: "GL-1",
}

FORM_TITLES = {
    "MP-01": "Conversion from Full time to Part time",
    "MP-02": "Leave Application",
    "MP-03": "Application for proceeding as Non-degree Student (Other Institution)",
    "MP-04": "Performance evaluation at host Institution/Industry",
    "MP-05": "APPLICATION FOR MERCY APPEAL",
    "MP-06": "Addition of Co-Supervisor from outside the Institute",
    "MP-07": "List of Suggested Examiners for M.Tech./MCA/MBA/M.Sc./MSW Thesis Examination Board",
    "MP-08": "CERTIFICATE (Plagiarism check)",
    "MP-09a": "REPORT OF M.Tech./MCA/MBA/M.Sc./MSW THESIS EXAMINATION BOARD (Interim)",
    "MP-09b": "REPORT OF M.Tech./MCA/MBA/M.Sc./MSW THESIS EXAMINATION BOARD",
    "MP-10": "FORM FOR REPORTING CASES REGARDING UNFAIR-MEANS",
    "GL-1": "Guidelines for Thesis submission",
}

EXPECTED_FORM_IDS = sorted(FORM_PAGE_IDS.values())


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


def match_section_heading(line: str) -> dict | None:
    """
    Return section metadata if the line is a real section heading.

    A real heading is a line such as "3. ADMISSION" whose text after the
    number starts with the known section title. Numbered list items such
    as "1. Master of Technology (M.Tech.)" are rejected.
    """
    match = SECTION_RE.match(line)

    if not match:
        return None

    number = match.group(1)
    remainder = match.group(2).strip()

    if number not in SECTION_TITLES:
        return None

    prefix = SECTION_HEADING_PREFIXES[number]

    if not remainder.upper().startswith(prefix):
        return None

    return {
        "number": number,
        "title": SECTION_TITLES[number],
        "source_title": remainder,
    }


def detect_sections(pages: list[dict]) -> list[dict]:
    """Detect Sections 1-16 only in the ordinance body, excluding TOC/front matter."""
    found = []

    for page in pages:
        page_no = page["page_number"]
        if not (BODY_START <= page_no <= BODY_END):
            continue

        for line in clean_lines(page["text"]):
            heading = match_section_heading(line)

            if heading:
                found.append(
                    {
                        "number": heading["number"],
                        "title": heading["title"],
                        "start_page": page_no,
                        "source_title": heading["source_title"],
                    }
                )

    # Keep the first real occurrence of each section.
    unique = {}
    for section in found:
        unique.setdefault(section["number"], section)

    sections = [
        unique[str(i)]
        for i in range(1, len(SECTION_TITLES) + 1)
        if str(i) in unique
    ]

    # Same-page section starts are valid.
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
    another (for example PDF pages 12, 16, 18 and 19).
    """
    clauses = []
    current_section = None

    for page in pages:
        page_no = page["page_number"]

        if not (BODY_START <= page_no <= BODY_END):
            continue

        for line in clean_lines(page["text"]):
            heading = match_section_heading(line)

            if heading:
                current_section = heading["number"]
                continue

            clause_match = CLAUSE_RE.match(line)

            if not clause_match:
                continue

            number = clause_match.group(1).rstrip(".")
            title = clause_match.group(2).strip()

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


def normalize_form_id(prefix: str, number: str, suffix: str | None) -> str:
    prefix = prefix.upper()

    # GL-1 is a single guideline sheet and is not zero-padded.
    if prefix == "GL":
        form_id = f"GL-{number}"
    else:
        form_id = f"MP-{number.zfill(2)}"

    if suffix:
        form_id += suffix.lower()

    return form_id


def detect_forms(pages: list[dict]) -> list[dict]:
    """
    Detect the annexure forms MP-01 to MP-10 (including MP-09a and MP-09b)
    and the GL-1 thesis guideline record.

    Each physical form starts on its own physical page, so the page is used
    as the authoritative anchor while the text is still scanned for the
    form title and clause references.
    """
    forms = []

    for page_no in range(FORM_START, FORM_END + 1):
        form_id = FORM_PAGE_IDS.get(page_no)

        if not form_id:
            continue

        page = next(
            (p for p in pages if p["page_number"] == page_no),
            None,
        )

        if page is None:
            continue

        forms.append(
            {
                "form_id": form_id,
                "start_page": page_no,
                "end_page": page_no,
                "page_count": 1,
                "title": FORM_TITLES.get(form_id, ""),
                "clauses": extract_form_clause_refs(page["text"]),
            }
        )

    return forms


def detect_form_references(pages: list[dict], clauses: list[dict]) -> dict:
    """
    Find references such as (Form: MP-02) or Form: GL-1 inside the
    ordinance body.

    The page lines are first joined so that references split across line
    breaks (for example "(Form: MP-" followed by "03)") are detected. The
    clause context is then resolved from the nearest detected clause that
    appears before the reference on the same page.

    These references are kept separate from actual form-page detection.
    """
    references = defaultdict(list)

    valid_clause_numbers = {clause["number"] for clause in clauses}

    for page in pages:
        page_no = page["page_number"]

        if not (BODY_START <= page_no <= BODY_END):
            continue

        lines = clean_lines(page["text"])
        joined = " ".join(lines)

        # Positions of real clauses on this page.
        clause_positions = []

        for match in CLAUSE_INLINE_RE.finditer(joined):
            number = match.group(1).rstrip(".")

            if number in valid_clause_numbers:
                clause_positions.append((match.start(), number))

        clause_positions.sort()

        for form_match in FORM_RE.finditer(joined):
            prefix, number, paren_suffix, bare_suffix = form_match.groups()
            suffix = paren_suffix or bare_suffix
            form_id = normalize_form_id(prefix, number, suffix)

            current_clause = None

            for position, clause_number in clause_positions:
                if position < form_match.start():
                    current_clause = clause_number
                else:
                    break

            references[form_id].append(
                {
                    "page": page_no,
                    "clause_context": current_clause,
                    "text": form_match.group(0),
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

    expected_sections = [str(i) for i in range(1, len(SECTION_TITLES) + 1)]
    actual_sections = [s["number"] for s in sections]

    missing_sections = [
        s for s in expected_sections if s not in actual_sections
    ]

    if missing_sections:
        errors.append(f"Missing sections: {missing_sections}")

    if len(sections) != len(SECTION_TITLES):
        errors.append(
            f"Expected {len(SECTION_TITLES)} sections, detected {len(sections)}"
        )

    unique_form_ids = sorted(
        set(f["form_id"] for f in forms)
    )

    missing_forms = [
        f for f in EXPECTED_FORM_IDS if f not in unique_form_ids
    ]

    if missing_forms:
        errors.append(f"Missing forms: {missing_forms}")

    if len(unique_form_ids) != len(EXPECTED_FORM_IDS):
        errors.append(
            f"Expected {len(EXPECTED_FORM_IDS)} unique form IDs, "
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

    if len(pages) != 56:
        warnings.append(
            f"Expected 56 pages for this source, got {len(pages)}"
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
    form_references = detect_form_references(pages, clauses)
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
            "name": "MNNIT Masters' Ordinance",
            "source_file": "Ordinances for Masters Programme 2023.pdf",
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

    print("\nMNNIT MASTERS' ORDINANCE - STRUCTURE PARSER")
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
