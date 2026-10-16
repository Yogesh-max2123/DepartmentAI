import { renderSidebar } from "./components/layout/sidebar.js";
import { renderTopbar } from "./components/layout/topbar.js";

import { renderLoginPage } from "./pages/login/login-page.js";

import { renderStudentLogin } from "./components/auth/student-login.js";
import { renderOfficialLogin } from "./components/auth/official-login.js";
import { renderDUGCLogin } from "./components/auth/dugc-login.js";

import { renderStudentDashboard } from "./pages/student/student-dashboard.js";

import {
  APIError,
  classifyApplicationDocument,
  createApplication,
  extractApplicationDocument,
  getApplication,
  getApplicationDocuments,
  getDeficiencies,
  getEligibility,
  getOrdinanceRetrieval,
  uploadApplicationDocument,
  validateApplicationDocument,
} from "./services/api.js";
import { loginUser, getCurrentUser, logoutUser } from "./services/auth.js";
const appState = {
  currentUser: getCurrentUser(),
  currentPage: "dashboard",
  selectedLoginRole: null,
  selectedApplicationId: null,
  applicationDetailsRequestId: 0,
  documentListRequestId: 0,
  documentUploadInProgress: false,
  documentActionsInProgress: new Set(),
  documentActionResults: {},
  academicReviewState: null,
  academicReviewRequestId: 0,
  academicReviewActionsInProgress: new Set(),
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
  if (appState.currentUser) {
    renderApplicationShell();
    navigateTo("dashboard");
  } else {
    renderLogin();
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

function handleLoginSubmit(event) {
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

  const user = loginUser(role, formData);

  if (!user) {
    showLoginError(role, "Please enter the required information.");

    return;
  }

  appState.currentUser = user;

  appState.currentPage = "dashboard";

  appState.selectedLoginRole = null;

  renderApplicationShell();

  setupApplicationEvents();

  navigateTo("dashboard");
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

  appState.currentPage = page;

  const pageContent = document.getElementById("page-content");

  if (!pageContent) {
    return;
  }

  if (appState.currentUser.role === "STUDENT") {
    pageContent.innerHTML = renderStudentPage(page);
  } else {
    pageContent.innerHTML = renderPlaceholderPage(page);
  }

  updateNavigation();
  updatePageTitle();

  if (page === "application-details") {
    void loadStudentApplicationDetails(appState.selectedApplicationId);
    void loadApplicationDocuments(appState.selectedApplicationId);
    void loadOrdinanceContext(appState.selectedApplicationId);
    restoreAcademicReviewPanels(appState.selectedApplicationId);
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

  return renderPlaceholderPage(page);
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

      <section class="applications-empty-state" aria-labelledby="applications-empty-title">
        <div class="applications-empty-mark" aria-hidden="true">▣</div>
        <div class="applications-empty-content">
          <span class="applications-state-label">Application records</span>
          <h2 id="applications-empty-title">Your applications will appear here</h2>
          <p>Your academic applications will be displayed here when application records are available.</p>
          <p class="applications-availability" role="status">
            Application listings are not currently available through the connected service.
          </p>
          <button type="button" class="primary-button" data-page="create-application">
            Create Application
          </button>
        </div>
      </section>
    </section>
  `;
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

        <section class="academic-review-panel" aria-labelledby="ordinance-context-title">
          <header class="academic-review-panel-heading">
            <div>
              <span class="applications-state-label">Retrieved reference material</span>
              <h3 id="ordinance-context-title">Retrieved Ordinance Context</h3>
            </div>
          </header>
          <div id="ordinance-context-content" class="academic-review-panel-content" aria-live="polite" aria-busy="true">
            <p class="academic-review-loading" role="status">Retrieving relevant ordinance context…</p>
          </div>
        </section>

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

function getAcademicReviewState(applicationId) {
  if (
    !appState.academicReviewState ||
    appState.academicReviewState.applicationId !== applicationId
  ) {
    appState.academicReviewState = {
      applicationId,
      ordinance: { status: "idle", data: null, error: null, requestId: 0 },
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

async function loadOrdinanceContext(applicationId) {
  const container = document.getElementById("ordinance-context-content");

  if (!container) {
    return;
  }

  if (!Number.isSafeInteger(applicationId) || applicationId <= 0) {
    renderM08Message(
      container,
      "No application selected",
      "Open an application to retrieve its relevant ordinance context.",
    );
    return;
  }

  const state = getAcademicReviewState(applicationId).ordinance;

  if (state.status === "success") {
    renderOrdinanceContext(container, state.data);
    return;
  }

  if (state.status === "loading") {
    return;
  }

  const requestId = ++state.requestId;
  state.status = "loading";
  renderM08Loading(container, "Retrieving relevant ordinance context…");

  try {
    const response = await getOrdinanceRetrieval(applicationId);

    if (!isCurrentAcademicReviewRequest("ordinance", applicationId, requestId)) {
      return;
    }

    if (!response || typeof response !== "object" || !Array.isArray(response.results)) {
      throw new Error("The ordinance service returned an invalid response.");
    }

    state.status = "success";
    state.data = response;
    state.error = null;
    renderOrdinanceContext(container, response);
  } catch (error) {
    if (!isCurrentAcademicReviewRequest("ordinance", applicationId, requestId)) {
      return;
    }

    state.status = "error";
    state.error = error;
    renderM08Message(
      container,
      error instanceof APIError && error.status === 404
        ? "Application not found"
        : "Unable to retrieve ordinance context",
      getAcademicReviewErrorMessage(error, "ordinance context"),
      "retry-ordinance-context",
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

function renderOrdinanceContext(container, response) {
  container.replaceChildren();
  container.setAttribute("aria-busy", "false");

  if (typeof response.query === "string" && response.query.trim()) {
    const query = document.createElement("p");
    query.className = "ordinance-context-query";
    query.textContent = `Retrieved for: ${response.query}`;
    container.append(query);
  }

  if (response.results.length === 0) {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent =
      "No ordinance context was returned for this application.";
    container.append(empty);
    return;
  }

  const results = document.createElement("div");
  results.className = "ordinance-context-results";

  for (const result of response.results) {
    if (!result || typeof result !== "object" || Array.isArray(result)) {
      continue;
    }

    const article = document.createElement("article");
    article.className = "ordinance-context-item";

    const references = [];
    if (isDisplayableValue(result.clause_number)) {
      references.push(`Clause ${result.clause_number}`);
    }
    if (
      isDisplayableValue(result.section_number) ||
      isDisplayableValue(result.section_title)
    ) {
      references.push(
        [result.section_number, result.section_title]
          .filter(isDisplayableValue)
          .join(" · "),
      );
    }
    if (
      Number.isFinite(result.page_start) &&
      Number.isFinite(result.page_end)
    ) {
      references.push(
        result.page_start === result.page_end
          ? `Page ${result.page_start}`
          : `Pages ${result.page_start}–${result.page_end}`,
      );
    }
    if (isDisplayableValue(result.chunk_id)) {
      references.push(`Source ${result.chunk_id}`);
    }

    if (references.length) {
      const referenceLine = document.createElement("p");
      referenceLine.className = "ordinance-context-reference";
      referenceLine.textContent = references.join("  |  ");
      article.append(referenceLine);
    }

    if (typeof result.chunk_text === "string" && result.chunk_text.trim()) {
      const text = document.createElement("p");
      text.className = "ordinance-context-text";
      text.textContent = result.chunk_text;
      article.append(text);
    }

    if (article.childElementCount) {
      results.append(article);
    }
  }

  if (!results.childElementCount) {
    const empty = document.createElement("p");
    empty.className = "academic-review-empty";
    empty.textContent =
      "The retrieval response did not contain displayable ordinance text.";
    container.append(empty);
    return;
  }

  container.append(results);
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
    if (action === "validate") {
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

function renderStudentAssistantPage() {
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
                <div class="empty-state compact-empty">
                    <div class="empty-state-icon">✦</div>
                    <h3>Assistant not yet connected</h3>
                    <p>The knowledge-base-backed assistant will be wired into this view once the student-side Q&A flow is connected.</p>
                </div>
            </div>
        </section>
    `;
}

function renderStudentSettingsPage() {
  return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Student Workspace</span>
                    <h1>Settings</h1>
                    <p>Manage your student workspace preferences and account information.</p>
                </div>
            </div>

            <div class="content-panel">
                <div class="empty-state">
                    <div class="empty-state-icon">⚙</div>
                    <h3>Student settings</h3>
                    <p>Profile and preference settings will be added here when the role-specific account configuration is implemented.</p>
                </div>
            </div>
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

  titleElement.textContent = pageTitles[appState.currentPage] || "DepartmentAI";
}

/* =========================================================
   Placeholder Pages
   ========================================================= */

function renderPlaceholderPage(page) {
  const title = pageTitles[page] || "DepartmentAI";

  return `
        <section class="page-section">

            <div class="page-heading">

                <div>

                    <span class="eyebrow">
                        DepartmentAI
                    </span>

                    <h1>
                        ${title}
                    </h1>

                    <p>
                        This workspace will be connected
                        to the DepartmentAI application
                        processing system.
                    </p>

                </div>

            </div>


            <div class="content-panel">

                <div class="empty-state">

                    <div class="empty-state-icon">
                        ✦
                    </div>

                    <h3>
                        ${title}
                    </h3>

                    <p>
                        The interface for this module
                        will be implemented in the
                        corresponding role workspace.
                    </p>

                </div>

            </div>

        </section>
    `;
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

async function handleApplicationSubmit(event) {
  const form = event.target;

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

  const applicantIdentifier = appState.currentUser?.identifier?.trim();

  if (!applicantIdentifier) {
    showApplicationSubmissionError(
      form,
      "Your student identifier is not available. Sign in again before submitting.",
    );
    return;
  }

  const formData = new FormData(form);
  const requestBody = {
    applicant_identifier: applicantIdentifier,
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
    }

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

  const retryOrdinanceButton = event.target.closest(
    '[data-action="retry-ordinance-context"]',
  );

  if (retryOrdinanceButton) {
    const state = appState.academicReviewState?.ordinance;
    if (state) {
      state.status = "idle";
    }
    void loadOrdinanceContext(appState.selectedApplicationId);
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

function logout() {
  logoutUser();

  appState.currentUser = null;

  appState.currentPage = "dashboard";

  appState.selectedLoginRole = null;

  renderLogin();
}

/* =========================================================
   Start Application
   ========================================================= */

initializeApp();
