from __future__ import annotations

import json
import re
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

# DepartmentAI-MTech/
# ├── ai/
# │   └── ingestion/
# │       └── intelligent_chunker.py
# └── documents/
#     └── mtech/
#         └── processed/
#             ├── mtech_ordinance_pages.json
#             ├── mtech_ordinance_structure.json
#             └── mtech_ordinance_chunks.json

BASE_DIR = Path(__file__).resolve().parents[2]

PAGES_JSON = (
    BASE_DIR
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_pages.json"
)

STRUCTURE_JSON = (
    BASE_DIR
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_structure.json"
)

OUTPUT_JSON = (
    BASE_DIR
    / "documents"
    / "mtech"
    / "processed"
    / "mtech_ordinance_chunks.json"
)


# ============================================================
# CHUNKING CONFIGURATION
# ============================================================

# Target size is deliberately moderate.
# Later we can tune this after inspecting retrieval quality.
TARGET_CHARS = 2500

# Maximum size before a clause is split.
MAX_CHARS = 3200

# Character overlap between consecutive chunks.
OVERLAP_CHARS = 600

# Only the actual ordinance body is chunked here.
BODY_START = 9
BODY_END = 38

# Forms are kept as separate chunks.
FORM_START = 39
FORM_END = 50

DOCUMENT_NAME = "MNNIT Masters' Ordinance"
SOURCE_FILE = "Ordinances for Masters Programme 2023.pdf"


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def load_json(path: Path):
    """Load a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    """Save JSON with readable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def normalize_text(text: str) -> str:
    """
    Normalize extracted PDF text without destroying useful structure.
    """

    # Normalize Windows line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove trailing whitespace.
    lines = [
        line.rstrip()
        for line in text.split("\n")
    ]

    # Collapse excessive blank lines.
    cleaned = []

    previous_blank = False

    for line in lines:
        if not line.strip():
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
        else:
            cleaned.append(line.strip())
            previous_blank = False

    return "\n".join(cleaned).strip()


def page_map(pages: list[dict]) -> dict[int, dict]:
    """Create page_number -> page object mapping."""
    return {
        page["page_number"]: page
        for page in pages
    }


def get_page_text(
    pages_by_number: dict[int, dict],
    start_page: int,
    end_page: int,
) -> str:
    """
    Combine text from a page range.
    """

    parts = []

    for page_number in range(start_page, end_page + 1):

        page = pages_by_number.get(page_number)

        if not page:
            continue

        text = normalize_text(page.get("text", ""))

        if text:
            parts.append(text)

    return "\n\n".join(parts)


# ============================================================
# SECTION METADATA
# ============================================================

def build_section_map(
    structure: dict,
) -> dict[str, dict]:
    """
    Create:

        section_number -> section metadata
    """

    result = {}

    for section in structure.get("sections", []):

        number = str(section["number"])

        result[number] = {
            "number": number,
            "title": section.get("title", ""),
            "start_page": section.get("start_page"),
            "end_page": section.get("end_page"),
        }

    return result


# ============================================================
# CLAUSE EXTRACTION
# ============================================================

def clause_pattern(number: str) -> re.Pattern:
    """
    Build a regex for a specific clause number.

    Example:

        8.2.4

    matches:

        8.2.4
        8.2.4.
    """

    escaped = re.escape(number)

    return re.compile(
        rf"^\s*{escaped}\.?\s*(.*)$"
    )


def remove_clause_heading(
    text: str,
    clause_number: str,
) -> str:
    """
    Remove the clause number/title line from the beginning
    of a clause's extracted text when possible.

    We retain the title separately in metadata.
    """

    lines = text.splitlines()

    if not lines:
        return text

    pattern = clause_pattern(clause_number)

    # The first line may contain the clause number.
    if pattern.match(lines[0]):
        lines = lines[1:]

    return "\n".join(lines).strip()


# ============================================================
# FORM REFERENCES
# ============================================================

FORM_REF_RE = re.compile(
    r"\b(MP|GL)\s*[-–]?\s*(\d{1,2})(?:\(([abAB])\)|([abAB]))?",
    re.IGNORECASE,
)


def normalize_form_id(prefix: str, number: str, suffix: str | None) -> str:
    prefix = prefix.upper()

    if prefix == "GL":
        form_id = f"GL-{number}"
    else:
        form_id = f"MP-{number.zfill(2)}"

    if suffix:
        form_id += suffix.lower()

    return form_id


def find_form_references(
    text: str,
) -> list[str]:
    """
    Find references such as:

        Form: MP-02
        Form: GL-1
        MP-09b
    """

    matches = FORM_REF_RE.findall(text)

    form_ids = set()

    for prefix, number, paren_suffix, bare_suffix in matches:
        form_ids.add(
            normalize_form_id(
                prefix,
                number,
                paren_suffix or bare_suffix,
            )
        )

    return sorted(form_ids)


def get_form_references_for_clause(
    structure: dict,
    clause_number: str,
) -> list[str]:

    references = structure.get(
        "form_references",
        {},
    )

    result = []

    for form_id, items in references.items():

        for item in items:

            if item.get("clause_context") == clause_number:
                result.append(form_id)

    return sorted(set(result))


# ============================================================
# TEXT SPLITTING
# ============================================================

def split_into_paragraphs(
    text: str,
) -> list[str]:
    """
    Split text primarily at paragraph boundaries.

    This is preferable to immediately cutting at arbitrary
    character positions.
    """

    paragraphs = re.split(
        r"\n\s*\n",
        text,
    )

    return [
        paragraph.strip()
        for paragraph in paragraphs
        if paragraph.strip()
    ]


def split_long_text(
    text: str,
    target_chars: int = TARGET_CHARS,
    max_chars: int = MAX_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[str]:
    """
    Split long clause text while trying to preserve sentence/
    paragraph boundaries.

    Strategy:

    1. Keep paragraphs together where possible.
    2. If a paragraph itself is too large, split by sentences.
    3. If still too large, fall back to word-based splitting.
    4. Add overlap between chunks.
    """

    text = normalize_text(text)

    if len(text) <= max_chars:
        return [text]

    paragraphs = split_into_paragraphs(text)

    chunks = []
    current = ""

    for paragraph in paragraphs:

        candidate = (
            paragraph
            if not current
            else current + "\n\n" + paragraph
        )

        if len(candidate) <= target_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        # If this paragraph is itself too large,
        # split it further.
        if len(paragraph) > max_chars:

            sentence_parts = re.split(
                r"(?<=[.!?])\s+",
                paragraph,
            )

            sentence_buffer = ""

            for sentence in sentence_parts:

                candidate_sentence = (
                    sentence
                    if not sentence_buffer
                    else sentence_buffer
                    + " "
                    + sentence
                )

                if len(candidate_sentence) <= target_chars:
                    sentence_buffer = candidate_sentence
                    continue

                if sentence_buffer:
                    chunks.append(sentence_buffer)

                sentence_buffer = sentence

            if sentence_buffer:
                current = sentence_buffer

        else:
            current = paragraph

    if current:
        chunks.append(current)

    # --------------------------------------------------------
    # Ensure no chunk exceeds max_chars.
    # --------------------------------------------------------

    final_chunks = []

    for chunk in chunks:

        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
            continue

        words = chunk.split()

        buffer = ""

        for word in words:

            candidate = (
                word
                if not buffer
                else buffer + " " + word
            )

            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                if buffer:
                    final_chunks.append(buffer)

                buffer = word

        if buffer:
            final_chunks.append(buffer)

    # --------------------------------------------------------
    # Add overlap.
    # --------------------------------------------------------

    if len(final_chunks) <= 1:
        return final_chunks

    overlapped = []

    previous = ""

    for chunk in final_chunks:

        if previous:

            overlap = previous[-overlap_chars:]

            # Try not to start with a broken word.
            first_space = overlap.find(" ")

            if first_space != -1:
                overlap = overlap[first_space + 1:]

            chunk = overlap + "\n" + chunk

        overlapped.append(chunk)

        previous = chunk

    return overlapped


# ============================================================
# CLAUSE CHUNK CREATION
# ============================================================

def create_clause_chunks(
    pages_by_number: dict[int, dict],
    structure: dict,
) -> list[dict]:

    chunks = []

    section_map = build_section_map(structure)

    clauses = structure.get(
        "clauses",
        [],
    )

    # Sort by document order rather than clause number.
    clauses = sorted(
        clauses,
        key=lambda clause: (
            clause.get("start_page", 0),
            tuple(
                int(part)
                for part in clause["number"].split(".")
            ),
        ),
    )

    for clause in clauses:

        clause_number = clause["number"]
        section_number = str(
            clause["section"]
        )

        start_page = clause["start_page"]
        end_page = clause["end_page"]

        # Restrict to actual ordinance body.
        if start_page < BODY_START:
            continue

        if start_page > BODY_END:
            continue

        end_page = min(
            end_page,
            BODY_END,
        )

        section = section_map.get(
            section_number,
            {},
        )

        raw_text = get_page_text(
            pages_by_number,
            start_page,
            end_page,
        )

        if not raw_text:
            continue

        content = remove_clause_heading(
            raw_text,
            clause_number,
        )

        # Don't leave empty content.
        if not content.strip():
            continue

        forms = get_form_references_for_clause(
            structure,
            clause_number,
        )

        # Also detect references directly from content.
        forms.extend(
            find_form_references(content)
        )

        forms = sorted(set(forms))

        sub_chunks = split_long_text(
            content
        )

        for index, chunk_text in enumerate(
            sub_chunks,
            start=1,
        ):

            chunk_id = (
                f"mtech_"
                f"{section_number}_"
                f"{clause_number.replace('.', '_')}_"
                f"{index:03d}"
            )

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document": DOCUMENT_NAME,
                    "source_file": SOURCE_FILE,

                    "content_type": "ordinance_clause",

                    "section": section_number,
                    "section_title": section.get(
                        "title",
                        "",
                    ),

                    "clause": clause_number,
                    "clause_title": clause.get(
                        "title",
                        "",
                    ),

                    "page_start": start_page,
                    "page_end": end_page,

                    "chunk_index": index,
                    "chunk_count": len(sub_chunks),

                    "forms_referenced": forms,

                    "text": chunk_text,

                    "character_count": len(chunk_text),
                    "word_count": len(
                        chunk_text.split()
                    ),
                }
            )

    return chunks


# ============================================================
# FORM CHUNK CREATION
# ============================================================

def create_form_chunks(
    pages_by_number: dict[int, dict],
    structure: dict,
) -> list[dict]:

    chunks = []

    forms = structure.get(
        "forms",
        [],
    )

    for index, form in enumerate(
        forms,
        start=1,
    ):

        form_id = form["form_id"]

        start_page = form["start_page"]
        end_page = form["end_page"]

        text = get_page_text(
            pages_by_number,
            start_page,
            end_page,
        )

        if not text:
            continue

        chunk_id = (
            f"form_"
            f"{form_id.lower().replace('-', '_')}_"
            f"{index:03d}"
        )

        chunks.append(
            {
                "chunk_id": chunk_id,
                "document": DOCUMENT_NAME,
                "source_file": SOURCE_FILE,

                "content_type": "form",

                "form_id": form_id,

                "form_title": form.get(
                    "title",
                    "",
                ),

                "clause_references": form.get(
                    "clauses",
                    [],
                ),

                "page_start": start_page,
                "page_end": end_page,

                "chunk_index": 1,
                "chunk_count": 1,

                "forms_referenced": [],

                "text": text,

                "character_count": len(text),
                "word_count": len(
                    text.split()
                ),
            }
        )

    return chunks


# ============================================================
# VALIDATION
# ============================================================

def validate_chunks(
    chunks: list[dict],
    structure: dict,
) -> dict:

    errors = []
    warnings = []

    # --------------------------------------------------------
    # Basic checks
    # --------------------------------------------------------

    if not chunks:
        errors.append(
            "No chunks were generated."
        )

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        errors.append(
            "Duplicate chunk IDs detected."
        )

    # --------------------------------------------------------
    # Every chunk needs useful metadata.
    # --------------------------------------------------------

    required_fields = [
        "chunk_id",
        "document",
        "source_file",
        "content_type",
        "page_start",
        "page_end",
        "text",
    ]

    for chunk in chunks:

        for field in required_fields:

            if field not in chunk:
                errors.append(
                    f"{chunk.get('chunk_id')}: "
                    f"missing field '{field}'"
                )

        if not chunk.get("text", "").strip():
            errors.append(
                f"{chunk.get('chunk_id')}: empty text"
            )

    # --------------------------------------------------------
    # Page validation
    # --------------------------------------------------------

    for chunk in chunks:

        start = chunk["page_start"]
        end = chunk["page_end"]

        if start > end:
            errors.append(
                f"{chunk['chunk_id']}: "
                f"invalid page range"
            )

        if chunk["content_type"] == "ordinance_clause":

            if start < BODY_START or start > BODY_END:
                errors.append(
                    f"{chunk['chunk_id']}: "
                    f"ordinance chunk outside body"
                )

    # --------------------------------------------------------
    # Check clause coverage.
    # --------------------------------------------------------

    expected_clauses = {
        clause["number"]
        for clause in structure.get(
            "clauses",
            [],
        )
    }

    actual_clauses = {
        chunk["clause"]
        for chunk in chunks
        if chunk["content_type"]
        == "ordinance_clause"
        and "clause" in chunk
    }

    missing_clauses = sorted(
        expected_clauses - actual_clauses,
        key=lambda x: tuple(
            int(part)
            for part in x.split(".")
        ),
    )

    if missing_clauses:
        warnings.append(
            "Clauses without chunks: "
            + ", ".join(missing_clauses)
        )

    # --------------------------------------------------------
    # Check form coverage.
    # --------------------------------------------------------

    expected_forms = {
        form["form_id"]
        for form in structure.get(
            "forms",
            [],
        )
    }

    actual_forms = {
        chunk["form_id"]
        for chunk in chunks
        if chunk["content_type"] == "form"
    }

    missing_forms = sorted(
        expected_forms - actual_forms
    )

    if missing_forms:
        warnings.append(
            "Forms without chunks: "
            + ", ".join(missing_forms)
        )

    # --------------------------------------------------------
    # Very large chunks.
    # --------------------------------------------------------

    large_chunks = [
        chunk["chunk_id"]
        for chunk in chunks
        if len(chunk["text"]) > MAX_CHARS
    ]

    if large_chunks:
        warnings.append(
            f"{len(large_chunks)} chunks exceed "
            f"{MAX_CHARS} characters."
        )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    ordinance_chunks = [
        chunk
        for chunk in chunks
        if chunk["content_type"]
        == "ordinance_clause"
    ]

    form_chunks = [
        chunk
        for chunk in chunks
        if chunk["content_type"]
        == "form"
    ]

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "statistics": {
            "total_chunks": len(chunks),
            "ordinance_chunks": len(
                ordinance_chunks
            ),
            "form_chunks": len(
                form_chunks
            ),
            "unique_clauses": len(
                {
                    chunk["clause"]
                    for chunk in ordinance_chunks
                }
            ),
            "unique_forms": len(
                {
                    chunk["form_id"]
                    for chunk in form_chunks
                }
            ),
            "average_characters": (
                round(
                    sum(
                        len(chunk["text"])
                        for chunk in chunks
                    )
                    / len(chunks),
                    2,
                )
                if chunks
                else 0
            ),
            "max_characters": (
                max(
                    len(chunk["text"])
                    for chunk in chunks
                )
                if chunks
                else 0
            ),
        },
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n"
        "MNNIT MASTERS' ORDINANCE - "
        "INTELLIGENT CHUNKER"
    )

    print("\nLoading page extraction...")
    pages_data = load_json(
        PAGES_JSON
    )

    print("Loading structure...")
    structure = load_json(
        STRUCTURE_JSON
    )

    # The page parser currently stores pages either directly
    # as a list or under a "pages" key.
    if isinstance(pages_data, dict):
        pages = pages_data.get(
            "pages",
            []
        )
    else:
        pages = pages_data

    if not pages:
        raise ValueError(
            "No pages found in "
            "mtech_ordinance_pages.json"
        )

    pages_by_number = page_map(
        pages
    )

    print(
        f"Pages loaded       : {len(pages)}"
    )

    print(
        "Creating clause-aware "
        "ordinance chunks..."
    )

    ordinance_chunks = create_clause_chunks(
        pages_by_number,
        structure,
    )

    print(
        f"Ordinance chunks   : "
        f"{len(ordinance_chunks)}"
    )

    print(
        "Creating form chunks..."
    )

    form_chunks = create_form_chunks(
        pages_by_number,
        structure,
    )

    print(
        f"Form chunks        : "
        f"{len(form_chunks)}"
    )

    # Keep ordinance clauses first, then forms.
    all_chunks = (
        ordinance_chunks
        + form_chunks
    )

    # --------------------------------------------------------
    # Global sequential index.
    # --------------------------------------------------------

    for index, chunk in enumerate(
        all_chunks,
        start=1,
    ):
        chunk["global_index"] = index

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validation = validate_chunks(
        all_chunks,
        structure,
    )

    output = {
        "document": {
            "name": DOCUMENT_NAME,
            "source_file": SOURCE_FILE,
            "chunking_method": (
                "structure-aware "
                "clause-based chunking"
            ),
            "target_characters": TARGET_CHARS,
            "maximum_characters": MAX_CHARS,
            "overlap_characters": OVERLAP_CHARS,
        },

        "chunks": all_chunks,

        "validation": validation,
    }

    save_json(
        OUTPUT_JSON,
        output,
    )

    # --------------------------------------------------------
    # Console report
    # --------------------------------------------------------

    print(
        "\n"
        "MNNIT MASTERS' ORDINANCE - "
        "CHUNKING RESULT"
    )

    print(
        f"Total chunks       : "
        f"{len(all_chunks)}"
    )

    print(
        f"Ordinance chunks   : "
        f"{len(ordinance_chunks)}"
    )

    print(
        f"Form chunks        : "
        f"{len(form_chunks)}"
    )

    print(
        f"Unique clauses     : "
        f"{validation['statistics']['unique_clauses']}"
    )

    print(
        f"Unique forms       : "
        f"{validation['statistics']['unique_forms']}"
    )

    print(
        f"Average characters : "
        f"{validation['statistics']['average_characters']}"
    )

    print(
        f"Maximum characters : "
        f"{validation['statistics']['max_characters']}"
    )

    print(
        "Validation         : "
        + (
            "PASS"
            if validation["valid"]
            else "FAIL"
        )
    )

    if validation["errors"]:

        print("\nERRORS")

        for error in validation["errors"]:
            print(
                " -",
                error,
            )

    if validation["warnings"]:

        print("\nWARNINGS")

        for warning in validation["warnings"]:
            print(
                " -",
                warning,
            )

    print(
        f"\nOutput: {OUTPUT_JSON}"
    )


if __name__ == "__main__":
    main()
