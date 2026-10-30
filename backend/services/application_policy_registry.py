import hashlib
import json
import os
from pathlib import Path

from backend.academic_programmes import get_programme_corpus
from backend.services.local_demo import (
    LOCAL_DEMO_SOURCE_FILE,
    LOCAL_DEMO_SOURCE_ID,
    local_demo_enabled,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_REGISTRY = (
    PROJECT_ROOT / "backend" / "config" / "application_policies.json"
)
POLICY_REGISTRY_ENV = "DEPARTMENTAI_APPLICATION_POLICY_CONFIG"
SUPPORTED_PROGRAMMES = {"UG", "MTECH", "PHD"}
SUPPORTED_PROCESSORS = {"pdf_text"}
APPROVAL_STATES = {"APPROVED", "UNVERIFIED"}
CONFIGURATION_SCOPES = {"INSTITUTIONAL", "TEST_ONLY"}


def _unavailable_registry(diagnostic, fingerprint=""):
    return {
        "status": "UNAVAILABLE",
        "registry_version": None,
        "fingerprint": fingerprint,
        "sources": [],
        "application_types": [],
        "diagnostics": [diagnostic],
    }


def _required_string(value, field, location, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{location}.{field} must be a non-empty string.")
        return None
    return value.strip()


def _validate_registry(document, fingerprint):
    errors = []
    if not isinstance(document, dict):
        return _unavailable_registry(
            "The application policy registry must be a JSON object.",
            fingerprint,
        )
    if document.get("schema_version") != 1:
        errors.append("schema_version must equal 1.")
    registry_version = _required_string(
        document.get("registry_version"),
        "registry_version",
        "registry",
        errors,
    )
    sources = document.get("sources")
    application_types = document.get("application_types")
    if not isinstance(sources, list):
        errors.append("sources must be an array.")
        sources = []
    if not isinstance(application_types, list):
        errors.append("application_types must be an array.")
        application_types = []

    source_by_id = {}
    for index, source in enumerate(sources):
        location = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{location} must be an object.")
            continue
        source_id = _required_string(
            source.get("source_id"), "source_id", location, errors
        )
        programme = source.get("programme")
        if programme not in SUPPORTED_PROGRAMMES:
            errors.append(
                f"{location}.programme must be one of "
                f"{', '.join(sorted(SUPPORTED_PROGRAMMES))}."
            )
        source_file = _required_string(
            source.get("source_file"), "source_file", location, errors
        )
        source_version = _required_string(
            source.get("source_version"), "source_version", location, errors
        )
        source_sha256 = _required_string(
            source.get("source_sha256"), "source_sha256", location, errors
        )
        approval_status = source.get("approval_status")
        if approval_status not in APPROVAL_STATES:
            errors.append(
                f"{location}.approval_status must be APPROVED or UNVERIFIED."
            )
        if approval_status == "APPROVED":
            _required_string(
                source.get("approval_evidence"),
                "approval_evidence",
                location,
                errors,
            )
        if source_id:
            if source_id in source_by_id:
                errors.append(f"Duplicate source_id {source_id!r}.")
            if source_id == LOCAL_DEMO_SOURCE_ID:
                if (
                    programme != "MTECH"
                    or source_file != LOCAL_DEMO_SOURCE_FILE
                    or source.get("activation_scope") != "TEST_ONLY"
                    or approval_status != "APPROVED"
                ):
                    errors.append(
                        f"{location} does not match the fixed TEST_ONLY "
                        "local demo source definition."
                    )
                try:
                    demo_is_enabled = local_demo_enabled()
                except (RuntimeError, ValueError):
                    demo_is_enabled = False
                if not demo_is_enabled:
                    errors.append(
                        f"{location} is available only in the explicit "
                        "local test demo profile."
                    )
                synthetic_source_path = (
                    PROJECT_ROOT
                    / ".local-demo"
                    / "sources"
                    / LOCAL_DEMO_SOURCE_FILE
                )
                try:
                    actual_hash = hashlib.sha256(
                        synthetic_source_path.read_bytes()
                    ).hexdigest()
                except OSError:
                    errors.append(
                        f"{location} synthetic local demo source is unavailable."
                    )
                else:
                    if (
                        source_sha256
                        and actual_hash != source_sha256.lower()
                    ):
                        errors.append(
                            f"{location} synthetic source hash does not "
                            "match the configured version."
                        )
            elif programme in SUPPORTED_PROGRAMMES and source_file:
                corpus = get_programme_corpus(programme)
                if source_file != corpus["source_file"]:
                    errors.append(
                        f"{location}.source_file does not match the "
                        "registered programme corpus."
                    )
                else:
                    source_path = (
                        PROJECT_ROOT / "documents" / programme.lower()
                        / source_file
                    )
                    try:
                        actual_hash = hashlib.sha256(
                            source_path.read_bytes()
                        ).hexdigest()
                    except OSError:
                        errors.append(
                            f"{location} source file is unavailable."
                        )
                    else:
                        if (
                            source_sha256
                            and actual_hash != source_sha256.lower()
                        ):
                            errors.append(
                                f"{location} source file hash does not match "
                                "the configured version."
                            )
            source_by_id[source_id] = {
                **source,
                "programme": programme,
                "source_file": source_file,
                "source_version": source_version,
                "source_sha256": source_sha256,
            }

    type_ids = set()
    normalized_types = []
    for index, item in enumerate(application_types):
        location = f"application_types[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} must be an object.")
            continue
        type_id = _required_string(
            item.get("application_type_id"),
            "application_type_id",
            location,
            errors,
        )
        display_title = _required_string(
            item.get("display_title"), "display_title", location, errors
        )
        programme = item.get("programme")
        if programme not in SUPPORTED_PROGRAMMES:
            errors.append(
                f"{location}.programme must be one of "
                f"{', '.join(sorted(SUPPORTED_PROGRAMMES))}."
            )
        approval_status = item.get("approval_status")
        if approval_status not in APPROVAL_STATES:
            errors.append(
                f"{location}.approval_status must be APPROVED or UNVERIFIED."
            )
        if approval_status == "APPROVED":
            _required_string(
                item.get("approval_evidence"),
                "approval_evidence",
                location,
                errors,
            )
        activation_scope = item.get("activation_scope")
        if activation_scope not in CONFIGURATION_SCOPES:
            errors.append(
                f"{location}.activation_scope must be INSTITUTIONAL or "
                "TEST_ONLY."
            )
        source_ids = item.get("source_ids")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or any(not isinstance(value, str) or not value for value in source_ids)
        ):
            errors.append(f"{location}.source_ids must be a non-empty string array.")
            source_ids = []
        for source_id in source_ids:
            source = source_by_id.get(source_id)
            if source is None:
                errors.append(
                    f"{location} references unknown source {source_id!r}."
                )
            elif source["programme"] != programme:
                errors.append(
                    f"{location} references a source from another programme."
                )
            elif approval_status == "APPROVED" and source[
                "approval_status"
            ] != "APPROVED":
                errors.append(
                    f"{location} uses source {source_id!r} without approval."
                )
        requirements = item.get("required_documents")
        if not isinstance(requirements, list):
            errors.append(f"{location}.required_documents must be an array.")
            requirements = []
        requirement_ids = set()
        for rule_index, rule in enumerate(requirements):
            rule_location = f"{location}.required_documents[{rule_index}]"
            if not isinstance(rule, dict):
                errors.append(f"{rule_location} must be an object.")
                continue
            requirement_id = _required_string(
                rule.get("requirement_id"),
                "requirement_id",
                rule_location,
                errors,
            )
            for field in (
                "description",
                "document_type",
                "citation",
                "evidence",
            ):
                _required_string(rule.get(field), field, rule_location, errors)
            condition = _required_string(
                rule.get("condition"),
                "condition",
                rule_location,
                errors,
            )
            if condition and condition != "ALWAYS":
                errors.append(
                    f"{rule_location}.condition is not supported; only "
                    "ALWAYS may be activated."
                )
            section_numbers = rule.get("section_numbers")
            if (
                not isinstance(section_numbers, list)
                or not section_numbers
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in section_numbers
                )
            ):
                errors.append(
                    f"{rule_location}.section_numbers must be a non-empty "
                    "string array."
                )
            if requirement_id in requirement_ids:
                errors.append(
                    f"{location} has duplicate requirement_id "
                    f"{requirement_id!r}."
                )
            if requirement_id:
                requirement_ids.add(requirement_id)
            if rule.get("source_id") not in source_ids:
                errors.append(
                    f"{rule_location}.source_id must reference one of "
                    f"{location}.source_ids."
                )
        eligibility_rules = item.get("eligibility_rules")
        if not isinstance(eligibility_rules, list):
            errors.append(f"{location}.eligibility_rules must be an array.")
            eligibility_rules = []
        for rule_index, rule in enumerate(eligibility_rules):
            rule_location = f"{location}.eligibility_rules[{rule_index}]"
            if not isinstance(rule, dict):
                errors.append(f"{rule_location} must be an object.")
                continue
            for field in (
                "rule_id",
                "description",
                "condition",
                "citation",
                "evidence",
            ):
                _required_string(rule.get(field), field, rule_location, errors)
            section_numbers = rule.get("section_numbers")
            if (
                not isinstance(section_numbers, list)
                or not section_numbers
                or any(
                    not isinstance(value, str) or not value.strip()
                    for value in section_numbers
                )
            ):
                errors.append(
                    f"{rule_location}.section_numbers must be a non-empty "
                    "string array."
                )
            if rule.get("source_id") not in source_ids:
                errors.append(
                    f"{rule_location}.source_id must reference one of "
                    f"{location}.source_ids."
                )
        processing = item.get("processing_capabilities")
        if (
            not isinstance(processing, list)
            or any(value not in SUPPORTED_PROCESSORS for value in processing)
        ):
            errors.append(
                f"{location}.processing_capabilities contains an unsupported "
                "processor."
            )

        if type_id:
            if type_id in type_ids:
                errors.append(f"Duplicate application_type_id {type_id!r}.")
            type_ids.add(type_id)
        normalized_types.append(
            {
                **item,
                "application_type_id": type_id,
                "display_title": display_title,
                "programme": programme,
                "activation_scope": activation_scope,
                "source_ids": source_ids,
                "required_documents": requirements,
                "eligibility_rules": eligibility_rules,
            }
        )

    if errors:
        return {
            "status": "CONFLICT",
            "registry_version": registry_version,
            "fingerprint": fingerprint,
            "sources": list(source_by_id.values()),
            "application_types": normalized_types,
            "diagnostics": [
                {"code": "POLICY_REGISTRY_INVALID", "message": message}
                for message in errors
            ],
        }

    has_approved_type = any(
        item["approval_status"] == "APPROVED" for item in normalized_types
    )
    return {
        "status": "AVAILABLE" if has_approved_type else "UNCONFIGURED",
        "registry_version": registry_version,
        "fingerprint": fingerprint,
        "sources": list(source_by_id.values()),
        "application_types": normalized_types,
        "diagnostics": [],
    }


def load_application_policy_registry(path=None):
    configured_path = path or os.environ.get(
        POLICY_REGISTRY_ENV,
        str(DEFAULT_POLICY_REGISTRY),
    )
    registry_path = Path(configured_path)
    try:
        content = registry_path.read_bytes()
    except OSError:
        return _unavailable_registry(
            "The configured application policy registry could not be read."
        )

    fingerprint = hashlib.sha256(content).hexdigest()
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _unavailable_registry(
            "The configured application policy registry is not valid UTF-8 JSON.",
            fingerprint,
        )
    return _validate_registry(document, fingerprint)


def resolve_application_policy(application_type, programme, registry=None):
    active_registry = registry or load_application_policy_registry()
    if active_registry["status"] in {"UNAVAILABLE", "CONFLICT"}:
        return {
            "status": active_registry["status"],
            "application_type": None,
            "diagnostics": active_registry["diagnostics"],
        }
    matches = [
        item
        for item in active_registry["application_types"]
        if item["application_type_id"] == application_type
    ]
    if len(matches) > 1:
        return {
            "status": "CONFLICT",
            "application_type": None,
            "diagnostics": [
                {
                    "code": "APPLICATION_TYPE_MAPPING_CONFLICT",
                    "message": "More than one policy maps to this application type.",
                }
            ],
        }
    if not matches:
        return {
            "status": "UNCONFIGURED",
            "application_type": None,
            "diagnostics": [
                {
                    "code": "APPLICATION_TYPE_MAPPING_MISSING",
                    "message": (
                        "No approved application-type-to-policy mapping is "
                        "configured. Supply an institutionally approved "
                        "mapping with required documents, citations, and "
                        "approval evidence."
                    ),
                }
            ],
        }
    policy = matches[0]
    if policy["approval_status"] != "APPROVED":
        return {
            "status": "UNVERIFIED",
            "application_type": policy,
            "diagnostics": [
                {
                    "code": "APPLICATION_TYPE_MAPPING_UNAPPROVED",
                    "message": (
                        "This application-type mapping is not approved for "
                        "operational use."
                    ),
                }
            ],
        }
    if (
        policy["activation_scope"] == "TEST_ONLY"
        and os.environ.get("DEPARTMENTAI_DATABASE_ENV") != "test"
    ):
        return {
            "status": "UNVERIFIED",
            "application_type": policy,
            "diagnostics": [
                {
                    "code": "TEST_POLICY_OUTSIDE_TEST_PROFILE",
                    "message": (
                        "A test-only application policy cannot be used "
                        "outside the isolated test database profile."
                    ),
                }
            ],
        }
    if policy["programme"] != programme:
        return {
            "status": "CONFLICT",
            "application_type": None,
            "diagnostics": [
                {
                    "code": "APPLICATION_TYPE_PROGRAMME_CONFLICT",
                    "message": (
                        "The verified programme does not match the approved "
                        "application-type mapping."
                    ),
                }
            ],
        }
    return {
        "status": "RESOLVED",
        "application_type": policy,
        "diagnostics": [],
    }
