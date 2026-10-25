const workspaceConfig = {
  OFFICIAL: {
    label: "Official",
    overview:
      "Claim submitted applications from the shared Official queue, then review records assigned to your account.",
    queueLabel: "My assigned applications",
    committeeLabel: "Committee coordination",
    pages: [
      ["applications", "Assigned applications"],
      ["application-processing", "Processing review"],
      ["committee", "Committee records"],
      ["audit", "Audit access"],
    ],
  },
  DUGC: {
    label: "DUGC",
    overview:
      "Review committee applications assigned to your authenticated development account.",
    queueLabel: "Assigned committee applications",
    committeeLabel: "Committee review records",
    pages: [
      ["applications", "Assigned committee applications"],
      ["committee", "Committee review"],
      ["decision-history", "Decision history"],
      ["audit", "Audit access"],
    ],
  },
};

const pageConfig = {
  applications: {
    title: (config) => config.queueLabel,
    description: "Submitted applications wait in the shared Official queue until an Official claims them. Claimed records appear in your assigned list.",
    review: true,
  },
  "application-processing": {
    title: () => "Application processing review",
    description:
      "Inspect assigned application records and apply only the transitions allowed by the server workflow.",
    review: true,
  },
  committee: {
    title: (config) => config.committeeLabel,
    description:
      "View assigned committee records. Official assignments and DUGC decisions are checked by the backend.",
    review: true,
  },
  "decision-history": {
    title: () => "Decision history",
    description:
      "View committee review records returned for a known application. These records are not an application-wide decision list.",
    review: true,
  },
};

export function renderRoleDashboard(role, user = null) {
  const config = workspaceConfig[role];
  if (!config) {
    return renderRoleWorkspacePage(role, "dashboard");
  }

  const links = config.pages
    .map(
      ([page, label]) => `
        <button type="button" class="role-workspace-link" data-page="${page}">
          <strong>${label}</strong>
          <span aria-hidden="true">→</span>
        </button>
      `,
    )
    .join("");

  return `
    <section class="page-section role-workspace" aria-labelledby="role-dashboard-title">
      <header class="page-heading">
        <div>
          <span class="eyebrow">${config.label} Workspace</span>
          <h1 id="role-dashboard-title">Governance workspace</h1>
          <p>${escapeHTML(config.overview)}</p>
          ${user?.identifier ? `<p class="role-workspace-identity">Local session identifier: ${escapeHTML(user.identifier)}</p>` : ""}
        </div>
      </header>
      <div class="role-workspace-notice" role="note">
        This development/test workspace uses server-verified credentials and record assignments.
        Institutional identity-provider integration is not configured; do not use real institutional accounts or records.
      </div>
      <section class="content-panel" aria-labelledby="role-dashboard-links-title">
        <h2 id="role-dashboard-links-title">Workspace pages</h2>
        <div class="role-workspace-links">${links}</div>
      </section>
    </section>
  `;
}

export function renderRoleWorkspacePage(role, page) {
  const config = workspaceConfig[role];
  if (!config) {
    return renderUnavailableRolePage(role);
  }

  if (page === "settings") {
    return renderRoleSettings(config.label);
  }

  if (page === "audit") {
    return `
      <section class="page-section role-workspace" aria-labelledby="role-audit-title">
        <header class="page-heading">
          <div>
            <span class="eyebrow">${config.label} Workspace</span>
            <h1 id="role-audit-title">Audit access</h1>
            <p>Audit records remain unavailable until an approved visibility policy is configured.</p>
          </div>
        </header>
        <div class="role-workspace-unavailable" role="status">
          <h2>Audit view unavailable</h2>
          <p>Server-side audit access is intentionally withheld until an approved student/staff visibility policy defines which event details may be disclosed.</p>
        </div>
      </section>
    `;
  }

  const pageDetails = pageConfig[page];
  if (!pageDetails) {
    return renderRoleDashboard(role);
  }

  const title = pageDetails.title(config);
  return `
    <section class="page-section role-workspace" aria-labelledby="role-workspace-title">
      <header class="page-heading">
        <div>
          <span class="eyebrow">${config.label} Workspace</span>
          <h1 id="role-workspace-title">${escapeHTML(title)}</h1>
          <p>${escapeHTML(pageDetails.description)}</p>
        </div>
      </header>
      <div class="role-workspace-notice" role="note">
        The backend enforces this account's provisioned role and record assignments. Institutional identity is not configured.
      </div>
      ${
        page === "applications"
          && role === "OFFICIAL"
          ? `
        <section class="content-panel" aria-labelledby="official-unassigned-title">
          <h2 id="official-unassigned-title">Unassigned submissions</h2>
          <p>Submitted applications in this shared queue are visible to authorized Official accounts. The first Official to claim an application becomes its assigned processor.</p>
          <div id="official-unassigned-list" aria-live="polite" aria-busy="true">
            <p role="status">Loading unassigned submissions…</p>
          </div>
        </section>
      `
          : ""
      }
      ${
        page === "applications"
          ? `
        <section class="content-panel" aria-labelledby="role-application-list-title">
          <h2 id="role-application-list-title">${escapeHTML(config.queueLabel)}</h2>
          <div id="role-application-list" aria-live="polite" aria-busy="true">
            <p role="status">Loading assigned applications…</p>
          </div>
        </section>
      `
          : ""
      }
      <section class="content-panel" aria-labelledby="role-application-lookup-title">
        <h2 id="role-application-lookup-title">Open an assigned record</h2>
        ${renderApplicationLookupForm(title)}
        <div id="role-application-lookup-result" class="role-application-result" aria-live="polite" aria-busy="false">
          <p class="role-workspace-empty">No application has been requested.</p>
        </div>
      </section>
      ${
        pageDetails.review
          ? `<section id="role-application-actions" class="content-panel" aria-live="polite" hidden></section>`
          : ""
      }
      ${
        pageDetails.review
          ? `
        <section class="role-review-sections" aria-label="Application review information">
          ${renderReadOnlySection("role-review-documents", "Submitted documents")}
          ${renderUnavailableSection("Eligibility information", "This endpoint regenerates database records and may call the AI provider. It is not invoked automatically from staff review pages.")}
          ${renderUnavailableSection("Identified deficiencies", "This endpoint regenerates database records. It is not invoked automatically from staff review pages.")}
          ${renderReadOnlySection("role-review-status", "Status history")}
          ${renderReadOnlySection("role-review-committees", "Committee review records")}
        </section>
        <p class="role-workspace-unsupported">Each workflow mutation is validated against the assigned account and server-defined transition rules. Audit data remains withheld pending a visibility policy.</p>
      `
          : ""
      }
    </section>
  `;
}

export function renderRoleSettings(roleLabel) {
  return `
    <section class="page-section student-settings-page" aria-labelledby="role-settings-title">
      <header class="page-heading">
        <div>
          <span class="eyebrow">${escapeHTML(roleLabel)} Workspace</span>
          <h1 id="role-settings-title">Settings</h1>
          <p>Review the authenticated development session and sign out.</p>
        </div>
      </header>
      <section class="student-settings-card">
        <h2>Session and access</h2>
        <p class="student-settings-note" role="note">
          Role and record permissions are server-enforced for local development accounts. Institutional identity and password management are unavailable.
        </p>
        <button type="button" class="secondary-button" data-action="logout">Sign out</button>
      </section>
    </section>
  `;
}

function renderApplicationLookupForm(label) {
  return `
    <form class="role-application-lookup-form" data-role-application-lookup novalidate>
      <label for="role-application-id">${escapeHTML(label)} — numeric application ID</label>
      <div class="role-application-lookup-controls">
        <input id="role-application-id" name="application_id" type="number" min="1" step="1" inputmode="numeric" required aria-describedby="role-application-id-help">
        <button type="submit" class="primary-button">Load record</button>
      </div>
      <small id="role-application-id-help">This lookup is subject to your server-assigned record permissions.</small>
      <p class="role-application-lookup-error" data-role-lookup-error role="alert" hidden></p>
    </form>
  `;
}

function renderReadOnlySection(id, title) {
  return `
    <section class="content-panel role-review-panel" aria-labelledby="${id}-title">
      <h2 id="${id}-title">${escapeHTML(title)}</h2>
      <div id="${id}" class="role-review-panel-content" aria-live="polite" aria-busy="false">
        <p class="role-workspace-empty">Load an application record to request this information.</p>
      </div>
    </section>
  `;
}

function renderUnavailableSection(title, reason) {
  return `
    <section class="content-panel role-review-panel">
      <h2>${escapeHTML(title)}</h2>
      <p class="role-workspace-unavailable" role="note">${escapeHTML(reason)}</p>
    </section>
  `;
}

function renderUnavailableRolePage(role) {
  return `
    <section class="page-section role-workspace" aria-labelledby="unsupported-role-title">
      <h1 id="unsupported-role-title">Workspace unavailable</h1>
      <p>No workspace is defined for role ${escapeHTML(role)}.</p>
    </section>
  `;
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
