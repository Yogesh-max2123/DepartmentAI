import {
  addGovernanceMeetingRecord,
  approveGovernanceMeeting,
  approveGovernanceMinutes,
  commentOnGovernanceMinutes,
  createManualGovernanceMinutes,
  createGovernanceMeeting,
  generateGovernanceMinutes,
  getGovernanceCandidateSlots,
  getGovernanceConfiguration,
  getGovernanceIntegrations,
  getGovernanceMeeting,
  getGovernanceMeetingNotice,
  getGovernanceMinutes,
  listGovernanceMeetings,
  respondToGovernanceMeeting,
  saveGovernanceMinutes,
  selectGovernanceMeetingSlot,
  submitGovernanceAvailability,
  submitGovernanceMinutes,
  updateGovernanceMeetingAgenda,
} from "../services/api.js";

export function renderGovernanceWorkspace(role = "DUGC") {
  const isOfficial = role === "OFFICIAL";
  return `
    <section class="page-section governance-workspace" aria-labelledby="governance-title">
      <header class="page-heading">
        <div>
          <span class="eyebrow">${isOfficial ? "Official Workspace" : "DUGC Workspace"}</span>
          <h1 id="governance-title">${isOfficial ? "Schedule committee meetings" : "Meeting governance"}</h1>
          <p>${isOfficial ? "Propose meetings only for applications assigned to your account and the committee assigned to those applications." : "Schedule with recorded committee availability, maintain meeting records, and review versioned minutes."}</p>
        </div>
      </header>
      <div class="role-workspace-notice" role="note">
        ${isOfficial ? "Candidate slots use only explicit availability submitted by committee members. Approval, confirmations, notices, and final sign-off remain separately policy-gated." : "Calendar and timetable checks, email or WhatsApp notices, and finalized-minutes indexing are not configured. Candidate slots use only committee members' explicit availability."}
      </div>
      <p id="governance-message" role="status" aria-live="polite"></p>
      <section class="content-panel">
        <h2>Committee</h2>
        <label for="governance-committee">${isOfficial ? "Committee assigned to your application" : "Accessible committee"}</label>
        <select id="governance-committee"></select>
        <button type="button" class="secondary-button" data-action="refresh">Refresh</button>
        ${isOfficial ? "" : '<h3>Integration status</h3><pre id="governance-integrations" class="role-review-data"></pre>'}
      </section>
      <section class="content-panel">
        <h2>Create a meeting proposal</h2>
        <form data-action="create-meeting" class="governance-form">
          <label>Title <input name="title" maxlength="160" required /></label>
          <label>Purpose <textarea name="purpose" maxlength="2000" required></textarea></label>
          <label>Search range starts <input name="proposed_start" type="datetime-local" required /></label>
          <label>Search range ends <input name="proposed_end" type="datetime-local" required /></label>
          <label>Duration in minutes <input name="duration_minutes" type="number" min="30" max="240" step="30" value="60" required /></label>
          <label>First agenda item <input name="agenda_title" maxlength="160" required /></label>
          <label>Agenda description <textarea name="agenda_description" maxlength="2000"></textarea></label>
          <label>${isOfficial ? "Assigned application IDs (required, comma-separated)" : "Assigned application IDs (optional, comma-separated)"} <input name="application_ids" inputmode="numeric" ${isOfficial ? "required" : ""} /></label>
          <button type="submit" class="primary-button">Create proposal</button>
        </form>
      </section>
      ${isOfficial ? "" : `
        <section class="content-panel">
          <h2>Submit availability</h2>
          <form data-action="availability" class="governance-form">
            <label>Available from <input name="available_from" type="datetime-local" required /></label>
            <label>Available until <input name="available_until" type="datetime-local" required /></label>
            <label>Availability
              <select name="availability">
                <option value="AVAILABLE">Available</option>
                <option value="UNAVAILABLE">Unavailable</option>
              </select>
            </label>
            <button type="submit" class="secondary-button">Save my availability</button>
          </form>
        </section>
      `}
      <section class="content-panel">
        <h2>Candidate slots</h2>
        <form data-action="search-slots" class="governance-form">
          <label>Range starts <input name="range_start" type="datetime-local" required /></label>
          <label>Range ends <input name="range_end" type="datetime-local" required /></label>
          <label>Duration in minutes <input name="duration_minutes" type="number" min="30" max="240" step="30" value="60" required /></label>
          <button type="submit" class="secondary-button">Find candidates</button>
        </form>
        <div id="governance-slots" aria-live="polite"></div>
      </section>
      <section class="content-panel">
        <h2>Committee meetings</h2>
        <div id="governance-meeting-list" aria-live="polite"></div>
      </section>
      <section id="governance-selected" class="content-panel" hidden>
        <h2>Selected meeting</h2>
        <div class="governance-actions">
          ${isOfficial ? "" : `
            <button type="button" class="secondary-button" data-action="approve-meeting" hidden>Request approval</button>
            <button type="button" class="secondary-button" data-action="respond-confirmed" hidden>Confirm attendance</button>
            <button type="button" class="secondary-button" data-action="respond-declined" hidden>Decline attendance</button>
          `}
          <button type="button" class="secondary-button" data-action="refresh-meeting">Reload meeting</button>
        </div>
        <p id="governance-meeting-state" role="status"></p>
        <p id="governance-meeting-policy-note" role="note"></p>
        <pre id="governance-meeting-details" class="role-review-data"></pre>
        <h3>Agenda editor</h3>
        <p>Agenda JSON can be revised only while the proposal is awaiting approval.</p>
        <form data-action="save-agenda" class="governance-form">
          <label>Agenda JSON <textarea name="agenda" rows="8"></textarea></label>
          <button type="submit" class="secondary-button" disabled>Save agenda revision</button>
        </form>
        ${isOfficial ? "" : `
        <h3>Draft notice</h3>
        <button type="button" class="secondary-button" data-action="load-notice">Preview notice</button>
        <pre id="governance-notice" class="role-review-data"></pre>
        <h3>Meeting records</h3>
        <p>Records are available only after the backend confirms the meeting.</p>
        <form data-action="add-record" class="governance-form" hidden>
          <label>Record type
            <select name="record_type">
              <option value="NOTE">Note</option>
              <option value="OBSERVATION">Observation</option>
              <option value="DECISION">Human decision</option>
              <option value="ATTENDANCE">Attendance record</option>
            </select>
          </label>
          <label>Agenda item index (zero-based, optional) <input name="agenda_item_index" type="number" min="0" /></label>
          <label>Record content <textarea name="content" maxlength="5000" required></textarea></label>
          <button type="submit" class="secondary-button">Add record</button>
        </form>
        <h3>Versioned minutes</h3>
        <button type="button" class="secondary-button" data-action="load-minutes">Reload minutes</button>
        <p>Any generated content is an unapproved draft for human review. Finalized-minute indexing is not implemented.</p>
        <p id="governance-minutes-state" role="status"></p>
        <button type="button" class="secondary-button" data-action="create-manual-minutes" hidden>Start manual draft</button>
        <button type="button" class="secondary-button" data-action="generate-minutes" hidden>Generate AI-assisted draft (human review required)</button>
        <p id="governance-minutes-policy-note" role="note"></p>
        <pre id="governance-minutes-context" class="role-review-data"></pre>
        <form data-action="save-minutes" class="governance-form" hidden>
          <label>Minutes content JSON <textarea name="content" rows="14"></textarea></label>
          <button type="submit" class="secondary-button" disabled>Save revision</button>
        </form>
        <div class="governance-actions">
          <button type="button" class="secondary-button" data-action="submit-minutes" hidden>Submit for committee review</button>
          <button type="button" class="secondary-button" data-action="approve-minutes" hidden>Finalize (authorized signatory only)</button>
        </div>
        <form data-action="comment-minutes" class="governance-form" hidden>
          <label>Review comment <textarea name="comment" maxlength="4000" required></textarea></label>
          <button type="submit" class="secondary-button">Add review comment</button>
        </form>
        `}
      </section>
    </section>
  `;
}

export function getGovernanceActionAvailability(
  meeting,
  minutes,
  integrations,
  username,
) {
  const status = meeting?.status;
  const policy = meeting?.workflow_policy;
  const normalizedUsername =
    typeof username === "string" ? username.trim().toLowerCase() : "";
  const isApprover = (usernames) =>
    normalizedUsername &&
    Array.isArray(usernames) &&
    usernames.some(
      (candidate) =>
        typeof candidate === "string" &&
        candidate.trim().toLowerCase() === normalizedUsername,
    );
  const versions = Array.isArray(minutes?.versions) ? minutes.versions : [];
  const latest = minutes?.latest_version;
  const isFinalized =
    latest?.status === "FINALIZED" ||
    versions.some((version) => version?.status === "FINALIZED");
  const records = Array.isArray(minutes?.records) ? minutes.records : [];
  const agenda = Array.isArray(meeting?.agenda) ? meeting.agenda : [];
  const decisions = new Set(
    records
      .filter(
        (record) =>
          record?.record_type === "DECISION" &&
          Number.isSafeInteger(record?.agenda_item_index),
      )
      .map((record) => record.agenda_item_index),
  );
  const hasCompleteMinutesInputs =
    Array.isArray(minutes?.records) &&
    Array.isArray(meeting?.agenda) &&
    agenda.length > 0 &&
    ["ATTENDANCE", "NOTE", "OBSERVATION"].every((type) =>
      records.some((record) => record?.record_type === type),
    ) &&
    agenda.every(
      (item, index) =>
        decisions.has(
          Number.isSafeInteger(item?.index) ? item.index : index,
        ),
    ) &&
    Array.isArray(minutes?.review_issues) &&
    minutes.review_issues.length === 0;
  const awaitingConfirmation =
    status === "APPROVED_PENDING_CONFIRMATIONS";
  const alreadyResponded =
    normalizedUsername &&
    Array.isArray(meeting?.confirmations) &&
    meeting.confirmations.some(
      (confirmation) =>
        typeof confirmation?.username === "string" &&
        confirmation.username.trim().toLowerCase() === normalizedUsername,
    );

  return {
    canSelectSlot: status === "PROPOSED",
    canEditAgenda: status === "PROPOSED",
    canRequestMeetingApproval:
      status === "PROPOSED" &&
      meeting?.proposed_slot_start != null &&
      isApprover(policy?.meeting_approver_usernames),
    canRespondToMeeting: awaitingConfirmation && !alreadyResponded,
    canAddMeetingRecords: status === "CONFIRMED" && !isFinalized,
    canCreateMinutes:
      status === "CONFIRMED" && !isFinalized && hasCompleteMinutesInputs,
    canGenerateMinutes:
      status === "CONFIRMED" &&
      !isFinalized &&
      hasCompleteMinutesInputs &&
      integrations?.minutes_generation?.status ===
        "APPROVAL_ENABLED_PROVIDER_NOT_HEALTH_CHECKED",
    canSaveMinutes:
      !isFinalized && ["DRAFT", "SUBMITTED"].includes(latest?.status),
    canSubmitMinutes:
      !isFinalized &&
      latest?.status === "DRAFT" &&
      hasCompleteMinutesInputs,
    canCommentOnMinutes: latest?.status === "SUBMITTED",
    canApproveMinutes:
      minutes?.finalization_configured === true &&
      isApprover(minutes?.meeting?.workflow_policy?.minutes_approver_usernames) &&
      latest?.status === "SUBMITTED" &&
      hasCompleteMinutesInputs,
    hasCompleteMinutesInputs,
    isFinalized,
  };
}

export async function initializeGovernanceWorkspace(root, currentUser = null) {
  const message = root.querySelector("#governance-message");
  const committeeSelect = root.querySelector("#governance-committee");
  const meetingList = root.querySelector("#governance-meeting-list");
  const slots = root.querySelector("#governance-slots");
  const selectedPanel = root.querySelector("#governance-selected");
  const selectedDetails = root.querySelector("#governance-meeting-details");
  const integrations = root.querySelector("#governance-integrations");
  const notice = root.querySelector("#governance-notice");
  const minutesContext = root.querySelector("#governance-minutes-context");
  const meetingState = root.querySelector("#governance-meeting-state");
  const meetingPolicyNote = root.querySelector(
    "#governance-meeting-policy-note",
  );
  const minutesState = root.querySelector("#governance-minutes-state");
  const minutesPolicyNote = root.querySelector(
    "#governance-minutes-policy-note",
  );
  let selectedMeetingId = null;
  let latestMeeting = null;
  let latestMinutes = null;
  let integrationStatus = null;

  const showError = (error) => {
    message.textContent =
      error?.message || "The governance request could not be completed.";
    message.setAttribute("role", "alert");
  };
  const showMessage = (text) => {
    message.textContent = text;
    message.setAttribute("role", "status");
  };
  const selectedCommittee = () => committeeSelect.value;
  const setActionVisible = (action, visible) => {
    const control = root.querySelector(`[data-action="${action}"]`);
    if (control) {
      control.hidden = !visible;
      if ("disabled" in control) {
        control.disabled = !visible;
      }
    }
  };
  const setMeetingActionAvailability = (meeting, minutes) => {
    const available = getGovernanceActionAvailability(
      meeting,
      minutes,
      integrationStatus,
      currentUser?.username,
    );
    if (currentUser?.role === "OFFICIAL") {
      setActionVisible("approve-meeting", false);
      setActionVisible("respond-confirmed", false);
      setActionVisible("respond-declined", false);
      setActionVisible("save-agenda", available.canEditAgenda);
      meetingState.textContent =
        meeting?.status === "PROPOSED"
          ? `Proposal saved. ${meeting.proposed_slot_start ? `Selected slot: ${meeting.proposed_slot_start}.` : "No slot is selected yet."} Assigned DUGC members will review it from the linked application.`
          : `Persisted meeting status: ${meeting?.status || "Unknown"}.`;
      meetingPolicyNote.textContent =
        "Meeting approval and participant confirmation are controlled by the assigned committee and configured workflow policy.";
      return;
    }
    setActionVisible("approve-meeting", available.canRequestMeetingApproval);
    setActionVisible("respond-confirmed", available.canRespondToMeeting);
    setActionVisible("respond-declined", available.canRespondToMeeting);
    setActionVisible("create-manual-minutes", available.canCreateMinutes);
    setActionVisible("generate-minutes", available.canGenerateMinutes);
    setActionVisible("submit-minutes", available.canSubmitMinutes);
    setActionVisible("approve-minutes", available.canApproveMinutes);
    for (const [action, visible] of [
      ["save-agenda", available.canEditAgenda],
      ["add-record", available.canAddMeetingRecords],
      ["save-minutes", available.canSaveMinutes],
      ["comment-minutes", available.canCommentOnMinutes],
    ]) {
      const control = root.querySelector(
        `[data-action="${action}"]`,
      );
      if (control) {
        control.hidden = !visible;
        const submit = control.querySelector('button[type="submit"]');
        if (submit) {
          submit.disabled = !visible;
        }
      }
    }

    const slot = meeting?.proposed_slot_start;
    meetingState.textContent =
      meeting?.status === "PROPOSED"
        ? `Proposal saved. ${slot ? `Selected slot: ${slot}.` : "No slot is selected yet."} A selected slot is not an approved or confirmed meeting.`
        : meeting?.status === "APPROVED_PENDING_CONFIRMATIONS"
          ? "Approved; awaiting committee-member confirmation."
          : meeting?.status === "CONFIRMED"
            ? "Meeting confirmed by the backend."
            : `Persisted meeting status: ${meeting?.status || "Unknown"}.`;

    if (meeting?.status === "PROPOSED") {
      const approvers = meeting?.workflow_policy?.meeting_approver_usernames;
      const userIsApprover =
        typeof currentUser?.username === "string" &&
        Array.isArray(approvers) &&
        approvers.some(
          (name) =>
            typeof name === "string" &&
            name.trim().toLowerCase() ===
              currentUser.username.trim().toLowerCase(),
        );
      meetingPolicyNote.textContent =
        !meeting?.workflow_policy || !Array.isArray(approvers) || !approvers.length
        ? "Approval is blocked: no approved meeting workflow policy is configured for this committee."
        : !userIsApprover
          ? "Approval is unavailable to this account; it is not listed as an authorized meeting approver."
          : !slot
            ? "Select a candidate slot before requesting approval."
          : "";
    } else {
      meetingPolicyNote.textContent = "";
    }

    const minuteNotes = [];
    if (!available.hasCompleteMinutesInputs && meeting?.status === "CONFIRMED") {
      const issues = Array.isArray(minutes?.review_issues)
        ? minutes.review_issues
            .map((issue) => issue?.message)
            .filter((value) => typeof value === "string")
        : [];
      minuteNotes.push(issues.length
        ? `Minutes drafting is blocked by unresolved review inputs: ${issues.join(" ")}`
        : "Minutes drafting is blocked until attendance, meeting notes, observations, and a human decision or deferral for each agenda item are recorded.");
    } else if (meeting?.status !== "CONFIRMED") {
      minuteNotes.push(
        "Minutes drafts are available only after the backend confirms the meeting.",
      );
    }
    if (
      integrationStatus?.minutes_generation?.status !==
      "APPROVAL_ENABLED_PROVIDER_NOT_HEALTH_CHECKED"
    ) {
      minuteNotes.push(
        "AI-assisted generation is unavailable until an approved provider configuration is enabled.",
      );
    }
    if (minutes?.finalization_configured !== true) {
      minuteNotes.push(
        "Final sign-off is blocked because no approved minutes signatory policy is configured.",
      );
    } else if (!available.canApproveMinutes) {
      minuteNotes.push(
        "Final sign-off is unavailable to this account unless it is listed as an authorized signatory and the latest version is submitted.",
      );
    }
    minutesPolicyNote.textContent = minuteNotes.join(" ");

    minutesState.textContent = latestMinutes
      ? `Current version ${latestMinutes.version_number ?? "unknown"}: ${latestMinutes.status || "unknown"}${latestMinutes.generation_method === "AI" ? " · AI-assisted draft for human review" : ""}.`
      : "No minutes version is currently available.";
  };
  const renderMeetingList = async () => {
    const response = await listGovernanceMeetings(selectedCommittee());
    meetingList.replaceChildren();
    const meetings = Array.isArray(response) ? response : [];
    if (!meetings.length) {
      meetingList.textContent = "No meetings are available for this committee.";
      return;
    }
    for (const meeting of meetings) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "role-workspace-link governance-meeting-link";
      button.dataset.action = "select-meeting";
      button.dataset.meetingId = String(meeting.id);
      button.textContent = `${meeting.title} · ${meeting.status} · ${meeting.proposed_start}`;
      meetingList.append(button);
    }
  };
  const renderMeeting = async (meetingId) => {
    selectedMeetingId = meetingId;
    latestMeeting = null;
    latestMinutes = null;
    selectedPanel.hidden = true;
    selectedDetails.textContent = "Loading persisted meeting details…";
    const isOfficial = currentUser?.role === "OFFICIAL";
    const [meeting, noticeData, minutes] = isOfficial
      ? [
          await getGovernanceMeeting(meetingId),
          { distribution_status: "NOT_SENT" },
          {
            latest_version: null,
            records: [],
            versions: [],
            comments: [],
            review_issues: [],
            finalization_configured: false,
          },
        ]
      : await Promise.all([
          getGovernanceMeeting(meetingId),
          getGovernanceMeetingNotice(meetingId),
          getGovernanceMinutes(meetingId),
        ]);
    latestMeeting = meeting;
    latestMinutes = minutes.latest_version || null;
    selectedPanel.hidden = false;
    setMeetingActionAvailability(meeting, minutes);
    selectedDetails.textContent = JSON.stringify(
      { ...meeting, review_issues: minutes.review_issues },
      null,
      2,
    );
    if (notice) {
      notice.textContent = JSON.stringify(noticeData, null, 2);
    }
    const agendaForm = root.querySelector('[data-action="save-agenda"]');
    agendaForm.elements.namedItem("agenda").value = JSON.stringify(
      meeting.agenda.map(({ title, description, application_ids = [] }) => ({
        title,
        description,
        application_ids,
      })),
      null,
      2,
    );
    if (minutesContext) {
      minutesContext.textContent = JSON.stringify(
        {
          records: minutes.records,
          versions: minutes.versions,
          comments: minutes.comments,
          review_issues: minutes.review_issues,
          finalization_configured: minutes.finalization_configured,
        },
        null,
        2,
      );
    }
    const minutesForm = root.querySelector('[data-action="save-minutes"]');
    if (minutesForm) {
      minutesForm.elements.namedItem("content").value = latestMinutes
        ? JSON.stringify(latestMinutes.content, null, 2)
        : "";
    }
    await renderMeetingList();
  };
  const reloadAll = async () => {
    selectedMeetingId = null;
    latestMeeting = null;
    latestMinutes = null;
    selectedPanel.hidden = true;
    const [configuration, integrationResponse] =
      currentUser?.role === "OFFICIAL"
        ? [await getGovernanceConfiguration(), null]
        : await Promise.all([
            getGovernanceConfiguration(),
            getGovernanceIntegrations(),
          ]);
    integrationStatus = integrationResponse;
    const committees = Array.isArray(configuration.committees)
      ? configuration.committees
      : [];
    committeeSelect.replaceChildren();
    for (const committee of committees) {
      const option = document.createElement("option");
      option.value = committee.committee_type;
      option.textContent = `${committee.committee_type} · ${committee.programme}`;
      committeeSelect.append(option);
    }
    if (integrations) {
      integrations.textContent = JSON.stringify(integrationStatus, null, 2);
    }
    const hasCommittees = committees.length > 0;
    committeeSelect.disabled = !hasCommittees;
    for (const selector of [
      '[data-action="create-meeting"]',
      '[data-action="availability"]',
      '[data-action="search-slots"]',
    ]) {
      const form = root.querySelector(selector);
      if (form) {
        form.hidden = !hasCommittees;
      }
    }
    if (!committees.length) {
      showMessage(
        currentUser?.role === "OFFICIAL"
          ? "No committee can be scheduled from your currently assigned applications."
          : "This account has no active committee memberships.",
      );
      return;
    }
    showMessage("Governance workspace ready.");
    await renderMeetingList();
  };

  const toIso = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.valueOf())) {
      throw new Error("Enter a valid local date and time.");
    }
    return date.toISOString();
  };
  const toLocalInputValue = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.valueOf())) {
      return "";
    }
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    return date.toISOString().slice(0, 16);
  };
  const runFormAction = async (form) => {
    const data = new FormData(form);
    if (form.dataset.action === "create-meeting") {
      const applicationIds = String(data.get("application_ids") || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
        .map(Number);
      if (applicationIds.some((id) => !Number.isSafeInteger(id) || id < 1)) {
        throw new Error("Application IDs must be positive whole numbers.");
      }
      const start = toIso(data.get("proposed_start"));
      const end = toIso(data.get("proposed_end"));
      const idempotencyKey =
        form.dataset.idempotencyKey || crypto.randomUUID();
      form.dataset.idempotencyKey = idempotencyKey;
      const created = await createGovernanceMeeting(
        {
          committee_type: selectedCommittee(),
          title: String(data.get("title")).trim(),
          purpose: String(data.get("purpose")).trim(),
          proposed_start: start,
          proposed_end: end,
          duration_minutes: Number(data.get("duration_minutes")),
          agenda: [
            {
              title: String(data.get("agenda_title")).trim(),
              description: String(data.get("agenda_description") || "").trim(),
              application_ids: applicationIds,
            },
          ],
        },
        idempotencyKey,
      );
      if (
        !Number.isSafeInteger(created?.id) ||
        created.id <= 0 ||
        typeof created.status !== "string"
      ) {
        throw new Error(
          "The service did not return a persisted meeting identifier and status.",
        );
      }
      delete form.dataset.idempotencyKey;
      form.reset();
      const slotSearchForm = root.querySelector(
        '[data-action="search-slots"]',
      );
      slotSearchForm.elements.namedItem("range_start").value =
        toLocalInputValue(created.proposed_start);
      slotSearchForm.elements.namedItem("range_end").value =
        toLocalInputValue(created.proposed_end);
      slotSearchForm.elements.namedItem("duration_minutes").value =
        String(created.duration_minutes);
      await renderMeeting(created.id);
      showMessage(
        `Meeting ${created.id} proposal saved with status ${created.status}. No notice has been sent.`,
      );
    } else if (form.dataset.action === "availability") {
      const saved = await submitGovernanceAvailability({
        committee_type: selectedCommittee(),
        available_from: toIso(data.get("available_from")),
        available_until: toIso(data.get("available_until")),
        availability: data.get("availability"),
      });
      if (saved?.status !== "RECORDED") {
        throw new Error("The service did not confirm availability recording.");
      }
      showMessage(`Availability status: ${saved.status}.`);
    } else if (form.dataset.action === "search-slots") {
      const response = await getGovernanceCandidateSlots({
        committeeType: selectedCommittee(),
        rangeStart: toIso(data.get("range_start")),
        rangeEnd: toIso(data.get("range_end")),
        durationMinutes: Number(data.get("duration_minutes")),
        excludeMeetingId: selectedMeetingId,
      });
      slots.replaceChildren();
      const heading = document.createElement("p");
      heading.textContent = `${response.status}. Faculty timetable: ${response.faculty_timetable}.`;
      slots.append(heading);
      for (const slot of response.candidate_slots || []) {
        if (!slot.candidate || latestMeeting?.status !== "PROPOSED") {
          continue;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.dataset.action = "choose-slot";
        button.dataset.start = slot.start;
        button.textContent = `Propose ${slot.start} – ${slot.end}`;
        slots.append(button);
      }
      if (!slots.querySelector('[data-action="choose-slot"]')) {
        slots.append(
          document.createTextNode(
            latestMeeting?.status === "PROPOSED"
              ? "No conflict-free candidate slots found."
              : "Select a persisted proposed meeting before choosing a candidate slot.",
          ),
        );
      }
    } else if (form.dataset.action === "save-agenda") {
      if (!selectedMeetingId) {
        throw new Error("Select a meeting first.");
      }
      const agenda = JSON.parse(String(data.get("agenda")));
      await updateGovernanceMeetingAgenda(selectedMeetingId, agenda);
      await renderMeeting(selectedMeetingId);
      showMessage("Agenda revision saved. No notice was sent.");
    } else if (form.dataset.action === "add-record") {
      if (!selectedMeetingId) {
        throw new Error("Select a meeting first.");
      }
      const agendaIndexText = String(data.get("agenda_item_index") || "").trim();
      await addGovernanceMeetingRecord(selectedMeetingId, {
        record_type: data.get("record_type"),
        agenda_item_index: agendaIndexText ? Number(agendaIndexText) : null,
        content: String(data.get("content")).trim(),
      });
      form.reset();
      await renderMeeting(selectedMeetingId);
      showMessage("Meeting record saved.");
    } else if (form.dataset.action === "save-minutes") {
      if (!selectedMeetingId || !latestMinutes) {
        throw new Error("Generate or select a draft minutes version first.");
      }
      const content = JSON.parse(String(data.get("content")));
      const revision = await saveGovernanceMinutes(
        selectedMeetingId,
        latestMinutes.id,
        content,
      );
      await renderMeeting(selectedMeetingId);
      latestMinutes = revision;
      showMessage("Minutes revision saved as a new version.");
    } else if (form.dataset.action === "comment-minutes") {
      if (!latestMinutes) {
        throw new Error("Select a submitted minutes version first.");
      }
      await commentOnGovernanceMinutes(
        latestMinutes.id,
        String(data.get("comment")).trim(),
      );
      form.reset();
      await renderMeeting(selectedMeetingId);
      showMessage("Review comment saved.");
    }
  };

  root.addEventListener("change", (event) => {
    if (event.target === committeeSelect) {
      renderMeetingList().catch(showError);
      selectedMeetingId = null;
      latestMeeting = null;
      latestMinutes = null;
      selectedPanel.hidden = true;
      slots.replaceChildren();
    }
  });
  root.addEventListener("submit", (event) => {
    const form = event.target.closest("form[data-action]");
    if (!form || form.dataset.submitting === "true") {
      return;
    }
    event.preventDefault();
    const submitButton = form.querySelector('button[type="submit"]');
    form.dataset.submitting = "true";
    if (submitButton) {
      submitButton.disabled = true;
    }
    runFormAction(form)
      .catch(showError)
      .finally(() => {
        delete form.dataset.submitting;
        if (submitButton?.isConnected) {
          submitButton.disabled = form.hidden;
        }
      });
  });
  root.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button || button.hidden || button.disabled) {
      return;
    }
    if (button.dataset.busy === "true") {
      return;
    }
    button.dataset.busy = "true";
    button.disabled = true;
    try {
      if (button.dataset.action === "refresh") {
        await reloadAll();
      } else if (button.dataset.action === "select-meeting") {
        await renderMeeting(Number(button.dataset.meetingId));
      } else if (button.dataset.action === "choose-slot") {
        if (!selectedMeetingId) {
          showMessage("Choose a meeting before proposing a slot.");
          return;
        }
        await selectGovernanceMeetingSlot(selectedMeetingId, button.dataset.start);
        await renderMeeting(selectedMeetingId);
        showMessage("Candidate slot proposed; approval and confirmations remain separate steps.");
      } else if (button.dataset.action === "approve-meeting") {
        await approveGovernanceMeeting(selectedMeetingId);
        await renderMeeting(selectedMeetingId);
        showMessage("Meeting approval state reloaded.");
      } else if (button.dataset.action === "respond-confirmed") {
        await respondToGovernanceMeeting(selectedMeetingId, "CONFIRMED");
        await renderMeeting(selectedMeetingId);
        showMessage("Attendance response recorded.");
      } else if (button.dataset.action === "respond-declined") {
        await respondToGovernanceMeeting(selectedMeetingId, "DECLINED");
        await renderMeeting(selectedMeetingId);
        showMessage("Decline response recorded.");
      } else if (button.dataset.action === "refresh-meeting") {
        await renderMeeting(selectedMeetingId);
      } else if (button.dataset.action === "load-notice") {
        notice.textContent = JSON.stringify(
          await getGovernanceMeetingNotice(selectedMeetingId),
          null,
          2,
        );
      } else if (button.dataset.action === "load-minutes") {
        await renderMeeting(selectedMeetingId);
      } else if (button.dataset.action === "create-manual-minutes") {
        const draft = await createManualGovernanceMinutes(selectedMeetingId);
        await renderMeeting(selectedMeetingId);
        latestMinutes = draft;
        showMessage("Human-authored minutes draft created from recorded meeting inputs.");
      } else if (button.dataset.action === "generate-minutes") {
        const generated = await generateGovernanceMinutes(selectedMeetingId);
        await renderMeeting(selectedMeetingId);
        latestMinutes = generated;
        showMessage("AI-assisted draft saved; verify every statement against recorded evidence.");
      } else if (button.dataset.action === "submit-minutes") {
        if (!latestMinutes) {
          throw new Error("Select a draft minutes version first.");
        }
        await submitGovernanceMinutes(latestMinutes.id);
        await renderMeeting(selectedMeetingId);
        showMessage("Minutes submitted for committee review.");
      } else if (button.dataset.action === "approve-minutes") {
        if (!latestMinutes) {
          throw new Error("Select a submitted minutes version first.");
        }
        const result = await approveGovernanceMinutes(latestMinutes.id);
        await renderMeeting(selectedMeetingId);
        showMessage(`Finalization status: ${result.status}; indexing: ${result.indexing_status}.`);
      }
    } catch (error) {
      showError(error);
    } finally {
      delete button.dataset.busy;
      if (button.isConnected) {
        button.disabled = button.hidden;
      }
    }
  });

  try {
    await reloadAll();
  } catch (error) {
    showError(error);
  }
}
