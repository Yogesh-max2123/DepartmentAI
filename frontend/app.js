const API_BASE = (
  new URLSearchParams(window.location.search).get("api") ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");
const SESSION_KEY = "departmentai.workflow.session";
const ROLE_ACCOUNTS = {
  student: { username: "MTECH20233359", label: "Student", route: "/student" },
  official: {
    username: "OFFICIAL01",
    label: "Official Staff",
    route: "/official",
  },
  dmpc: { username: "DMPC01", label: "DMPC Committee", route: "/dmpc" },
};
const ROLE_VIEWS = {
  student: [
    { id: "chat", label: "Ordinance assistant", icon: "✦" },
    { id: "application", label: "New application", icon: "＋" },
    { id: "tracker", label: "My applications", icon: "▤" },
  ],
  official: [
    { id: "queue", label: "Incoming queue", icon: "▣" },
    { id: "workspace", label: "Claimed workspace", icon: "◈" },
    { id: "scheduler", label: "Scheduler tools", icon: "◷" },
  ],
  dmpc: [{ id: "committee", label: "Committee queue", icon: "▤" }],
};
const FIVE_HEADINGS = [
  "Relevant ordinance clauses",
  "Similar previous cases (citing the synthetic data)",
  "Identified deficiencies",
  "Possible course of action",
  "Initial draft resolution",
];
const APPLICATION_STAGES = [
  { id: "submitted", label: "Submitted" },
  { id: "under-review", label: "Under Review" },
  { id: "official-action", label: "Official Action" },
  { id: "meeting-proposed", label: "Meeting Proposed" },
  { id: "meeting-scheduled", label: "Meeting Scheduled" },
  { id: "minutes-generated", label: "Minutes Generated" },
];

const app = document.getElementById("app");
const toastRegion = document.getElementById("toast-region");
let activeView = "";
let selectedRole = "student";
let chatHistory = [];
let studentPollTimer = null;
let officialApplications = [];
let dmpcApplications = [];
let selectedApplicationId = null;
let analyzedDraft = null;
let analysisBusy = false;
let draftRevision = 0;
let selectedDraftFiles = [];

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character],
  );
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}

function getSession() {
  try {
    const session = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
    if (session && session.username && session.password && session.role) {
      return session;
    }
  } catch (error) {
    console.warn("Could not read the portal session.", error);
  }
  return null;
}

function saveSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

function authHeader(session = getSession()) {
  if (!session) return {};
  return {
    Authorization: `Basic ${encodeBase64(`${session.username}:${session.password}`)}`,
  };
}

function encodeBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

async function requestJson(path, options = {}, authenticated = true) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (authenticated) {
    Object.assign(headers, authHeader());
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (error) {
    throw new Error(
      `Could not connect to the portal API at ${API_BASE}. Check that FastAPI is running and CORS permits this frontend.`,
    );
  }

  let data;
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }
  if (!response.ok) {
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ||
          JSON.stringify(detail) ||
          `Request failed (${response.status}).`;
    throw new Error(message);
  }
  return data;
}

function notify(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4800);
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.textContent;
    button.textContent = label || "Working…";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalLabel || button.textContent;
    button.disabled = false;
    delete button.dataset.originalLabel;
  }
}

function roleName(role) {
  return ROLE_ACCOUNTS[role]?.label || role;
}

function goToRole(role) {
  const path = ROLE_ACCOUNTS[role]?.route || "/";
  if (window.location.hash !== `#${path}`) {
    window.location.hash = path;
  } else {
    renderApp();
  }
}

function showLogin() {
  stopPolling();
  app.innerHTML = `
        <section class="login-page">
            <div class="login-story">
                <div class="brand-lockup">
                    <span class="brand-mark">D</span>
                    <span><strong>DepartmentAI</strong><small>M.Tech. governance portal</small></span>
                </div>
                <div class="login-story-copy">
                    <span class="eyebrow">M.Tech. · DMPC · Academic governance</span>
                    <h1>One connected journey, from application to committee decision.</h1>
                    <p>Grounded ordinance assistance, document verification, official review, meeting coordination, and committee minutes in one secure workspace.</p>
                    <div class="journey"><span>01 Student services</span><span>02 Official review</span><span>03 DMPC committee</span></div>
                </div>
                <footer>DepartmentAI · Academic governance workspace</footer>
            </div>
            <div class="login-panel">
                <form id="login-form" class="login-card">
                    <h2>Welcome back</h2>
                    <p>Sign in with your portal account to continue.</p>
                    <div class="role-picker" role="group" aria-label="Choose your portal role">
                        ${Object.entries(ROLE_ACCOUNTS)
                          .map(
                            ([role, account]) => `
                            <button type="button" class="role-choice ${role === selectedRole ? "is-active" : ""}" data-role="${role}">${escapeHtml(account.label)}</button>
                        `,
                          )
                          .join("")}
                    </div>
                    <div class="field-wrap">
                        <label class="form-label" for="login-username">Account ID</label>
                        <input class="field" id="login-username" name="username" autocomplete="username" required value="${escapeHtml(ROLE_ACCOUNTS[selectedRole].username)}">
                    </div>
                    <div class="field-wrap">
                        <label class="form-label" for="login-password">Password</label>
                        <input class="field" id="login-password" name="password" type="password" autocomplete="current-password" required>
                    </div>
                    <button class="primary-button full-width" id="login-submit" type="submit">Sign in to ${escapeHtml(ROLE_ACCOUNTS[selectedRole].label)}</button>
                    <p class="login-note">Passwords are configured by the administrator in the backend environment. Your session is held in this browser tab.</p>
                </form>
            </div>
        </section>`;

  document.querySelectorAll(".role-choice").forEach((button) => {
    button.addEventListener("click", () => {
      selectedRole = button.dataset.role;
      document
        .querySelectorAll(".role-choice")
        .forEach((choice) =>
          choice.classList.toggle("is-active", choice === button),
        );
      const username = document.getElementById("login-username");
      username.value = ROLE_ACCOUNTS[selectedRole].username;
      document.getElementById("login-submit").textContent =
        `Sign in to ${ROLE_ACCOUNTS[selectedRole].label}`;
    });
  });

  document.getElementById("login-form").addEventListener("submit", login);
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  const username = form.elements.username.value.trim();
  const password = form.elements.password.value;
  setBusy(button, true, "Verifying credentials…");
  try {
    const response = await requestJson(
      "/workflow/login",
      {
        method: "POST",
        headers: {
          Authorization: `Basic ${encodeBase64(`${username}:${password}`)}`,
        },
      },
      false,
    );
    const expected = ROLE_ACCOUNTS[selectedRole];
    if (response.role !== selectedRole || username !== expected.username) {
      throw new Error("Choose the role that matches this account ID.");
    }
    saveSession({ username, password, role: response.role });
    chatHistory = [];
    goToRole(response.role);
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

function logout() {
  sessionStorage.removeItem(SESSION_KEY);
  chatHistory = [];
  selectedApplicationId = null;
  selectedDraftFiles = [];
  analyzedDraft = null;
  draftRevision += 1;
  window.location.hash = "";
  showLogin();
}

function renderShell(session, viewId) {
  const role = session.role;
  const navItems = ROLE_VIEWS[role];
  if (!navItems.some((item) => item.id === viewId)) viewId = navItems[0].id;
  activeView = viewId;

  app.innerHTML = `
        <div class="app-shell">
            <header class="topbar">
                <div class="topbar-brand">
                    <span class="brand-mark">D</span>
                    <span><strong>DepartmentAI</strong><small>M.Tech. governance portal</small></span>
                </div>
                <div class="user-tools">
                    <span class="user-chip">${escapeHtml(roleName(role))} · ${escapeHtml(session.username)}</span>
                    <button class="secondary-button" id="logout-button" type="button">Log out</button>
                </div>
            </header>
            <div class="portal-layout">
                <nav class="side-nav" aria-label="Portal sections">
                    <p class="nav-caption">${escapeHtml(roleName(role))} workspace</p>
                    ${navItems
                      .map(
                        (item) => `
                        <button class="nav-item ${item.id === viewId ? "is-active" : ""}" data-view="${item.id}" type="button">
                            <span class="nav-icon">${item.icon}</span>${escapeHtml(item.label)}
                        </button>
                    `,
                      )
                      .join("")}
                </nav>
                <main class="workspace" id="workspace"></main>
            </div>
        </div>`;

  document.getElementById("logout-button").addEventListener("click", logout);
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => navigateView(button.dataset.view));
  });
  if (role === "student") renderStudentView(viewId);
  if (role === "official") renderOfficialView(viewId);
  if (role === "dmpc") renderDmpcView(viewId);
}

function navigateView(viewId) {
  const session = getSession();
  if (!session) return showLogin();
  activeView = viewId;
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewId);
  });
  const route = `#${ROLE_ACCOUNTS[session.role].route}/${viewId}`;
  if (window.location.hash !== route) window.location.hash = route;
  if (session.role === "student") renderStudentView(viewId);
  if (session.role === "official") renderOfficialView(viewId);
  if (session.role === "dmpc") renderDmpcView(viewId);
}

function pageHeading(title, subtitle, action = "") {
  return `<div class="page-heading"><div><h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle)}</p></div>${action}</div>`;
}

function renderStudentView(viewId) {
  stopPolling();
  if (viewId !== "application") {
    selectedDraftFiles = [];
    analyzedDraft = null;
    draftRevision += 1;
  }
  const workspace = document.getElementById("workspace");
  if (viewId === "chat") {
    workspace.innerHTML = `
            ${pageHeading("AI Ordinance Assistant", "Ask grounded questions about M.Tech. ordinances, procedures, make-up examinations, and required documents.")}
            <section class="panel chat-panel">
                <div class="panel-heading"><h2>Ask DepartmentAI</h2><span class="status-badge blue">Ordinance RAG</span></div>
                <div class="chat-messages" id="student-chat-messages">
                    <div class="chat-message bot">Hello! Ask a question about the Masters’ Programme ordinance or application procedures. Answers include retrieved source references where available.</div>
                </div>
                <form class="chat-form" id="student-chat-form">
                    <input class="field" id="student-chat-input" name="question" placeholder="For example: What documents are required for a thesis extension?" autocomplete="off" required>
                    <button class="primary-button" id="student-chat-send" type="submit">Send</button>
                </form>
            </section>`;
    document
      .getElementById("student-chat-form")
      .addEventListener("submit", sendStudentChat);
  } else if (viewId === "application") {
    renderApplicationForm(workspace);
  } else {
    workspace.innerHTML = `${pageHeading("My applications", "Follow each request as it moves from submission through official and committee review.", `<button class="secondary-button" id="refresh-applications" type="button">Refresh</button>`)}
            <div class="application-list" id="student-applications"><div class="empty-state">Loading your application history…</div></div>`;
    document
      .getElementById("refresh-applications")
      .addEventListener("click", loadStudentApplications);
    loadStudentApplications();
    studentPollTimer = window.setInterval(loadStudentApplications, 20000);
  }
}

async function sendStudentChat(event) {
  event.preventDefault();
  const input = document.getElementById("student-chat-input");
  const button = document.getElementById("student-chat-send");
  const question = input.value.trim();
  if (!question) return;
  const messages = document.getElementById("student-chat-messages");
  appendChatMessage(messages, question, "user");
  input.value = "";
  setBusy(button, true, "Thinking…");
  try {
    const data = await requestJson("/workflow/student/chat", {
      method: "POST",
      body: JSON.stringify({ question, conversation_history: chatHistory }),
    });
    appendChatMessage(messages, data.answer, "bot", data.sources || []);
    chatHistory.push(
      { role: "user", content: question },
      { role: "assistant", content: data.answer },
    );
  } catch (error) {
    appendChatMessage(
      messages,
      `I couldn’t retrieve an answer: ${error.message}`,
      "bot",
    );
  } finally {
    setBusy(button, false);
    messages.scrollTop = messages.scrollHeight;
    input.focus();
  }
}

function appendChatMessage(container, text, role, sources = []) {
  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.innerHTML = inlineMarkdown(text).replace(/\n/g, "<br>");
  if (role === "bot" && sources.length) {
    const sourceList = document.createElement("div");
    sourceList.className = "chat-sources";
    sourceList.innerHTML = `<strong>Retrieved sources</strong><br>${sources
      .map((source) => {
        const details = [
          source.chunk_type || "ordinance",
          source.section
            ? `Section ${source.section}${source.section_title ? ` · ${source.section_title}` : ""}`
            : "",
          source.clause ? `Clause ${source.clause}` : "",
          source.pages ? `Pages ${source.pages}` : "",
          source.source_file || source.chunk_id || "",
        ].filter(Boolean);
        return `• ${escapeHtml(details.join(" — "))}`;
      })
      .join("<br>")}`;
    message.appendChild(sourceList);
  }
  container.appendChild(message);
  container.scrollTop = container.scrollHeight;
}

function renderApplicationForm(workspace) {
  selectedDraftFiles = [];
  analyzedDraft = null;
  workspace.innerHTML = `
        ${pageHeading("New DMPC application", "Describe the request and let the AI gatekeeper check supporting documents against retrieved ordinance requirements.")}
        <section class="panel">
            <form id="application-form">
                <div class="form-grid">
                    <div class="field-wrap">
                        <label class="form-label" for="application-category">Category</label>
                        <select class="select-field" id="application-category" name="category" required>
                            <option value="">Choose a category</option>
                            <option>Academic performance / SPI-CPI</option>
                            <option>Leave or attendance</option>
                            <option>Thesis / supervisor</option>
                            <option>Registration / course</option>
                            <option>Make-up examination</option>
                            <option>Stipend / fellowship</option>
                            <option>Other DMPC matter</option>
                        </select>
                    </div>
                    <div class="field-wrap">
                        <label class="form-label" for="application-subject">Subject</label>
                        <input class="field" id="application-subject" name="subject" placeholder="Short title for your request" required>
                    </div>
                    <div class="field-wrap span-two">
                        <label class="form-label" for="application-description">Reason / description</label>
                        <textarea class="text-area" id="application-description" name="description" placeholder="Explain the request, relevant dates, and circumstances." required></textarea>
                    </div>
                    <div class="field-wrap span-two">
                        <label class="form-label" for="application-files">Supporting documents</label>
                        <div class="upload-zone">
                            <input id="application-files" name="files" type="file" multiple accept=".pdf,.txt,.csv,text/*,application/pdf">
                            <small>Upload PDF or text documents. Scanned PDFs without selectable text need an OCR/extracted text version. Maximum 10 MB per file.</small>
                            <div id="draft-file-list" class="mt-2 space-y-2"></div>
                        </div>
                    </div>
                </div>
                <div class="report-box hidden" id="verification-report" aria-live="polite"></div>
                <div class="button-row">
                    <button class="secondary-button" id="analyze-draft" type="button">✦ AI Assisted Analysis</button>
                    <button class="primary-button" id="submit-application" type="submit" disabled>Submit Application</button>
                    <span class="helper-text" id="gatekeeper-hint">Complete AI analysis with zero deficiencies to enable submission.</span>
                </div>
            </form>
        </section>`;

  const form = document.getElementById("application-form");
  form.addEventListener("input", invalidateAnalysis);
  form.addEventListener("change", invalidateAnalysis);
  document
    .getElementById("application-files")
    .addEventListener("change", (event) => {
      const input = event.currentTarget;
      selectedDraftFiles.push(...Array.from(input.files || []));
      input.value = "";
      renderDraftFiles("draft-file-list", selectedDraftFiles, () =>
        invalidateAnalysis(),
      );
    });
  renderDraftFiles("draft-file-list", selectedDraftFiles, () =>
    invalidateAnalysis(),
  );
  document
    .getElementById("analyze-draft")
    .addEventListener("click", analyzeDraft);
  form.addEventListener("submit", submitApplication);
}

function invalidateAnalysis(event) {
  draftRevision += 1;
  if (analysisBusy) return;
  analyzedDraft = null;
  const submit = document.getElementById("submit-application");
  if (submit) submit.disabled = true;
  const hint = document.getElementById("gatekeeper-hint");
  if (hint)
    hint.textContent =
      "Draft changed. Run AI Assisted Analysis again before submission.";
  const report = document.getElementById("verification-report");
  if (report && !report.classList.contains("hidden")) {
    report.className = "report-box";
    report.innerHTML =
      "<h3>Analysis is out of date</h3><p>Any change to your form or files requires a fresh verification.</p>";
  }
}

function formatFileSize(size) {
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  return `${size ? Math.max(0.1, size / 1024).toFixed(1) : "0"} KB`;
}

function renderDraftFiles(containerId, files, onRemove) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.className = "draft-file-list mt-2 space-y-2";
  container.innerHTML = files.length
    ? files
        .map(
          (file, index) => `
            <div class="draft-file-row">
                <span class="draft-file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                <span class="draft-file-size">${formatFileSize(file.size)}</span>
                <button class="draft-file-remove" type="button" data-file-index="${index}" aria-label="Remove ${escapeHtml(file.name)}">Remove</button>
            </div>`,
        )
        .join("")
    : `<div class="draft-file-empty">No files selected</div>`;
  container.querySelectorAll(".draft-file-remove").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.fileIndex);
      if (!Number.isInteger(index) || index < 0 || index >= files.length) return;
      files.splice(index, 1);
      renderDraftFiles(containerId, files, onRemove);
      onRemove?.();
    });
  });
}

function currentDraft() {
  const form = document.getElementById("application-form");
  return {
    category: form.elements.category.value.trim(),
    subject: form.elements.subject.value.trim(),
    description: form.elements.description.value.trim(),
  };
}

async function serializeUploads() {
  return serializeFiles(selectedDraftFiles);
}

async function serializeFiles(files) {
  if (files.some((file) => file.size > 10 * 1024 * 1024)) {
    throw new Error("Each file must be 10 MB or smaller.");
  }
  return Promise.all(
    files.map(
      (file) =>
        new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () =>
            resolve({
              file_name: file.name,
              content_type: file.type || "",
              content_base64: String(reader.result).split(",")[1],
            });
          reader.onerror = () =>
            reject(new Error(`Could not read ${file.name}.`));
          reader.readAsDataURL(file);
        }),
    ),
  );
}

async function makeDraftPayload() {
  const draft = currentDraft();
  if (!draft.category || !draft.subject || !draft.description) {
    throw new Error(
      "Complete the category, subject, and reason before analysis.",
    );
  }
  return { ...draft, uploaded_files: await serializeUploads() };
}

async function analyzeDraft() {
  if (analysisBusy) return;
  const button = document.getElementById("analyze-draft");
  const report = document.getElementById("verification-report");
  analysisBusy = true;
  const analysisRevision = draftRevision;
  analyzedDraft = null;
  document.getElementById("submit-application").disabled = true;
  setBusy(button, true, "Checking requirements…");
  report.className = "report-box";
  report.innerHTML =
    "<h3>AI Verification Report</h3><p>Retrieving ordinance requirements and reviewing your supporting documents…</p>";
  try {
    const payload = await makeDraftPayload();
    const data = await requestJson("/workflow/student/analyze-draft", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (analysisRevision !== draftRevision) {
      throw new Error(
        "The draft changed during analysis. Run AI Assisted Analysis again.",
      );
    }
    const deficiencies = Array.isArray(data.deficiencies)
      ? data.deficiencies
      : [];
    const canSubmit = deficiencies.length === 0 && data.can_submit === true;
    analyzedDraft = canSubmit ? JSON.stringify(payload) : null;
    report.className = `report-box ${canSubmit ? "is-pass" : "is-fail"}`;
    report.innerHTML = canSubmit
      ? "<h3>✓ Verified — no deficiencies found</h3><p>Your documents passed the AI-assisted check against the retrieved ordinance requirements. You can now submit your application.</p>"
      : `<h3>Review needed · ${deficiencies.length || 1} item${deficiencies.length === 1 ? "" : "s"}</h3><ul>${(deficiencies.length ? deficiencies : ["The AI gatekeeper did not verify this draft. Please retry after reviewing your documents."]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    document.getElementById("submit-application").disabled = !canSubmit;
    document.getElementById("gatekeeper-hint").textContent = canSubmit
      ? "Verified draft. Submission is enabled."
      : "Resolve the listed items and run the analysis again.";
    if (canSubmit)
      notify("Documents verified. Your application is ready to submit.");
  } catch (error) {
    report.className = "report-box is-fail";
    report.innerHTML = `<h3>Analysis unavailable</h3><p>${escapeHtml(error.message)}</p><p>Submission remains disabled until analysis succeeds.</p>`;
    notify(error.message, "error");
  } finally {
    analysisBusy = false;
    setBusy(button, false);
  }
}

async function submitApplication(event) {
  event.preventDefault();
  const button = document.getElementById("submit-application");
  if (!analyzedDraft || button.disabled) {
    notify(
      "Run AI Assisted Analysis and pass the document gate before submitting.",
      "error",
    );
    return;
  }
  setBusy(button, true, "Submitting securely…");
  try {
    const payload = await makeDraftPayload();
    if (JSON.stringify(payload) !== analyzedDraft) {
      analyzedDraft = null;
      button.disabled = true;
      throw new Error(
        "The draft changed after analysis. Run AI Assisted Analysis again.",
      );
    }
    const response = await requestJson("/workflow/student/submit", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    notify(`Application #${response.application.id} submitted successfully.`);
    renderApplicationForm(document.getElementById("workspace"));
    await loadStudentApplications();
  } catch (error) {
    notify(error.message, "error");
    if (!analyzedDraft) button.disabled = true;
  } finally {
    if (button.isConnected) setBusy(button, false);
  }
}

function stopPolling() {
  if (studentPollTimer) {
    window.clearInterval(studentPollTimer);
    studentPollTimer = null;
  }
}

function statusLabel(status) {
  return (
    {
      SUBMITTED: "Submitted",
      UNDER_REVIEW: "Under Review",
      DEFICIENCY_FOUND: "Deficiencies Found",
      RESUBMITTED: "Resubmitted",
      CLAIMED_BY_OFFICIAL: "Claimed by Official",
      APPROVED_BY_OFFICIAL: "Approved by Official",
      MEETING_PROPOSED: "Meeting Proposed",
      RESCHEDULE_REQUESTED: "Reschedule Requested",
      MEETING_SCHEDULED: "Meeting Scheduled",
      MINUTES_GENERATED: "Minutes Generated",
      REJECTED: "Rejected",
    }[status] ||
    status ||
    "Unknown"
  );
}

function statusColor(status) {
  if (
    ["APPROVED_BY_OFFICIAL", "MEETING_SCHEDULED", "MINUTES_GENERATED"].includes(
      status,
    )
  )
    return "green";
  if (status === "MEETING_PROPOSED") return "purple";
  if (status === "DEFICIENCY_FOUND" || status === "REJECTED") return "red";
  if (
    [
      "CLAIMED_BY_OFFICIAL",
      "UNDER_REVIEW",
      "RESUBMITTED",
      "RESCHEDULE_REQUESTED",
    ].includes(status)
  )
    return "amber";
  return "blue";
}

function applicationStageIndex(status) {
  if (status === "SUBMITTED") return 0;
  if (["UNDER_REVIEW", "DEFICIENCY_FOUND", "RESUBMITTED"].includes(status))
    return 1;
  if (
    ["CLAIMED_BY_OFFICIAL", "APPROVED_BY_OFFICIAL", "REJECTED"].includes(status)
  )
    return 2;
  if (["MEETING_PROPOSED", "RESCHEDULE_REQUESTED"].includes(status)) return 3;
  if (status === "MEETING_SCHEDULED") return 4;
  if (status === "MINUTES_GENERATED") return 5;
  return -1;
}

function renderApplicationTimeline(item) {
  const currentStage = applicationStageIndex(item.status);
  const deficiency = item.status === "DEFICIENCY_FOUND";
  const stages = APPLICATION_STAGES.map((stage, index) => {
    const state =
      index < currentStage
        ? "complete"
        : index === currentStage
          ? deficiency
            ? "error"
            : "current"
          : "";
    const detail =
      index === currentStage
        ? statusLabel(item.status)
        : index === 2 && item.status === "APPROVED_BY_OFFICIAL"
          ? "Approved"
          : "";
    return `<li class="timeline-step ${state}">
        <span class="timeline-marker" aria-hidden="true">${index < currentStage ? "✓" : index + 1}</span>
        <span class="timeline-copy"><strong>${escapeHtml(stage.label)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</span>
      </li>`;
  }).join("");
  return `<ol class="application-timeline" aria-label="Application progress">${stages}</ol>${
    deficiency
      ? `<div class="deficiency-callout" role="alert">
          <strong>Action required · Deficiencies found</strong>
          <p>${escapeHtml(item.official_remarks || "Please review the official remarks and submit the requested documents.")}</p>
        </div>`
      : item.status === "RESCHEDULE_REQUESTED"
        ? `<div class="timeline-note"><strong>DMPC requested a new meeting date.</strong><p>${escapeHtml(item.official_remarks || "The official will propose a replacement date range.")}</p></div>`
        : ""
  }`;
}

async function loadStudentApplications() {
  const container = document.getElementById("student-applications");
  if (!container) return;
  try {
    const session = getSession();
    const response = await requestJson(
      `/workflow/student/applications/${encodeURIComponent(session.username)}`,
    );
    const applications = response.applications || [];
    container.innerHTML = applications.length
      ? applications
          .map(
            (item) => `
                <article class="application-card">
                    <div class="application-card-top">
                        <div><h3>#${escapeHtml(item.id)} · ${escapeHtml(item.subject)}</h3><p>${escapeHtml(item.category)} · Submitted ${formatDate(item.created_at)}</p></div>
                        <span class="status-badge ${statusColor(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
                    </div>
                    <p>${escapeHtml(item.description)}</p>
                    ${renderApplicationTimeline(item)}
                    ${item.scheduler_proposal_id ? `<p>Meeting reference: ${escapeHtml(item.scheduler_proposal_id)}</p>` : ""}
                    ${item.final_decision ? `<p><strong>Committee decision:</strong> ${escapeHtml(item.final_decision)}</p>` : ""}
                    ${item.status === "DEFICIENCY_FOUND" ? `<button class="danger-button resubmit-application" data-id="${escapeHtml(item.id)}" type="button">Fix Deficiencies &amp; Resubmit</button>` : ""}
                </article>`,
          )
          .join("")
      : `<div class="empty-state">No applications yet. Start a new request and submit it after it passes the AI document gate.</div>`;
    container.querySelectorAll(".resubmit-application").forEach((button) => {
      button.addEventListener("click", () =>
        openResubmissionModal(
          applications.find((item) => item.id === Number(button.dataset.id)),
        ),
      );
    });
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Could not load applications: ${escapeHtml(error.message)}</div>`;
  }
}

function openResubmissionModal(item) {
  if (!item || item.status !== "DEFICIENCY_FOUND") return;
  selectedDraftFiles = [];
  document.getElementById("resubmission-dialog")?.remove();
  const dialog = document.createElement("dialog");
  dialog.id = "resubmission-dialog";
  dialog.className = "portal-dialog resubmission-dialog";
  dialog.innerHTML = `
    <form class="dialog-card" id="resubmission-form">
      <div class="dialog-heading">
        <div><span class="eyebrow">Application #${escapeHtml(item.id)}</span><h2>Fix deficiencies &amp; resubmit</h2></div>
        <button class="icon-button" type="button" data-close-dialog aria-label="Close dialog">×</button>
      </div>
      <div class="deficiency-callout" role="alert">
        <strong>Official remarks · Please address these items</strong>
        <p>${escapeHtml(item.official_remarks || "Review the application requirements and attach the requested documents.")}</p>
      </div>
      <div class="field-wrap">
        <label class="form-label" for="resubmission-files">Additional supporting documents</label>
        <div class="upload-zone">
          <input id="resubmission-files" name="files" type="file" multiple accept=".pdf,.txt,.csv,text/*,application/pdf">
          <small>Select all new or corrected documents. They will be appended to the files already on your application.</small>
          <div id="draft-file-list" class="mt-2 space-y-2"></div>
        </div>
      </div>
      <div class="field-wrap">
        <label class="form-label" for="resubmission-remarks">Your remarks</label>
        <textarea class="text-area" id="resubmission-remarks" name="student_remarks" placeholder="Explain what you have added or corrected."></textarea>
      </div>
      <div class="report-box hidden" id="resubmission-report" aria-live="polite"></div>
      <div class="button-row dialog-actions">
        <button class="secondary-button" id="analyze-resubmission" type="button">✦ AI Assisted Analysis</button>
        <button class="primary-button" id="submit-resubmission" type="submit" disabled>Resubmit Application</button>
      </div>
      <p class="helper-text" id="resubmission-hint">Analysis with zero deficiencies is required before resubmission.</p>
    </form>`;
  document.body.appendChild(dialog);

  const form = dialog.querySelector("#resubmission-form");
  const filesInput = dialog.querySelector("#resubmission-files");
  const report = dialog.querySelector("#resubmission-report");
  const submitButton = dialog.querySelector("#submit-resubmission");
  const analyzeButton = dialog.querySelector("#analyze-resubmission");
  let analyzedPayload = null;
  let revision = 0;
  let busy = false;
  const invalidateResubmission = () => {
    revision += 1;
    analyzedPayload = null;
    submitButton.disabled = true;
    if (!busy && !report.classList.contains("hidden")) {
      report.className = "report-box";
      report.innerHTML =
        "<h3>Analysis is out of date</h3><p>Run a fresh check for the selected files.</p>";
      dialog.querySelector("#resubmission-hint").textContent =
        "Files changed. Run AI Assisted Analysis again.";
    }
  };
  selectedDraftFiles = [];
  renderDraftFiles(
    "draft-file-list",
    selectedDraftFiles,
    invalidateResubmission,
  );

  dialog.querySelector("[data-close-dialog]").addEventListener("click", () => {
    dialog.close();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  filesInput.addEventListener("change", () => {
    selectedDraftFiles.push(...Array.from(filesInput.files || []));
    filesInput.value = "";
    renderDraftFiles(
      "draft-file-list",
      selectedDraftFiles,
      invalidateResubmission,
    );
    invalidateResubmission();
  });
  dialog.querySelector("#resubmission-remarks").addEventListener("input", () => {
    revision += 1;
    analyzedPayload = null;
    submitButton.disabled = true;
    if (!busy && !report.classList.contains("hidden")) {
      report.className = "report-box";
      report.innerHTML =
        "<h3>Analysis is out of date</h3><p>Run a fresh check before resubmitting.</p>";
    }
  });

  analyzeButton.addEventListener("click", async () => {
    if (busy) return;
    if (!selectedDraftFiles.length) {
      notify("Select at least one file to resubmit.", "error");
      return;
    }
    busy = true;
    const analysisRevision = revision;
    analyzedPayload = null;
    submitButton.disabled = true;
    setBusy(analyzeButton, true, "Checking requirements…");
    report.className = "report-box";
    report.innerHTML =
      "<h3>AI Verification Report</h3><p>Checking the additional documents against ordinance requirements…</p>";
    try {
      const payload = {
        category: item.category,
        subject: item.subject,
        description: item.description,
        student_remarks: dialog
          .querySelector("#resubmission-remarks")
          .value.trim(),
        uploaded_files: await serializeUploads(),
      };
      const result = await requestJson("/workflow/student/analyze-draft", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (analysisRevision !== revision) {
        throw new Error(
          "The resubmission changed during analysis. Run the analysis again.",
        );
      }
      const deficiencies = Array.isArray(result.deficiencies)
        ? result.deficiencies
        : [];
      const canSubmit = deficiencies.length === 0 && result.can_submit === true;
      analyzedPayload = canSubmit ? JSON.stringify(payload) : null;
      report.className = `report-box ${canSubmit ? "is-pass" : "is-fail"}`;
      report.innerHTML = canSubmit
        ? "<h3>✓ Verified — no deficiencies found</h3><p>The new files passed the AI-assisted check. You may resubmit this application.</p>"
        : `<h3>Review needed · ${deficiencies.length || 1} item${deficiencies.length === 1 ? "" : "s"}</h3><ul>${(deficiencies.length ? deficiencies : ["The documents were not verified. Submission is blocked."]).map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`;
      submitButton.disabled = !canSubmit;
      dialog.querySelector("#resubmission-hint").textContent = canSubmit
        ? "Verified. Resubmission is enabled."
        : "Resolve the listed items and run the analysis again.";
    } catch (error) {
      report.className = "report-box is-fail";
      report.innerHTML = `<h3>Analysis unavailable</h3><p>${escapeHtml(error.message)}</p><p>Resubmission remains disabled until analysis succeeds.</p>`;
      notify(error.message, "error");
    } finally {
      busy = false;
      setBusy(analyzeButton, false);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!analyzedPayload || submitButton.disabled) {
      notify("Run AI Assisted Analysis and pass the document gate first.", "error");
      return;
    }
    setBusy(submitButton, true, "Resubmitting…");
    try {
      const payload = {
        uploaded_files: await serializeUploads(),
        student_remarks: dialog
          .querySelector("#resubmission-remarks")
          .value.trim(),
      };
      const checkedPayload = {
        category: item.category,
        subject: item.subject,
        description: item.description,
        student_remarks: payload.student_remarks,
        uploaded_files: payload.uploaded_files,
      };
      if (JSON.stringify(checkedPayload) !== analyzedPayload) {
        analyzedPayload = null;
        submitButton.disabled = true;
        throw new Error(
          "The resubmission changed after analysis. Run AI Assisted Analysis again.",
        );
      }
      const response = await requestJson(
        `/workflow/student/resubmit/${encodeURIComponent(item.id)}`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      notify(`Application #${item.id} resubmitted successfully.`);
      selectedDraftFiles = [];
      dialog.close();
      await loadStudentApplications();
    } catch (error) {
      notify(error.message, "error");
      if (!analyzedPayload) submitButton.disabled = true;
    } finally {
      if (submitButton.isConnected) {
        setBusy(submitButton, false);
        if (!analyzedPayload) submitButton.disabled = true;
      }
    }
  });
  dialog.addEventListener(
    "close",
    () => {
      selectedDraftFiles = [];
      dialog.remove();
    },
    { once: true },
  );
  dialog.showModal();
}

function showRemarksDialog({ title, description, label, placeholder, confirmLabel }) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "portal-dialog";
    dialog.innerHTML = `
      <form class="dialog-card remarks-dialog" method="dialog">
        <div class="dialog-heading">
          <div><span class="eyebrow">Application action</span><h2>${escapeHtml(title)}</h2></div>
          <button class="icon-button" type="button" data-cancel aria-label="Close dialog">×</button>
        </div>
        <p class="dialog-description">${escapeHtml(description)}</p>
        <label class="form-label" for="action-remarks">${escapeHtml(label)}</label>
        <textarea class="text-area" id="action-remarks" required minlength="1" placeholder="${escapeHtml(placeholder)}"></textarea>
        <div class="button-row dialog-actions">
          <button class="secondary-button" type="button" data-cancel>Cancel</button>
          <button class="primary-button" type="submit">${escapeHtml(confirmLabel)}</button>
        </div>
      </form>`;
    document.body.appendChild(dialog);
    const form = dialog.querySelector("form");
    const remarks = dialog.querySelector("#action-remarks");
    let result = null;
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = remarks.value.trim();
      if (!value) {
        remarks.setCustomValidity("Please enter a remark.");
        remarks.reportValidity();
        return;
      }
      result = value;
      dialog.close();
    });
    dialog.querySelectorAll("[data-cancel]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener(
      "close",
      () => {
        dialog.remove();
        resolve(result);
      },
      { once: true },
    );
    dialog.showModal();
    remarks.focus();
  });
}

function formatDate(value) {
  if (!value) return "date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function renderOfficialView(viewId) {
  if (viewId === "queue") {
    renderOfficialQueue();
  } else if (viewId === "workspace") {
    renderOfficialWorkspace();
  } else {
    renderSchedulerTools();
  }
}

function renderOfficialQueue() {
  const workspace = document.getElementById("workspace");
  workspace.innerHTML = `${pageHeading("Incoming applications", "Claim a student request to prepare a grounded five-heading RAG recommendation.", `<button class="secondary-button" id="refresh-official-queue" type="button">Refresh queue</button>`)}
        <div class="queue-list" id="official-queue"><div class="empty-state">Loading incoming applications…</div></div>`;
  document
    .getElementById("refresh-official-queue")
    .addEventListener("click", loadOfficialQueue);
  loadOfficialQueue();
}

async function loadOfficialQueue() {
  const container = document.getElementById("official-queue");
  if (!container) return;
  try {
    const response = await requestJson("/workflow/official/applications");
    officialApplications = response.applications || [];
    container.innerHTML = officialApplications.length
      ? officialApplications
          .map(
            (item) => {
              const needsAttention = [
                "RESUBMITTED",
                "RESCHEDULE_REQUESTED",
              ].includes(item.status);
              const canClaim = [
                "SUBMITTED",
                "UNDER_REVIEW",
                "RESUBMITTED",
                "RESCHEDULE_REQUESTED",
              ].includes(item.status);
              return `
                <article class="queue-card ${needsAttention ? "queue-card-attention" : ""}">
                    <div class="queue-card-top">
                        <div><h3>#${escapeHtml(item.id)} · ${escapeHtml(item.subject)}</h3><p>${escapeHtml(item.category)} · Student ${escapeHtml(item.student_reg_no)} · ${formatDate(item.created_at)}</p></div>
                        <span class="status-badge ${statusColor(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
                    </div>
                    ${needsAttention ? `<p class="attention-note">${item.status === "RESUBMITTED" ? "Updated documents submitted — priority review requested." : "DMPC requested a new meeting date — please propose a replacement range."}</p>` : ""}
                    <p>${escapeHtml(item.description)}</p>
                    ${item.student_remarks ? `<p><strong>Student remarks:</strong> ${escapeHtml(item.student_remarks)}</p>` : ""}
                    ${item.official_remarks && item.status === "RESCHEDULE_REQUESTED" ? `<p><strong>DMPC remark:</strong> ${escapeHtml(item.official_remarks)}</p>` : ""}
                    ${item.claimed_by ? `<p>Claimed by ${escapeHtml(item.claimed_by)}</p>` : ""}
                    <div class="button-row"><button class="primary-button claim-button" data-id="${escapeHtml(item.id)}" type="button" ${canClaim ? "" : "disabled"}>${canClaim ? needsAttention ? "Review Priority Application" : "Claim Application & Run RAG" : item.claimed_by ? `Claimed by ${escapeHtml(item.claimed_by)}` : "Not available"}</button></div>
                </article>`;
            },
          )
          .join("")
      : `<div class="empty-state">The official queue is clear. New student submissions will appear here.</div>`;
    container.querySelectorAll(".claim-button").forEach((button) => {
      button.addEventListener("click", () =>
        claimApplication(Number(button.dataset.id), button),
      );
    });
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Could not load official queue: ${escapeHtml(error.message)}</div>`;
  }
}

async function claimApplication(appId, button) {
  setBusy(button, true, "Claiming & generating recommendation…");
  try {
    const data = await requestJson(`/workflow/official/claim/${appId}`, {
      method: "POST",
    });
    selectedApplicationId = appId;
    notify(`Application #${appId} claimed. Recommendation generated.`);
    navigateView("workspace");
    renderClaimedWorkspace(data.application);
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
    loadOfficialQueue();
  }
}

function renderOfficialWorkspace() {
  const workspace = document.getElementById("workspace");
  workspace.innerHTML = `${pageHeading("Official review workspace", "Review the RAG recommendation, record a decision, or schedule a DMPC meeting.")}<div class="queue-list" id="claimed-workspace"><div class="empty-state">Loading claimed applications…</div></div>`;
  loadOfficialQueueForWorkspace();
}

async function loadOfficialQueueForWorkspace() {
  const container = document.getElementById("claimed-workspace");
  try {
    const response = await requestJson("/workflow/official/applications");
    officialApplications = response.applications || [];
    const session = getSession();
    const claimed = officialApplications.filter(
      (item) =>
        item.status === "CLAIMED_BY_OFFICIAL" &&
        item.claimed_by === session.username,
    );
    if (selectedApplicationId) {
      const selected = claimed.find(
        (item) => item.id === selectedApplicationId,
      );
      if (selected) return renderClaimedWorkspace(selected);
    }
    if (!claimed.length) {
      container.innerHTML = `<div class="empty-state">No applications are currently claimed by your account. Claim one from the incoming queue to open its review workspace.</div>`;
      return;
    }
    container.innerHTML = claimed
      .map(
        (item) => `
            <article class="queue-card">
                <div class="queue-card-top"><div><h3>#${escapeHtml(item.id)} · ${escapeHtml(item.subject)}</h3><p>${escapeHtml(item.category)} · ${escapeHtml(item.student_reg_no)}</p></div><span class="status-badge amber">Claimed by you</span></div>
                <p>${escapeHtml(item.description)}</p>
                <button class="primary-button open-workspace" data-id="${escapeHtml(item.id)}" type="button">Open review</button>
            </article>`,
      )
      .join("");
    container.querySelectorAll(".open-workspace").forEach((button) => {
      button.addEventListener("click", () => {
        selectedApplicationId = Number(button.dataset.id);
        const item = claimed.find(
          (record) => record.id === selectedApplicationId,
        );
        if (item) renderClaimedWorkspace(item);
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Could not load claimed applications: ${escapeHtml(error.message)}</div>`;
  }
}

function renderClaimedWorkspace(item) {
  selectedApplicationId = item.id;
  const workspace =
    document.getElementById("claimed-workspace") ||
    document.getElementById("workspace");
  if (!workspace) return;
  const recommendation =
    item.official_rag_recommendation ||
    "No recommendation is saved yet. Return to the incoming queue and claim this application to generate one.";
  workspace.innerHTML = `
        ${pageHeading(`Application #${item.id}`, "Official review · The recommendation is decision support for human review, not an automatic ruling.", `<span class="status-badge amber">${escapeHtml(statusLabel(item.status))}</span>`)}
        <div class="grid-two">
            <section class="panel">
                <h2 class="section-title">Student request</h2>
                <p><strong>Student:</strong> ${escapeHtml(item.student_name || item.student_reg_no)}</p>
                <p><strong>Category:</strong> ${escapeHtml(item.category)}</p>
                <p><strong>Subject:</strong> ${escapeHtml(item.subject)}</p>
                <p>${escapeHtml(item.description)}</p>
                ${renderUploadedFiles(item.uploaded_files)}
            </section>
            <section class="panel">
                <h2 class="section-title">Yogesh’s Official RAG Recommendation</h2>
                <p class="helper-text">Five-heading recommendation from retrieved ordinance clauses and synthetic precedent sources.</p>
                <div class="recommendation" id="recommendation-${escapeHtml(item.id)}">${inlineMarkdown(recommendation)}</div>
                <div class="chat-sources">${renderSourceList(item.official_rag_sources)}</div>
                ${item.official_rag_recommendation ? "" : `<button class="secondary-button" id="retry-recommendation" type="button">Generate recommendation</button>`}
            </section>
        </div>
        <section class="panel" style="margin-top:16px">
            <h2 class="section-title">Official action</h2>
            <label class="form-label" for="official-remarks">Remarks for the record</label>
            <textarea class="text-area" id="official-remarks" placeholder="Add a brief note supporting the next action."></textarea>
            <div class="button-row">
                <button class="secondary-button" id="mark-under-review" type="button">Mark Under Review</button>
                <button class="danger-button" id="send-back-student" type="button">Send Back to Student</button>
                <button class="primary-button" id="approve-directly" type="button">Approve</button>
                <button class="secondary-button" id="toggle-schedule-form" type="button">Schedule DMPC Meeting</button>
            </div>
            <form id="official-schedule-form" class="inline-form hidden">
                <div class="field-wrap"><label class="form-label" for="meeting-date-start">Date range start</label><input class="field" id="meeting-date-start" type="date" required></div>
                <div class="field-wrap"><label class="form-label" for="meeting-date-end">Date range end</label><input class="field" id="meeting-date-end" type="date" required></div>
                <div class="field-wrap span-two"><label class="form-label" for="meeting-agenda">DMPC agenda</label><textarea class="text-area" id="meeting-agenda" required>${escapeHtml(item.subject)} — Application #${escapeHtml(item.id)}</textarea></div>
                <div class="field-wrap"><label class="form-label" for="meeting-duration">Duration (minutes)</label><select class="select-field" id="meeting-duration"><option>60</option><option>90</option><option>120</option></select></div>
                <div class="field-wrap"><label class="form-label">Scheduling mode</label><label class="helper-text"><input id="meeting-use-gemini" type="checkbox" checked> Allow Gemini tool orchestration</label></div>
                <div class="span-two"><button class="primary-button" id="propose-workflow-meeting" type="submit">Find slots & send proposal</button></div>
            </form>
        </section>`;
  document
    .getElementById("approve-directly")
    .addEventListener("click", directApprove);
  document
    .getElementById("mark-under-review")
    .addEventListener("click", () =>
      submitOfficialAction("mark_under_review", "Application marked under review."),
    );
  document
    .getElementById("send-back-student")
    .addEventListener("click", sendBackToStudent);
  const retryRecommendation = document.getElementById("retry-recommendation");
  if (retryRecommendation) {
    retryRecommendation.addEventListener("click", () =>
      retryOfficialRecommendation(item.id, retryRecommendation),
    );
  }
  document
    .getElementById("toggle-schedule-form")
    .addEventListener("click", () => {
      document
        .getElementById("official-schedule-form")
        .classList.toggle("hidden");
    });
  document
    .getElementById("official-schedule-form")
    .addEventListener("submit", proposeWorkflowMeeting);
}

async function retryOfficialRecommendation(appId, button) {
  setBusy(button, true, "Generating recommendation…");
  try {
    const data = await requestJson(`/workflow/official/claim/${appId}`, {
      method: "POST",
    });
    renderClaimedWorkspace(data.application);
    notify("RAG recommendation generated.");
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

function renderUploadedFiles(files) {
  if (!Array.isArray(files) || !files.length)
    return `<p class="helper-text">No supporting files attached.</p>`;
  return `<div class="file-list">${files.map((file) => `<span class="file-pill">${escapeHtml(file.file_name || "Document")}</span>`).join("")}</div>`;
}

function renderSourceList(sources) {
  if (!Array.isArray(sources) || !sources.length)
    return "No source records saved.";
  return sources
    .map((source) => {
      const bits = [
        source.chunk_type,
        source.section && `Section ${source.section}`,
        source.clause && `Clause ${source.clause}`,
        source.source_file || source.chunk_id,
      ].filter(Boolean);
      return `• ${escapeHtml(bits.join(" · "))}`;
    })
    .join("<br>");
}

async function directApprove() {
  const button = document.getElementById("approve-directly");
  setBusy(button, true, "Saving decision…");
  try {
    await requestJson(`/workflow/official/decision/${selectedApplicationId}`, {
      method: "POST",
      body: JSON.stringify({
        decision: "approve",
        official_remarks: document.getElementById("official-remarks").value,
      }),
    });
    notify("Official approval recorded.");
    selectedApplicationId = null;
    navigateView("queue");
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

async function submitOfficialAction(decision, successMessage, remarks) {
  try {
    await requestJson(`/workflow/official/decision/${selectedApplicationId}`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        official_remarks:
          remarks ?? document.getElementById("official-remarks")?.value.trim() ?? "",
      }),
    });
    notify(successMessage);
    selectedApplicationId = null;
    navigateView("queue");
  } catch (error) {
    notify(error.message, "error");
  }
}

async function sendBackToStudent() {
  const remarks = await showRemarksDialog({
    title: "Send application back",
    description:
      "The student will see these remarks and can resubmit corrected or missing documents.",
    label: "Required official remarks",
    placeholder: "List each missing or incorrect document and what needs correction.",
    confirmLabel: "Send Back to Student",
  });
  if (remarks === null) return;
  await submitOfficialAction(
    "send_back_deficiency",
    "Application returned to the student with deficiency remarks.",
    remarks,
  );
}

async function proposeWorkflowMeeting(event) {
  event.preventDefault();
  const button = document.getElementById("propose-workflow-meeting");
  const start = document.getElementById("meeting-date-start").value;
  const end = document.getElementById("meeting-date-end").value;
  if (!start || !end || end < start) {
    notify("Choose a valid date range.", "error");
    return;
  }
  setBusy(button, true, "Checking calendars & proposing…");
  try {
    const data = await requestJson(
      `/workflow/official/decision/${selectedApplicationId}`,
      {
        method: "POST",
        body: JSON.stringify({
          decision: "schedule_meeting",
          official_remarks: document.getElementById("official-remarks").value,
          date_range: `${start} to ${end}`,
          agenda: document.getElementById("meeting-agenda").value.trim(),
          duration_minutes: Number(
            document.getElementById("meeting-duration").value,
          ),
          use_gemini: document.getElementById("meeting-use-gemini").checked,
        }),
      },
    );
    notify(`DMPC proposal ${data.application.scheduler_proposal_id} created.`);
    selectedApplicationId = null;
    navigateView("queue");
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

function renderSchedulerTools() {
  const workspace = document.getElementById("workspace");
  workspace.innerHTML = `
        ${pageHeading("Scheduler tools", "Standalone scheduling utility using the existing /schedule/* endpoints. Application-linked meetings should be proposed from the review workspace.")}
        <div class="grid-two">
            <section class="panel">
                <h2 class="section-title">Propose a committee meeting</h2>
                <form id="standalone-schedule-form">
                    <div class="field-wrap"><label class="form-label" for="standalone-committee">Committee</label><select class="select-field" id="standalone-committee"><option>DMPC</option><option>DUGC</option><option>DDPC</option></select></div>
                    <div class="field-wrap"><label class="form-label" for="standalone-start">Date range start</label><input class="field" id="standalone-start" type="date" required></div>
                    <div class="field-wrap"><label class="form-label" for="standalone-end">Date range end</label><input class="field" id="standalone-end" type="date" required></div>
                    <div class="field-wrap"><label class="form-label" for="standalone-duration">Duration</label><select class="select-field" id="standalone-duration"><option>60</option><option>90</option><option>120</option></select></div>
                    <div class="field-wrap"><label class="form-label" for="standalone-agenda">Agenda</label><textarea class="text-area" id="standalone-agenda" required></textarea></div>
                    <button class="primary-button" id="standalone-propose" type="submit">Propose meeting</button>
                </form>
            </section>
            <section class="panel">
                <div class="panel-heading" style="padding:0 0 14px;border:0"><h2>Recent proposals</h2><button class="secondary-button" id="refresh-proposals" type="button">Refresh</button></div>
                <div class="queue-list" id="standalone-proposals"><div class="empty-state">Loading proposals…</div></div>
            </section>
        </div>`;
  document
    .getElementById("standalone-schedule-form")
    .addEventListener("submit", createStandaloneProposal);
  document
    .getElementById("refresh-proposals")
    .addEventListener("click", loadStandaloneProposals);
  loadStandaloneProposals();
}

async function createStandaloneProposal(event) {
  event.preventDefault();
  const start = document.getElementById("standalone-start").value;
  const end = document.getElementById("standalone-end").value;
  if (!start || !end || end < start)
    return notify("Choose a valid date range.", "error");
  const button = document.getElementById("standalone-propose");
  setBusy(button, true, "Finding slots…");
  try {
    const data = await requestJson(
      "/schedule/propose",
      {
        method: "POST",
        body: JSON.stringify({
          committee_name: document.getElementById("standalone-committee").value,
          date_range: `${start} to ${end}`,
          agenda: document.getElementById("standalone-agenda").value.trim(),
          duration_minutes: Number(
            document.getElementById("standalone-duration").value,
          ),
          use_gemini: false,
        }),
      },
      false,
    );
    notify(
      `Proposal ${data.proposal?.proposal_id || data.proposal_id || ""} created.`,
    );
    await loadStandaloneProposals();
  } catch (error) {
    notify(error.message, "error");
  } finally {
    setBusy(button, false);
  }
}

async function loadStandaloneProposals() {
  const container = document.getElementById("standalone-proposals");
  if (!container) return;
  try {
    const data = await requestJson("/schedule/proposals", {}, false);
    const proposals = data.proposals || [];
    container.innerHTML = proposals.length
      ? proposals
          .slice()
          .reverse()
          .map((proposal) => standaloneProposalCard(proposal))
          .join("")
      : `<div class="empty-state">No meeting proposals created yet.</div>`;
    container.querySelectorAll(".standalone-approve").forEach((button) => {
      button.addEventListener("click", () =>
        approveStandaloneProposal(
          button.dataset.id,
          Number(button.dataset.slot),
          button,
        ),
      );
    });
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Could not load scheduler proposals: ${escapeHtml(error.message)}</div>`;
  }
}

function standaloneProposalCard(proposal) {
  const slots = proposal.slots || [];
  return `<article class="queue-card">
        <h3>${escapeHtml(proposal.proposal_id)} · ${escapeHtml(proposal.committee)}</h3>
        <p>${escapeHtml(proposal.agenda)} · ${escapeHtml(proposal.date_range)}</p>
        <p>Status: ${escapeHtml(proposal.status)}</p>
        <div class="proposal-slots">${slots.map((slot, index) => `<div class="proposal-slot">${index + 1}. ${escapeHtml(slot.date)} · ${escapeHtml(slot.start)}–${escapeHtml(slot.end)} · ${escapeHtml(slot.weekday || "")}</div>`).join("") || "<div class='proposal-slot'>No available slots.</div>"}</div>
        ${proposal.status === "awaiting_hod_consent" && slots.length ? `<div class="button-row">${slots.map((_, index) => `<button class="secondary-button standalone-approve" data-id="${escapeHtml(proposal.proposal_id)}" data-slot="${index + 1}" type="button">Approve slot ${index + 1}</button>`).join("")}</div>` : ""}
    </article>`;
}

async function approveStandaloneProposal(proposalId, slotIndex, button) {
  setBusy(button, true, "Issuing invite…");
  try {
    await requestJson(
      "/schedule/approve",
      {
        method: "POST",
        body: JSON.stringify({
          proposal_id: proposalId,
          approved: true,
          slot_index: slotIndex,
          use_gemini: false,
        }),
      },
      false,
    );
    notify("Meeting approved. Mock email and calendar invite dispatched.");
    await loadStandaloneProposals();
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

function renderDmpcView() {
  const workspace = document.getElementById("workspace");
  workspace.innerHTML = `${pageHeading("DMPC committee portal", "Review proposed meeting slots, approve the schedule, and prepare official minutes.", `<button class="secondary-button" id="refresh-dmpc" type="button">Refresh queue</button>`)}
        <div class="queue-list" id="dmpc-queue"><div class="empty-state">Loading committee applications…</div></div>`;
  document
    .getElementById("refresh-dmpc")
    .addEventListener("click", loadDmpcQueue);
  loadDmpcQueue();
}

async function loadDmpcQueue() {
  const container = document.getElementById("dmpc-queue");
  if (!container) return;
  try {
    const response = await requestJson("/workflow/dmpc/applications");
    dmpcApplications = response.applications || [];
    container.innerHTML = dmpcApplications.length
      ? dmpcApplications.map((item) => renderDmpcCard(item)).join("")
      : `<div class="empty-state">No applications are waiting for DMPC action.</div>`;
    container.querySelectorAll(".approve-meeting").forEach((button) => {
      button.addEventListener("click", () =>
        approveDmpcMeeting(
          Number(button.dataset.id),
          Number(button.dataset.slot),
          button,
        ),
      );
    });
    container.querySelectorAll(".request-reschedule").forEach((button) => {
      button.addEventListener("click", () =>
        requestDmpcReschedule(Number(button.dataset.id), button),
      );
    });
    container.querySelectorAll(".minutes-form").forEach((form) => {
      form.addEventListener("submit", generateMinutes);
    });
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Could not load DMPC queue: ${escapeHtml(error.message)}</div>`;
  }
}

function renderDmpcCard(item) {
  const proposal = item.scheduler_proposal_data || {};
  const slots = proposal.slots || [];
  const meetingProposed = item.status === "MEETING_PROPOSED";
  const meetingScheduled = ["MEETING_SCHEDULED", "MINUTES_GENERATED"].includes(
    item.status,
  );
  const approvedSlot = item.approved_slot || {};
  return `<article class="queue-card">
        <div class="queue-card-top">
            <div><h3>#${escapeHtml(item.id)} · ${escapeHtml(item.subject)}</h3><p>${escapeHtml(item.category)} · Student ${escapeHtml(item.student_reg_no)}</p></div>
            <span class="status-badge ${statusColor(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <p>${escapeHtml(item.description)}</p>
        ${item.official_rag_recommendation ? `<details><summary class="form-label">View official recommendation</summary><div class="recommendation">${inlineMarkdown(item.official_rag_recommendation)}</div></details>` : ""}
        ${
          meetingProposed
            ? `<p><strong>Proposal:</strong> ${escapeHtml(item.scheduler_proposal_id || "")}</p>
            <div class="proposal-slots">${slots.map((slot, index) => `<label class="proposal-slot"><input type="radio" name="slot-${escapeHtml(item.id)}" value="${index + 1}" ${index === 0 ? "checked" : ""}> ${index + 1}. ${escapeHtml(slot.date)} · ${escapeHtml(slot.start)}–${escapeHtml(slot.end)} · ${escapeHtml(slot.weekday || "")}</label>`).join("") || "<div class='proposal-slot'>No available slots were returned. Ask the official to create a new date range.</div>"}</div>
            <div class="button-row">${slots.length ? `<button class="primary-button approve-meeting" data-id="${escapeHtml(item.id)}" type="button">Approve Meeting Schedule & Issue Invite</button>` : ""}
            <button class="secondary-button request-reschedule" data-id="${escapeHtml(item.id)}" type="button">Request Reschedule</button></div>`
            : ""
        }
        ${meetingScheduled ? `<p><strong>Approved slot:</strong> ${escapeHtml(approvedSlot.date || "")} ${escapeHtml(approvedSlot.start || "")}–${escapeHtml(approvedSlot.end || "")}</p>` : ""}
        ${
          meetingScheduled
            ? `
            <form class="minutes-form" data-id="${escapeHtml(item.id)}">
                <div class="inline-form">
                    <div class="field-wrap span-two"><label class="form-label" for="meeting-notes-${escapeHtml(item.id)}">Meeting notes</label><textarea class="text-area" id="meeting-notes-${escapeHtml(item.id)}" name="meeting_notes" placeholder="Record the discussion and member observations.">${escapeHtml(item.meeting_notes || "")}</textarea></div>
                    <div class="field-wrap span-two"><label class="form-label" for="final-decision-${escapeHtml(item.id)}">Final decision</label><textarea class="text-area" id="final-decision-${escapeHtml(item.id)}" name="final_decision" required placeholder="Enter the committee's approved decision.">${escapeHtml(item.final_decision || "")}</textarea></div>
                    <div class="span-two"><button class="primary-button" type="submit">${item.status === "MINUTES_GENERATED" ? "Regenerate Official Minutes" : "Generate Official Minutes"}</button></div>
                </div>
            </form>
            ${item.generated_minutes ? `<div class="minutes-output">${inlineMarkdown(item.generated_minutes)}</div>` : ""}
            <div class="minutes-output hidden" id="generated-minutes-${escapeHtml(item.id)}"></div>`
            : ""
        }
    </article>`;
}

async function approveDmpcMeeting(appId, slotIndex, button) {
  setBusy(button, true, "Issuing official invite…");
  try {
    const data = await requestJson(`/workflow/dmpc/approve-meeting/${appId}`, {
      method: "POST",
      body: JSON.stringify({
        slot_index: slotIndex,
        hod_comment: "",
        use_gemini: false,
      }),
    });
    notify("Schedule approved. Mock email and calendar invitation dispatched.");
    await loadDmpcQueue();
    const card = document.querySelector(`#dmpc-queue .queue-card`);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

async function requestDmpcReschedule(appId, button) {
  const remarks = await showRemarksDialog({
    title: "Request a new meeting date",
    description:
      "The application will return to the Official queue so a replacement date range can be proposed.",
    label: "Reason for rescheduling",
    placeholder: "For example, a committee member is unavailable on the proposed dates.",
    confirmLabel: "Request Reschedule",
  });
  if (remarks === null) return;
  setBusy(button, true, "Sending request…");
  try {
    await requestJson(`/workflow/dmpc/approve-meeting/${appId}`, {
      method: "POST",
      body: JSON.stringify({
        action: "request_reschedule",
        hod_comment: remarks,
      }),
    });
    notify("Reschedule requested. The Official has been notified in the queue.");
    await loadDmpcQueue();
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

async function generateMinutes(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const appId = Number(form.dataset.id);
  const button = form.querySelector("button[type=submit]");
  const output = document.getElementById(`generated-minutes-${appId}`);
  const values = new FormData(form);
  const finalDecision = String(values.get("final_decision") || "").trim();
  if (!finalDecision) {
    notify(
      "Enter the committee's final decision before generating minutes.",
      "error",
    );
    return;
  }
  setBusy(button, true, "Drafting official minutes…");
  try {
    const data = await requestJson(`/workflow/dmpc/generate-minutes/${appId}`, {
      method: "POST",
      body: JSON.stringify({
        meeting_notes: values.get("meeting_notes") || "",
        final_decision: finalDecision,
      }),
    });
    output.classList.remove("hidden");
    output.innerHTML = inlineMarkdown(data.minutes);
    notify("Minutes generated and saved to the application record.");
    await loadDmpcQueue();
  } catch (error) {
    notify(error.message, "error");
    setBusy(button, false);
  }
}

function renderApp() {
  const session = getSession();
  if (!session) {
    showLogin();
    return;
  }
  const hash = window.location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean);
  const role = session.role;
  if (parts[0] && parts[0] !== role) {
    goToRole(role);
    return;
  }
  const viewId = parts[1] || ROLE_VIEWS[role][0].id;
  renderShell(session, viewId);
}

window.addEventListener("hashchange", renderApp);
renderApp();
