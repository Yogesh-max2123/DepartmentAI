from dataclasses import dataclass
from typing import Protocol

from backend.academic_programmes import normalize_programme


IDENTITY_STATES = {
    "VERIFIED",
    "UNVERIFIED",
    "NOT_CONFIGURED",
    "UNAVAILABLE",
    "CONFLICT",
}


class ProgrammeIdentityUnavailableError(RuntimeError):
    pass


class ProgrammeIdentityConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProgrammeIdentity:
    status: str
    programme: str | None = None
    subject_identifier: str | None = None
    source_id: str | None = None
    source_version: str | None = None


class ProgrammeIdentityProvider(Protocol):
    def resolve(self, subject_identifier: str) -> ProgrammeIdentity:
        """Return programme identity obtained from an authoritative source."""


class UnconfiguredProgrammeIdentityProvider:
    def resolve(self, subject_identifier: str) -> ProgrammeIdentity:
        return ProgrammeIdentity(
            status="NOT_CONFIGURED",
            subject_identifier=subject_identifier,
        )


def resolve_programme_identity(subject_identifier, provider=None):
    active_provider = provider or UnconfiguredProgrammeIdentityProvider()
    try:
        identity = active_provider.resolve(subject_identifier)
    except ProgrammeIdentityUnavailableError:
        return ProgrammeIdentity(
            status="UNAVAILABLE",
            subject_identifier=subject_identifier,
        )
    except ProgrammeIdentityConflictError:
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )

    if not isinstance(identity, ProgrammeIdentity):
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )
    if identity.status not in IDENTITY_STATES:
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )
    if identity.subject_identifier != subject_identifier:
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )
    if identity.status != "VERIFIED":
        return ProgrammeIdentity(
            status=identity.status,
            subject_identifier=subject_identifier,
        )
    if (
        not identity.source_id
        or not identity.source_version
        or not identity.programme
    ):
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )
    try:
        programme = normalize_programme(identity.programme)
    except ValueError:
        return ProgrammeIdentity(
            status="CONFLICT",
            subject_identifier=subject_identifier,
        )
    return ProgrammeIdentity(
        status="VERIFIED",
        programme=programme,
        subject_identifier=subject_identifier,
        source_id=identity.source_id,
        source_version=identity.source_version,
    )
