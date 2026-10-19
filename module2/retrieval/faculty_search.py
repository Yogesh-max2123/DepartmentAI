
import hashlib
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from module2.database.connection import get_connection


MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

TOP_K = 8
BATCH_SIZE = 32
EMBEDDING_DIMENSION = 384

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_FILE = CACHE_DIR / "faculty_embeddings.npz"

_model = None
_records = None
_embeddings = None


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------

def get_model():
    """Load the existing local embedding model only once."""
    global _model

    if _model is None:
        _model = SentenceTransformer(
            MODEL_NAME,
            local_files_only=True,
        )

        if _model.get_embedding_dimension() != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Expected {EMBEDDING_DIMENSION}-dimensional embeddings."
            )

    return _model


# ---------------------------------------------------------
# Faculty-name normalization and resolution
# ---------------------------------------------------------

TITLE_WORDS = {
    "dr",
    "doctor",
    "prof",
    "professor",
    "mr",
    "mrs",
    "ms",
    "sir",
    "madam",
}


def normalize_person_name(text):
    """
    Normalize a person's name while ignoring common titles and punctuation.

    Examples:
        Professor Dr. Shashank Srivastava -> shashank srivastava
        M.M. Gore                         -> m m gore
    """
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    tokens = [token for token in tokens if token not in TITLE_WORDS]
    return " ".join(tokens)


def resolve_faculty(question, records, faculty_name=None):
    """
    Resolve a faculty member using names actually present in the database.

    Returns:
        (faculty_ids, display_name, status)

    status is one of:
        matched, none, ambiguous, unresolved
    """
    name_to_ids = {}
    name_to_display = {}

    for record in records:
        display_name = (record.get("faculty_name") or "").strip()
        name_key = normalize_person_name(display_name)

        if not name_key:
            continue

        name_to_ids.setdefault(name_key, set()).add(record["faculty_id"])
        name_to_display.setdefault(name_key, display_name)

    # An explicitly supplied faculty name must resolve to a database name.
    if faculty_name is not None:
        requested_key = normalize_person_name(faculty_name)

        if requested_key in name_to_ids:
            return (
                name_to_ids[requested_key],
                name_to_display[requested_key],
                "matched",
            )

        # Permit a full database name contained in the supplied name.
        matches = [
            key for key in name_to_ids
            if f" {key} " in f" {requested_key} "
        ]

        if matches:
            longest = max(matches, key=len)
            return (
                name_to_ids[longest],
                name_to_display[longest],
                "matched",
            )

        return set(), None, "unresolved"

    query_key = normalize_person_name(question)
    padded_query = f" {query_key} "

    # First preference: an entire normalized faculty name appears in the
    # question. Prefer the longest match to avoid partial-name collisions.
    full_matches = [
        key for key in name_to_ids
        if f" {key} " in padded_query
    ]

    if full_matches:
        longest_length = max(len(key) for key in full_matches)
        longest_matches = [
            key for key in full_matches
            if len(key) == longest_length
        ]

        if len(longest_matches) == 1:
            key = longest_matches[0]
            return name_to_ids[key], name_to_display[key], "matched"

        # Different names with the same match length must not be guessed.
        return set(), None, "ambiguous"

    # If only a surname is supplied, resolve it only when unique.
    query_tokens = set(query_key.split())
    surname_matches = [
        key for key in name_to_ids
        if key.split() and key.split()[-1] in query_tokens
    ]

    unique_surnames = set(surname_matches)

    if len(unique_surnames) == 1:
        key = next(iter(unique_surnames))
        return name_to_ids[key], name_to_display[key], "matched"

    if len(unique_surnames) > 1:
        return set(), None, "ambiguous"

    # A title followed by an unrecognized name should not silently trigger
    # a search across unrelated faculty.
    has_person_title = bool(
        re.search(
            r"\b(?:professor|prof\.?|dr\.?|doctor)\b",
            question or "",
            flags=re.IGNORECASE,
        )
    )

    if has_person_title:
        return set(), None, "unresolved"

    # No person was specified; a directory-wide search is allowed.
    return set(), None, "none"


# ---------------------------------------------------------
# Database corpus
# ---------------------------------------------------------

def fetch_corpus():
    """
    Fetch searchable records from Module II tables only.

    Each query returns:
        record_id, faculty_id, faculty_name, section,
        title, content, source_url, record_year
    """
    queries = [
        (
            "basic_information",
            """
            SELECT f.id, f.id, f.full_name,
                   'basic_information', f.full_name,
                   concat_ws(' ', f.full_name, f.designation,
                       f.department, f.qualification,
                       f.area_of_interest, f.email, f.phone),
                   f.profile_url, NULL::text
            FROM m2_faculties f
            WHERE f.is_active IS DISTINCT FROM FALSE
            ORDER BY f.id
            """,
        ),
        (
            "education",
            """
            SELECT e.id, e.faculty_id, f.full_name,
                   'education', e.degree,
                   concat_ws(' ', f.full_name, e.degree,
                       e.specialization, e.institution,
                       e.year::text, e.details),
                   e.source_url, NULL::text
            FROM m2_education e
            JOIN m2_faculties f ON f.id = e.faculty_id
            ORDER BY e.id
            """,
        ),
        (
            "courses",
            """
            SELECT c.id, c.faculty_id, f.full_name,
                   'courses', c.course_name,
                   concat_ws(' ', f.full_name, c.course_name,
                       c.course_status, c.course_code,
                       c.academic_year::text, c.semester::text),
                   c.source_url, NULL::text
            FROM m2_courses c
            JOIN m2_faculties f ON f.id = c.faculty_id
            ORDER BY c.id
            """,
        ),
        (
            "research_areas",
            """
            SELECT r.id, r.faculty_id, f.full_name,
                   'research_areas', r.research_area,
                   concat_ws(' ', f.full_name, r.research_area),
                   r.source_url, NULL::text
            FROM m2_research_areas r
            JOIN m2_faculties f ON f.id = r.faculty_id
            ORDER BY r.id
            """,
        ),
        (
            "responsibilities",
            """
            SELECT r.id, r.faculty_id, f.full_name,
                   'responsibilities', r.role_title,
                   concat_ws(' ', f.full_name, r.role_title,
                       r.organization, r.department,
                       r.details, r.is_current::text),
                   r.source_url, NULL::text
            FROM m2_responsibilities r
            JOIN m2_faculties f ON f.id = r.faculty_id
            ORDER BY r.id
            """,
        ),
        (
            "publications",
            """
            SELECT p.id, fp.faculty_id, f.full_name,
                   'publications', p.title,
                   concat_ws(' ', f.full_name, p.title,
                       p.publication_type, p.journal_or_conference,
                       p.publisher, p.publication_year::text,
                       p.volume, p.issue, p.pages, p.doi,
                       p.indexing_information, p.impact_information,
                       p.authors, p.source_document),
                   p.source_url, p.publication_year::text
            FROM m2_publications p
            JOIN m2_faculty_publications fp
                ON fp.publication_id = p.id
            JOIN m2_faculties f ON f.id = fp.faculty_id
            ORDER BY p.id, fp.faculty_id
            """,
        ),
        (
            "achievements",
            """
            SELECT a.id, a.faculty_id, f.full_name,
                   'achievements', a.title,
                   concat_ws(' ', f.full_name, a.category,
                       a.title, a.description, a.organization,
                       a.venue, a.role, a.year::text, a.status),
                   a.source_url, a.year::text
            FROM m2_achievements a
            JOIN m2_faculties f ON f.id = a.faculty_id
            ORDER BY a.id
            """,
        ),
        (
            "thesis_supervision",
            """
            SELECT t.id, t.faculty_id, f.full_name,
                   'thesis_supervision', t.research_topic,
                   concat_ws(' ', f.full_name, t.program_level,
                       t.student_name, t.research_topic,
                       t.registration_year::text,
                       t.completion_year::text, t.status,
                       t.details),
                   t.source_url, t.completion_year::text
            FROM m2_thesis_supervision t
            JOIN m2_faculties f ON f.id = t.faculty_id
            ORDER BY t.id
            """,
        ),
        (
            "memberships",
            """
            SELECT m.id, m.faculty_id, f.full_name,
                   'memberships', m.organization,
                   concat_ws(' ', f.full_name, m.organization,
                       m.membership_type, m.membership_number,
                       m.details),
                   m.source_url, NULL::text
            FROM m2_memberships m
            JOIN m2_faculties f ON f.id = m.faculty_id
            ORDER BY m.id
            """,
        ),
        (
            "research_ids",
            """
            SELECT r.id, r.faculty_id, f.full_name,
                   'research_ids', r.identifier_type,
                   concat_ws(' ', f.full_name, r.identifier_type,
                       r.identifier_value),
                   COALESCE(r.identifier_url, r.source_url), NULL::text
            FROM m2_research_ids r
            JOIN m2_faculties f ON f.id = r.faculty_id
            ORDER BY r.id
            """,
        ),
        (
            "projects",
            """
            SELECT p.id, fp.faculty_id, f.full_name,
                   'projects', p.title,
                   concat_ws(' ', f.full_name, p.title,
                       p.funding_agency, p.reference_number,
                       p.status, p.description, p.amount::text),
                   p.source_url, NULL::text
            FROM m2_projects p
            JOIN m2_faculty_projects fp ON fp.project_id = p.id
            JOIN m2_faculties f ON f.id = fp.faculty_id
            ORDER BY p.id
            """,
        ),
    ]

    records = []
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            for section, sql in queries:
                cur.execute(sql)

                for row in cur.fetchall():
                    (
                        record_id,
                        faculty_id,
                        faculty_name,
                        _,
                        title,
                        content,
                        source_url,
                        record_year,
                    ) = row

                    content = (content or "").strip()

                    if not content:
                        continue

                    records.append({
                        "record_id": record_id,
                        "faculty_id": faculty_id,
                        "faculty_name": faculty_name or "",
                        "section": section,
                        "title": title or "",
                        "content": content,
                        "source_url": source_url,
                        "record_year": record_year,
                    })
    finally:
        conn.close()

    return records


# ---------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------

def corpus_fingerprint(records):
    digest = hashlib.sha256()

    for record in records:
        digest.update(
            (
                f"{record['section']}|"
                f"{record['record_id']}|"
                f"{record['faculty_id']}|"
                f"{record['content']}\n"
            ).encode("utf-8")
        )

    return digest.hexdigest()


def build_embeddings(records):
    """Reuse cached embeddings when searchable content is unchanged."""
    global _embeddings

    if not records:
        _embeddings = np.empty(
            (0, EMBEDDING_DIMENSION),
            dtype=np.float32,
        )
        return

    fingerprint = corpus_fingerprint(records)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        try:
            with np.load(CACHE_FILE, allow_pickle=False) as cache:
                cached_fingerprint = str(cache["fingerprint"].item())
                cached_embeddings = cache["embeddings"]

            if (
                cached_fingerprint == fingerprint
                and cached_embeddings.shape
                == (len(records), EMBEDDING_DIMENSION)
            ):
                _embeddings = cached_embeddings.astype(
                    np.float32,
                    copy=False,
                )
                return
        except (OSError, ValueError, KeyError):
            pass

    model = get_model()
    texts = [record["content"] for record in records]

    _embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    # Save through a temporary file to avoid leaving a partial cache.
    temporary_file = CACHE_DIR / "faculty_embeddings.tmp.npz"

    np.savez_compressed(
        temporary_file,
        fingerprint=np.array(fingerprint),
        embeddings=_embeddings,
    )
    temporary_file.replace(CACHE_FILE)


def refresh_corpus():
    """Reload Module II data and rebuild embeddings only if needed."""
    global _records, _embeddings

    _records = fetch_corpus()
    _embeddings = None
    build_embeddings(_records)

    return len(_records)


def ensure_corpus_loaded():
    global _records

    if _records is None:
        _records = fetch_corpus()
        build_embeddings(_records)


# ---------------------------------------------------------
# Query intent
# ---------------------------------------------------------

SECTION_INTENTS = {
    "research_areas": (
        "research area",
        "research areas",
        "research interest",
        "research interests",
        "area of research",
        "areas of research",
        "area of interest",
        "areas of interest",
    ),
    "publications": (
        "publication",
        "publications",
        "published paper",
        "published papers",
        "research paper",
        "research papers",
        "papers",
        "journal",
        "journals",
        "conference",
        "conferences",
        "doi",
    ),
    "education": (
        "education",
        "educational background",
        "degree",
        "degrees",
        "qualification",
        "qualifications",
        "studied",
    ),
    "courses": (
        "course",
        "courses",
        "teaching",
        "taught",
        "subject",
        "subjects",
    ),
    "responsibilities": (
        "responsibility",
        "responsibilities",
        "role",
        "roles",
        "position",
        "positions",
    ),
    "achievements": (
        "achievement",
        "achievements",
        "award",
        "awards",
        "honour",
        "honor",
        "recognition",
    ),
    "thesis_supervision": (
        "thesis",
        "theses",
        "supervised",
        "supervision",
        "doctoral student",
        "phd student",
        "ph.d student",
    ),
    "memberships": (
        "membership",
        "memberships",
        "professional body",
        "professional bodies",
    ),
    "research_ids": (
        "orcid",
        "scholar id",
        "research id",
        "scopus id",
    ),
    "projects": (
        "project",
        "projects",
        "funding",
        "grant",
        "grants",
    ),
    "basic_information": (
        "basic information",
        "contact",
        "email",
        "phone",
        "designation",
        "profile",
    ),
}

STOP_WORDS = {
    "what", "which", "who", "is", "are", "the", "a", "an",
    "of", "for", "to", "in", "on", "and", "or", "does",
    "do", "has", "have", "about", "tell", "me", "show",
    "give", "please", "with", "by", "from", "their", "his",
    "her", "recent", "latest", "newest", "professor", "prof",
    "dr", "doctor", "mr", "mrs", "ms",
}


def detect_requested_sections(question):
    """Return sections explicitly requested by the question."""
    q = (question or "").lower()
    detected = []

    for section, phrases in SECTION_INTENTS.items():
        if any(phrase in q for phrase in phrases):
            detected.append(section)

    return detected


def keyword_score(question, record, resolved_name=None):
    question_tokens = set(tokenize(question))
    terms = question_tokens - STOP_WORDS

    # Once a person is resolved, their name should not dominate the
    # relevance score for every record belonging to that person.
    if resolved_name:
        terms -= set(tokenize(resolved_name))

    if not terms:
        return 0.0

    content_tokens = set(tokenize(record["content"]))
    title_tokens = set(tokenize(record["title"]))

    matched = sum(
        1 for term in terms
        if term in content_tokens or term in title_tokens
    )

    return matched / len(terms)


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def publication_year(record):
    """Extract a plausible four-digit year from the publication year field."""
    value = str(record.get("record_year") or "").strip()

    match = re.search(r"\b(?:19|20)\d{2}\b", value)

    if not match:
        return None

    year = int(match.group(0))

    if 1900 <= year <= 2100:
        return year

    return None


def is_recent_query(question):
    q = (question or "").lower()
    return any(
        word in q
        for word in ("recent", "latest", "newest", "most recent", "last few years")
    )


# ---------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------

def faculty_search(
    question,
    top_k=TOP_K,
    faculty_name=None,
    sections=None,
):
    """
    Search Module II faculty records.

    Faculty identity is resolved before ranking. If a faculty member is
    identified, records from other faculty are excluded.

    `sections` may restrict results, e.g. ["publications"].
    If omitted, sections explicitly requested in the question are detected.
    """
    global _records, _embeddings

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")

    ensure_corpus_loaded()

    if not _records:
        return []

    faculty_ids, resolved_name, status = resolve_faculty(
        question,
        _records,
        faculty_name=faculty_name,
    )

    # Never fall back to a directory-wide search when a person was
    # explicitly supplied but could not be resolved.
    if status in {"ambiguous", "unresolved"}:
        return []

    allowed_sections = (
        set(sections)
        if sections is not None
        else set(detect_requested_sections(question))
    )

    selected_indices = [
        index
        for index, record in enumerate(_records)
        if (
            (not allowed_sections or record["section"] in allowed_sections)
            and (
                status != "matched"
                or record["faculty_id"] in faculty_ids
            )
        )
    ]

    if not selected_indices:
        return []

    model = get_model()
    query_embedding = model.encode(
        question,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    similarities = _embeddings[selected_indices] @ query_embedding

    selected_records = [_records[i] for i in selected_indices]
    valid_years = [
        publication_year(record)
        for record in selected_records
        if record["section"] == "publications"
    ]
    valid_years = [year for year in valid_years if year is not None]

    min_year = min(valid_years) if valid_years else None
    max_year = max(valid_years) if valid_years else None

    ranked = []

    for index, semantic_similarity in zip(
        selected_indices,
        similarities,
    ):
        record = _records[index]

        lexical = keyword_score(
            question,
            record,
            resolved_name=resolved_name if status == "matched" else None,
        )

        score = (
            0.75 * float(semantic_similarity)
            + 0.25 * lexical
        )

        # Explicit section requests receive a small relevance preference.
        if allowed_sections and record["section"] in allowed_sections:
            score += 0.10

        # For "recent publications", prefer newer publication years.
        if (
            is_recent_query(question)
            and record["section"] == "publications"
        ):
            year = publication_year(record)

            if year is not None:
                if min_year is not None and max_year is not None:
                    if max_year > min_year:
                        score += 0.08 * (
                            (year - min_year) / (max_year - min_year)
                        )
                    else:
                        score += 0.08

        result = dict(record)
        result.update({
            "semantic_score": float(semantic_similarity),
            "keyword_score": float(lexical),
            "relevance_score": float(score),
            "resolved_faculty": resolved_name,
        })
        ranked.append(result)

    ranked.sort(
        key=lambda item: item["relevance_score"],
        reverse=True,
    )

    # If multiple sections were requested, reserve places for each section
    # before filling remaining places by overall relevance.
    requested_sections = [
        section for section in SECTION_INTENTS
        if section in allowed_sections
    ]

    if len(requested_sections) > 1:
        quota = max(1, top_k // len(requested_sections))
        selected = []
        selected_keys = set()

        for section in requested_sections:
            section_results = [
                item for item in ranked
                if item["section"] == section
            ]

            for item in section_results[:quota]:
                key = (item["section"], item["record_id"], item["faculty_id"])

                if key not in selected_keys:
                    selected.append(item)
                    selected_keys.add(key)

        # Fill unused places if a requested section has too few records.
        for item in ranked:
            key = (item["section"], item["record_id"], item["faculty_id"])

            if key not in selected_keys:
                selected.append(item)
                selected_keys.add(key)

            if len(selected) >= top_k:
                break

        selected.sort(
            key=lambda item: item["relevance_score"],
            reverse=True,
        )
        return selected[:top_k]

    return ranked[:top_k]


# ---------------------------------------------------------
# Display and command-line validation
# ---------------------------------------------------------

def display_results(results):
    if not results:
        print("No matching faculty information found.")
        return

    faculty_names = {
        result["faculty_name"]
        for result in results
        if result.get("faculty_name")
    }

    if len(faculty_names) == 1:
        print(f"\nFaculty: {next(iter(faculty_names))}")

    for rank, result in enumerate(results, start=1):
        print(f"\n[{rank}] {result['faculty_name']} — {result['section']}")
        print(f"Title: {result['title']}")

        if result.get("record_year"):
            print(f"Year: {result['record_year']}")

        print(f"Relevance: {result['relevance_score']:.4f}")
        print(f"Information: {result['content']}")
        print(f"Source: {result['source_url'] or 'Not recorded'}")


if __name__ == "__main__":
    question = input("Ask about CSE faculty: ").strip()

    try:
        ensure_corpus_loaded()

        _, matched_name, status = resolve_faculty(
            question,
            _records,
        )

        if status == "ambiguous":
            print(
                "The faculty name is ambiguous. Please enter the "
                "faculty member's full name."
            )
        elif status == "unresolved":
            print(
                "Could not identify that faculty member in the database. "
                "Check the name against the faculty directory."
            )
        else:
            if status == "matched":
                print(f"Resolved faculty: {matched_name}")

            results = faculty_search(question)
            display_results(results)

            requested = detect_requested_sections(question)
            returned = {item["section"] for item in results}

            missing = [
                section for section in requested
                if section not in returned
            ]

            if missing:
                print(
                    "\nNo matching records were returned for these "
                    "requested sections: "
                    + ", ".join(missing)
                )

    except Exception as exc:
        print(f"Faculty retrieval failed: {exc}")
