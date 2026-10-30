import assert from "node:assert/strict";

import {
  getGovernanceActionAvailability,
  renderGovernanceWorkspace,
} from "./governance-workspace.js";

const api = await import(
  `file://${process.cwd()}/frontend/services/api.js?governance-workspace-test`
);

const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({
    url: String(url),
    method: options.method || "GET",
    headers: options.headers || {},
    body: options.body ? JSON.parse(options.body) : null,
  });
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => ({ status: "OK" }),
  };
};

await api.createGovernanceMeeting(
  { committee_type: "DDPC", title: "Synthetic meeting" },
  "test-idempotency-key",
);
await api.getGovernanceCandidateSlots({
  committeeType: "DDPC",
  rangeStart: "2026-10-30T09:00:00Z",
  rangeEnd: "2026-10-30T11:00:00Z",
  durationMinutes: 60,
  excludeMeetingId: 12,
});
await api.updateGovernanceMeetingAgenda(12, [
  { title: "Review", description: "", application_ids: [] },
]);
await api.createManualGovernanceMinutes(12);
await api.saveGovernanceMinutes(12, 4, { sections: [] });
await api.getApplicationGovernanceMeetings(18);
await api.approveApplicationGovernanceMeeting(18, 12);
await api.respondToApplicationGovernanceMeeting(18, 12, "CONFIRMED");

assert.equal(requests[0].method, "POST");
assert.equal(requests[0].url, "http://127.0.0.1:8000/governance/meetings");
assert.equal(
  requests[0].headers["Idempotency-Key"],
  "test-idempotency-key",
);
assert.match(requests[1].url, /exclude_meeting_id=12/);
assert.equal(requests[2].method, "PATCH");
assert.equal(requests[3].url, "http://127.0.0.1:8000/governance/meetings/12/minutes");
assert.equal(
  requests[4].url,
  "http://127.0.0.1:8000/governance/meetings/12/minutes/4",
);
assert.equal(
  requests[5].url,
  "http://127.0.0.1:8000/governance/applications/18/meetings",
);
assert.equal(
  requests[6].url,
  "http://127.0.0.1:8000/governance/applications/18/meetings/12/approve",
);
assert.equal(
  requests[7].body.response,
  "CONFIRMED",
);

const markup = renderGovernanceWorkspace();
for (const requiredAction of [
  'data-action="create-meeting"',
  'data-action="availability"',
  'data-action="search-slots"',
  'data-action="save-agenda"',
  'data-action="create-manual-minutes"',
  'data-action="generate-minutes"',
  'data-action="approve-minutes"',
]) {
  assert.ok(markup.includes(requiredAction), `Missing UI action ${requiredAction}`);
}
assert.ok(markup.includes("Calendar and timetable checks"));
assert.ok(markup.includes("not configured"));
assert.ok(markup.includes("human review"));
assert.match(markup, /data-action="approve-minutes" hidden/);
const officialMarkup = renderGovernanceWorkspace("OFFICIAL");
assert.match(officialMarkup, /Schedule committee meetings/);
assert.match(officialMarkup, /Assigned application IDs \(required/);
assert.doesNotMatch(officialMarkup, /data-action="availability"/);
assert.doesNotMatch(officialMarkup, /data-action="approve-meeting"/);

const proposedMeeting = {
  status: "PROPOSED",
  proposed_slot_start: "2026-10-30T09:00:00Z",
  workflow_policy: {
    meeting_approver_usernames: ["governance-approver"],
  },
};
const emptyMinutes = {
  meeting: {
    workflow_policy: {
      minutes_approver_usernames: ["governance-approver"],
    },
  },
  versions: [],
  latest_version: null,
  records: [],
  review_issues: [],
  finalization_configured: false,
};
const disabledIntegrations = {
  minutes_generation: { status: "APPROVAL_REQUIRED" },
};
const proposedControls = getGovernanceActionAvailability(
  proposedMeeting,
  emptyMinutes,
  disabledIntegrations,
  "governance-approver",
);
assert.equal(proposedControls.canRequestMeetingApproval, true);
assert.equal(proposedControls.canAddMeetingRecords, false);
assert.equal(proposedControls.canCreateMinutes, false);
assert.equal(proposedControls.canGenerateMinutes, false);

const confirmedMeeting = {
  ...proposedMeeting,
  status: "CONFIRMED",
  agenda: [{ index: 0, title: "Review" }],
  confirmations: [],
};
const completeMinutes = {
  ...emptyMinutes,
  meeting: {
    workflow_policy: {
      minutes_approver_usernames: ["governance-approver"],
    },
  },
  finalization_configured: true,
  records: [
    { record_type: "ATTENDANCE", agenda_item_index: null },
    { record_type: "NOTE", agenda_item_index: 0 },
    { record_type: "OBSERVATION", agenda_item_index: 0 },
    { record_type: "DECISION", agenda_item_index: 0 },
  ],
  review_issues: [],
  versions: [{ id: 2, version_number: 1, status: "SUBMITTED" }],
  latest_version: { id: 2, version_number: 1, status: "SUBMITTED" },
};
const confirmedControls = getGovernanceActionAvailability(
  confirmedMeeting,
  completeMinutes,
  {
    minutes_generation: {
      status: "APPROVAL_ENABLED_PROVIDER_NOT_HEALTH_CHECKED",
    },
  },
  "governance-approver",
);
assert.equal(confirmedControls.canAddMeetingRecords, true);
assert.equal(confirmedControls.canCreateMinutes, true);
assert.equal(confirmedControls.canGenerateMinutes, true);
assert.equal(confirmedControls.canSubmitMinutes, false);
assert.equal(confirmedControls.canCommentOnMinutes, true);
assert.equal(confirmedControls.canApproveMinutes, true);
assert.equal(
  getGovernanceActionAvailability(
    confirmedMeeting,
    completeMinutes,
    disabledIntegrations,
    "not-a-signatory",
  ).canApproveMinutes,
  false,
);
assert.equal(
  getGovernanceActionAvailability(
    { ...proposedMeeting, status: "APPROVED_PENDING_CONFIRMATIONS" },
    emptyMinutes,
    disabledIntegrations,
    "governance-approver",
  ).canRespondToMeeting,
  true,
);

console.log("governance workspace tests passed: API contract and workflow controls render");
