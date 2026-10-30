export function renderStudentDashboard(currentUser = null) {
  const studentName = currentUser?.name?.trim() || "";
  const registrationNumber = currentUser?.identifier?.trim() || "";
  const programmeNotice = renderProgrammeIdentityNotice(currentUser);
  const identity = [studentName, registrationNumber]
    .filter(Boolean)
    .map(escapeHTML);

  return `
    <section class="dashboard-page student-dashboard" aria-labelledby="student-workspace-title">
      <header class="dashboard-header">
        <div class="dashboard-header-content">
          <span class="eyebrow">Student Workspace</span>
          <h1 id="student-workspace-title">Student Workspace</h1>
          <p class="dashboard-welcome">
            ${studentName ? `Welcome, ${escapeHTML(studentName)}.` : "Welcome to your student workspace."}
          </p>
          <p>Academic services and institutional information for your department.</p>
        </div>

        ${
          identity.length
            ? `
          <div class="dashboard-identity" aria-label="Student identity">
            <div class="dashboard-avatar" aria-hidden="true">${getInitials(studentName)}</div>
            <div class="dashboard-identity-text">
              ${studentName ? `<strong>${escapeHTML(studentName)}</strong>` : ""}
              ${registrationNumber ? `<span>Registration number: ${escapeHTML(registrationNumber)}</span>` : ""}
            </div>
          </div>
        `
            : ""
        }
      </header>

      ${programmeNotice}

      <section class="dashboard-overview" aria-labelledby="application-overview-title">
        <div>
          <span class="section-kicker">Overview</span>
          <h2 id="application-overview-title">Application overview</h2>
        </div>
        <p>Your application totals and recent records are loaded from your authenticated account.</p>
      </section>

      <div class="dashboard-content-grid">
        <section class="dashboard-panel" aria-labelledby="recent-applications-title">
          <div class="panel-header">
            <div>
              <span class="section-kicker">Applications</span>
              <h2 id="recent-applications-title">Recent applications</h2>
            </div>
            <button type="button" class="text-button" data-page="applications">
              View all <span aria-hidden="true">→</span>
            </button>
          </div>

          <div id="student-recent-applications" aria-live="polite" aria-busy="true">
            <p role="status">Loading your applications…</p>
          </div>
        </section>

        <section class="dashboard-panel" aria-labelledby="quick-actions-title">
          <div class="panel-header">
            <div>
              <span class="section-kicker">Services</span>
              <h2 id="quick-actions-title">Quick actions</h2>
            </div>
          </div>

          <div class="quick-action-list">
            <button type="button" class="quick-action" data-page="create-application">
              <span class="quick-action-icon" aria-hidden="true">+</span>
              <span class="quick-action-content">
                <strong>Create Application</strong>
                <small>Start a new academic application</small>
              </span>
              <span class="quick-action-arrow" aria-hidden="true">→</span>
            </button>
            <button type="button" class="quick-action" data-page="applications">
              <span class="quick-action-icon" aria-hidden="true">▣</span>
              <span class="quick-action-content">
                <strong>My Applications</strong>
                <small>Open your application workspace</small>
              </span>
              <span class="quick-action-arrow" aria-hidden="true">→</span>
            </button>
            <button type="button" class="quick-action" data-page="assistant">
              <span class="quick-action-icon" aria-hidden="true">✦</span>
              <span class="quick-action-content">
                <strong>Academic Assistant</strong>
                <small>Ask about academic rules</small>
              </span>
              <span class="quick-action-arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </section>
      </div>

      <aside class="dashboard-info-panel" aria-labelledby="assistant-panel-title">
        <div class="info-panel-icon" aria-hidden="true">✦</div>
        <div class="info-panel-content">
          <span class="section-kicker">Academic guidance</span>
          <h2 id="assistant-panel-title">DepartmentAI Academic Assistant</h2>
          <p>
            Get AI-assisted academic information based on approved institutional knowledge. Responses are guidance only; final academic decisions remain with authorized people.
          </p>
        </div>
        <button type="button" class="secondary-button" data-page="assistant">
          Open Assistant
        </button>
      </aside>
    </section>
  `;
}

function renderProgrammeIdentityNotice(currentUser) {
  const status = currentUser?.programmeIdentityStatus;
  const programme = currentUser?.verifiedProgramme;

  if (status === "VERIFIED" && typeof programme === "string" && programme) {
    return `
      <aside class="programme-identity-notice programme-identity-verified" role="status">
        <strong>Verified programme: ${escapeHTML(programme)}</strong>
        <span>This programme was supplied by the authenticated profile.</span>
      </aside>
    `;
  }

  return `
    <aside class="programme-identity-notice" role="status">
      <strong>Programme identity is not verified</strong>
      <span>
        This deployment has no approved student-profile provisioning source.
        Programme-specific eligibility and committee routing are unavailable;
        there is no self-service profile correction action.
      </span>
    </aside>
  `;
}

function getInitials(name) {
  if (!name) {
    return "S";
  }

  const parts = name.trim().split(/\s+/).filter(Boolean);

  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase();
  }

  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function escapeHTML(value) {
  return value.replace(/[&<>"']/g, (character) => {
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
