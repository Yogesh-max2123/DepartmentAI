"""Read-only, schema-grounded Module II data-quality checks."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Mapping, Sequence

QUALITY_CATEGORIES = (
    "faculty",
    "publications",
    "projects",
    "achievements",
)

QUALITY_SCAN_LIMIT = 5_000
QUALITY_MAX_PAGE_SIZE = 100

_REQUIRED_FIELDS = {
    "faculty": ("full_name", "department", "profile_url", "source_name"),
    "publications": ("title", "publication_type"),
    "projects": ("title",),
    "achievements": ("category",),
}


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _as_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year


def _issue(
    category: str,
    record: Mapping[str, Any],
    issue_type: str,
    field: str,
    classification: str,
    explanation: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"{category}:{record['id']}:{issue_type}:{field}",
        "category": category,
        "record_id": record["id"],
        "record_label": (
            record.get("full_name")
            or record.get("title")
            or f"{category.title()} record {record['id']}"
        ),
        "field": field,
        "issue_type": issue_type,
        "classification": classification,
        "explanation": explanation,
        "evidence": dict(evidence),
        "source_url": record.get("source_url"),
    }


def _required_value_issues(
    category: str,
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues = []
    for field in _REQUIRED_FIELDS[category]:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(
                _issue(
                    category,
                    record,
                    "missing_required_value",
                    field,
                    "objective",
                    f"{field} is required by the persisted Module II schema but is blank.",
                    {"stored_value": value},
                )
            )
    return issues


def _inconsistency_issues(
    category: str,
    record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues = []
    start = _as_date(record.get("start_date"))
    end = _as_date(record.get("end_date"))
    if start is not None and end is not None and end < start:
        issues.append(
            _issue(
                category,
                record,
                "date_range_inconsistent",
                "end_date",
                "objective",
                "The stored end_date precedes the stored start_date.",
                {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                },
            )
        )
    if category == "publications":
        publication_date = _as_date(record.get("publication_date"))
        publication_year = _as_year(record.get("publication_year"))
        if (
            publication_date is not None
            and publication_year is not None
            and publication_date.year != publication_year
        ):
            issues.append(
                _issue(
                    category,
                    record,
                    "publication_year_mismatch",
                    "publication_year",
                    "objective",
                    "publication_year does not match the year in publication_date.",
                    {
                        "publication_date": publication_date.isoformat(),
                        "publication_year": publication_year,
                    },
                )
            )
    return issues


def _duplicate_groups(
    category: str,
    records: Sequence[Mapping[str, Any]],
) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if category == "faculty":
            key = (
                _normalized_text(record.get("full_name")),
                _normalized_text(record.get("department")),
            )
            if all(key):
                groups[key].append(record)
        elif category == "publications":
            title = _normalized_text(record.get("title"))
            year = _as_year(record.get("publication_year"))
            if year is None:
                publication_date = _as_date(record.get("publication_date"))
                year = publication_date.year if publication_date else None
            if title and year is not None:
                groups[(title, year)].append(record)
        elif category == "projects":
            key = (
                _normalized_text(record.get("title")),
                _normalized_text(record.get("funding_agency")),
            )
            if all(key):
                groups[key].append(record)
        elif category == "achievements":
            title = _normalized_text(record.get("title"))
            category_value = _normalized_text(record.get("category"))
            year = _as_year(record.get("year"))
            if year is None:
                event_date = _as_date(record.get("event_date"))
                year = event_date.year if event_date else None
            if title and category_value and year is not None:
                groups[(title, category_value, year)].append(record)
    return {key: items for key, items in groups.items() if len(items) > 1}


def _duplicate_issues(
    category: str,
    groups: Mapping[tuple[Any, ...], Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    matching_fields = {
        "faculty": ("full_name", "department"),
        "publications": ("title", "publication_year", "publication_date"),
        "projects": ("title", "funding_agency"),
        "achievements": ("title", "category", "year", "event_date"),
    }[category]
    match_rule = {
        "faculty": "case-insensitive, whitespace-normalized full_name and department",
        "publications": (
            "case-insensitive, whitespace-normalized title and publication year "
            "(publication_date year is used when publication_year is absent)"
        ),
        "projects": "case-insensitive, whitespace-normalized title and funding_agency",
        "achievements": (
            "case-insensitive, whitespace-normalized title, category, and year "
            "(event_date year is used when year is absent)"
        ),
    }[category]
    issues = []
    for key, group in groups.items():
        ordered_group = sorted(group, key=lambda record: str(record["id"]))
        representative = ordered_group[0]
        candidate_ids = [record["id"] for record in ordered_group]
        candidate_values = [
            {
                "record_id": record["id"],
                **{field: record.get(field) for field in matching_fields},
            }
            for record in ordered_group[:20]
        ]
        evidence = {
            "matching_rule": match_rule,
            "comparison_key": list(key),
            "candidate_values": candidate_values,
            "candidate_values_truncated": len(ordered_group) > len(candidate_values),
            "candidate_record_ids": candidate_ids[:100],
            "candidate_record_ids_truncated": len(candidate_ids) > 100,
            "candidate_record_count": len(candidate_ids),
        }
        issues.append(
            _issue(
                category,
                representative,
                "possible_duplicate",
                "record",
                "heuristic",
                "This record is part of an in-scope candidate group matching the "
                "listed fields. It is a potential duplicate for human inspection, "
                "not a confirmed duplicate.",
                evidence,
            )
        )
    return issues


def build_data_quality_report(
    records_by_category: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    category: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """Build findings from bounded, already department-scoped persisted rows."""
    categories = (category,) if category else QUALITY_CATEGORIES
    issues: list[dict[str, Any]] = []
    record_counts: dict[str, int] = {}
    for record_category in categories:
        records = records_by_category[record_category]
        record_counts[record_category] = len(records)
        for record in records:
            issues.extend(_required_value_issues(record_category, record))
            issues.extend(_inconsistency_issues(record_category, record))
        groups = _duplicate_groups(record_category, records)
        issues.extend(_duplicate_issues(record_category, groups))

    issues.sort(
        key=lambda item: (
            item["category"],
            str(item["record_id"]),
            item["issue_type"],
            item["field"],
        )
    )
    total = len(issues)
    objective = sum(issue["classification"] == "objective" for issue in issues)
    potential_duplicates = sum(
        issue["issue_type"] == "possible_duplicate" for issue in issues
    )
    return {
        "summary": {
            "record_counts": record_counts,
            "records_scanned": sum(record_counts.values()),
            "total_issues": total,
            "objective_issues": objective,
            "potential_duplicate_findings": potential_duplicates,
        },
        "issues": issues[offset : offset + limit],
        "limit": limit,
        "offset": offset,
        "total": total,
    }
