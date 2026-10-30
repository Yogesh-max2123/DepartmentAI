from copy import deepcopy
from datetime import date

from module2.data_quality import build_data_quality_report


def _report(records_by_category, category=None):
    return build_data_quality_report(
        records_by_category,
        category=category,
        limit=50,
        offset=0,
    )


def test_required_schema_values_and_persisted_inconsistencies_are_objective():
    report = _report(
        {
            "faculty": [
                {
                    "id": 1,
                    "full_name": " ",
                    "department": "Synthetic Department",
                    "profile_url": "https://example.invalid/1",
                    "source_name": "Synthetic source",
                }
            ],
            "publications": [
                {
                    "id": 2,
                    "title": "Synthetic paper",
                    "publication_type": "Journal",
                    "publication_date": date(2024, 2, 1),
                    "publication_year": 2023,
                }
            ],
            "projects": [
                {
                    "id": 3,
                    "title": "Synthetic project",
                    "start_date": date(2025, 1, 1),
                    "end_date": date(2024, 12, 31),
                }
            ],
            "achievements": [
                {
                    "id": 4,
                    "category": "",
                    "title": None,
                    "start_date": date(2025, 1, 1),
                    "end_date": date(2024, 12, 31),
                }
            ],
        }
    )

    issue_types = {
        (issue["category"], issue["issue_type"], issue["field"])
        for issue in report["issues"]
    }
    assert ("faculty", "missing_required_value", "full_name") in issue_types
    assert (
        "publications",
        "publication_year_mismatch",
        "publication_year",
    ) in issue_types
    assert ("projects", "date_range_inconsistent", "end_date") in issue_types
    assert ("achievements", "missing_required_value", "category") in issue_types
    assert ("achievements", "date_range_inconsistent", "end_date") in issue_types
    assert report["summary"]["objective_issues"] == 5


def test_duplicate_candidates_are_explainable_heuristics_and_read_only():
    records = [
        {
            "id": 11,
            "full_name": "Synthetic Faculty",
            "department": "Synthetic Department",
            "profile_url": "https://example.invalid/11",
            "source_name": "Synthetic source",
        },
        {
            "id": 12,
            "full_name": " synthetic   faculty ",
            "department": "synthetic department",
            "profile_url": "https://example.invalid/12",
            "source_name": "Synthetic source",
        },
    ]
    before = deepcopy(records)

    report = _report(
        {
            "faculty": records,
            "publications": [],
            "projects": [],
            "achievements": [],
        },
        category="faculty",
    )

    assert len(report["issues"]) == 1
    assert report["issues"][0]["issue_type"] == "possible_duplicate"
    assert report["issues"][0]["classification"] == "heuristic"
    assert report["issues"][0]["evidence"]["candidate_record_ids"] == [11, 12]
    assert report["issues"][0]["evidence"]["candidate_record_count"] == 2
    assert "potential duplicate" in report["issues"][0]["explanation"]
    assert records == before


def test_research_duplicate_suggestions_include_the_matching_record_evidence():
    report = _report(
        {
            "faculty": [],
            "publications": [
                {
                    "id": 51,
                    "title": "Synthetic paper",
                    "publication_type": "Journal",
                    "publication_date": date(2025, 1, 1),
                    "publication_year": None,
                },
                {
                    "id": 52,
                    "title": " synthetic   PAPER ",
                    "publication_type": "Conference",
                    "publication_date": date(2025, 8, 1),
                    "publication_year": None,
                },
            ],
            "projects": [
                {
                    "id": 53,
                    "title": "Synthetic project",
                    "funding_agency": "Research Council",
                },
                {
                    "id": 54,
                    "title": " synthetic project ",
                    "funding_agency": "research council",
                },
            ],
            "achievements": [
                {
                    "id": 55,
                    "title": "Synthetic award",
                    "category": "Prize",
                    "year": None,
                    "event_date": date(2025, 3, 1),
                },
                {
                    "id": 56,
                    "title": "synthetic award",
                    "category": "prize",
                    "year": None,
                    "event_date": date(2025, 4, 1),
                },
            ],
        }
    )

    duplicates = [
        issue
        for issue in report["issues"]
        if issue["issue_type"] == "possible_duplicate"
    ]
    assert len(duplicates) == 3
    publication_issue = next(
        issue for issue in duplicates if issue["category"] == "publications"
    )
    assert publication_issue["evidence"]["comparison_key"] == [
        "synthetic paper",
        2025,
    ]
    assert "publication_date year" in publication_issue["evidence"]["matching_rule"]
    assert len(publication_issue["evidence"]["candidate_values"]) == 2
    achievement_issue = next(
        issue for issue in duplicates if issue["category"] == "achievements"
    )
    assert "event_date year" in achievement_issue["evidence"]["matching_rule"]


def test_large_duplicate_group_keeps_evidence_payload_bounded():
    faculty_records = [
        {
            "id": index,
            "full_name": "Synthetic Faculty",
            "department": "Synthetic Department",
            "profile_url": f"https://example.invalid/{index}",
            "source_name": "Synthetic source",
        }
        for index in range(1, 151)
    ]

    report = _report(
        {
            "faculty": faculty_records,
            "publications": [],
            "projects": [],
            "achievements": [],
        },
        category="faculty",
    )

    evidence = report["issues"][0]["evidence"]
    assert len(report["issues"]) == 1
    assert evidence["candidate_record_count"] == 150
    assert len(evidence["candidate_record_ids"]) == 100
    assert evidence["candidate_record_ids_truncated"] is True
    assert len(evidence["candidate_values"]) == 20
    assert evidence["candidate_values_truncated"] is True


def test_empty_dataset_is_distinct_from_nonempty_dataset_with_no_issues():
    empty = _report(
        {
            "faculty": [],
            "publications": [],
            "projects": [],
            "achievements": [],
        }
    )
    clean = _report(
        {
            "faculty": [
                {
                    "id": 21,
                    "full_name": "Synthetic Faculty",
                    "department": "Synthetic Department",
                    "profile_url": "https://example.invalid/21",
                    "source_name": "Synthetic source",
                }
            ],
            "publications": [],
            "projects": [],
            "achievements": [],
        }
    )

    assert empty["summary"]["records_scanned"] == 0
    assert empty["summary"]["total_issues"] == 0
    assert clean["summary"]["records_scanned"] == 1
    assert clean["summary"]["total_issues"] == 0


def test_required_values_that_satisfy_schema_and_consistent_dates_are_not_flagged():
    report = _report(
        {
            "faculty": [
                {
                    "id": 31,
                    "full_name": "Synthetic Faculty",
                    "department": "Synthetic Department",
                    "profile_url": "https://example.invalid/31",
                    "source_name": "Synthetic source",
                }
            ],
            "publications": [
                {
                    "id": 32,
                    "title": "Synthetic paper",
                    "publication_type": "Journal",
                    "publication_date": date(2025, 2, 1),
                    "publication_year": 2025,
                }
            ],
            "projects": [
                {
                    "id": 33,
                    "title": "Synthetic project",
                    "start_date": date(2024, 1, 1),
                    "end_date": date(2025, 1, 1),
                }
            ],
            "achievements": [],
        }
    )

    assert report["issues"] == []


def test_category_selection_limits_the_review_and_pagination_is_bounded():
    report = build_data_quality_report(
        {
            "faculty": [
                {
                    "id": 41,
                    "full_name": "",
                    "department": "",
                    "profile_url": "",
                    "source_name": "",
                }
            ],
        },
        category="faculty",
        limit=2,
        offset=1,
    )

    assert report["summary"]["record_counts"] == {"faculty": 1}
    assert report["summary"]["total_issues"] == 4
    assert len(report["issues"]) == 2
    assert report["offset"] == 1
