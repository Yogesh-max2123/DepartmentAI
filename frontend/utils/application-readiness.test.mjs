import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { canSubmitApplication } from "./application-readiness.js";

const ready = {
  readiness_status: "READY",
  is_stale: false,
  application_version: "current-version",
  current_application_version: "current-version",
  required_documents: [],
  document_matches: [],
  deficiencies: [],
  deficiency_count: 0,
  blocking_conditions: [],
  programme_identity: {
    status: "VERIFIED",
    programme: "MTECH",
    source_id: "student-registry",
    source_version: "2026-01",
  },
  policy: {
    status: "RESOLVED",
    application_type_id: "approved-type",
    approval_status: "APPROVED",
  },
  rules: {
    status: "RESOLVED",
    provenance_verified: true,
    sources: [
      { source_id: "approved-policy", source_version: "2026-01" },
    ],
  },
  document_processing: [],
};

assert.equal(canSubmitApplication(ready), true);
assert.equal(
  canSubmitApplication({
    ...ready,
    required_documents: [
      { requirement_id: "transcript", source_id: "approved-policy" },
    ],
    document_matches: [
      {
        requirement_id: "transcript",
        document_id: 7,
        status: "PRESENT",
      },
    ],
    document_processing: [
      {
        document_id: 7,
        valid: true,
        classification_status: "CLASSIFIED",
        extraction_status: "COMPLETED",
      },
    ],
  }),
  true,
);
assert.equal(canSubmitApplication(null), false);
assert.equal(
  canSubmitApplication({ ...ready, readiness_status: "RULES_UNRESOLVED" }),
  false,
);
assert.equal(canSubmitApplication({ ...ready, is_stale: true }), false);
assert.equal(
  canSubmitApplication({ ...ready, current_application_version: "older" }),
  false,
);
assert.equal(canSubmitApplication({ ...ready, required_documents: null }), false);
assert.equal(
  canSubmitApplication({ ...ready, document_matches: [{ status: "PRESENT" }] }),
  false,
);
assert.equal(
  canSubmitApplication({ ...ready, deficiencies: [{ description: "Missing" }] }),
  false,
);
assert.equal(canSubmitApplication({ ...ready, deficiency_count: null }), false);
assert.equal(
  canSubmitApplication({
    ...ready,
    blocking_conditions: ["Rule scope unresolved"],
  }),
  false,
);
assert.equal(
  canSubmitApplication({
    ...ready,
    rules: { ...ready.rules, provenance_verified: false },
  }),
  false,
);
assert.equal(
  canSubmitApplication({ ...ready, programme_identity: undefined }),
  false,
);
assert.equal(
  canSubmitApplication({
    ...ready,
    programme_identity: { ...ready.programme_identity, status: "NOT_CONFIGURED" },
  }),
  false,
);
assert.equal(canSubmitApplication({ ...ready, policy: undefined }), false);
assert.equal(
  canSubmitApplication({
    ...ready,
    policy: { ...ready.policy, approval_status: "PENDING" },
  }),
  false,
);
assert.equal(
  canSubmitApplication({
    ...ready,
    rules: { ...ready.rules, sources: [{ source_id: "unversioned" }] },
  }),
  false,
);
assert.equal(
  canSubmitApplication({
    ...ready,
    document_processing: [
      {
        valid: true,
        classification_status: "NEEDS_REVIEW",
        extraction_status: "COMPLETED",
      },
    ],
  }),
  false,
);

const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
assert.equal(
  (appSource.match(/id="application-readiness-section"/g) || []).length,
  1,
);
assert.equal(
  (
    appSource.match(
      /<h2 id="application-readiness-title">AI-Assisted Analysis<\/h2>/g,
    ) || []
  ).length,
  1,
);
assert.doesNotMatch(appSource, /id="eligibility-analysis-title"/);
assert.doesNotMatch(appSource, /id="identified-deficiencies-title"/);
assert.ok(
  appSource.indexOf('id="application-readiness-section"') <
    appSource.indexOf('id="application-submit-controls"'),
);
assert.ok(
  appSource.indexOf('id="document-management-title"') <
    appSource.indexOf('id="application-readiness-section"'),
);
assert.ok(
  appSource.indexOf('id="application-readiness-section"') <
    appSource.indexOf("application-secondary-history"),
);
assert.ok(
  appSource.indexOf("application-secondary-history") <
    appSource.indexOf('id="application-submit-controls"'),
);

console.log("application readiness submission-gate tests passed");
