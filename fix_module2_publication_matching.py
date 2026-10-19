
from __future__ import annotations

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
PERSISTENCE = ROOT / "module2" / "ingestion" / "publication_persistence.py"
BULK = ROOT / "module2" / "ingestion" / "publication_bulk_ingestion.py"

NEW_MATCHER = r'''def _normalize_person_name(name: str) -> str:
    """Normalize names for punctuation-insensitive matching."""
    value = (name or "").casefold()
    value = re.sub(
        r"\b(lieutenant|professor|prof|doctor|dr|mr|mrs|ms|miss|lt)\b",
        " ",
        value,
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _find_faculty_id(
    cursor,
    faculty_name: str,
    profile_url: str | None = None,
) -> int | None:
    """Resolve faculty by profile URL first, then unique normalized name."""
    if not faculty_name:
        return None

    # Prefer the authoritative profile URL when supplied.
    if profile_url:
        cursor.execute(
            """
            SELECT id
            FROM m2_faculties
            WHERE LOWER(RTRIM(profile_url, '/')) =
                  LOWER(RTRIM(%s, '/'))
            LIMIT 2
            """,
            (profile_url.strip(),),
        )
        rows = cursor.fetchall()

        if len(rows) == 1:
            return rows[0][0]

        if len(rows) > 1:
            raise ValueError(
                f"Ambiguous faculty profile_url in m2_faculties: "
                f"{profile_url}"
            )

    cursor.execute("SELECT id, full_name FROM m2_faculties")
    faculty_rows = cursor.fetchall()

    # Explicit aliases for known differences in source and stored names.
    aliases = {
        "m m gore": "manoj madhava gore",
        "r s yadav": "rama shankar yadav",
        "d s kushwaha": "dharmender singh kushwaha",
        "d k yadav": "dharmendra kumar yadav",
        "kailash w kalare": "kailash wamanrao kalare",
        "prasun chandra tripathi": "prasun tripathi",
    }

    source_key = _normalize_person_name(faculty_name)
    alias_target = aliases.get(source_key)
    target_keys = {source_key}

    if alias_target:
        target_keys.add(_normalize_person_name(alias_target))

    matches = [
        faculty_id
        for faculty_id, stored_name in faculty_rows
        if _normalize_person_name(stored_name) in target_keys
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous faculty name '{faculty_name}' matches multiple "
            "database rows; the directory profile URL is required."
        )

    return None
'''


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = path.with_suffix(
        path.suffix + f".before_matching_fix_{stamp}.bak"
    )
    shutil.copy2(path, target)
    return target


def main() -> int:
    if not PERSISTENCE.is_file() or not BULK.is_file():
        print("ERROR: Run this script from the DepartmentAI project root.")
        print(f"Expected: {PERSISTENCE}")
        print(f"Expected: {BULK}")
        return 2

    persistence_text = PERSISTENCE.read_text(encoding="utf-8")
    bulk_text = BULK.read_text(encoding="utf-8")

    # Replace only the faculty-matching function.
    pattern = re.compile(
        r"def _find_faculty_id\(.*?(?=\ndef _find_existing_publication\()",
        re.S,
    )

    if not pattern.search(persistence_text):
        print(
            "ERROR: Could not locate _find_faculty_id() safely. "
            "No files changed."
        )
        return 3

    if "def _normalize_person_name(" not in persistence_text:
        persistence_text = pattern.sub(
            NEW_MATCHER + "\n",
            persistence_text,
            count=1,
        )

    # Add an optional profile URL to the persistence function.
    signature_old = (
        "def persist_publications(\n"
        "    faculty_name: str,\n"
        "    publications: Iterable[PublicationRecord],\n"
        ") -> dict[str, int]:"
    )

    signature_new = (
        "def persist_publications(\n"
        "    faculty_name: str,\n"
        "    publications: Iterable[PublicationRecord],\n"
        "    profile_url: str | None = None,\n"
        ") -> dict[str, int]:"
    )

    if signature_old in persistence_text:
        persistence_text = persistence_text.replace(
            signature_old,
            signature_new,
            1,
        )
    elif signature_new not in persistence_text:
        print(
            "ERROR: Could not locate persist_publications() signature. "
            "No files changed."
        )
        return 4

    # Pass the profile URL to the faculty matcher.
    old_call = """            faculty_id = _find_faculty_id(
                cursor,
                faculty_name,
            )"""

    new_call = """            faculty_id = _find_faculty_id(
                cursor,
                faculty_name,
                profile_url=profile_url,
            )"""

    if old_call in persistence_text:
        persistence_text = persistence_text.replace(
            old_call,
            new_call,
            1,
        )
    elif new_call not in persistence_text:
        print(
            "ERROR: Could not locate the faculty matcher call. "
            "No files changed."
        )
        return 5

    # Pass the discovered directory profile URL from bulk ingestion.
    bulk_old = "result = persist_publications(faculty.name, records)"
    bulk_new = (
        "result = persist_publications("
        "faculty.name, records, profile_url=faculty.profile_url)"
    )

    if bulk_old in bulk_text:
        bulk_text = bulk_text.replace(bulk_old, bulk_new, 1)
    elif bulk_new not in bulk_text:
        print(
            "ERROR: Could not locate the expected persistence call in "
            "bulk ingestion. No files changed."
        )
        return 6

    # Validate both proposed files before writing.
    try:
        ast.parse(persistence_text, filename=str(PERSISTENCE))
        ast.parse(bulk_text, filename=str(BULK))
    except SyntaxError as exc:
        print(f"ERROR: Syntax validation failed: {exc}. No files changed.")
        return 7

    # Back up originals before making changes.
    p_backup = backup(PERSISTENCE)
    b_backup = backup(BULK)

    PERSISTENCE.write_text(
        persistence_text,
        encoding="utf-8",
        newline="\n",
    )
    BULK.write_text(
        bulk_text,
        encoding="utf-8",
        newline="\n",
    )

    # Validate the written files.
    try:
        ast.parse(
            PERSISTENCE.read_text(encoding="utf-8"),
            filename=str(PERSISTENCE),
        )
        ast.parse(
            BULK.read_text(encoding="utf-8"),
            filename=str(BULK),
        )
    except SyntaxError as exc:
        print(f"ERROR: Post-write syntax validation failed: {exc}")
        print("Original-file backups:")
        print(f"  {p_backup}")
        print(f"  {b_backup}")
        return 8

    print("PATCH APPLIED AND PYTHON SYNTAX VALIDATION PASSED.")
    print(f"Backup: {p_backup}")
    print(f"Backup: {b_backup}")
    print("Changed:")
    print(f"  {PERSISTENCE}")
    print(f"  {BULK}")
    print(
        "Matching prefers profile URLs, then unique normalized names "
        "and explicit aliases."
    )
    print(
        "Ambiguous name-only matches fail safely instead of linking "
        "publications to an uncertain faculty record."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
