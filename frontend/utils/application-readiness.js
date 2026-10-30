export function canSubmitApplication(readiness) {
  const requiredDocuments = readiness?.required_documents;
  const documentMatches = readiness?.document_matches;
  const rules = readiness?.rules;
  const documentProcessing = readiness?.document_processing;
  const sources = rules?.sources;
  const identity = readiness?.programme_identity;
  const policy = readiness?.policy;
  const sourcesAreVerified =
    Array.isArray(sources) &&
    sources.length > 0 &&
    sources.every(
      (source) =>
        typeof source?.source_id === "string" &&
        source.source_id.trim().length > 0 &&
        typeof source.source_version === "string" &&
        source.source_version.trim().length > 0,
    );
  const sourceIds = new Set(
    sourcesAreVerified ? sources.map((source) => source.source_id) : [],
  );
  const requirementIds = new Set();
  const requirementsAreVerified =
    Array.isArray(requiredDocuments) &&
    requiredDocuments.every((requirement) => {
      if (
        !requirement ||
        typeof requirement.requirement_id !== "string" ||
        !requirement.requirement_id.trim() ||
        typeof requirement.source_id !== "string" ||
        !sourceIds.has(requirement.source_id) ||
        requirementIds.has(requirement.requirement_id)
      ) {
        return false;
      }
      requirementIds.add(requirement.requirement_id);
      return true;
    });
  const processedDocumentIds = Array.isArray(documentProcessing)
    ? new Set(
        documentProcessing
          .filter((document) => Number.isSafeInteger(document?.document_id))
          .map((document) => document.document_id),
      )
    : new Set();
  const matchesAreVerified =
    Array.isArray(documentMatches) &&
    requirementsAreVerified &&
    documentMatches.length === requiredDocuments.length &&
    documentMatches.every(
      (match) =>
        match &&
        typeof match.requirement_id === "string" &&
        requirementIds.has(match.requirement_id) &&
        Number.isSafeInteger(match.document_id) &&
        processedDocumentIds.has(match.document_id) &&
        ["MATCHED", "PRESENT", "SATISFIED"].includes(match.status),
    ) &&
    new Set(documentMatches.map((match) => match.requirement_id)).size ===
      requirementIds.size;

  return (
    readiness?.readiness_status === "READY" &&
    readiness.is_stale === false &&
    typeof readiness.application_version === "string" &&
    readiness.application_version.length > 0 &&
    readiness.current_application_version === readiness.application_version &&
    identity?.status === "VERIFIED" &&
    typeof identity.programme === "string" &&
    identity.programme.trim().length > 0 &&
    typeof identity.source_id === "string" &&
    identity.source_id.trim().length > 0 &&
    typeof identity.source_version === "string" &&
    identity.source_version.trim().length > 0 &&
    policy?.status === "RESOLVED" &&
    typeof policy.application_type_id === "string" &&
    policy.application_type_id.trim().length > 0 &&
    policy.approval_status === "APPROVED" &&
    sourcesAreVerified &&
    requirementsAreVerified &&
    matchesAreVerified &&
    Array.isArray(readiness.deficiencies) &&
    readiness.deficiencies.length === 0 &&
    readiness.deficiency_count === 0 &&
    Array.isArray(readiness.blocking_conditions) &&
    readiness.blocking_conditions.length === 0 &&
    rules?.status === "RESOLVED" &&
    rules.provenance_verified === true &&
    Array.isArray(documentProcessing) &&
    documentProcessing.every(
      (document) =>
        Number.isSafeInteger(document?.document_id) &&
        document?.valid === true &&
        document.classification_status === "CLASSIFIED" &&
        document.extraction_status === "COMPLETED",
    )
  );
}
