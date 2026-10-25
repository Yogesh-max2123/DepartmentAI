import { renderSidebar } from "./components/layout/sidebar.js";
import { renderTopbar } from "./components/layout/topbar.js";

import { renderLoginPage } from "./pages/login/login-page.js";

import { renderStudentLogin } from "./components/auth/student-login.js";
import { renderOfficialLogin } from "./components/auth/official-login.js";
import { renderDUGCLogin } from "./components/auth/dugc-login.js";

import { renderStudentDashboard } from "./pages/student/student-dashboard.js";
import {
  renderRoleDashboard,
  renderRoleSettings,
  renderRoleWorkspacePage,
} from "./pages/role-workspaces.js?v=session-persistence";

import {
  APIError,
  askQuestion,
  classifyApplicationDocument,
  assignApplicationToCommittee,
  createApplication,
  downloadApplicationDocument,
  extractApplicationDocument,
  generateApplicationAnalysis,
  getApplication,
  getApplicationDocuments,
  getCommitteeReviews,
  getDeficiencies,
  getEligibility,
  listApplications,
  getStatusHistory,
  getUnassignedOfficialApplications,
  claimOfficialApplication,
  submitApplication,
  updateApplicationStatus,
  updateCommitteeDecision,
  uploadApplicationDocument,
  validateApplicationDocument,
} from "./services/api.js?v=session-persistence";
import {
  loginUser,
  getCurrentUser,
  logoutUser,
  restoreSession,
} from "./services/auth.js?v=session-persistence";
const appState = {
  currentUser: getCurrentUser(),
  currentPage: "dashboard",
  selectedLoginRole: null,
  selectedApplicationId: null,
  queueRequestIds: new Map(),
  applicationDetailsRequestId: 0,
  roleWorkspaceRequestId: 0,
  documentListRequestId: 0,
  documentUploadInProgress: false,
  documentActionsInProgress: new Set(),
  documentActionResults: {},
  academicReviewState: null,
  academicReviewRequestId: 0,
  academicReviewActionsInProgress: new Set(),
  aiAnalysisState: null,
  aiAnalysisActionsInProgress: new Set(),
  applicationWorkflowState: null,
  assistantState: {
    messages: [
      {
        role: "assistant",
        content:
          "Ask about undergraduate ordinances, degree requirements, or departmental procedures. Responses are informational only and should be checked against official rules and authorized human decisions.",
        sources: [],
      },
    ],
    isLoading: false,
    error: null,
  },
};

const pageTitles = {
  dashboard: "Dashboard",
  assistant: "Academic Assistant",
  applications: "My Applications",
  "create-application": "Create Application",
  "application-details": "Application Details",
  "application-processing": "Application Processing",
  committee: "Committee Workspace",
  "decision-history": "Decision History",
  audit: "Audit Trail",
  settings: "Settings",
};

/* =========================================================
   Application Initialization
   ========================================================= */

function initializeApp() {
  window.addEventListener("departmentai:session-expired", handleSessionExpired);
  void restoreApplicationSession();
}

async function restoreApplicationSession() {
  const app = document.getElementById("app");
  app.innerHTML = '<main class="session-loading" role="status">Checking your session…</main>';
  try {
    appState.currentUser = await restoreSession();
    if (appState.currentUser) {
      renderApplicationShell();
      setupApplicationEvents();
      navigateTo("dashboard");
    } else {
      renderLogin();
    }
  } catch (error) {
    appState.currentUser = null;
    renderLogin();
    const message = document.getElementById("login-global-message");
    if (message) {
      message.textContent =
        error instanceof APIError
          ? error.message
          : "Unable to verify your session. Please try again.";
      message.hidden = false;
    }
  }
}

/* =========================================================
   Login
   ========================================================= */

function renderLogin() {
  const app = document.getElementById("app");

  app.innerHTML = renderLoginPage();

  setupLoginEvents();
}

function setupLoginEvents() {
  const app = document.getElementById("app");

  app.onclick = handleLoginClick;

  app.onsubmit = handleLoginSubmit;
}

function handleLoginClick(event) {
  const roleButton = event.target.closest("[data-login-role]");

  if (roleButton) {
    selectLoginRole(roleButton.dataset.loginRole);

    return;
  }

  const changeRoleButton = event.target.closest("#change-login-role");

  if (changeRoleButton) {
    showRoleSelection();
  }
}

function selectLoginRole(role) {
  appState.selectedLoginRole = role;

  const roleSelection = document.getElementById("login-role-selection");

  const formContainer = document.getElementById("login-form-container");

  const selectedRoleLogin = document.getElementById("selected-role-login");

  if (!roleSelection || !formContainer || !selectedRoleLogin) {
    return;
  }

  roleSelection.classList.add("hidden");

  formContainer.classList.remove("hidden");

  if (role === "STUDENT") {
    selectedRoleLogin.innerHTML = renderStudentLogin();
  } else if (role === "OFFICIAL") {
    selectedRoleLogin.innerHTML = renderOfficialLogin();
  } else if (role === "DUGC") {
    selectedRoleLogin.innerHTML = renderDUGCLogin();
  }
}

async function handleLoginSubmit(event) {
  const form = event.target;

  if (!form.classList.contains("role-login-form")) {
    return;
  }

  event.preventDefault();

  const role = appState.selectedLoginRole;

  if (!role) {
    return;
  }

  const formData = new FormData(form);

  const submitButton = form.querySelector('button[type="submit"]');
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Signing in…";
  }
  try {
    const user = await loginUser(role, formData);
    if (!user) {
      showLoginError(role, "Enter your account username and password.");
      return;
    }

    appState.currentUser = user;
    appState.currentPage = "dashboard";
    appState.selectedLoginRole = null;
    renderApplicationShell();
    setupApplicationEvents();
    navigateTo("dashboard");
  } catch (error) {
    showLoginError(
      role,
      error instanceof APIError
        ? error.message
        : "Sign-in failed. Verify the account type and try again.",
    );
  } finally {
    if (submitButton?.isConnected) {
      submitButton.disabled = false;
      submitButton.textContent = "Sign in";
    }
  }
}

function handleSessionExpired() {
  appState.currentUser = null;
  appState.currentPage = "dashboard";
  appState.selectedLoginRole = null;
  renderLogin();
  const message = document.getElementById("login-global-message");
  if (message) {
    message.textContent =
      "Your session expired or was revoked. Sign in again.";
    message.hidden = false;
  }
}

function showLoginError(role, message) {
  const errorElement = document.getElementById(
    `${role.toLowerCase()}-login-error`,
  );

  if (!errorElement) {
    return;
  }

  errorElement.textContent = message;

  errorElement.classList.remove("hidden");
}

function showRoleSelection() {
  appState.selectedLoginRole = null;

  const roleSelection = document.getElementById("login-role-selection");

  const formContainer = document.getElementById("login-form-container");

  if (!roleSelection || !formContainer) {
    return;
  }

  formContainer.classList.add("hidden");

  roleSelection.classList.remove("hidden");

  const selectedRoleLogin = document.getElementById("selected-role-login");

  if (selectedRoleLogin) {
    selectedRoleLogin.innerHTML = "";
  }
}

/* =========================================================
   Application Shell
   ========================================================= */

function renderApplicationShell() {
  const app = document.getElementById("app");

  app.innerHTML = `
        <aside id="sidebar"></aside>

        <div class="main-shell">

            <header id="topbar"></header>

            <main
                id="page-content"
                class="page-content"
            ></main>

        </div>
    `;

  renderShell();
}

function renderShell() {
  const sidebar = document.getElementById("sidebar");

  const topbar = document.getElementById("topbar");

  if (sidebar) {
    sidebar.innerHTML = renderSidebar(
      appState.currentPage,
      appState.currentUser,
    );
  }

  if (topbar) {
    topbar.innerHTML = renderTopbar(appState.currentUser);
  }
}

/* =========================================================
   Page Navigation
   ========================================================= */
function navigateTo(page) {
  if (!appState.currentUser) {
    renderLogin();
    return;
  }

  appState.roleWorkspaceRequestId += 1;
  appState.currentPage = page;

  const pageContent = document.getElementById("page-content");

  if (!pageContent) {
    return;
  }

  if (appState.currentUser.role === "STUDENT") {
    pageContent.innerHTML = renderStudentPage(page);
  } else if (page === "dashboard") {
    pageContent.innerHTML = renderRoleDashboard(
      appState.currentUser.role,
      appState.currentUser,
    );
  } else if (page === "assistant") {
    pageContent.innerHTML = renderStudentAssistantPage();
  } else {
    pageContent.innerHTML = renderRoleWorkspacePage(
      appState.currentUser.role,
      page,
    );
  }

  updateNavigation();
  updatePageTitle();

  if (page === "application-details") {
    void loadStudentApplicationDetails(appState.selectedApplicationId);
    void loadApplicationDocuments(appState.selectedApplicationId);
    restoreAcademicReviewPanels(appState.selectedApplicationId);
    restoreAiAnalysisPanel(appState.selectedApplicationId);
    restoreApplicationWorkflowPanels(appState.selectedApplicationId);
    void loadApplicationWorkflowPanel(
      appState.selectedApplicationId,
      "statusHistory",
      true,
    );
    void loadApplicationWorkflowPanel(
      appState.selectedApplicationId,
      "committeeReviews",
      true,
    );
  }
  if (page === "applications") {
    if (appState.currentUser.role === "STUDENT") {
      void loadApplicationQueue("student-application-list", "application-details");
    } else {
      void loadRoleWorkspaceQueue();
    }
  } else if (page === "dashboard" && appState.currentUser.role === "STUDENT") {
    void loadApplicationQueue("student-recent-applications", "application-details", 5);
  }
}

function renderStudentPage(page) {
  if (page === "dashboard") {
    return renderStudentDashboard(appState.currentUser);
  }

  if (page === "applications") {
    return renderStudentApplicationsPage();
  }

  if (page === "create-application") {
    return renderStudentCreateApplicationPage();
  }

  if (page === "application-details") {
    return renderStudentApplicationDetailsPage();
  }

  if (page === "assistant") {
    return renderStudentAssistantPage();
  }

  if (page === "settings") {
    return renderStudentSettingsPage();
  }

  return renderRoleWorkspacePage("STUDENT", page);
}

function renderStudentApplicationsPage() {
  return `
    <section class="page-section applications-page" aria-labelledby="applications-title">
      <header class="applications-heading">
        <div class="applications-heading-copy">
          <span class="eyebrow">Student Workspace</span>
          <h1 id="applications-title">My Applications</h1>
          <p>View your academic application records and their progress in one place.</p>
        </div>
        <button type="button" class="secondary-button" data-page="dashboard">
          <span aria-hidden="true">←</span>
          Back to Dashboard
        </button>
      </header>

      <section id="student-application-list" class="applications-empty-state" aria-live="polite" aria-busy="true">
        <p role="status">Loading your applications…</p>
      </section>
    </section>
  `;
}

async function loadApplicationQueue(
  containerId,
  destinationPage,
  limit = 20,
  load = listApplications,
  emptyMessage = "No applications are currently available to this account.",
) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  const requestId = (appState.queueRequestIds.get(containerId) || 0) + 1;
  appState.queueRequestIds.set(containerId, requestId);
  container.replaceChildren();
  container.setAttribute("aria-busy", "true");
  const loading = document.createElement("p");
  loading.setAttribute("role", "status");
  loading.textContent = "Loading applications…";
  container.append(loading);

  try {
    const response = await load({ limit, offset: 0 });
    if (
      requestId !== appState.queueRequestIds.get(containerId) ||
      !container.isConnected
    ) {
      return;
    }
    if (!Array.isArray(response?.items)) {
      throw new Error("The application list response was invalid.");
    }
    container.replaceChildren();
    if (response.items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "applications-availability";
      empty.textContent = emptyMessage;
      container.append(empty);
      if (appState.currentUser?.role === "STUDENT") {
        const createButton = document.createElement("button");
        createButton.type = "button";
        createButton.className = "primary-button";
        createButton.dataset.page = "create-application";
        createButton.textContent = "Create Application";
        container.append(createButton);
      }
      return;
    }

    const list = document.createElement("ul");
    list.className = "application-queue-list";
    for (const application of response.items) {
      if (!Number.isSafeInteger(application?.id) || application.id < 1) {
        continue;
      }
      const item = document.createElement("li");
      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.className = "application-queue-item";
      openButton.dataset.applicationId = String(application.id);
      openButton.dataset.page = destinationPage;
      const number = document.createElement("strong");
      number.textContent =
        typeof application.application_number === "string"
          ? application.application_number
          : `Application ${application.id}`;
      const description = document.createElement("span");
      description.textContent = [
        application.title,
        application.application_type,
        application.status,
      ]
        .filter((value) => typeof value === "string" && value.trim())
        .join(" · ");
      openButton.append(number, description);
      item.append(openButton);
      if (containerId === "official-unassigned-list") {
        const claimButton = document.createElement("button");
        claimButton.type = "button";
        claimButton.className = "secondary-button";
        claimButton.dataset.action = "claim-official-application";
        claimButton.dataset.applicationId = String(application.id);
        claimButton.textContent = "Claim application";
        item.append(claimButton);
      }
      list.append(item);
    }
    if (!list.childElementCount) {
      throw new Error("The application list contained no valid records.");
    }
    container.append(list);
  } catch (error) {
    if (
      requestId !== appState.queueRequestIds.get(containerId) ||
      !container.isConnected
    ) {
      return;
    }
    container.replaceChildren();
    const message = document.createElement("p");
    message.className = "role-workspace-unavailable";
    message.setAttribute("role", "alert");
    message.textContent =
      error instanceof APIError
        ? error.message
        : "Unable to load applications. Please try again.";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary-button";
    retry.dataset.action = "retry-application-queue";
    retry.dataset.queueContainer = containerId;
    retry.dataset.queuePage = destinationPage;
    retry.dataset.queueLimit = String(limit);
    retry.dataset.queueType =
      containerId === "official-unassigned-list"
        ? "unassigned-official"
        : "assigned";
    retry.textContent = "Try again";
    container.append(message, retry);
  } finally {
    if (
      requestId === appState.queueRequestIds.get(containerId) &&
      container.isConnected
    ) {
      container.setAttribute("aria-busy", "false");
    }
  }
}

function loadRoleWorkspaceQueue() {
  if (appState.currentUser?.role === "OFFICIAL") {
    void loadApplicationQueue(
      "official-unassigned-list",
      "application-processing",
      20,
      getUnassignedOfficialApplications,
      "No unassigned submissions are waiting for an Official.",
    );
  }
  const destinationPage =
    appState.currentUser?.role === "DUGC"
      ? "committee"
      : "application-processing";
  return loadApplicationQueue(
    "role-application-list",
    destinationPage,
  );
}

async function claimOfficialQueueApplication(button) {
  const applicationId = Number(button.dataset.applicationId);
  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    return;
  }

  button.disabled = true;
  button.textContent = "Claiming…";
  const container = document.getElementById("official-unassigned-list");
  try {
    await claimOfficialApplication(applicationId);
    await Promise.all([
      loadApplicationQueue(
        "official-unassigned-list",
        "application-processing",
        20,
        getUnassignedOfficialApplications,
        "No unassigned submissions are waiting for an Official.",
      ),
      loadApplicationQueue(
        "role-application-list",
        "application-processing",
      ),
    ]);
    if (container?.isConnected) {
      const message = document.createElement("p");
      message.setAttribute("role", "status");
      message.textContent =
        "The application was claimed and added to your assigned applications.";
      container.append(message);
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = "Claim application";
    const message = document.createElement("p");
    message.setAttribute("role", "alert");
    message.textContent =
      error instanceof APIError
        ? error.message
        : "The application could not be claimed. Refresh the queue and try again.";
    button.parentElement?.append(message);
  }
}

async function submitStudentApplicationFromDetails(button) {
  const applicationId = appState.selectedApplicationId;
  const content = document.getElementById("application-details-content");
  if (!Number.isSafeInteger(applicationId) || applicationId <= 0 || !content) {
    return;
  }

  button.disabled = true;
  button.textContent = "Submitting…";
  try {
    const response = await submitApplication(applicationId);
    if (response?.new_status !== "SUBMITTED") {
      throw new Error("The service did not confirm application submission.");
    }
    await loadStudentApplicationDetails(applicationId);
    await loadApplicationWorkflowPanel(applicationId, "statusHistory", true);
  } catch (error) {
    const message = document.createElement("p");
    message.setAttribute("role", "alert");
    message.textContent =
      error instanceof APIError
        ? error.message
        : "The application could not be submitted. Please refresh and try again.";
    content.append(message);
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.textContent = "Submit to Official queue";
    }
  }
}

function renderStudentCreateApplicationPage() {
  return `
    <section class="page-section create-application-page" aria-labelledby="create-application-title">
      <header class="applications-heading">
        <div class="applications-heading-copy">
          <span class="eyebrow">Student Workspace</span>
          <h1 id="create-application-title">Create Application</h1>
          <p>Provide the details for your academic request. The department will review it through the established process.</p>
        </div>
        <button type="button" class="secondary-button" data-page="dashboard">
          <span aria-hidden="true">←</span>
          Back to Dashboard
        </button>
      </header>

      <div class="create-application-grid">
        <aside class="create-application-guidance" aria-labelledby="application-guidance-title">
          <span class="applications-state-label">Before you begin</span>
          <h2 id="application-guidance-title">A clear request helps the department review your application.</h2>
          <p>New applications are created as drafts. You can provide a concise title and describe the request if those details are useful.</p>
        </aside>

        <div class="create-application-form-panel">
          <form id="create-application-form" novalidate>
            <div class="create-application-form-fields">
              <div class="create-application-field">
                <label for="application-type">
                  Application type <span class="required-indicator">Required</span>
                </label>
                <input
                  id="application-type"
                  name="application_type"
                  type="text"
                  autocomplete="off"
                  aria-describedby="application-type-help"
                  required
                />
                <small id="application-type-help">Enter the type of academic request you are making.</small>
              </div>

              <div class="create-application-field">
                <label for="application-title">Application title <span>Optional</span></label>
                <input
                  id="application-title"
                  name="title"
                  type="text"
                  autocomplete="off"
                  placeholder="A short description of your request"
                />
              </div>

              <div class="create-application-field">
                <label for="application-description">Description <span>Optional</span></label>
                <textarea
                  id="application-description"
                  name="description"
                  rows="5"
                  placeholder="Add any context that may help explain your request"
                ></textarea>
              </div>

              <p id="application-submit-error" class="application-submit-error" role="alert" hidden></p>
              <p id="application-submit-loading" class="application-submit-loading" role="status" aria-live="polite" hidden>
                Creating your application…
              </p>

              <div class="create-application-actions">
                <button type="button" class="secondary-button" data-page="applications">Back to My Applications</button>
                <button id="create-application-submit" type="submit" class="primary-button">Create Application</button>
              </div>
            </div>
          </form>

          <section id="application-submit-success" class="application-submit-success" aria-labelledby="application-success-title" hidden>
            <span class="application-success-mark" aria-hidden="true">✓</span>
            <h2 id="application-success-title">Application created</h2>
            <p id="application-success-message">The service confirmed that your application was created.</p>
            <div id="application-success-details"></div>
            <div class="create-application-actions">
              <button type="button" class="secondary-button" data-page="applications">My Applications</button>
              <button type="button" class="primary-button" data-page="dashboard">Back to Dashboard</button>
            </div>
          </section>
        </div>
      </div>
        </section>
  `;
}

function renderStudentApplicationDetailsPage() {
  return `
    <section class="page-section application-details-page" aria-labelledby="application-details-title">
      <header class="applications-heading">
        <div class="applications-heading-copy">
          <span class="eyebrow">Student Workspace</span>
          <h1 id="application-details-title">Application Details</h1>
          <p>Review the information returned for this application.</p>
        </div>
        <div class="application-details-navigation">
          <button type="button" class="secondary-button" data-page="applications">My Applications</button>
          <button type="button" class="secondary-button" data-page="dashboard">Dashboard</button>
        </div>
      </header>

      <section
        id="application-details-content"
        class="application-details-content"
        aria-live="polite"
        aria-busy="true"
      >
        <p class="application-details-loading" role="status">Loading application details…</p>
      </section>

      <section class="application-workflow" aria-labelledby="application-status-history-title">
        <header class="application-workflow-heading">
          <span class="applications-state-label">Application lifecycle</span>
          <h2 id="application-status-history-title">Status history</h2>
          <p>Current status is shown above. Status changes are controlled by authorized department staff.</p>
        </header>
        <div id="application-status-history" class="application-workflow-panel" aria-live="polite" aria-busy="true">
          <p class="application-workflow-loading" role="status">Loading status history…</p>
        </div>
      </section>

      <section class="application-workflow" aria-labelledby="committee-decisions-title">
        <header class="application-workflow-heading">
          <span class="applications-state-label">Human review</span>
          <h2 id="committee-decisions-title">Committee decisions</h2>
          <p>Only decisions recorded by a committee are shown here. AI-assisted analysis is separate and advisory.</p>
        </header>
        <div id="application-committee-reviews" class="application-workflow-panel" aria-live="polite" aria-busy="true">
          <p class="application-workflow-loading" role="status">Loading committee review information…</p>
        </div>
      </section>

      <section class="application-workflow" aria-labelledby="application-activity-title">
        <header class="application-workflow-heading">
          <span class="applications-state-label">History availability</span>
          <h2 id="application-activity-title">Application activity</h2>
          <p>Activity history is unavailable until the backend can verify the student's identity and application ownership.</p>
        </header>
        <div id="application-audit-activity" class="application-workflow-panel" aria-live="polite" aria-busy="false">
          <p role="status">Audit access is withheld until an approved event-visibility policy is configured.</p>
        </div>
      </section>

      <section class="document-management" aria-labelledby="document-management-title">
        <header class="document-management-heading">
          <div>
            <span class="applications-state-label">Supporting materials</span>
            <h2 id="document-management-title">Documents</h2>
            <p>Upload and review documents associated with this application.</p>
          </div>
        </header>

        <form id="application-document-upload-form" class="document-upload-form" novalidate>
          <div class="document-upload-fields">
            <div class="document-upload-file-field">
              <label for="application-document-file">Choose a document <span>Required</span></label>
              <input
                id="application-document-file"
                name="file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                aria-describedby="application-document-file-help application-document-selected-file"
                required
              />
              <small id="application-document-file-help">Accepted formats: PDF, JPG, JPEG, PNG.</small>
              <small id="application-document-selected-file" class="document-selected-file">No file selected</small>
            </div>

            <div class="document-upload-type-field">
              <label for="application-document-type">Document type <span>Optional</span></label>
              <select id="application-document-type" name="document_type">
                <option value="">Choose a document type</option>
                <option value="MARKSHEET">Marksheet</option>
                <option value="IDENTITY_PROOF">Identity proof</option>
                <option value="APPLICATION_FORM">Application form</option>
                <option value="CERTIFICATE">Certificate</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
          </div>

          <p id="document-upload-error" class="document-feedback document-feedback-error" role="alert" hidden></p>
          <p id="document-upload-status" class="document-feedback" role="status" aria-live="polite" hidden></p>

          <div class="document-upload-actions">
            <button id="application-document-upload-button" type="submit" class="primary-button">Upload document</button>
          </div>
        </form>

        <div
          id="application-document-list"
          class="application-document-list"
          aria-live="polite"
          aria-busy="true"
        >
          <p class="application-documents-loading" role="status">Loading documents…</p>
        </div>
      </section>

      <section class="academic-review" aria-labelledby="academic-review-title">
        <header class="academic-review-heading">
          <span class="applications-state-label">Academic review support</span>
          <h2 id="academic-review-title">Institutional context and analysis</h2>
          <p>AI-assisted information supports review. Final academic decisions remain with authorized officials or committees.</p>
        </header>

        <section class="academic-review-panel" aria-labelledby="eligibility-analysis-title">
          <header class="academic-review-panel-heading">
            <div>
              <span class="applications-state-label">System analysis</span>
              <h3 id="eligibility-analysis-title">Eligibility Analysis</h3>
            </div>
            <button type="button" class="secondary-button" data-action="run-eligibility-analysis">
              Run eligibility analysis
            </button>
          </header>
          <p class="academic-review-side-effect-note">
            This analysis may use AI and replaces stored eligibility results for this application. It does not make an official decision.
          </p>
          <div id="eligibility-analysis-content" class="academic-review-panel-content" aria-live="polite" aria-busy="false">
            <p class="academic-review-idle-state">Eligibility analysis has not been requested.</p>
          </div>
        </section>

        <section class="academic-review-panel" aria-labelledby="identified-deficiencies-title">
          <header class="academic-review-panel-heading">
            <div>
              <span class="applications-state-label">System analysis</span>
              <h3 id="identified-deficiencies-title">AI-Identified Deficiencies</h3>
            </div>
            <button type="button" class="secondary-button" data-action="refresh-deficiencies">
              Refresh deficiency analysis
            </button>
          </header>
          <p class="academic-review-side-effect-note">
            Refreshing removes and rebuilds stored deficiency findings from current eligibility results. This is not an official decision.
          </p>
          <div id="deficiencies-content" class="academic-review-panel-content" aria-live="polite" aria-busy="false">
            <p class="academic-review-idle-state">Deficiency analysis has not been requested.</p>
          </div>
        </section>

        <section class="academic-review-panel" aria-labelledby="ai-analysis-title">
          <header class="academic-review-panel-heading">
            <div>
              <span class="applications-state-label">AI-generated recommendation</span>
              <h3 id="ai-analysis-title">AI-Assisted Analysis</h3>
            </div>
            <button
              type="button"
              class="secondary-button"
              id="generate-ai-analysis-button"
              data-action="generate-ai-analysis"
            >
              Generate AI analysis
            </button>
          </header>
          <p class="academic-review-side-effect-note">
            Requesting analysis contacts the AI service and saves a new analysis record for this application. Previous analyses are not deleted. AI-generated output is advisory only and is not an official academic or committee decision.
          </p>
          <div
            id="ai-analysis-content"
            class="academic-review-panel-content"
            aria-live="polite"
            aria-busy="false"
          >
            <p class="academic-review-idle-state">AI-assisted analysis has not been requested.</p>
          </div>
        </section>
      </section>
    </section>
  `;
}

async function loadStudentApplicationDetails(applicationId) {
  const content = document.getElementById("application-details-content");

  if (!content) {
    return;
  }

  const requestId = ++appState.applicationDetailsRequestId;
  const validId = Number.isSafeInteger(applicationId) && applicationId > 0;

  if (!validId) {
    content.setAttribute("aria-busy", "false");
    renderApplicationDetailsMessage(
      content,
      "No application selected",
      "Open Application Details from a successfully created application to view its information.",
    );
    return;
  }

  content.setAttribute("aria-busy", "true");
  content.replaceChildren();
  const loadingMessage = document.createElement("p");
  loadingMessage.className = "application-details-loading";
  loadingMessage.setAttribute("role", "status");
  loadingMessage.textContent = "Loading application details…";
  content.append(loadingMessage);

  try {
    const application = await getApplication(applicationId);

    if (
      requestId !== appState.applicationDetailsRequestId ||
      appState.currentPage !== "application-details"
    ) {
      return;
    }

    if (
      !application ||
      typeof application !== "object" ||
      Array.isArray(application)
    ) {
      throw new Error("The application service returned an invalid response.");
    }

    renderApplicationDetails(content, application);
  } catch (error) {
    if (
      requestId !== appState.applicationDetailsRequestId ||
      appState.currentPage !== "application-details"
    ) {
      return;
    }

    if (error instanceof APIError && error.status === 404) {
      renderApplicationDetailsMessage(
        content,
        "Application not found",
        "This application could not be found. Return to My Applications or the dashboard.",
      );
    } else {
      renderApplicationDetailsMessage(
        content,
        "Unable to load application details",
        error instanceof APIError && error.status === 0
          ? "The service could not be reached. Check your connection and try again."
          : "The application details could not be retrieved right now. Please try again.",
        true,
      );
    }
  } finally {
    if (requestId === appState.applicationDetailsRequestId) {
      content.setAttribute("aria-busy", "false");
    }
  }
}

async function loadApplicationDocuments(applicationId) {
  const container = document.getElementById("application-document-list");

  if (!container) {
    return;
  }

  const requestId = ++appState.documentListRequestId;
  const validId = Number.isSafeInteger(applicationId) && applicationId > 0;

  if (!validId) {
    container.setAttribute("aria-busy", "false");
    renderDocumentListMessage(
      container,
      "No application selected",
      "Select an application before viewing its documents.",
    );
    return;
  }

  container.setAttribute("aria-busy", "true");
  container.replaceChildren();
  const loadingMessage = document.createElement("p");
  loadingMessage.className = "application-documents-loading";
  loadingMessage.setAttribute("role", "status");
  loadingMessage.textContent = "Loading documents…";
  container.append(loadingMessage);

  try {
    const response = await getApplicationDocuments(applicationId);

    if (
      requestId !== appState.documentListRequestId ||
      appState.currentPage !== "application-details"
    ) {
      return;
    }

    if (!Array.isArray(response?.documents)) {
      throw new Error("The document service returned an invalid response.");
    }

    appState.applicationDocuments = response.documents;
    renderApplicationDocumentList(container, response.documents);
  } catch (error) {
    if (
      requestId !== appState.documentListRequestId ||
      appState.currentPage !== "application-details"
    ) {
      return;
    }

    if (error instanceof APIError && error.status === 404) {
      renderDocumentListMessage(
        container,
        "Application not found",
        "Documents are unavailable because this application could not be found.",
      );
    } else {
      renderDocumentListMessage(
        container,
        "Unable to load documents",
        error instanceof APIError && error.status === 0
          ? "The document service could not be reached. Check your connection and try again."
          : "The document list could not be retrieved right now.",
        true,
      );
    }
  } finally {
    if (requestId === appState.documentListRequestId) {
      container.setAttribute("aria-busy", "false");
    }
  }
}

function getApplicationWorkflowState(applicationId) {
  if (
    !appState.applicationWorkflowState ||
    appState.applicationWorkflowState.applicationId !== applicationId
  ) {
    appState.applicationWorkflowState = {
      applicationId,
      statusHistory: { status: "idle", data: null, error: null, requestId: 0 },
      committeeReviews: {
        status: "idle",
        data: null,
        error: null,
        requestId: 0,
      },
    };
  }

  return appState.applicationWorkflowState;
}

const applicationWorkflowResources = {
  statusHistory: {
    containerId: "application-status-history",
    responseKey: "history",
    loadingText: "Loading status history…",
    sectionName: "status history",
    load: getStatusHistory,
    render: renderStatusHistory,
  },
  committeeReviews: {
    containerId: "application-committee-reviews",
    responseKey: "reviews",
    loadingText: "Loading committee review information…",
    sectionName: "committee review information",
    load: getCommitteeReviews,
    render: renderCommitteeReviews,
  },
};

function restoreApplicationWorkflowPanels(applicationId) {
  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    for (const resource of Object.values(applicationWorkflowResources)) {
      const container = document.getElementById(resource.containerId);
      if (container) {
        renderWorkflowMessage(
          container,
          "No application selected",
          "Open an application to view its workflow information.",
        );
      }
    }
    return;
  }

  const state = getApplicationWorkflowState(applicationId);
  for (const [key, resource] of Object.entries(
    applicationWorkflowResources,
  )) {
    const container = document.getElementById(resource.containerId);
    const section = state[key];
    if (!container || !section) {
      continue;
    }

    if (section.status === "success") {
      resource.render(container, section.data);
    } else if (section.status === "error") {
      renderWorkflowMessage(
        container,
        `Unable to load ${resource.sectionName}`,
        getWorkflowErrorMessage(section.error),
        true,
        key,
      );
    }
  }
}

async function loadApplicationWorkflowPanel(
  applicationId,
  key,
  forceRefresh = false,
) {
  const resource = applicationWorkflowResources[key];
  const container = document.getElementById(resource?.containerId);
  if (!resource || !container) {
    return;
  }

  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    renderWorkflowMessage(
      container,
      "No application selected",
      "Open an application to view its workflow information.",
    );
    return;
  }

  const state = getApplicationWorkflowState(applicationId)[key];
  if (state.status === "success" && !forceRefresh) {
    resource.render(container, state.data);
    return;
  }
  if (state.status === "loading" && !forceRefresh) {
    return;
  }

  const requestId = ++state.requestId;
  state.status = "loading";
  renderWorkflowLoading(container, resource.loadingText);

  try {
    const response = await resource.load(applicationId);
    if (
      requestId !== state.requestId ||
      appState.selectedApplicationId !== applicationId
    ) {
      return;
    }
    if (appState.currentPage !== "application-details") {
      state.status = "idle";
      return;
    }
    if (!Array.isArray(response?.[resource.responseKey])) {
      throw new Error(
        `The service returned invalid ${resource.sectionName}.`,
      );
    }

    state.status = "success";
    state.data = response[resource.responseKey];
    state.error = null;
    resource.render(container, state.data);
  } catch (error) {
    if (
      requestId !== state.requestId ||
      appState.selectedApplicationId !== applicationId
    ) {
      return;
    }
    if (appState.currentPage !== "application-details") {
      state.status = "idle";
      return;
    }

    state.status = "error";
    state.error = error;
    renderWorkflowMessage(
      container,
      `Unable to load ${resource.sectionName}`,
      getWorkflowErrorMessage(error),
      true,
      key,
    );
  }
}

function getWorkflowErrorMessage(error) {
  if (error instanceof APIError && error.status === 0) {
    return "The application service could not be reached. Check your connection and try again.";
  }
  if (error instanceof APIError && error.status === 404) {
    return "The application could not be found.";
  }
  return "The service could not provide this information. Please try again.";
}

function renderWorkflowLoading(container, message) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "true");
  const loading = document.createElement("p");
  loading.className = "application-workflow-loading";
  loading.setAttribute("role", "status");
  loading.textContent = message;
  container.append(loading);
}

function renderWorkflowMessage(
  container,
  title,
  message,
  canRetry = false,
  resourceKey = "",
) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  const state = document.createElement("div");
  state.className = "application-workflow-message";
  state.setAttribute("role", "status");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const description = document.createElement("p");
  description.textContent = message;
  state.append(heading, description);

  if (canRetry && resourceKey) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary-button";
    retry.dataset.action = "retry-application-workflow";
    retry.dataset.workflowResource = resourceKey;
    retry.textContent = "Try again";
    state.append(retry);
  }

  container.append(state);
}

function sortWorkflowRows(rows, dateKey) {
  return rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const leftDate = Date.parse(left.row?.[dateKey] ?? "");
      const rightDate = Date.parse(right.row?.[dateKey] ?? "");
      const leftTime = Number.isNaN(leftDate) ? 0 : leftDate;
      const rightTime = Number.isNaN(rightDate) ? 0 : rightDate;
      return leftTime - rightTime || left.index - right.index;
    })
    .map(({ row }) => row);
}

function renderStatusHistory(container, history) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  if (history.length === 0) {
    renderWorkflowMessage(
      container,
      "No status changes recorded",
      "Status history will appear here when the service records a change.",
    );
    return;
  }

  const list = document.createElement("ol");
  list.className = "application-workflow-list";
  for (const entry of sortWorkflowRows(history, "created_at")) {
    const item = document.createElement("li");
    item.className = "application-workflow-item";
    const heading = document.createElement("h3");
    const oldStatus =
      typeof entry?.old_status === "string" ? entry.old_status : "";
    const newStatus =
      typeof entry?.new_status === "string" ? entry.new_status : "";
    heading.textContent = oldStatus
      ? `${oldStatus} → ${newStatus || "Status updated"}`
      : newStatus || "Status recorded";
    item.append(heading);

    const metadata = document.createElement("p");
    const timestamp = formatApplicationDate(entry?.created_at);
    metadata.textContent = timestamp || "";
    if (metadata.textContent) {
      item.append(metadata);
    }

    if (typeof entry?.reason === "string" && entry.reason.trim()) {
      const reason = document.createElement("p");
      reason.className = "application-workflow-reason";
      reason.textContent = entry.reason;
      item.append(reason);
    }
    list.append(item);
  }
  container.append(list);
}

function renderCommitteeReviews(container, reviews) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  if (reviews.length === 0) {
    renderWorkflowMessage(
      container,
      "No committee review recorded",
      "A committee review will appear here when the service records one.",
    );
    return;
  }

  const list = document.createElement("ol");
  list.className = "application-workflow-list";
  for (const review of sortWorkflowRows(reviews, "assigned_at")) {
    const item = document.createElement("li");
    item.className = "application-workflow-item";
    const heading = document.createElement("h3");
    heading.textContent =
      typeof review?.committee_type === "string" &&
      review.committee_type.trim()
        ? review.committee_type
        : "Committee review";
    item.append(heading);

    const status = document.createElement("p");
    const reviewStatus =
      typeof review?.review_status === "string"
        ? review.review_status
        : "Status unavailable";
    const assignedAt = formatApplicationDate(review?.assigned_at);
    status.textContent = [reviewStatus, assignedAt]
      .filter(Boolean)
      .join(" · ");
    item.append(status);

    if (typeof review?.decision === "string" && review.decision.trim()) {
      const decision = document.createElement("p");
      decision.className = "application-committee-decision";
      decision.textContent = `Committee decision: ${review.decision}`;
      item.append(decision);
    }

    if (
      typeof review?.decision_reason === "string" &&
      review.decision_reason.trim()
    ) {
      const reason = document.createElement("p");
      reason.className = "application-workflow-reason";
      reason.textContent = review.decision_reason;
      item.append(reason);
    }

    const decidedAt = formatApplicationDate(review?.decided_at);
    if (decidedAt) {
      const decisionDate = document.createElement("p");
      decisionDate.textContent = `Decision recorded: ${decidedAt}`;
      item.append(decisionDate);
    }
    list.append(item);
  }
  container.append(list);
}

function getAcademicReviewState(applicationId) {
  if (
    !appState.academicReviewState ||
    appState.academicReviewState.applicationId !== applicationId
  ) {
    appState.academicReviewState = {
      applicationId,
      eligibility: { status: "idle", data: null, error: null, requestId: 0 },
      deficiencies: { status: "idle", data: null, error: null, requestId: 0 },
    };
  }

  return appState.academicReviewState;
}

function restoreAcademicReviewPanels(applicationId) {
  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    return;
  }

  const state = getAcademicReviewState(applicationId);
  const eligibilityContent = document.getElementById(
    "eligibility-analysis-content",
  );
  const deficienciesContent = document.getElementById("deficiencies-content");

  if (state.eligibility.status === "success" && eligibilityContent) {
    renderEligibilityAnalysis(eligibilityContent, state.eligibility.data);
  } else if (state.eligibility.status === "error" && eligibilityContent) {
    renderM08Message(
      eligibilityContent,
      "Unable to retrieve eligibility analysis",
      getAcademicReviewErrorMessage(state.eligibility.error, "eligibility"),
      "run-eligibility-analysis",
    );
  }

  if (state.deficiencies.status === "success" && deficienciesContent) {
    renderIdentifiedDeficiencies(deficienciesContent, state.deficiencies.data);
  } else if (state.deficiencies.status === "error" && deficienciesContent) {
    renderM08Message(
      deficienciesContent,
      "Unable to retrieve deficiency information",
      getAcademicReviewErrorMessage(state.deficiencies.error, "deficiencies"),
      "refresh-deficiencies",
    );
  }
}

function isCurrentAcademicReviewRequest(section, applicationId, requestId) {
  return (
    appState.currentPage === "application-details" &&
    appState.selectedApplicationId === applicationId &&
    appState.academicReviewState?.applicationId === applicationId &&
    appState.academicReviewState[section]?.requestId === requestId
  );
}

async function runAcademicReviewAction(action) {
  const applicationId = appState.selectedApplicationId;
  const isEligibility = action === "eligibility";
  const section = isEligibility ? "eligibility" : "deficiencies";
  const containerId = isEligibility
    ? "eligibility-analysis-content"
    : "deficiencies-content";
  const buttonAction = isEligibility
    ? "run-eligibility-analysis"
    : "refresh-deficiencies";
  const actionKey = `${section}:${applicationId}`;
  const container = document.getElementById(containerId);

  if (
    !container ||
    !Number.isSafeInteger(applicationId) ||
    applicationId <= 0 ||
    appState.academicReviewActionsInProgress.has(actionKey)
  ) {
    return;
  }

  const warning = isEligibility
    ? "This analysis may contact the AI service and replaces stored eligibility results for this application. Continue?"
    : "This refresh replaces stored deficiency findings based on current eligibility results. Continue?";

  if (!window.confirm(warning)) {
    return;
  }

  const state = getAcademicReviewState(applicationId)[section];
  const requestId = ++state.requestId;
  const button = document.querySelector(`[data-action="${buttonAction}"]`);

  appState.academicReviewActionsInProgress.add(actionKey);
  if (button) {
    button.disabled = true;
    button.textContent = isEligibility ? "Analyzing…" : "Refreshing…";
  }
  state.status = "loading";
  state.error = null;
  container.setAttribute("aria-busy", "true");
  renderM08Loading(
    container,
    isEligibility
      ? "Analyzing available eligibility evidence…"
      : "Refreshing deficiency findings…",
  );

  try {
    const response = isEligibility
      ? await getEligibility(applicationId)
      : await getDeficiencies(applicationId);

    if (!isCurrentAcademicReviewRequest(section, applicationId, requestId)) {
      return;
    }

    const listKey = isEligibility ? "results" : "deficiencies";
    if (!response || typeof response !== "object" || !Array.isArray(response[listKey])) {
      throw new Error("The analysis service returned an invalid response.");
    }

    state.status = "success";
    state.data = response;
    state.error = null;

    if (isEligibility) {
      renderEligibilityAnalysis(container, response);
    } else {
      renderIdentifiedDeficiencies(container, response);
    }
  } catch (error) {
    if (!isCurrentAcademicReviewRequest(section, applicationId, requestId)) {
      return;
    }

    state.status = "error";
    state.error = error;
    renderM08Message(
      container,
      error instanceof APIError && error.status === 404
        ? "Application not found"
        : isEligibility
          ? "Unable to retrieve eligibility analysis"
          : "Unable to retrieve deficiency information",
      getAcademicReviewErrorMessage(error, section),
      buttonAction,
    );
  } finally {
    appState.academicReviewActionsInProgress.delete(actionKey);
    if (button) {
      button.disabled = false;
      button.textContent = isEligibility
        ? "Run eligibility analysis"
        : "Refresh deficiency analysis";
    }
    if (isCurrentAcademicReviewRequest(section, applicationId, requestId)) {
      container.setAttribute("aria-busy", "false");
    }
  }
}

function renderEligibilityAnalysis(container, response) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  if (Number.isFinite(response.requirements_analyzed)) {
    const count = document.createElement("p");
    count.className = "academic-review-summary";
    count.textContent = `Requirements analyzed: ${response.requirements_analyzed}`;
    container.append(count);
  }

  if (response.results.length === 0) {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent = Number.isFinite(response.requirements_analyzed) &&
      response.requirements_analyzed === 0
      ? "No requirement records were available for this analysis."
      : "The analysis returned no eligibility result items.";
    container.append(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "academic-analysis-results";
  for (const result of response.results) {
    if (!result || typeof result !== "object" || Array.isArray(result)) {
      continue;
    }

    const item = document.createElement("article");
    item.className = "academic-analysis-item";
    appendReviewField(item, "Requirement", result.requirement_id);
    appendReviewField(item, "Analysis result", result.result);
    appendReviewField(item, "Supporting evidence", result.evidence);
    if (Number.isFinite(result.confidence)) {
      appendReviewField(item, "Model confidence", result.confidence);
    }
    appendReviewField(item, "Source chunk", result.source_chunk_id);
    if (item.childElementCount) {
      list.append(item);
    }
  }

  if (list.childElementCount) {
    container.append(list);
  } else {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent = "No displayable eligibility details were returned.";
    container.append(empty);
  }
}

function renderIdentifiedDeficiencies(container, response) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  if (Number.isFinite(response.deficiencies_detected)) {
    const count = document.createElement("p");
    count.className = "academic-review-summary";
    count.textContent = `Deficiencies detected: ${response.deficiencies_detected}`;
    container.append(count);
  }

  if (response.deficiencies.length === 0) {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent =
      "No deficiencies were returned by the current analysis.";
    container.append(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "academic-analysis-results";
  for (const deficiency of response.deficiencies) {
    if (!deficiency || typeof deficiency !== "object" || Array.isArray(deficiency)) {
      continue;
    }

    const item = document.createElement("article");
    item.className = "academic-analysis-item";
    appendReviewField(item, "Description", deficiency.description);
    appendReviewField(item, "Assessment result", deficiency.status);
    appendReviewField(item, "Severity", deficiency.severity);
    appendReviewField(item, "Evidence", deficiency.evidence);
    appendReviewField(item, "Requirement", deficiency.requirement_id);
    appendReviewField(item, "Source chunk", deficiency.source_chunk_id);
    if (item.childElementCount) {
      list.append(item);
    }
  }

  if (list.childElementCount) {
    container.append(list);
  } else {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent = "No displayable deficiency details were returned.";
    container.append(empty);
  }
}

function appendReviewField(container, label, value) {
  if (!isDisplayableValue(value)) {
    return;
  }

  const field = document.createElement("div");
  field.className = "academic-review-result-field";
  const term = document.createElement("strong");
  term.textContent = label;
  const content = document.createElement("p");
  content.textContent = String(value);
  field.append(term, content);
  container.append(field);
}

function isDisplayableValue(value) {
  return (
    (typeof value === "string" && value.trim() !== "") ||
    (typeof value === "number" && Number.isFinite(value))
  );
}

function renderM08Loading(container, message) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "true");
  const loading = document.createElement("p");
  loading.className = "academic-review-loading";
  loading.setAttribute("role", "status");
  loading.textContent = message;
  container.append(loading);
}

function renderM08Message(container, title, message, retryAction = null) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  const state = document.createElement("div");
  state.className = "academic-review-message";
  state.setAttribute("role", "status");
  const heading = document.createElement("h4");
  heading.textContent = title;
  const description = document.createElement("p");
  description.textContent = message;
  state.append(heading, description);

  if (retryAction) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary-button";
    retry.dataset.action = retryAction;
    retry.textContent = "Try again";
    state.append(retry);
  }

  container.append(state);
}

function getAcademicReviewErrorMessage(error, section) {
  if (error instanceof APIError && error.status === 0) {
    return "The academic information service could not be reached. Please try again.";
  }
  if (error instanceof APIError && error.status === 404) {
    return "The application could not be found.";
  }
  if (error instanceof APIError && error.status === 400) {
    return `The service could not provide ${section} for this application.`;
  }
  return `Unable to retrieve ${section} right now. Please try again.`;
}

/* =========================================================
   M09 — AI-Assisted Analysis State
   ========================================================= */

function getAiAnalysisState(applicationId) {
  if (
    !appState.aiAnalysisState ||
    appState.aiAnalysisState.applicationId !== applicationId
  ) {
    appState.aiAnalysisState = {
      applicationId,
      status: "idle",
      data: null,
      error: null,
      requestId: 0,
    };
  }

  return appState.aiAnalysisState;
}

function restoreAiAnalysisPanel(applicationId) {
  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    return;
  }

  const state = getAiAnalysisState(applicationId);
  const container = document.getElementById("ai-analysis-content");

  if (!container) {
    return;
  }

  if (state.status === "success") {
    renderAiAnalysis(container, state.data);
  } else if (state.status === "error") {
    renderM08Message(
      container,
      "Unable to retrieve AI analysis",
      getAcademicReviewErrorMessage(state.error, "AI analysis"),
      "retry-ai-analysis",
    );
  } else if (state.status === "loading") {
    renderM08Loading(container, "Requesting AI-assisted analysis\u2026");
    const button = document.querySelector(
      '[data-action="generate-ai-analysis"]',
    );
    if (button) {
      button.disabled = true;
      button.textContent = "Generating\u2026";
    }
  }
}

async function runAiAnalysis() {
  const applicationId = appState.selectedApplicationId;
  const actionKey = `ai-analysis:${applicationId}`;
  const container = document.getElementById("ai-analysis-content");
  const button = document.querySelector(
    '[data-action="generate-ai-analysis"]',
  );

  if (
    !container ||
    !Number.isSafeInteger(applicationId) ||
    applicationId <= 0 ||
    appState.aiAnalysisActionsInProgress.has(actionKey)
  ) {
    return;
  }

  const confirmed = window.confirm(
    "This will contact the AI service and save a new analysis record for this application.\n\n" +
    "Previous analyses will not be deleted.\n\n" +
    "The result is AI-generated and is not an official academic or committee decision.\n\n" +
    "Continue?",
  );

  if (!confirmed) {
    return;
  }

  const state = getAiAnalysisState(applicationId);
  const requestId = ++state.requestId;

  appState.aiAnalysisActionsInProgress.add(actionKey);
  state.status = "loading";
  state.error = null;
  container.setAttribute("aria-busy", "true");

  if (button) {
    button.disabled = true;
    button.textContent = "Generating\u2026";
  }

  renderM08Loading(container, "Requesting AI-assisted analysis\u2026");

  try {
    const response = await generateApplicationAnalysis(applicationId);

    if (
      appState.currentPage !== "application-details" ||
      appState.selectedApplicationId !== applicationId ||
      appState.aiAnalysisState?.applicationId !== applicationId ||
      appState.aiAnalysisState?.requestId !== requestId
    ) {
      return;
    }

    if (
      !response ||
      typeof response !== "object" ||
      Array.isArray(response)
    ) {
      throw new Error(
        "The AI analysis service returned an invalid response.",
      );
    }

    state.status = "success";
    state.data = response;
    state.error = null;
    const currentContainer = document.getElementById("ai-analysis-content");
    if (currentContainer) {
      renderAiAnalysis(currentContainer, response);
    }
  } catch (error) {
    if (
      appState.currentPage !== "application-details" ||
      appState.selectedApplicationId !== applicationId ||
      appState.aiAnalysisState?.applicationId !== applicationId ||
      appState.aiAnalysisState?.requestId !== requestId
    ) {
      return;
    }

    state.status = "error";
    state.error = error;
    const currentContainer = document.getElementById("ai-analysis-content");
    if (currentContainer) {
      renderM08Message(
        currentContainer,
        error instanceof APIError && error.status === 404
          ? "Application not found"
          : "Unable to retrieve AI analysis",
        getAcademicReviewErrorMessage(error, "AI analysis"),
        "retry-ai-analysis",
      );
    }
  } finally {
    appState.aiAnalysisActionsInProgress.delete(actionKey);
    if (
      appState.currentPage === "application-details" &&
      appState.selectedApplicationId === applicationId &&
      appState.aiAnalysisState?.applicationId === applicationId &&
      appState.aiAnalysisState?.requestId === requestId
    ) {
      const currentContainer = document.getElementById(
        "ai-analysis-content",
      );
      const currentButton = document.querySelector(
        '[data-action="generate-ai-analysis"]',
      );
      if (currentContainer) {
        currentContainer.setAttribute("aria-busy", "false");
      }
      if (currentButton) {
        currentButton.disabled = false;
        currentButton.textContent = "Generate AI analysis";
      }
    }
  }
}

function renderAiAnalysis(container, response) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  // Advisory notice — always shown first
  const advisory = document.createElement("p");
  advisory.className = "ai-analysis-advisory";
  advisory.textContent =
    "This is an AI-generated recommendation only. It is not an official academic " +
    "or committee decision. Final approval or rejection must be made by authorized " +
    "officials or the appropriate committee.";
  container.append(advisory);

  // Metadata row
  const meta = document.createElement("dl");
  meta.className = "ai-analysis-meta";

  const metaFields = [];
  if (isDisplayableValue(response.analysis_type)) {
    metaFields.push(["Type", response.analysis_type]);
  }
  if (isDisplayableValue(response.model)) {
    metaFields.push(["Model", response.model]);
  }
  if (isDisplayableValue(response.created_at)) {
    metaFields.push(["Generated", String(response.created_at)]);
  }
  if (Number.isFinite(response.analysis_id)) {
    metaFields.push(["Analysis ID", response.analysis_id]);
  }
  if (Number.isFinite(response.documents_analyzed)) {
    metaFields.push(["Documents", response.documents_analyzed]);
  }
  if (Number.isFinite(response.requirements_analyzed)) {
    metaFields.push(["Requirements", response.requirements_analyzed]);
  }
  if (Number.isFinite(response.eligibility_results)) {
    metaFields.push(["Eligibility results", response.eligibility_results]);
  }
  if (Number.isFinite(response.deficiencies)) {
    metaFields.push(["Deficiencies", response.deficiencies]);
  }
  if (Number.isFinite(response.ordinance_results)) {
    metaFields.push(["Ordinance sources", response.ordinance_results]);
  }

  for (const [label, value] of metaFields) {
    const item = document.createElement("div");
    item.className = "ai-analysis-meta-item";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = String(value);
    item.append(dt, dd);
    meta.append(item);
  }

  if (meta.childElementCount) {
    container.append(meta);
  }

  // Analysis text — rendered as preformatted text; the field is free-form
  // and section headings are not guaranteed, so no structural parsing is done.
  const analysisText =
    typeof response.analysis === "string" ? response.analysis.trim() : "";

  if (!analysisText) {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent = "The analysis did not return any text content.";
    container.append(empty);
    return;
  }

  const textBlock = document.createElement("pre");
  textBlock.className = "ai-analysis-text";
  textBlock.textContent = analysisText;
  container.append(textBlock);
}

function renderApplicationDocumentList(container, documents) {
  container.replaceChildren();

  if (documents.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "document-list-empty";

    const heading = document.createElement("h3");
    heading.textContent = "No documents uploaded";

    const message = document.createElement("p");
    message.textContent =
      "Documents added to this application will appear here.";

    emptyState.append(heading, message);
    container.append(emptyState);
    return;
  }

  const listHeading = document.createElement("p");
  listHeading.className = "document-list-count";
  listHeading.textContent = `${documents.length} ${documents.length === 1 ? "document" : "documents"}`;
  container.append(listHeading);

  const list = document.createElement("div");
  list.className = "application-document-items";

  for (const documentRecord of documents) {
    list.append(renderApplicationDocument(documentRecord));
  }

  container.append(list);
}

function renderApplicationDocument(documentRecord) {
  const item = document.createElement("article");
  item.className = "application-document-item";

  const header = document.createElement("header");
  header.className = "application-document-header";

  const fileName = document.createElement("h3");
  fileName.textContent =
    typeof documentRecord?.file_name === "string" &&
      documentRecord.file_name.trim()
      ? documentRecord.file_name
      : "Document";
  header.append(fileName);

  if (typeof documentRecord?.upload_status === "string") {
    const uploadStatus = document.createElement("span");
    uploadStatus.className = "document-upload-status";
    uploadStatus.textContent = documentRecord.upload_status;
    header.append(uploadStatus);
  }

  item.append(header);

  const metadata = document.createElement("dl");
  metadata.className = "application-document-metadata";
  appendDocumentMetadata(
    metadata,
    "Document type",
    documentRecord?.document_type,
  );
  appendDocumentMetadata(
    metadata,
    "File size",
    formatDocumentFileSize(documentRecord?.file_size),
  );
  appendDocumentMetadata(metadata, "File format", documentRecord?.mime_type);
  appendDocumentMetadata(
    metadata,
    "Uploaded",
    formatApplicationDate(documentRecord?.uploaded_at),
  );
  if (metadata.childElementCount) {
    item.append(metadata);
  }

  const actionResults =
    appState.documentActionResults[String(documentRecord?.id)] || {};
  appendDocumentActionResults(item, actionResults);

  const documentId = Number(documentRecord?.id);
  if (Number.isSafeInteger(documentId) && documentId > 0) {
    const actions = document.createElement("div");
    actions.className = "application-document-actions";

    const canExtract = documentRecord?.mime_type === "application/pdf";
    actions.append(
      createDocumentActionButton(documentId, "download", "Download"),
      createDocumentActionButton(documentId, "validate", "Validate"),
      createDocumentActionButton(
        documentId,
        "extract",
        "Extract text",
        !canExtract,
        canExtract ? "" : "Text extraction is supported for PDF documents.",
      ),
      createDocumentActionButton(documentId, "classify", "Classify"),
    );

    item.append(actions);
  }

  return item;
}

function appendDocumentMetadata(list, label, value) {
  if (
    (typeof value !== "string" && typeof value !== "number") ||
    String(value).trim() === ""
  ) {
    return;
  }

  const item = document.createElement("div");
  item.className = "application-document-metadata-item";

  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = String(value);
  item.append(term, description);
  list.append(item);
}

function formatDocumentFileSize(value) {
  if (!Number.isFinite(value) || value < 0) {
    return null;
  }

  if (value < 1024) {
    return `${value} B`;
  }

  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`;
}

function createDocumentActionButton(
  documentId,
  action,
  label,
  disabled = false,
  title = "",
) {
  const button = document.createElement("button");
  const actionKey = `${action}:${documentId}`;
  const inProgress = appState.documentActionsInProgress.has(actionKey);

  button.type = "button";
  button.className = "secondary-button";
  button.dataset.documentAction = action;
  button.dataset.documentId = String(documentId);
  button.disabled = disabled || inProgress;
  button.title = title;
  button.textContent = inProgress ? `${label}…` : label;
  return button;
}

function appendDocumentActionResults(item, results) {
  const messages = [];

  if (results.validation?.valid === true) {
    messages.push("Document validation passed.");
  } else if (results.validation?.error) {
    messages.push(`Validation needs attention: ${results.validation.error}`);
  }

  if (results.extraction) {
    const status = results.extraction.extraction_status;
    if (typeof status === "string") {
      const textLength = Number.isFinite(results.extraction.text_length)
        ? ` (${results.extraction.text_length} characters)`
        : "";
      messages.push(`Extraction: ${status}${textLength}`);
    }
  } else if (results.extractionError) {
    messages.push(`Extraction: ${results.extractionError}`);
  }

  if (typeof results.classification?.document_type === "string") {
    messages.push(`Classification: ${results.classification.document_type}`);
  } else if (results.classificationError) {
    messages.push(`Classification: ${results.classificationError}`);
  } else if (results.downloadError) {
    messages.push(`Download: ${results.downloadError}`);
  }

  if (!messages.length) {
    return;
  }

  const feedback = document.createElement("ul");
  feedback.className = "application-document-action-results";
  for (const message of messages) {
    const result = document.createElement("li");
    result.textContent = message;
    feedback.append(result);
  }

  if (
    typeof results.extraction?.extracted_text === "string" &&
    results.extraction.extracted_text.trim()
  ) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "View extracted text";
    const extractedText = document.createElement("pre");
    extractedText.textContent = results.extraction.extracted_text;
    details.append(summary, extractedText);
    feedback.append(details);
  }

  item.append(feedback);
}

function renderDocumentListMessage(
  container,
  title,
  message,
  canRetry = false,
) {
  container.replaceChildren();

  const uploadForm = document.getElementById(
    "application-document-upload-form",
  );
  if (uploadForm) {
    uploadForm.hidden =
      title === "No application selected" || title === "Application not found";
  }

  const state = document.createElement("div");
  state.className = "document-list-message";
  state.setAttribute("role", "status");

  const heading = document.createElement("h3");
  heading.textContent = title;
  const description = document.createElement("p");
  description.textContent = message;
  state.append(heading, description);

  if (canRetry) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "secondary-button";
    retry.dataset.action = "retry-document-list";
    retry.textContent = "Try again";
    state.append(retry);
  }

  container.append(state);
}

async function runApplicationDocumentAction(button) {
  const action = button.dataset.documentAction;
  const documentId = Number(button.dataset.documentId);
  const applicationId = appState.selectedApplicationId;
  const actionKey = `${action}:${documentId}`;

  if (
    appState.documentActionsInProgress.has(actionKey) ||
    !Number.isSafeInteger(applicationId) ||
    applicationId <= 0 ||
    !Number.isSafeInteger(documentId) ||
    documentId <= 0
  ) {
    return;
  }

  appState.documentActionsInProgress.add(actionKey);
  renderApplicationDocumentList(
    document.getElementById("application-document-list"),
    appState.applicationDocuments || [],
  );

  try {
    let result;
    if (action === "download") {
      const download = await downloadApplicationDocument(
        applicationId,
        documentId,
      );
      const url = URL.createObjectURL(download.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = download.fileName;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } else if (action === "validate") {
      result = await validateApplicationDocument(applicationId, documentId);
      appState.documentActionResults[String(documentId)] = {
        ...appState.documentActionResults[String(documentId)],
        validation: result,
      };
    } else if (action === "extract") {
      result = await extractApplicationDocument(applicationId, documentId);
      appState.documentActionResults[String(documentId)] = {
        ...appState.documentActionResults[String(documentId)],
        extraction: result,
      };
    } else if (action === "classify") {
      result = await classifyApplicationDocument(applicationId, documentId);
      appState.documentActionResults[String(documentId)] = {
        ...appState.documentActionResults[String(documentId)],
        classification: result,
      };
    }

    if (action === "classify") {
      await loadApplicationDocuments(applicationId);
    }
  } catch (error) {
    const results = appState.documentActionResults[String(documentId)] || {};
    const message = getDocumentActionError(error, action);

    if (action === "validate") {
      results.validation = { error: message };
    } else {
      const errorKey = {
        extract: "extractionError",
        classify: "classificationError",
        download: "downloadError",
      }[action];
      if (errorKey) {
        results[errorKey] = message;
      }
    }

    appState.documentActionResults[String(documentId)] = results;
  } finally {
    appState.documentActionsInProgress.delete(actionKey);

    if (appState.currentPage === "application-details") {
      renderApplicationDocumentList(
        document.getElementById("application-document-list"),
        appState.applicationDocuments || [],
      );
    }
  }
}

function renderApplicationDetails(content, application) {
  content.replaceChildren();

  const summary = document.createElement("header");
  summary.className = "application-details-summary";

  const summaryLabel = document.createElement("span");
  summaryLabel.className = "applications-state-label";
  summaryLabel.textContent = "Application record";
  summary.append(summaryLabel);

  const number = createApplicationDetailField(
    "Application number",
    application.application_number,
  );
  if (number) {
    number.classList.add("application-details-number");
    summary.append(number);
  }

  const status = createApplicationDetailField(
    "Current status",
    application.status,
  );
  if (status) {
    status.classList.add("application-details-status");
    summary.append(status);
  }

  content.append(summary);

  const fields = document.createElement("dl");
  fields.className = "application-details-grid";

  const applicationFields = [
    ["Application type", application.application_type],
    ["Title", application.title],
    ["Description", application.description],
    [
      "Applicant identifier",
      application.applicant_identifier === appState.currentUser?.identifier
        ? application.applicant_identifier
        : null,
    ],
    ["Submitted", formatApplicationDate(application.submitted_at)],
    ["Created", formatApplicationDate(application.created_at)],
    ["Last updated", formatApplicationDate(application.updated_at)],
  ];

  for (const [label, value] of applicationFields) {
    const field = createApplicationDetailField(label, value);
    if (field) {
      fields.append(field);
    }
  }

  if (fields.childElementCount) {
    content.append(fields);
  }

  if (
    appState.currentUser?.role === "STUDENT" &&
    application.status === "DRAFT" &&
    Number.isSafeInteger(application.id)
  ) {
    const submission = document.createElement("section");
    submission.className = "application-submit-controls";
    const explanation = document.createElement("p");
    explanation.textContent =
      "Submit this draft when it is ready. Submitted applications enter the shared Official queue and are visible to authorized Official accounts until one claims the application.";
    const submitButton = document.createElement("button");
    submitButton.type = "button";
    submitButton.className = "primary-button";
    submitButton.dataset.action = "submit-student-application";
    submitButton.textContent = "Submit to Official queue";
    submission.append(explanation, submitButton);
    content.append(submission);
  } else if (
    appState.currentUser?.role === "STUDENT" &&
    application.status === "SUBMITTED"
  ) {
    const submissionStatus = document.createElement("p");
    submissionStatus.className = "application-submit-status";
    submissionStatus.setAttribute("role", "status");
    submissionStatus.textContent =
      "Submitted to the shared Official queue. An Official will claim it for processing.";
    content.append(submissionStatus);
  }
}

function createApplicationDetailField(label, value) {
  if (
    (typeof value !== "string" && typeof value !== "number") ||
    String(value).trim() === ""
  ) {
    return null;
  }

  const item = document.createElement("div");
  item.className = "application-details-field";

  const term = document.createElement("dt");
  term.textContent = label;

  const description = document.createElement("dd");
  description.textContent = String(value);

  item.append(term, description);
  return item;
}

function formatApplicationDate(value) {
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
}

function renderApplicationDetailsMessage(
  content,
  title,
  message,
  canRetry = false,
) {
  content.replaceChildren();

  const panel = document.createElement("div");
  panel.className = "application-details-message";
  panel.setAttribute("role", "status");

  const heading = document.createElement("h2");
  heading.textContent = title;

  const description = document.createElement("p");
  description.textContent = message;
  panel.append(heading, description);

  if (canRetry) {
    const retryButton = document.createElement("button");
    retryButton.type = "button";
    retryButton.className = "secondary-button";
    retryButton.dataset.action = "retry-application-details";
    retryButton.textContent = "Try again";
    panel.append(retryButton);
  }

  content.append(panel);
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };

    return entities[character];
  });
}

function renderAssistantMessageMarkup(message) {
  const role = message?.role === "user" ? "user" : "assistant";
  const content = String(message?.content ?? "").trim();
  const sources = Array.isArray(message?.sources) ? message.sources : [];

  const sourceMarkup = sources.length
    ? `<ul class="assistant-sources">${sources
        .map((source) => {
          const title = source?.title ? String(source.title) : "Knowledge source";
          const page = source?.page ? `, p. ${String(source.page)}` : "";
          const citation = source?.citation ? ` · ${String(source.citation)}` : "";

          return `<li><strong>${escapeHTML(title)}</strong><span>${escapeHTML(page + citation)}</span></li>`;
        })
        .join("")}</ul>`
    : "";

  return `
    <div class="assistant-message assistant-message-${role}">
      <div class="assistant-message-bubble">
        <p>${escapeHTML(content || " ")}</p>
        ${sourceMarkup}
      </div>
    </div>
  `;
}

function renderStudentAssistantPage() {
  const state = appState.assistantState || {
    messages: [
      {
        role: "assistant",
        content:
          "Ask about undergraduate ordinances, degree requirements, or departmental procedures. Responses are informational only and should be checked against official rules and authorized human decisions.",
        sources: [],
      },
    ],
    isLoading: false,
    error: null,
  };

  const messageMarkup = state.messages
    .map((message) => renderAssistantMessageMarkup(message))
    .join("");

  return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Academic Services</span>
                    <h1>Academic Assistant</h1>
                    <p>Ask questions about academic rules and requirements using the official DepartmentAI knowledge base.</p>
                </div>
            </div>

            <div class="content-panel assistant-panel">
                <div class="assistant-box">
                    <div class="assistant-box-header">
                        <span class="assistant-badge">AI-Assisted</span>
                    </div>
                    <p>Academic guidance is informational and must be checked against official department requirements and authorized human decisions.</p>
                </div>

                <div class="assistant-chat" aria-live="polite">
                    ${messageMarkup}
                    ${state.isLoading ? `<div class="assistant-message assistant-message-assistant"><div class="assistant-message-bubble assistant-loading"><span class="assistant-loading-dot"></span><span class="assistant-loading-dot"></span><span class="assistant-loading-dot"></span></div></div>` : ""}
                </div>

                ${state.error ? `<div class="assistant-inline-error" role="alert">${escapeHTML(state.error)}</div>` : ""}

                <form id="assistant-question-form" class="assistant-form" novalidate>
                    <label for="assistant-question" class="assistant-label">Ask the Academic Assistant</label>
                    <textarea
                        id="assistant-question"
                        name="question"
                        rows="4"
                        placeholder="Ask about course requirements, academic rules, or department policy."
                        ${state.isLoading ? "disabled" : ""}
                    ></textarea>
                    <div class="assistant-form-actions">
                        <button type="button" class="secondary-button" data-action="clear-assistant-conversation" ${state.isLoading ? "disabled" : ""}>
                            Clear
                        </button>
                        <button type="submit" class="primary-button" ${state.isLoading ? "disabled" : ""}>
                            ${state.isLoading ? "Asking..." : "Ask"}
                        </button>
                    </div>
                </form>
            </div>
        </section>
    `;
}

function renderStudentSettingsPage() {
  const user = appState.currentUser;
  const profileItems = [
    ["Name", user?.name],
    ["Role", user?.role],
    ["Account identifier", user?.identifier],
  ]
    .filter(([, value]) => typeof value === "string" && value.trim())
    .map(
      ([label, value]) => `
        <div class="student-settings-field">
          <dt>${escapeHTML(label)}</dt>
          <dd>${escapeHTML(value.trim())}</dd>
        </div>
      `,
    )
    .join("");

  return `
    <section class="page-section student-settings-page" aria-labelledby="student-settings-title">
      <header class="page-heading">
        <div>
          <span class="eyebrow">Student Workspace</span>
          <h1 id="student-settings-title">Settings</h1>
          <p>Review the profile information available in this session and manage sign-out.</p>
        </div>
      </header>

      <section class="student-settings-card" aria-labelledby="student-profile-title">
        <div class="student-settings-card-heading">
          <div>
            <span class="applications-state-label">Session profile</span>
            <h2 id="student-profile-title">Account information</h2>
          </div>
        </div>
        <dl class="student-settings-fields">
          ${profileItems || '<div class="student-settings-field"><dt>Profile</dt><dd>Unavailable in this session</dd></div>'}
        </dl>
        <p class="student-settings-note" role="note">
          The session is authenticated by the local development backend and expires after 30 minutes.
          Institutional identity and password management are not configured.
        </p>
        <button type="button" class="secondary-button" data-action="logout">Sign out</button>
      </section>
    </section>
    `;
}

/* =========================================================
   Navigation UI
   ========================================================= */

function updateNavigation() {
  const activePage =
    appState.currentPage === "application-details"
      ? "applications"
      : appState.currentPage;

  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === activePage);
  });
}

function updatePageTitle() {
  const titleElement = document.getElementById("current-page-title");

  if (!titleElement) {
    return;
  }

  const roleTitles = {
    OFFICIAL: {
      dashboard: "Governance workspace",
      applications: "Application lookup",
      "application-processing": "Application processing review",
      committee: "Committee coordination",
      audit: "Audit access",
      settings: "Settings",
    },
    DUGC: {
      dashboard: "Governance workspace",
      applications: "Assigned application lookup",
      committee: "Committee review records",
      "decision-history": "Decision history",
      audit: "Audit access",
      settings: "Settings",
    },
  };
  titleElement.textContent =
    roleTitles[appState.currentUser?.role]?.[appState.currentPage] ||
    pageTitles[appState.currentPage] ||
    "DepartmentAI";
}

function renderRoleApplicationActions(application) {
  const panel = document.getElementById("role-application-actions");
  if (!panel) {
    return;
  }
  panel.replaceChildren();
  panel.hidden = false;

  const heading = document.createElement("h2");
  heading.textContent = "Authorized workflow actions";
  panel.append(heading);

  const feedback = document.createElement("p");
  feedback.dataset.roleActionFeedback = "";
  feedback.setAttribute("role", "status");
  panel.append(feedback);

  if (appState.currentUser?.role === "OFFICIAL") {
    const transitions = Array.isArray(application.allowed_transitions)
      ? application.allowed_transitions.filter(
          (value) => typeof value === "string",
        )
      : [];
    if (transitions.length) {
      const form = document.createElement("form");
      form.dataset.roleStatusUpdate = "";
      const label = document.createElement("label");
      label.textContent = "Next application status";
      const select = document.createElement("select");
      select.name = "new_status";
      select.required = true;
      for (const transition of transitions) {
        const option = document.createElement("option");
        option.value = transition;
        option.textContent = transition.replaceAll("_", " ");
        select.append(option);
      }
      label.append(select);
      const reasonLabel = document.createElement("label");
      reasonLabel.textContent = "Review note (optional)";
      const reason = document.createElement("textarea");
      reason.name = "reason";
      reason.maxLength = 2000;
      reasonLabel.append(reason);
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "primary-button";
      submit.textContent = "Update status";
      form.append(label, reasonLabel, submit);
      panel.append(form);
    }

    if (application.status === "COMMITTEE_REVIEW") {
      const form = document.createElement("form");
      form.dataset.roleCommitteeAssignment = "";
      const label = document.createElement("label");
      label.textContent = "Assign committee";
      const select = document.createElement("select");
      select.name = "committee_type";
      select.required = true;
      for (const type of ["DUGC", "DMPC", "DDPC"]) {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = type;
        select.append(option);
      }
      label.append(select);
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "secondary-button";
      submit.textContent = "Assign committee";
      form.append(label, submit);
      panel.append(form);
    }
  }
}

async function loadRoleWorkspaceApplication(applicationId, form) {
  const result = document.getElementById("role-application-lookup-result");
  const error = form.querySelector("[data-role-lookup-error]");
  const submit = form.querySelector('button[type="submit"]');
  const requestId = ++appState.roleWorkspaceRequestId;

  if (!result || !error || !submit) {
    return;
  }

  result.replaceChildren();
  result.setAttribute("aria-busy", "true");
  const loading = document.createElement("p");
  loading.className = "role-workspace-empty";
  loading.setAttribute("role", "status");
  loading.textContent = "Loading application information…";
  result.append(loading);
  error.hidden = true;
  submit.disabled = true;
  submit.textContent = "Loading…";

  try {
    const application = await getApplication(applicationId);
    if (
      requestId !== appState.roleWorkspaceRequestId ||
      appState.currentUser?.role === "STUDENT"
    ) {
      return;
    }

    if (
      !application ||
      typeof application !== "object" ||
      Array.isArray(application)
    ) {
      throw new Error("The application service returned an invalid record.");
    }

    appState.selectedApplicationId = applicationId;
    renderRoleApplicationRecord(result, application);
    renderRoleApplicationActions(application);
    const reads = [
      ["role-review-documents", "documents", () => getApplicationDocuments(applicationId)],
      ["role-review-status", "status history", () => getStatusHistory(applicationId)],
      ["role-review-committees", "committee reviews", () => getCommitteeReviews(applicationId)],
    ];

    await Promise.all(
      reads.map(async ([containerId, label, load]) => {
        const container = document.getElementById(containerId);
        if (!container) {
          return;
        }

        container.replaceChildren();
        container.setAttribute("aria-busy", "true");
        const status = document.createElement("p");
        status.setAttribute("role", "status");
        status.textContent = `Loading ${label}…`;
        container.append(status);

        try {
          const response = await load();
          if (requestId !== appState.roleWorkspaceRequestId) {
            return;
          }
          renderRoleReadOnlyResponse(container, response);
        } catch (readError) {
          if (requestId !== appState.roleWorkspaceRequestId) {
            return;
          }
          renderRoleReadOnlyError(container, readError, label);
        }
      }),
    );
  } catch (lookupError) {
    if (requestId !== appState.roleWorkspaceRequestId) {
      return;
    }
    renderRoleLookupError(result, lookupError);
  } finally {
    if (requestId === appState.roleWorkspaceRequestId) {
      result.setAttribute("aria-busy", "false");
      submit.disabled = false;
      submit.textContent = "Load record";
    }
  }
}

function renderRoleApplicationRecord(container, application) {
  container.replaceChildren();
  const heading = document.createElement("h3");
  heading.textContent =
    typeof application.application_number === "string"
      ? application.application_number
      : "Application record";
  container.append(heading);

  const fields = document.createElement("dl");
  fields.className = "application-details-grid";
  for (const [label, value] of [
    ["Application ID", application.id],
    ["Application type", application.application_type],
    ["Title", application.title],
    ["Description", application.description],
    ["Applicant identifier", application.applicant_identifier],
    ["Current status", application.status],
    ["Submitted", formatApplicationDate(application.submitted_at)],
    ["Created", formatApplicationDate(application.created_at)],
    ["Last updated", formatApplicationDate(application.updated_at)],
  ]) {
    const field = createApplicationDetailField(label, value);
    if (field) {
      fields.append(field);
    }
  }
  container.append(fields);
}

function renderRoleReadOnlyResponse(container, response) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");
  const collectionKey = [
    "documents",
    "history",
    "reviews",
    "results",
    "deficiencies",
  ].find((key) => Array.isArray(response?.[key]));
  const records = collectionKey ? response[collectionKey] : [response];

  if (records.length === 0) {
    const empty = document.createElement("p");
    empty.className = "role-workspace-empty";
    empty.textContent = "The service returned no records for this section.";
    container.append(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "role-review-record-list";
  for (const record of records) {
    if (!record || typeof record !== "object" || Array.isArray(record)) {
      continue;
    }
    const article = document.createElement("article");
    article.className = "role-review-record";
    const heading = document.createElement("h3");
    heading.textContent =
      record.file_name ||
      record.decision ||
      record.new_status ||
      record.committee_type ||
      record.title ||
      `${collectionKey || "Service"} record`;
    article.append(heading);

    const fields = document.createElement("dl");
    for (const [key, value] of Object.entries(record)) {
      if (
        value == null ||
        typeof value === "object" ||
        /file_path|actor_id|changed_by|decided_by|uploaded_by/i.test(key)
      ) {
        continue;
      }
      const field = createApplicationDetailField(
        formatWorkspaceFieldLabel(key),
        value,
      );
      if (field) {
        fields.append(field);
      }
    }
    if (fields.childElementCount) {
      article.append(fields);
    }
    if (
      collectionKey === "documents" &&
      Number.isSafeInteger(record.id)
    ) {
      article.append(
        createDocumentActionButton(record.id, "download", "Download document"),
      );
    }
    if (
      container.id === "role-review-committees" &&
      appState.currentUser?.role === "DUGC" &&
      record.review_status !== "COMPLETED" &&
      Number.isSafeInteger(record.id)
    ) {
      const form = document.createElement("form");
      form.dataset.roleCommitteeDecision = "";
      form.dataset.reviewId = String(record.id);
      const decisionLabel = document.createElement("label");
      decisionLabel.textContent = "Committee decision";
      const decision = document.createElement("select");
      decision.name = "decision";
      decision.required = true;
      for (const value of ["APPROVED", "REJECTED"]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        decision.append(option);
      }
      decisionLabel.append(decision);
      const reasonLabel = document.createElement("label");
      reasonLabel.textContent = "Decision rationale (required)";
      const reason = document.createElement("textarea");
      reason.name = "decision_reason";
      reason.maxLength = 2000;
      reason.required = true;
      reasonLabel.append(reason);
      const submit = document.createElement("button");
      submit.type = "submit";
      submit.className = "primary-button";
      submit.textContent = "Record human decision";
      form.append(decisionLabel, reasonLabel, submit);
      article.append(form);
    }

    if (typeof record.chunk_text === "string" && record.chunk_text.trim()) {
      const excerpt = document.createElement("p");
      excerpt.className = "role-review-excerpt";
      excerpt.textContent = record.chunk_text;
      article.append(excerpt);
    }
    list.append(article);
  }
  if (list.childElementCount) {
    container.append(list);
  } else {
    renderRoleReadOnlyError(
      container,
      new Error("No displayable records were returned."),
      collectionKey || "review information",
    );
  }
}

function formatWorkspaceFieldLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function renderRoleReadOnlyError(container, error, section) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");
  const message = document.createElement("p");
  message.className = "role-workspace-error";
  message.setAttribute("role", "status");
  message.textContent = getRoleWorkspaceErrorText(error, section);
  container.append(message);
}

function renderRoleLookupError(container, error) {
  container.replaceChildren();
  const message = document.createElement("p");
  message.className = "role-workspace-error";
  message.setAttribute("role", "alert");
  message.textContent = getRoleWorkspaceErrorText(error, "application record");
  container.append(message);
}

function getRoleWorkspaceErrorText(error, resource) {
  if (error instanceof APIError && error.status === 404) {
    return `The ${resource} was not found.`;
  }
  if (error instanceof APIError && error.status === 0) {
    return error.message === "The backend request timed out."
      ? `The request for ${resource} timed out. Check database/API reachability before retrying.`
      : `The backend could not be reached for ${resource}. Check the API origin and browser CORS settings.`;
  }
  if (error instanceof APIError && error.status === 401) {
    return `The backend rejected the ${resource} request as unauthenticated.`;
  }
  if (error instanceof APIError && error.status === 403) {
    return `The backend denied access to the ${resource}.`;
  }
  return `The service could not load the ${resource}.`;
}

/* =========================================================
   Global Application Events
   ========================================================= */

function setupApplicationEvents() {
  const app = document.getElementById("app");

  app.onclick = handleApplicationClick;
  app.onsubmit = handleApplicationSubmit;
  app.onchange = handleApplicationChange;

  document.onkeydown = handleDocumentKeydown;
}

async function submitRoleWorkflowAction(form) {
  const applicationId = appState.selectedApplicationId;
  const submit = form.querySelector('button[type="submit"]');
  if (!Number.isSafeInteger(applicationId) || !submit) {
    return;
  }
  const data = new FormData(form);
  submit.disabled = true;
  const label = submit.textContent;
  submit.textContent = "Saving…";

  try {
    if (form.matches("[data-role-status-update]")) {
      await updateApplicationStatus(applicationId, {
        new_status: String(data.get("new_status")),
        reason: String(data.get("reason") || "").trim() || null,
      });
    } else if (form.matches("[data-role-committee-assignment]")) {
      await assignApplicationToCommittee(applicationId, {
        committee_type: String(data.get("committee_type")),
      });
    } else if (form.matches("[data-role-committee-decision]")) {
      await updateCommitteeDecision(Number(form.dataset.reviewId), {
        decision: String(data.get("decision")),
        decision_reason: String(data.get("decision_reason")).trim(),
      });
    }

    const lookupForm = document.querySelector(
      "[data-role-application-lookup]",
    );
    if (!lookupForm) {
      return;
    }
    await loadRoleWorkspaceApplication(applicationId, lookupForm);
    const feedback = document.querySelector("[data-role-action-feedback]");
    if (feedback) {
      feedback.textContent = "The backend confirmed the workflow action.";
    }
  } catch (error) {
    const feedback = document.querySelector("[data-role-action-feedback]");
    if (feedback) {
      feedback.textContent =
        error instanceof APIError
          ? error.message
          : "The workflow action could not be completed.";
      feedback.setAttribute("role", "alert");
    }
  } finally {
    if (submit.isConnected) {
      submit.disabled = false;
      submit.textContent = label;
    }
  }
}

async function handleApplicationSubmit(event) {
  const form = event.target;

  if (
    form.matches(
      "[data-role-status-update], [data-role-committee-assignment], [data-role-committee-decision]",
    )
  ) {
    event.preventDefault();
    if (!form.reportValidity()) {
      return;
    }
    await submitRoleWorkflowAction(form);
    return;
  }

  if (form.matches("[data-role-application-lookup]")) {
    event.preventDefault();
    const idInput = form.elements.namedItem("application_id");
    const applicationId = Number(idInput.value);
    idInput.setCustomValidity(
      Number.isSafeInteger(applicationId) && applicationId > 0
        ? ""
        : "Enter a positive whole-number application ID.",
    );
    if (!form.reportValidity()) {
      return;
    }

    await loadRoleWorkspaceApplication(applicationId, form);
    return;
  }

  if (form.matches("#assistant-question-form")) {
    event.preventDefault();
    await submitAssistantQuestion(form);
    return;
  }

  if (form.matches("#application-document-upload-form")) {
    event.preventDefault();
    await submitApplicationDocument(form);
    return;
  }

  if (!form.matches("#create-application-form")) {
    return;
  }

  event.preventDefault();

  if (form.dataset.submitting === "true") {
    return;
  }

  const applicationTypeInput = form.elements.namedItem("application_type");
  applicationTypeInput.setCustomValidity(
    applicationTypeInput.value.trim() ? "" : "Enter an application type.",
  );

  if (!form.reportValidity()) {
    return;
  }

  const formData = new FormData(form);
  const requestBody = {
    application_type: applicationTypeInput.value.trim(),
    title: formData.get("title")?.trim() || null,
    description: formData.get("description")?.trim() || null,
  };
  const submitButton = form.querySelector("#create-application-submit");
  const loadingMessage = form.querySelector("#application-submit-loading");
  const errorMessage = form.querySelector("#application-submit-error");

  form.dataset.submitting = "true";
  form.setAttribute("aria-busy", "true");
  submitButton.disabled = true;
  submitButton.textContent = "Creating application…";
  loadingMessage.hidden = false;
  errorMessage.hidden = true;

  try {
    const response = await createApplication(requestBody);
    showApplicationSubmissionSuccess(form, response);
  } catch (error) {
    showApplicationSubmissionError(form, getApplicationSubmissionError(error));
  } finally {
    form.dataset.submitting = "false";
    form.removeAttribute("aria-busy");
    loadingMessage.hidden = true;

    if (!form.hidden) {
      submitButton.disabled = false;
      submitButton.textContent = "Create Application";
    }
  }
}

function handleApplicationChange(event) {
  if (!event.target.matches("#application-document-file")) {
    return;
  }

  const file = event.target.files?.[0];
  const selectedFile = document.getElementById(
    "application-document-selected-file",
  );

  if (selectedFile) {
    selectedFile.textContent = file?.name || "No file selected";
  }

  event.target.setCustomValidity("");
}

async function submitApplicationDocument(form) {
  if (appState.documentUploadInProgress) {
    return;
  }

  const applicationId = appState.selectedApplicationId;
  const fileInput = form.elements.namedItem("file");
  const file = fileInput.files?.[0];
  const extension = file?.name.match(/\.[^.]+$/)?.[0]?.toLowerCase() || "";
  const allowedExtensions = new Set([".pdf", ".jpg", ".jpeg", ".png"]);

  fileInput.setCustomValidity(
    !file
      ? "Choose a document to upload."
      : !allowedExtensions.has(extension)
        ? "Choose a PDF, JPG, JPEG, or PNG file."
        : "",
  );

  if (!form.reportValidity()) {
    return;
  }

  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    showDocumentUploadError(
      form,
      "No application is selected. Return to Application Details and try again.",
    );
    return;
  }

  const formData = new FormData(form);
  if (!formData.get("document_type")) {
    formData.delete("document_type");
  }

  const submitButton = form.querySelector(
    "#application-document-upload-button",
  );
  const errorMessage = form.querySelector("#document-upload-error");
  const statusMessage = form.querySelector("#document-upload-status");

  appState.documentUploadInProgress = true;
  form.dataset.uploading = "true";
  form.setAttribute("aria-busy", "true");
  submitButton.disabled = true;
  submitButton.textContent = "Uploading…";
  errorMessage.hidden = true;
  statusMessage.textContent = "Uploading document…";
  statusMessage.hidden = false;

  try {
    const response = await uploadApplicationDocument(applicationId, formData);
    const returnedFileName =
      typeof response?.file_name === "string" && response.file_name.trim()
        ? response.file_name
        : "";

    statusMessage.textContent = returnedFileName
      ? `The service confirmed the upload of ${returnedFileName}.`
      : "The service confirmed the document upload.";
    form.reset();
    document.getElementById("application-document-selected-file").textContent =
      "No file selected";
    fileInput.setCustomValidity("");
    await loadApplicationDocuments(applicationId);
  } catch (error) {
    statusMessage.hidden = true;
    showDocumentUploadError(form, getDocumentActionError(error, "upload"));
  } finally {
    appState.documentUploadInProgress = false;
    form.dataset.uploading = "false";
    form.removeAttribute("aria-busy");
    submitButton.disabled = false;
    submitButton.textContent = "Upload document";
  }
}

function showDocumentUploadError(form, message) {
  const errorMessage = form.querySelector("#document-upload-error");

  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function getDocumentActionError(error, action) {
  const pastTense =
    {
      upload: "uploaded",
      validate: "validated",
      extract: "extracted",
      classify: "classified",
    }[action] || "processed";

  if (!(error instanceof APIError)) {
    return `Unable to ${action} this document right now. Please try again.`;
  }

  if (error.status === 0) {
    return `The service could not be reached, so we could not confirm the document was ${pastTense}.`;
  }

  if (error.status === 400) {
    return action === "upload"
      ? "This file could not be accepted. Choose a supported file and try again."
      : `The document could not be ${pastTense}. Review the document and try again.`;
  }

  if (error.status === 404) {
    return "This application or document could not be found.";
  }

  if (error.status >= 500) {
    return `The service could not ${action} this document. Please try again later.`;
  }

  return `Unable to ${action} this document right now. Please try again.`;
}

function showApplicationSubmissionSuccess(form, response) {
  const successPanel = document.getElementById("application-submit-success");
  const successDetails = document.getElementById("application-success-details");
  const successActions = successPanel.querySelector(
    ".create-application-actions",
  );

  successDetails.replaceChildren();
  successActions.querySelector('[data-page="application-details"]')?.remove();

  appState.selectedApplicationId =
    Number.isSafeInteger(response?.id) && response.id > 0 ? response.id : null;

  if (appState.selectedApplicationId !== null) {
    const detailsButton = document.createElement("button");
    detailsButton.type = "button";
    detailsButton.className = "secondary-button";
    detailsButton.dataset.page = "application-details";
    detailsButton.dataset.applicationId = String(
      appState.selectedApplicationId,
    );
    detailsButton.textContent = "View application details";
    successActions.prepend(detailsButton);
  }

  if (
    typeof response?.application_number === "string" &&
    response.application_number.trim()
  ) {
    const applicationNumber = document.createElement("p");
    applicationNumber.textContent = `Application number: ${response.application_number}`;
    successDetails.append(applicationNumber);
  }

  if (typeof response?.status === "string" && response.status.trim()) {
    const applicationStatus = document.createElement("p");
    applicationStatus.textContent = `Status: ${response.status}`;
    successDetails.append(applicationStatus);
  }

  form.hidden = true;
  successPanel.hidden = false;
}

function showApplicationSubmissionError(form, message) {
  const errorMessage = form.querySelector("#application-submit-error");

  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function getApplicationSubmissionError(error) {
  if (!(error instanceof APIError)) {
    return "Unable to submit your application right now. Please try again.";
  }

  if (error.status === 0) {
    return "The service is unavailable, so we could not confirm whether your application was created. Please contact the department before trying again.";
  }

  if (error.status === 400 || error.status === 422) {
    return "Please review the application details. The service could not accept this request.";
  }

  if (error.status === 401 || error.status === 403) {
    return "You do not have permission to submit this application. Sign in again or contact the department.";
  }

  if (error.status >= 500) {
    return "The service could not confirm completion. Please contact the department before trying again.";
  }

  return "Unable to submit your application right now. Please try again.";
}

function resetAssistantConversation() {
  appState.assistantState = {
    messages: [
      {
        role: "assistant",
        content:
          "Ask about undergraduate ordinances, degree requirements, or departmental procedures. Responses are informational only and should be checked against official rules and authorized human decisions.",
        sources: [],
      },
    ],
    isLoading: false,
    error: null,
  };

  if (appState.currentPage === "assistant") {
    const pageContent = document.getElementById("page-content");
    if (pageContent) {
      pageContent.innerHTML = renderStudentAssistantPage();
    }
  }
}

async function submitAssistantQuestion(form) {
  const questionInput = form?.querySelector("#assistant-question");
  const question = questionInput?.value?.trim();

  if (!question) {
    appState.assistantState.error = "Please enter a question before submitting.";
    if (appState.currentPage === "assistant") {
      const pageContent = document.getElementById("page-content");
      if (pageContent) {
        pageContent.innerHTML = renderStudentAssistantPage();
      }
    }
    return;
  }

  const state = appState.assistantState;
  state.error = null;
  state.isLoading = true;
  state.messages.push({ role: "user", content: question, sources: [] });

  if (appState.currentPage === "assistant") {
    const pageContent = document.getElementById("page-content");
    if (pageContent) {
      pageContent.innerHTML = renderStudentAssistantPage();
    }
  }

  try {
    const conversationHistory = state.messages
      .slice(0, -1)
      .filter((message) => message?.role && ["user", "assistant"].includes(message.role))
      .map((message) => ({
        role: message.role,
        message: String(message.content ?? "").trim(),
      }))
      .filter((message) => message.message.length > 0);

    const response = await askQuestion(question, conversationHistory);
    state.messages.push({
      role: "assistant",
      content: response?.answer || "I could not generate a response for that question.",
      sources: Array.isArray(response?.sources) ? response.sources : [],
    });
  } catch (error) {
    const errorMessage =
      error instanceof APIError && error.message
        ? error.message
        : "I could not answer that question right now. Please try again.";
    state.error = errorMessage;
  } finally {
    state.isLoading = false;
    if (appState.currentPage === "assistant") {
      const pageContent = document.getElementById("page-content");
      if (pageContent) {
        pageContent.innerHTML = renderStudentAssistantPage();
      }
    }
    if (form) {
      form.reset();
    }
  }
}

function handleApplicationClick(event) {
  const navigationTarget = event.target.closest("[data-page]");

  if (navigationTarget) {
    event.preventDefault();

    const page = navigationTarget.dataset.page;

    if (page) {
      if (
        page === "application-details" &&
        navigationTarget.dataset.applicationId
      ) {
        const applicationId = Number(navigationTarget.dataset.applicationId);
        appState.selectedApplicationId =
          Number.isSafeInteger(applicationId) && applicationId > 0
            ? applicationId
            : null;
      }

      navigateTo(page);
      if (
        navigationTarget.dataset.applicationId &&
        appState.currentUser?.role !== "STUDENT"
      ) {
        const form = document.querySelector("[data-role-application-lookup]");
        const input = form?.elements.namedItem("application_id");
        if (form && input) {
          input.value = navigationTarget.dataset.applicationId;
          form.requestSubmit();
        }
      }
      closeMobileMenu();
    }

    return;
  }

  const retryQueueButton = event.target.closest(
    '[data-action="retry-application-queue"]',
  );
  if (retryQueueButton) {
    const isUnassigned =
      retryQueueButton.dataset.queueType === "unassigned-official";
    void loadApplicationQueue(
      retryQueueButton.dataset.queueContainer,
      retryQueueButton.dataset.queuePage,
      Number(retryQueueButton.dataset.queueLimit) || 20,
      isUnassigned ? getUnassignedOfficialApplications : listApplications,
      isUnassigned
        ? "No unassigned submissions are waiting for an Official."
        : undefined,
    );
    return;
  }

  const claimButton = event.target.closest(
    '[data-action="claim-official-application"]',
  );
  if (claimButton) {
    void claimOfficialQueueApplication(claimButton);
    return;
  }

  const submitApplicationButton = event.target.closest(
    '[data-action="submit-student-application"]',
  );
  if (submitApplicationButton) {
    void submitStudentApplicationFromDetails(submitApplicationButton);
    return;
  }

  const documentActionButton = event.target.closest("[data-document-action]");

  if (documentActionButton) {
    void runApplicationDocumentAction(documentActionButton);
    return;
  }

  const retryDocumentListButton = event.target.closest(
    '[data-action="retry-document-list"]',
  );

  if (retryDocumentListButton) {
    void loadApplicationDocuments(appState.selectedApplicationId);
    return;
  }

  const retryDetailsButton = event.target.closest(
    '[data-action="retry-application-details"]',
  );

  if (retryDetailsButton) {
    void loadStudentApplicationDetails(appState.selectedApplicationId);
    return;
  }

  const retryWorkflowButton = event.target.closest(
    '[data-action="retry-application-workflow"]',
  );

  if (retryWorkflowButton) {
    const resourceKey = retryWorkflowButton.dataset.workflowResource;
    const workflow = appState.applicationWorkflowState;
    const state = workflow?.[resourceKey];
    if (state) {
      state.status = "idle";
      void loadApplicationWorkflowPanel(
        appState.selectedApplicationId,
        resourceKey,
      );
    }
    return;
  }

  const eligibilityButton = event.target.closest(
    '[data-action="run-eligibility-analysis"]',
  );

  if (eligibilityButton) {
    void runAcademicReviewAction("eligibility");
    return;
  }

  const deficienciesButton = event.target.closest(
    '[data-action="refresh-deficiencies"]',
  );

  if (deficienciesButton) {
    void runAcademicReviewAction("deficiencies");
    return;
  }

  const clearAssistantButton = event.target.closest(
    '[data-action="clear-assistant-conversation"]',
  );

  if (clearAssistantButton) {
    resetAssistantConversation();
    return;
  }

  const aiAnalysisButton = event.target.closest(
    '[data-action="generate-ai-analysis"]',
  );

  if (aiAnalysisButton) {
    void runAiAnalysis();
    return;
  }

  const retryAiAnalysisButton = event.target.closest(
    '[data-action="retry-ai-analysis"]',
  );

  if (retryAiAnalysisButton) {
    const state = appState.aiAnalysisState;
    if (
      state &&
      state.applicationId === appState.selectedApplicationId
    ) {
      state.status = "idle";
    }
    void runAiAnalysis();
    return;
  }

  const mobileMenuButton = event.target.closest("#mobile-menu-button");

  if (mobileMenuButton) {
    const sidebar = document.getElementById("sidebar");

    const isOpen = sidebar?.classList.toggle("mobile-open");

    mobileMenuButton.setAttribute("aria-expanded", String(Boolean(isOpen)));

    return;
  }

  const logoutButton = event.target.closest("[data-action='logout']");

  if (logoutButton) {
    logout();
  }

  const closeMobileMenuButton = event.target.closest(
    "[data-action='close-mobile-menu']",
  );

  if (closeMobileMenuButton) {
    closeMobileMenu();
  }
}

function handleDocumentKeydown(event) {
  if (event.key !== "Escape") {
    return;
  }

  const sidebar = document.getElementById("sidebar");

  if (sidebar?.classList.contains("mobile-open")) {
    closeMobileMenu();
  }
}

function closeMobileMenu() {
  const sidebar = document.getElementById("sidebar");

  const menuButton = document.getElementById("mobile-menu-button");

  sidebar?.classList.remove("mobile-open");
  menuButton?.setAttribute("aria-expanded", "false");
}

/* =========================================================
   Logout
   ========================================================= */

async function logout() {
  let logoutError = null;
  try {
    await logoutUser();
  } catch {
    logoutError =
      "This browser cleared its session, but the server could not confirm revocation. The session expires automatically within 30 minutes.";
  }
  appState.currentUser = null;

  appState.currentPage = "dashboard";

  appState.selectedLoginRole = null;

  renderLogin();
  if (logoutError) {
    const message = document.getElementById("login-global-message");
    if (message) {
      message.textContent = logoutError;
      message.hidden = false;
    }
  }
}

/* =========================================================
   Start Application
   ========================================================= */

initializeApp();
