import json

import backend.services.application_policy_registry as policy_registry
from backend.services.application_policy_registry import (
    DEFAULT_POLICY_REGISTRY,
    load_application_policy_registry,
    resolve_application_policy,
)
from backend.services.local_demo import (
    LOCAL_DEMO_SOURCE_FILE,
    LOCAL_DEMO_SOURCE_ID,
)
from backend.database import seed_local_demo
from backend.services.application_readiness_service import (
    _validate_retrieval_results,
)
from backend.services.programme_identity import (
    ProgrammeIdentity,
    ProgrammeIdentityConflictError,
    ProgrammeIdentityUnavailableError,
    resolve_programme_identity,
)


def _approved_test_policy():
    registry = json.loads(DEFAULT_POLICY_REGISTRY.read_text(encoding="utf-8"))
    registry["registry_version"] = "synthetic-test-policy-v1"
    registry["application_types"] = [
        {
            "application_type_id": "SYNTHETIC_UG_LEAVE",
            "display_title": "Synthetic UG leave request",
            "programme": "UG",
            "approval_status": "APPROVED",
            "activation_scope": "TEST_ONLY",
            "approval_evidence": "Synthetic test-only approval fixture.",
            "source_ids": ["UG_ORDINANCE_2023"],
            "required_documents": [
                {
                    "requirement_id": "supporting-document",
                    "description": "A supporting document",
                    "document_type": "SUPPORTING_DOCUMENT",
                    "condition": "ALWAYS",
                    "source_id": "UG_ORDINANCE_2023",
                    "citation": "Synthetic test citation; not operational.",
                    "section_numbers": ["1.6"],
                    "evidence": "Synthetic test evidence; not operational.",
                }
            ],
            "eligibility_rules": [],
            "processing_capabilities": ["pdf_text"],
        }
    ]
    return registry


def test_default_registry_has_approved_sources_but_no_active_application_types():
    registry = load_application_policy_registry()

    assert registry["status"] == "UNCONFIGURED"
    assert registry["application_types"] == []
    assert {source["programme"] for source in registry["sources"]} == {
        "UG",
        "MTECH",
        "PHD",
    }
    assert all(
        source["approval_status"] == "APPROVED"
        and source["source_version"] == "BOG-73.13(A)-2023-08-10"
        for source in registry["sources"]
    )
    assert resolve_application_policy(
        "Free text application",
        "UG",
        registry,
    )["status"] == "UNCONFIGURED"


def test_approved_policy_requires_an_exact_application_id_and_programme(
    tmp_path,
):
    registry_path = tmp_path / "policies.json"
    registry_path.write_text(
        json.dumps(_approved_test_policy()),
        encoding="utf-8",
    )
    registry = load_application_policy_registry(registry_path)
    assert registry["status"] == "AVAILABLE"

    resolved = resolve_application_policy(
        "SYNTHETIC_UG_LEAVE",
        "UG",
        registry,
    )
    assert resolved["status"] == "RESOLVED"
    assert resolved["application_type"]["required_documents"][0][
        "source_id"
    ] == "UG_ORDINANCE_2023"
    assert (
        resolve_application_policy(
            "Synthetic UG leave request",
            "UG",
            registry,
        )["status"]
        == "UNCONFIGURED"
    )
    assert (
        resolve_application_policy(
            "SYNTHETIC_UG_LEAVE",
            "PHD",
            registry,
        )["status"]
        == "CONFLICT"
    )


def test_synthetic_source_requires_explicit_test_demo_profile(
    tmp_path,
    monkeypatch,
):
    application, _ = seed_local_demo._build_policy_documents()
    synthetic_source = next(
        source
        for source in application["sources"]
        if source["source_id"] == LOCAL_DEMO_SOURCE_ID
    )
    application["sources"] = [synthetic_source]
    source_path = (
        tmp_path
        / ".local-demo"
        / "sources"
        / LOCAL_DEMO_SOURCE_FILE
    )
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(seed_local_demo.DEMO_RULES.encode("utf-8"))
    registry_path = tmp_path / "demo-policy.json"
    registry_path.write_text(json.dumps(application), encoding="utf-8")

    monkeypatch.setattr(policy_registry, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(policy_registry, "local_demo_enabled", lambda: True)
    monkeypatch.setenv("DEPARTMENTAI_DATABASE_ENV", "test")
    enabled = policy_registry.load_application_policy_registry(registry_path)
    assert enabled["status"] == "AVAILABLE"
    assert resolve_application_policy(
        "LOCAL_DEMO_MTECH",
        "MTECH",
        enabled,
    )["status"] == "RESOLVED"

    monkeypatch.setattr(policy_registry, "local_demo_enabled", lambda: False)
    disabled = policy_registry.load_application_policy_registry(registry_path)
    assert disabled["status"] == "CONFLICT"
    assert any(
        "explicit local test demo profile" in item["message"]
        for item in disabled["diagnostics"]
    )


def test_unapproved_or_conflicting_policy_cannot_be_resolved(tmp_path):
    document = _approved_test_policy()
    document["application_types"][0]["approval_status"] = "UNVERIFIED"
    registry_path = tmp_path / "unapproved.json"
    registry_path.write_text(json.dumps(document), encoding="utf-8")
    unapproved = load_application_policy_registry(registry_path)
    assert (
        resolve_application_policy(
            "SYNTHETIC_UG_LEAVE",
            "UG",
            unapproved,
        )["status"]
        == "UNVERIFIED"
    )

    document["application_types"].append(document["application_types"][0])
    conflict_path = tmp_path / "conflicting.json"
    conflict_path.write_text(json.dumps(document), encoding="utf-8")
    conflicted = load_application_policy_registry(conflict_path)
    assert conflicted["status"] == "CONFLICT"


def test_policy_requires_explicit_sections_for_rule_citations(tmp_path):
    document = _approved_test_policy()
    del document["application_types"][0]["required_documents"][0][
        "section_numbers"
    ]
    registry_path = tmp_path / "missing-rule-section.json"
    registry_path.write_text(json.dumps(document), encoding="utf-8")

    registry = load_application_policy_registry(registry_path)

    assert registry["status"] == "CONFLICT"
    assert any(
        "section_numbers must be a non-empty string array"
        in diagnostic["message"]
        for diagnostic in registry["diagnostics"]
    )


def test_policy_configuration_change_has_a_new_fingerprint(tmp_path):
    document = _approved_test_policy()
    first_path = tmp_path / "first.json"
    first_path.write_text(json.dumps(document), encoding="utf-8")
    first = load_application_policy_registry(first_path)
    document["registry_version"] = "synthetic-test-policy-v2"
    second_path = tmp_path / "second.json"
    second_path.write_text(json.dumps(document), encoding="utf-8")
    second = load_application_policy_registry(second_path)

    assert first["fingerprint"] != second["fingerprint"]


def test_identity_provider_states_are_validated_and_subject_bound():
    class VerifiedTestProvider:
        def resolve(self, subject_identifier):
            return ProgrammeIdentity(
                status="VERIFIED",
                programme="UG",
                subject_identifier=subject_identifier,
                source_id="synthetic-test-provider",
                source_version="synthetic-test-v1",
            )

    class UnavailableTestProvider:
        def resolve(self, subject_identifier):
            raise ProgrammeIdentityUnavailableError("test-only unavailable")

    class ConflictTestProvider:
        def resolve(self, subject_identifier):
            raise ProgrammeIdentityConflictError("test-only conflict")

    verified = resolve_programme_identity(
        "SYNTHETIC-STUDENT",
        VerifiedTestProvider(),
    )
    assert verified.status == "VERIFIED"
    assert verified.programme == "UG"

    assert (
        resolve_programme_identity(
            "SYNTHETIC-STUDENT",
            UnavailableTestProvider(),
        ).status
        == "UNAVAILABLE"
    )
    assert (
        resolve_programme_identity(
            "SYNTHETIC-STUDENT",
            ConflictTestProvider(),
        ).status
        == "CONFLICT"
    )
    assert (
        resolve_programme_identity("SYNTHETIC-STUDENT").status
        == "NOT_CONFIGURED"
    )
    mismatched = resolve_programme_identity(
        "SYNTHETIC-STUDENT",
        type(
            "MismatchedProvider",
            (),
            {
                "resolve": lambda _self, _subject: ProgrammeIdentity(
                    status="VERIFIED",
                    programme="UG",
                    subject_identifier="OTHER-STUDENT",
                    source_id="synthetic-test-provider",
                    source_version="synthetic-test-v1",
                )
            },
        )(),
    )
    assert mismatched.status == "CONFLICT"


def test_retrieval_requires_matching_versioned_source_metadata():
    policy_type = {
        "source_ids": ["UG_ORDINANCE_2023"],
        "required_documents": [
            {
                "source_id": "UG_ORDINANCE_2023",
                "section_numbers": ["1.6"],
            }
        ],
        "eligibility_rules": [],
    }
    sources = {
        "UG_ORDINANCE_2023": {
            "source_file": "UG Ordinance.pdf",
            "source_version": "BOG-73.13(A)-2023-08-10",
            "source_sha256": (
                "742f71b5ce832a7b4adf0372b7caf678eef52766fa239c1075ae334079adc90c"
            ),
        }
    }
    valid = [
        {
            "source_file": "UG Ordinance.pdf",
            "chunk_id": "ug-chunk-1",
            "chunk_text": "Source-backed test excerpt.",
            "source_id": "UG_ORDINANCE_2023",
            "source_version": "BOG-73.13(A)-2023-08-10",
            "source_sha256": (
                "742f71b5ce832a7b4adf0372b7caf678eef52766fa239c1075ae334079adc90c"
            ),
            "source_metadata_status": "VERIFIED",
            "section_number": "1.6",
            "page_start": 11,
            "page_end": 11,
        }
    ]
    evidence, source_ids, diagnostics = _validate_retrieval_results(
        policy_type,
        sources,
        valid,
    )
    assert diagnostics == []
    assert source_ids == {"UG_ORDINANCE_2023"}
    assert evidence[0]["source_version"] == "BOG-73.13(A)-2023-08-10"

    unrelated_section = [{**valid[0], "section_number": "9.9"}]
    _evidence, source_ids, diagnostics = _validate_retrieval_results(
        policy_type,
        sources,
        unrelated_section,
    )
    assert source_ids == {"UG_ORDINANCE_2023"}
    assert diagnostics[0]["code"] == (
        "AUTHORITATIVE_RULE_SECTION_NOT_RETRIEVED"
    )

    invalid = [
        {
            **valid[0],
            "source_file": "unrelated-draft.pdf",
        }
    ]
    _evidence, source_ids, diagnostics = _validate_retrieval_results(
        policy_type,
        sources,
        invalid,
    )
    assert source_ids == set()
    assert diagnostics[0]["code"] == "AUTHORITATIVE_SOURCE_METADATA_INVALID"
