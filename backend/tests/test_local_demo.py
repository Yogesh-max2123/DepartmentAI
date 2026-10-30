from types import SimpleNamespace

import pytest

import backend.services.local_demo as local_demo
from backend.database import seed_local_demo


def test_local_demo_identity_is_limited_to_synthetic_student():
    provider = local_demo.LocalDemoProgrammeIdentityProvider()

    identity = provider.resolve(local_demo.LOCAL_DEMO_STUDENT_IDENTIFIER)
    other_identity = provider.resolve("REAL-STUDENT-IDENTIFIER")

    assert identity.status == "VERIFIED"
    assert identity.programme == "MTECH"
    assert identity.source_id == local_demo.LOCAL_DEMO_IDENTITY_SOURCE
    assert other_identity.status == "NOT_CONFIGURED"


def test_local_demo_flag_is_opt_in(monkeypatch):
    monkeypatch.delenv(local_demo.LOCAL_DEMO_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setattr(
        local_demo,
        "get_database_settings",
        lambda: pytest.fail("Database settings should not be read when disabled."),
    )

    assert local_demo.local_demo_enabled() is False


def test_local_demo_flag_rejects_non_test_database(monkeypatch):
    monkeypatch.setenv(local_demo.LOCAL_DEMO_ENVIRONMENT_VARIABLE, "1")
    monkeypatch.setattr(
        local_demo,
        "get_database_settings",
        lambda: SimpleNamespace(
            environment="development",
            database="departmentai_dev",
        ),
    )

    with pytest.raises(RuntimeError, match="isolated test database"):
        local_demo.local_demo_enabled()


def test_local_demo_flag_rejects_non_loopback_test_database(monkeypatch):
    monkeypatch.setenv(local_demo.LOCAL_DEMO_ENVIRONMENT_VARIABLE, "1")
    monkeypatch.setattr(
        local_demo,
        "get_database_settings",
        lambda: SimpleNamespace(
            environment="test",
            database="departmentai_test",
            host="192.0.2.10",
        ),
    )

    with pytest.raises(RuntimeError, match="loopback"):
        local_demo.local_demo_enabled()


@pytest.mark.parametrize(
    ("environment", "database", "host"),
    [
        ("development", "departmentai_dev", "127.0.0.1"),
        ("test", "departmentai_test", "192.0.2.10"),
        ("test", "departmentai_dev", "127.0.0.1"),
    ],
)
def test_seeder_rejects_noncanonical_database_targets(
    environment,
    database,
    host,
):
    with pytest.raises(RuntimeError):
        seed_local_demo._validate_profile(
            SimpleNamespace(
                environment=environment,
                database=database,
                host=host,
            )
        )


def test_generated_policies_are_test_only_and_explicitly_synthetic():
    application, workflow = seed_local_demo._build_policy_documents()
    demo_application = application["application_types"][0]

    assert (
        demo_application["activation_scope"] == "TEST_ONLY"
    )
    assert "not institutional approval" in (
        demo_application["approval_evidence"]
    )
    assert demo_application["source_ids"] == [
        local_demo.LOCAL_DEMO_SOURCE_ID
    ]
    assert {
        requirement["document_type"]
        for requirement in demo_application["required_documents"]
    } == {"APPLICATION_FORM", "MARKSHEET"}
    demo_source = next(
        source
        for source in application["sources"]
        if source["source_id"] == local_demo.LOCAL_DEMO_SOURCE_ID
    )
    assert demo_source["activation_scope"] == "TEST_ONLY"
    assert demo_source["source_sha256"] == seed_local_demo.hashlib.sha256(
        seed_local_demo.DEMO_RULES.encode("utf-8")
    ).hexdigest()
    assert (
        workflow["committee_policies"][0]["activation_scope"]
        == "TEST_ONLY"
    )
    assert (
        workflow["committee_policies"][0]["minimum_confirmations"] == 2
    )
