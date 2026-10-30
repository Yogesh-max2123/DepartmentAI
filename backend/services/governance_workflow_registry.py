import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKFLOW_REGISTRY = (
    PROJECT_ROOT / "backend" / "config" / "governance_workflows.json"
)
WORKFLOW_REGISTRY_ENV = "DEPARTMENTAI_GOVERNANCE_WORKFLOW_CONFIG"
SUPPORTED_COMMITTEES = {"DUGC", "DMPC", "DDPC"}
SUPPORTED_SCOPES = {"INSTITUTIONAL", "TEST_ONLY"}


def _unavailable(message):
    return {
        "status": "UNAVAILABLE",
        "registry_version": None,
        "committee_policies": [],
        "diagnostics": [message],
    }


def _validate(document):
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return _unavailable("Workflow registry schema_version must equal 1.")
    version = document.get("registry_version")
    policies = document.get("committee_policies")
    if not isinstance(version, str) or not version.strip():
        return _unavailable("Workflow registry_version is required.")
    if not isinstance(policies, list):
        return _unavailable("committee_policies must be an array.")

    normalized = []
    seen = set()
    errors = []
    for index, policy in enumerate(policies):
        location = f"committee_policies[{index}]"
        if not isinstance(policy, dict):
            errors.append(f"{location} must be an object.")
            continue
        committee = policy.get("committee_type")
        status = policy.get("approval_status")
        scope = policy.get("activation_scope")
        evidence = policy.get("approval_evidence")
        confirmations = policy.get("minimum_confirmations")
        meeting_approvers = policy.get("meeting_approver_usernames")
        minutes_approvers = policy.get("minutes_approver_usernames")
        index_final = policy.get("index_finalized_minutes")
        if committee not in SUPPORTED_COMMITTEES or committee in seen:
            errors.append(f"{location}.committee_type is invalid or duplicated.")
        if status != "APPROVED":
            errors.append(f"{location}.approval_status must be APPROVED.")
        if scope not in SUPPORTED_SCOPES:
            errors.append(f"{location}.activation_scope is invalid.")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"{location}.approval_evidence is required.")
        if (
            not isinstance(confirmations, int)
            or isinstance(confirmations, bool)
            or confirmations < 1
        ):
            errors.append(f"{location}.minimum_confirmations must be positive.")
        for field, names in (
            ("meeting_approver_usernames", meeting_approvers),
            ("minutes_approver_usernames", minutes_approvers),
        ):
            if not isinstance(names, list) or any(
                not isinstance(name, str) or not name.strip()
                for name in names
            ):
                errors.append(f"{location}.{field} must be a string array.")
            elif len(
                {name.strip().lower() for name in names}
            ) != len(names):
                errors.append(f"{location}.{field} cannot contain duplicates.")
        if not isinstance(index_final, bool):
            errors.append(
                f"{location}.index_finalized_minutes must be a boolean."
            )
        if committee in SUPPORTED_COMMITTEES:
            seen.add(committee)
            normalized.append(
                {
                    **policy,
                    "committee_type": committee,
                    "meeting_approver_usernames": [
                        name.strip().lower()
                        for name in meeting_approvers
                        if isinstance(name, str) and name.strip()
                    ] if isinstance(meeting_approvers, list) else [],
                    "minutes_approver_usernames": [
                        name.strip().lower()
                        for name in minutes_approvers
                        if isinstance(name, str) and name.strip()
                    ] if isinstance(minutes_approvers, list) else [],
                }
            )
    if errors:
        result = _unavailable("; ".join(errors))
        result["registry_version"] = version.strip()
        return result
    return {
        "status": "AVAILABLE" if normalized else "UNCONFIGURED",
        "registry_version": version.strip(),
        "committee_policies": normalized,
        "diagnostics": [],
    }


def load_governance_workflow_registry(path=None):
    configured = path or os.environ.get(
        WORKFLOW_REGISTRY_ENV,
        str(DEFAULT_WORKFLOW_REGISTRY),
    )
    try:
        payload = Path(configured).read_text(encoding="utf-8")
    except OSError:
        return _unavailable("The workflow registry could not be read.")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError:
        return _unavailable("The workflow registry is not valid JSON.")
    return _validate(document)


def get_committee_workflow_policy(committee_type, registry=None):
    active = registry or load_governance_workflow_registry()
    if active["status"] in {"UNAVAILABLE"}:
        return None
    for policy in active["committee_policies"]:
        if policy["committee_type"] == committee_type:
            if (
                policy["activation_scope"] == "TEST_ONLY"
                and os.environ.get("DEPARTMENTAI_DATABASE_ENV") != "test"
            ):
                return None
            return policy
    return None
