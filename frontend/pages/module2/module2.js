import {
  APIError,
  downloadModule2Export,
  generateModule2Report,
  getModule2DataQuality,
  getModule2ExportDatasets,
  getModule2Faculty,
  getModule2FacultyDetail,
  getModule2ReportTemplates,
  getModule2ResearchRecords,
  getModule2ResearchStatistics,
  hasAccessToken,
  previewModule2Report,
} from "../../services/api.js";

const FACULTY_PERMISSION = "module2.faculty.read";
const RESEARCH_PERMISSION = "module2.research.read";
const STATISTICS_PERMISSION = "module2.research.statistics.read";
const DATA_QUALITY_PERMISSION = "module2.data_quality.read";
const REPORTS_PERMISSION = "module2.reports.generate";
const EXPORT_PERMISSIONS = [
  "module2.export.faculty_profiles",
  "module2.export.publications",
];
const PAGE_SIZE = 50;
const MAX_OFFSET = 100_000;

const RESEARCH_TYPES = {
  publications: {
    label: "Publications",
    fields: [
      "publication_type",
      "journal_or_conference",
      "publisher",
      "publication_date",
      "publication_year",
      "doi",
      "authors",
      "faculty_name",
      "department",
      "source_url",
    ],
  },
  projects: {
    label: "Projects",
    fields: [
      "funding_agency",
      "reference_number",
      "start_date",
      "end_date",
      "status",
      "description",
      "faculty_name",
      "department",
      "source_url",
    ],
  },
  achievements: {
    label: "Achievements",
    fields: [
      "category",
      "description",
      "organization",
      "venue",
      "role",
      "event_date",
      "start_date",
      "end_date",
      "year",
      "status",
      "faculty_name",
      "department",
      "source_url",
    ],
  },
};

const FACULTY_FIELDS = [
  "designation",
  "department",
  "qualification",
  "area_of_interest",
  "verification_status",
  "source_name",
  "source_last_fetched_at",
  "profile_url",
  "source_url",
];

const STATISTIC_LABELS = {
  publications: "Publications",
  projects: "Research projects",
  achievements: "Achievements",
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
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

function hasPermission(capabilityState, permission) {
  return (
    capabilityState?.status === "ready" &&
    Array.isArray(capabilityState.capabilities?.permissions) &&
    capabilityState.capabilities.permissions.includes(permission)
  );
}

function canAccessExports(capabilityState) {
  return EXPORT_PERMISSIONS.some((permission) =>
    hasPermission(capabilityState, permission),
  );
}

function availableViews(capabilityState) {
  if (capabilityState?.status !== "ready") {
    return [];
  }
  const permissions = capabilityState.capabilities?.permissions || [];
  const hasDataPermission = [
    FACULTY_PERMISSION,
    RESEARCH_PERMISSION,
    STATISTICS_PERMISSION,
    DATA_QUALITY_PERMISSION,
    REPORTS_PERMISSION,
    ...EXPORT_PERMISSIONS,
  ].some((permission) => permissions.includes(permission));
  if (!hasDataPermission) {
    return [];
  }
  const views = [{ id: "overview", label: "Overview" }];
  if (permissions.includes(FACULTY_PERMISSION)) {
    views.push({ id: "faculty", label: "Faculty directory" });
  }
  if (permissions.includes(RESEARCH_PERMISSION)) {
    views.push({ id: "research", label: "Research records" });
  }
  if (permissions.includes(STATISTICS_PERMISSION)) {
    views.push({ id: "statistics", label: "Statistics" });
  }
  if (permissions.includes(DATA_QUALITY_PERMISSION)) {
    views.push({ id: "data-quality", label: "Data quality" });
  }
  if (canAccessExports(capabilityState)) {
    views.push({ id: "exports", label: "Reports & exports" });
  }
  if (permissions.includes(REPORTS_PERMISSION)) {
    views.push({ id: "reporting", label: "Reporting" });
  }
  return views;
}

function renderCapabilityNotice(capabilityState) {
  if (capabilityState?.status === "unauthenticated") {
    return '<p class="module2-message" role="status">Sign in to view Module II.</p>';
  }
  if (capabilityState?.status === "loading") {
    return '<p class="module2-message" role="status">Checking your Module II access…</p>';
  }
  if (capabilityState?.status === "denied") {
    return `
      <section class="module2-message module2-message-blocked" role="status">
        <h2>Module II access is not assigned</h2>
        <p>Your authenticated account has no Module II permission grant. Access is managed by an administrator; changing a role or URL will not grant it.</p>
      </section>
    `;
  }
  if (capabilityState?.status === "configuration") {
    return `
      <section class="module2-message module2-message-blocked" role="status">
        <h2>Module II access is unavailable</h2>
        <p>The server could not verify the Module II capability service or permission configuration. An administrator must review the server-side setup.</p>
      </section>
    `;
  }
  if (capabilityState?.status === "error") {
    return `
      <section class="module2-message" role="alert">
        <h2>Could not verify Module II access</h2>
        <p>The authenticated capability service is unavailable. Try again when the service is reachable.</p>
        <button type="button" class="secondary-button" data-module2-action="retry-capabilities">Retry</button>
      </section>
    `;
  }
  if (capabilityState?.status !== "ready") {
    return '<p class="module2-message" role="status">Sign in to view Module II.</p>';
  }
  if (!availableViews(capabilityState).length) {
    return `
      <section class="module2-message module2-message-blocked" role="status">
        <h2>No Module II features are assigned</h2>
        <p>Your account is authenticated, but no supported Module II feature is enabled for it.</p>
      </section>
    `;
  }
  return "";
}

export function renderModule2Page(capabilityState = { status: "loading" }) {
  const notice = renderCapabilityNotice(capabilityState);
  const views = availableViews(capabilityState);
  const departments = capabilityState?.capabilities?.departments;
  const scope =
    capabilityState?.status === "ready" && Array.isArray(departments)
      ? `<p class="module2-scope"><strong>Authorized department scope:</strong> ${escapeHtml(departments.join(", ") || "None")}. The server enforces this scope for every request.</p>`
      : "";

  return `
    <section class="page-section module2-page" aria-labelledby="module2-title">
      <header class="page-heading module2-heading">
        <div>
          <span class="eyebrow">SoStudy · Module II</span>
          <h1 id="module2-title">Faculty &amp; Research</h1>
          <p>Read-only faculty and research information available to your authenticated account.</p>
        </div>
      </header>
      ${scope}
      ${
        notice ||
        `
          <nav class="module2-tabs" aria-label="Module II areas">
            ${views
              .map(
                (view) => `
                  <button
                    type="button"
                    class="module2-tab"
                    data-module2-view="${view.id}"
                    aria-pressed="${view.id === "overview"}"
                  >${view.label}</button>
                `,
              )
              .join("")}
          </nav>
          <section id="module2-content" class="module2-content" aria-live="polite" aria-busy="false"></section>
        `
      }
    </section>
  `;
}

function fieldLabel(key) {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFieldValue(key, value) {
  if (value == null || value === "") {
    return "—";
  }
  if (key.endsWith("_date") || key.endsWith("_at")) {
    const dateValue = String(value);
    return escapeHtml(dateValue.length >= 10 ? dateValue.slice(0, 10) : dateValue);
  }
  if (key === "status" || key === "verification_status") {
    return escapeHtml(String(value).replaceAll("_", " "));
  }
  if (Array.isArray(value) || (typeof value === "object" && value !== null)) {
    return escapeHtml(JSON.stringify(value));
  }
  return escapeHtml(value);
}

function renderField(key, value) {
  if (
    (key === "source_url" || key === "profile_url") &&
    typeof value === "string"
  ) {
    let url;
    try {
      url = new URL(value);
    } catch {
      url = null;
    }
    if (url && ["http:", "https:"].includes(url.protocol)) {
      return `<a href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(value)}</a>`;
    }
  }
  return formatFieldValue(key, value);
}

function renderFieldList(record, fields) {
  return `
    <dl class="module2-fields">
      ${fields
        .filter((field) => Object.hasOwn(record, field))
        .map(
          (field) => `
            <div>
              <dt>${fieldLabel(field)}</dt>
              <dd>${renderField(field, record[field])}</dd>
            </div>
          `,
        )
        .join("")}
    </dl>
  `;
}

function renderLoadError(error, resource, retryAction = "retry") {
  let message = `The ${resource} service could not be reached.`;
  let retryable = true;
  if (error instanceof APIError) {
    if (error.status === 401) {
      message = "Your session expired. Sign in again to continue.";
      retryable = false;
    } else if (error.status === 403) {
      message = `The server denied access to ${resource}. No records were loaded.`;
      retryable = false;
    } else if (error.status === 404) {
      message = `The requested ${resource} is not available.`;
      retryable = false;
    } else if (error.status === 409) {
      message = `The ${resource} request conflicts with the current server state.`;
      retryable = false;
    } else if (error.status === 422) {
      message = `The server rejected the ${resource} filters. Check the values and try again.`;
      retryable = false;
    } else if (error.status === 503) {
      message = `The ${resource} service or Module II database profile is unavailable.`;
    } else if (error.status === 0) {
      message = `The ${resource} service could not be reached.`;
    } else if (error.status < 500) {
      message = `The ${resource} request failed.`;
      retryable = false;
    }
  } else if (!(error instanceof Error)) {
    message = `The ${resource} response was unavailable.`;
  }
  return `
    <section class="module2-message" role="alert">
      <p>${message}</p>
      ${
        retryable
          ? `<button type="button" class="secondary-button" data-module2-action="${retryAction}">Retry</button>`
          : ""
      }
    </section>
  `;
}

function renderDatabaseConfigurationNotice(capabilityState) {
  if (capabilityState.capabilities?.database_profile_configured !== false) {
    return "";
  }
  return `
    <section class="module2-message module2-message-blocked" role="status">
      <h2>Module II database profile is not configured</h2>
      <p>Your access permissions are verified, but the server has no complete Module II database profile. An administrator must configure the isolated profile before records can be loaded.</p>
    </section>
  `;
}

function renderOverview(state) {
  const capState = state.capabilityState;
  const statsAllowed = hasPermission(capState, STATISTICS_PERMISSION);
  const metrics =
    !statsAllowed
      ? Object.entries(STATISTIC_LABELS)
          .map(
            ([key, label]) => `
              <div class="module2-metric">
                <dt>${label}</dt>
                <dd>Unavailable</dd>
                <small>Statistics permission is not assigned.</small>
              </div>
            `,
          )
          .join("")
      : state.statsStatus === "success"
        ? Object.entries(STATISTIC_LABELS)
            .map(([key, label]) => {
              const value = state.statistics?.counts?.[key];
              const valid = Number.isSafeInteger(value) && value >= 0;
              return `
                <div class="module2-metric">
                  <dt>${label}</dt>
                  <dd>${valid ? value : "Unavailable"}</dd>
                  <small>${valid ? "Persisted records in your authorized department scope." : "The API did not return a valid count."}</small>
                </div>
              `;
            })
            .join("")
        : state.statsStatus === "error"
          ? Object.entries(STATISTIC_LABELS)
              .map(
                ([, label]) => `
                  <div class="module2-metric">
                    <dt>${label}</dt>
                    <dd>Unavailable</dd>
                    <small>Statistics could not be loaded.</small>
                  </div>
                `,
              )
              .join("")
          : Object.entries(STATISTIC_LABELS)
              .map(
                ([, label]) => `
                  <div class="module2-metric">
                    <dt>${label}</dt>
                    <dd>Loading…</dd>
                    <small>${label} count from authorized persisted records.</small>
                  </div>
                `,
              )
              .join("");
  const featureRows = [
    [
      FACULTY_PERMISSION,
      "Faculty directory",
      "Browse in-scope faculty profiles.",
      "faculty",
    ],
    [
      RESEARCH_PERMISSION,
      "Research records",
      "Publications, research projects, and achievements.",
      "research",
    ],
    [
      STATISTICS_PERMISSION,
      "Research statistics",
      "Counts of persisted publications, projects, and achievements.",
      "statistics",
    ],
    [
      DATA_QUALITY_PERMISSION,
      "Data quality review",
      "Read-only checks on persisted records in your authorized scope.",
      "data-quality",
    ],
  ]
    .filter(([permission]) => hasPermission(capState, permission))
    .map(
      ([, label, description, view]) => `
        <li>
          <button type="button" class="module2-feature-link" data-module2-view="${view}">
            <span><strong>${label}</strong><small>${description}</small></span>
            <span aria-hidden="true">→</span>
          </button>
        </li>
      `,
    );
  if (canAccessExports(capState)) {
    featureRows.push(`
      <li>
        <button type="button" class="module2-feature-link" data-module2-view="exports">
          <span><strong>Reports &amp; exports</strong><small>Only server-allowlisted datasets and formats.</small></span>
          <span aria-hidden="true">→</span>
        </button>
      </li>
    `);
  }
  if (hasPermission(capState, REPORTS_PERMISSION)) {
    featureRows.push(`
      <li>
        <button type="button" class="module2-feature-link" data-module2-view="reporting">
          <span><strong>Configurable draft reports</strong><small>Preview and generate scoped, clearly labeled draft documents.</small></span>
          <span aria-hidden="true">→</span>
        </button>
      </li>
    `);
  }
  const refreshed =
    state.statsReceivedAt && statsAllowed
      ? `<p class="module2-refresh-time">Received at ${escapeHtml(state.statsReceivedAt)} (your browser’s local time).</p>`
      : "";

  return `
    <div class="module2-overview">
      ${renderDatabaseConfigurationNotice(capState)}
      <section class="module2-section" aria-labelledby="module2-overview-counts">
        <div class="module2-section-heading">
          <div>
            <h2 id="module2-overview-counts">Research summary</h2>
            <p>Counts are returned by the authorized statistics API; zero is shown only when the API returns zero.</p>
          </div>
        </div>
        <dl class="module2-metrics">${metrics}</dl>
        ${
          state.statsStatus === "error"
            ? capState.capabilities?.database_profile_configured === false
              ? '<p class="module2-message module2-message-blocked" role="status">Statistics are unavailable until the server’s isolated Module II database profile is configured.</p>'
              : renderLoadError(state.statsError, "statistics", "retry-statistics")
            : ""
        }
        ${refreshed}
      </section>
      <section class="module2-section" aria-labelledby="module2-overview-areas">
        <h2 id="module2-overview-areas">Available areas</h2>
        ${
          featureRows.length
            ? `<ul class="module2-feature-list">${featureRows.join("")}</ul>`
            : "<p>No data features are enabled for this account.</p>"
        }
        <ul class="module2-unavailable-list">
          ${
            hasPermission(capState, DATA_QUALITY_PERMISSION)
              ? ""
              : "<li><strong>Data quality review:</strong> unavailable; a separate authorized permission is required.</li>"
          }
          <li><strong>Student supervision:</strong> unavailable; the backend denies supervision access.</li>
          <li><strong>Faculty chatbot:</strong> unavailable; no authenticated retrieval capability is supported.</li>
        </ul>
      </section>
    </div>
  `;
}

function renderPagination(items, offset, actionName) {
  const hasNext =
    items.length === PAGE_SIZE && offset + PAGE_SIZE <= MAX_OFFSET;
  return `
    <div class="module2-pagination" aria-label="Result pages">
      <span>Showing ${items.length} records · offset ${offset}</span>
      <div>
        <button type="button" class="secondary-button" data-module2-action="${actionName}-previous" ${offset === 0 ? "disabled" : ""}>Previous</button>
        <button type="button" class="secondary-button" data-module2-action="${actionName}-next" ${hasNext ? "" : "disabled"}>Next</button>
      </div>
    </div>
  `;
}

function renderFacultyList(state) {
  const rows = state.facultyItems
    .map((profile) => {
      if (!profile || !Number.isSafeInteger(profile.id)) {
        return "";
      }
      return `
        <li class="module2-result-row">
          <div>
            <h3>${escapeHtml(profile.full_name || "Name unavailable")}</h3>
            <p>${[profile.designation, profile.department].filter(Boolean).map(escapeHtml).join(" · ") || "Faculty details unavailable"}</p>
            <p>${escapeHtml(profile.area_of_interest || "Research interests unavailable")}</p>
          </div>
          <button type="button" class="secondary-button" data-module2-faculty-id="${profile.id}">View profile</button>
        </li>
      `;
    })
    .join("");
  return `
    <div class="module2-directory">
      <div class="module2-section-heading">
        <div><h2>Faculty directory</h2><p>Results are restricted to the department scope assigned to your account.</p></div>
        <button type="button" class="secondary-button" data-module2-action="refresh-faculty">Refresh</button>
      </div>
      <div class="module2-search-row">
        <label for="module2-faculty-query">Search faculty name or research interest</label>
        <input id="module2-faculty-query" type="search" maxlength="200" value="${escapeHtml(state.facultyQuery)}" data-module2-faculty-query />
        <button type="button" class="primary-button" data-module2-action="search-faculty">Search</button>
      </div>
      ${
        state.facultyItems.length
          ? `<ul class="module2-result-list">${rows}</ul>`
          : '<p class="module2-empty">No faculty matched this search in your authorized scope.</p>'
      }
      ${renderPagination(state.facultyItems, state.facultyOffset, "faculty")}
    </div>
  `;
}

function renderFacultyDetail(profile) {
  const name = profile.full_name || "Faculty profile";
  return `
    <section class="module2-detail">
      <button type="button" class="secondary-button" data-module2-action="back-to-faculty">← Back to directory</button>
      <h2>${escapeHtml(name)}</h2>
      ${renderFieldList(profile, FACULTY_FIELDS)}
      <p class="module2-provenance">Profile data is read-only and provided by the authorized Module II API.</p>
    </section>
  `;
}

function renderResearchRecords(state) {
  const definition = RESEARCH_TYPES[state.researchType];
  const cards = state.researchItems
    .map((record) => {
      if (!record || typeof record !== "object" || Array.isArray(record)) {
        return "";
      }
      const title =
        typeof record.title === "string" && record.title.trim()
          ? record.title
          : definition.label.slice(0, -1);
      return `
        <li class="module2-research-card">
          <h3>${escapeHtml(title)}</h3>
          <details>
            <summary>Record details</summary>
            ${renderFieldList(record, definition.fields)}
          </details>
        </li>
      `;
    })
    .join("");
  return `
    <section class="module2-research">
      <div class="module2-section-heading">
        <div><h2>Research records</h2><p>Persisted records supported by the read-only API. Results are department-scoped and paginated.</p></div>
        <button type="button" class="secondary-button" data-module2-action="refresh-research">Refresh</button>
      </div>
      <div class="module2-category-tabs" role="group" aria-label="Research record category">
        ${Object.entries(RESEARCH_TYPES)
          .map(
            ([type, item]) => `
              <button type="button" class="module2-tab" data-module2-record-type="${type}" aria-pressed="${state.researchType === type}">${item.label}</button>
            `,
          )
          .join("")}
      </div>
      <div class="module2-search-row module2-research-filters">
        <label>Search records
          <input type="search" maxlength="200" value="${escapeHtml(state.researchQuery)}" data-module2-research-query />
        </label>
        <label>Year from
          <input type="number" min="1900" max="2100" value="${escapeHtml(state.yearFrom)}" data-module2-year-from />
        </label>
        <label>Year to
          <input type="number" min="1900" max="2100" value="${escapeHtml(state.yearTo)}" data-module2-year-to />
        </label>
        <button type="button" class="primary-button" data-module2-action="apply-research-filters">Apply filters</button>
      </div>
      <p class="module2-filter-error" data-module2-filter-error role="alert" hidden></p>
      ${
        state.researchItems.length
          ? `<ul class="module2-research-list">${cards}</ul>`
          : `<p class="module2-empty">No ${definition.label.toLowerCase()} matched these filters in your authorized scope.</p>`
      }
      ${renderPagination(state.researchItems, state.researchOffset, "research")}
    </section>
  `;
}

function renderStatistics(state) {
  const databaseNotice = renderDatabaseConfigurationNotice(
    state.capabilityState,
  );
  if (databaseNotice) {
    return databaseNotice;
  }
  if (state.statsStatus === "loading" || state.statsStatus === "idle") {
    return '<p class="module2-message" role="status">Loading authorized research statistics…</p>';
  }
  if (state.statsStatus === "error") {
    return renderLoadError(state.statsError, "statistics", "retry-statistics");
  }
  const counts = state.statistics?.counts;
  if (
    !counts ||
    Object.keys(STATISTIC_LABELS).some(
      (key) => !Number.isSafeInteger(counts[key]) || counts[key] < 0,
    )
  ) {
    return '<p class="module2-message" role="alert">The statistics API returned an invalid response. Counts are unavailable.</p>';
  }
  return `
    <section class="module2-section">
      <div class="module2-section-heading">
        <div><h2>Research statistics</h2><p>Counts reflect persisted records in your authorized department scope at request time. The API does not provide period filters.</p></div>
        <button type="button" class="secondary-button" data-module2-action="retry-statistics">Refresh</button>
      </div>
      <dl class="module2-metrics">
        ${Object.entries(STATISTIC_LABELS)
          .map(
            ([key, label]) => `
              <div class="module2-metric">
                <dt>${label}</dt>
                <dd>${counts[key]}</dd>
                <small>Persisted ${label.toLowerCase()} records.</small>
              </div>
            `,
          )
          .join("")}
      </dl>
      <p class="module2-refresh-time">Received at ${escapeHtml(state.statsReceivedAt)} (your browser’s local time).</p>
    </section>
  `;
}

const QUALITY_CATEGORY_LABELS = {
  faculty: "Faculty",
  publications: "Publications",
  projects: "Projects",
  achievements: "Achievements",
};

function renderDataQuality(state) {
  const databaseNotice = renderDatabaseConfigurationNotice(
    state.capabilityState,
  );
  if (databaseNotice) {
    return databaseNotice;
  }
  if (state.qualityStatus === "loading" || state.qualityStatus === "idle") {
    return '<p class="module2-message" role="status">Loading authorized data-quality findings…</p>';
  }
  if (state.qualityStatus === "error") {
    return renderLoadError(
      state.qualityError,
      "data-quality review",
      "retry-data-quality",
    );
  }
  const report = state.qualityReport;
  const summary = report?.summary;
  if (
    !summary ||
    !summary.record_counts ||
    !Number.isSafeInteger(summary.records_scanned) ||
    !Number.isSafeInteger(summary.total_issues) ||
    !Number.isSafeInteger(summary.objective_issues) ||
    !Number.isSafeInteger(summary.potential_duplicate_findings) ||
    !Array.isArray(report.issues) ||
    !Number.isSafeInteger(report.total)
  ) {
    return '<p class="module2-message" role="alert">The data-quality API returned an invalid response. Findings are unavailable.</p>';
  }
  const categories = Object.entries(QUALITY_CATEGORY_LABELS);
  const findings = report.issues
    .map((issue) => {
      const evidence = escapeHtml(JSON.stringify(issue.evidence, null, 2));
      const source =
        typeof issue.source_url === "string"
          ? `<p><strong>Source:</strong> ${renderField("source_url", issue.source_url)}</p>`
          : "";
      return `
        <li class="module2-quality-issue">
          <div class="module2-section-heading">
            <div>
              <h3>${escapeHtml(issue.record_label)} <span class="module2-quality-record-id">#${escapeHtml(issue.record_id)}</span></h3>
              <p>${escapeHtml(QUALITY_CATEGORY_LABELS[issue.category] || issue.category)} · ${escapeHtml(fieldLabel(issue.field))} · ${escapeHtml(issue.issue_type.replaceAll("_", " "))}</p>
            </div>
            <span class="module2-quality-classification">${issue.classification === "heuristic" ? "Potential match" : "Schema/data check"}</span>
          </div>
          <p>${escapeHtml(issue.explanation)}</p>
          ${source}
          <details>
            <summary>Inspect persisted evidence</summary>
            <pre>${evidence}</pre>
          </details>
        </li>
      `;
    })
    .join("");
  const counts = Object.entries(summary.record_counts)
    .map(
      ([category, count]) => `
        <div class="module2-metric">
          <dt>${escapeHtml(QUALITY_CATEGORY_LABELS[category] || category)}</dt>
          <dd>${Number.isSafeInteger(count) ? count : "Unavailable"}</dd>
          <small>Records inspected in this category.</small>
        </div>
      `,
    )
    .join("");
  const resultState =
    summary.records_scanned === 0
      ? `<p class="module2-empty">No persisted records were found for this authorized scope and category filter.</p>`
      : summary.total_issues === 0
        ? `<p class="module2-empty">No issues were detected in ${summary.records_scanned} inspected records.</p>`
        : `<p class="module2-provenance">${summary.objective_issues} objective findings and ${summary.potential_duplicate_findings} potential-duplicate findings. Potential duplicates are heuristic suggestions, not confirmed duplicates.</p>
           <ul class="module2-quality-list">${findings || '<li class="module2-empty">No findings on this page.</li>'}</ul>
           <div class="module2-pagination" aria-label="Data-quality finding pages">
             <span>Showing ${report.issues.length} of ${report.total} findings · offset ${report.offset}</span>
             <div>
               <button type="button" class="secondary-button" data-module2-action="quality-previous" ${report.offset <= 0 ? "disabled" : ""}>Previous</button>
               <button type="button" class="secondary-button" data-module2-action="quality-next" ${report.offset + report.issues.length >= report.total ? "disabled" : ""}>Next</button>
             </div>
           </div>`
      ;
  return `
    <section class="module2-section" aria-labelledby="module2-quality-heading">
      <div class="module2-section-heading">
        <div>
          <h2 id="module2-quality-heading">Data quality review</h2>
          <p>Read-only checks on persisted, authorized records. No source records are changed.</p>
        </div>
        <button type="button" class="secondary-button" data-module2-action="refresh-data-quality">Refresh</button>
      </div>
      <div class="module2-search-row module2-quality-filters">
        <label for="module2-quality-category">Record category</label>
        <select id="module2-quality-category" data-module2-quality-category>
          <option value="all" ${state.qualityCategory === "all" ? "selected" : ""}>All supported categories</option>
          ${categories
            .map(
              ([key, label]) =>
                `<option value="${key}" ${state.qualityCategory === key ? "selected" : ""}>${label}</option>`,
            )
            .join("")}
        </select>
        <button type="button" class="primary-button" data-module2-action="apply-quality-filter">Apply filter</button>
      </div>
      <dl class="module2-metrics module2-quality-metrics">
        ${counts}
        <div class="module2-metric"><dt>Total findings</dt><dd>${summary.total_issues}</dd><small>Across inspected authorized records.</small></div>
        <div class="module2-metric"><dt>Objective checks</dt><dd>${summary.objective_issues}</dd><small>Required values or stored-value inconsistencies.</small></div>
        <div class="module2-metric"><dt>Potential duplicates</dt><dd>${summary.potential_duplicate_findings}</dd><small>Heuristic; requires human inspection.</small></div>
      </dl>
      <p class="module2-provenance">A complete review is limited to ${escapeHtml(5000)} records per selected category; larger datasets return unavailable rather than partial findings. Reviewer actions, corrections, and dismissals are not supported.</p>
      ${resultState}
    </section>
  `;
}

function renderExportDatasets(state) {
  const databaseNotice = renderDatabaseConfigurationNotice(
    state.capabilityState,
  );
  if (databaseNotice) {
    return databaseNotice;
  }
  if (state.exportStatus === "loading" || state.exportStatus === "idle") {
    return '<p class="module2-message" role="status">Loading permitted export datasets…</p>';
  }
  if (state.exportStatus === "error") {
    return renderLoadError(state.exportError, "export datasets", "retry-exports");
  }
  const response = state.exportMetadata;
  const formats = Array.isArray(response?.formats) ? response.formats : [];
  const datasets = Array.isArray(response?.datasets) ? response.datasets : [];
  if (!formats.length || !datasets.length) {
    return '<p class="module2-empty">No export datasets are enabled for this account.</p>';
  }
  return `
    <section class="module2-section">
      <div class="module2-section-heading">
        <div><h2>Reports &amp; exports</h2><p>Downloads use only the datasets, columns, formats, and department scope allowed by the server.</p></div>
        <button type="button" class="secondary-button" data-module2-action="retry-exports">Refresh</button>
      </div>
      <ul class="module2-export-list">
        ${datasets
          .map((dataset) => {
            if (
              typeof dataset?.name !== "string" ||
              !Array.isArray(dataset.columns)
            ) {
              return "";
            }
            const name = escapeHtml(dataset.name);
            return `
              <li class="module2-export-row">
                <div>
                  <h3>${name.replaceAll("_", " ")}</h3>
                  <p>Available fields: ${dataset.columns.map(escapeHtml).join(", ")}</p>
                </div>
                <label>Format
                  <select data-module2-format="${name}">
                    ${formats.map((format) => `<option value="${escapeHtml(format)}">${escapeHtml(format.toUpperCase())}</option>`).join("")}
                  </select>
                </label>
                <button type="button" class="primary-button" data-module2-download="${name}" ${state.exportPending.has(dataset.name) ? "disabled" : ""}>
                  ${state.exportPending.has(dataset.name) ? "Preparing…" : "Download"}
                </button>
              </li>
            `;
          })
          .join("")}
      </ul>
      <p class="module2-provenance">The server enforces the maximum export size and field allowlist. No unrestricted tables are available.</p>
    </section>
  `;
}

function renderReportPreview(report) {
  const columns = Array.isArray(report?.columns) ? report.columns : [];
  const rows = Array.isArray(report?.preview_rows) ? report.preview_rows : [];
  if (!columns.length || !rows.length) {
    return '<p class="module2-empty">No persisted records matched this template and filter.</p>';
  }
  return `
    <div class="module2-report-table-wrap">
      <table class="module2-report-table">
        <caption>First ${rows.length} matching persisted records</caption>
        <thead><tr>${columns.map((column) => `<th scope="col">${escapeHtml(column.label)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>${columns.map((column) => `<td>${escapeHtml(row[column.key] ?? "—")}</td>`).join("")}</tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderReporting(state) {
  if (state.reportTemplatesStatus === "loading" || state.reportTemplatesStatus === "idle") {
    return '<p class="module2-message" role="status">Loading authorized report templates…</p>';
  }
  if (state.reportTemplatesStatus === "error") {
    return renderLoadError(state.reportTemplatesError, "report templates", "retry-report-templates");
  }
  const templates = Array.isArray(state.reportTemplates?.templates)
    ? state.reportTemplates.templates
    : [];
  const selectedTemplate =
    templates.find((template) => template.id === state.reportTemplateId) ||
    templates[0];
  if (!selectedTemplate) {
    return '<p class="module2-empty">No configurable report templates are available.</p>';
  }
  const formats = Array.isArray(selectedTemplate.supported_formats)
    ? selectedTemplate.supported_formats
    : [];
  const supportsPeriod = Array.isArray(selectedTemplate.filters) &&
    selectedTemplate.filters.includes("year_from");
  const report = state.reportPreview;
  const preview =
    state.reportPreviewStatus === "loading"
      ? '<p class="module2-message" role="status">Preparing report preview from authorized persisted records…</p>'
      : state.reportPreviewStatus === "error"
        ? renderLoadError(state.reportPreviewError, "report preview", "preview-report")
        : state.reportPreviewStatus === "success"
          ? `
              <section class="module2-report-preview" data-report-status="${escapeHtml(report.status)}" aria-labelledby="module2-report-preview-title">
                <h3 id="module2-report-preview-title">Server-generated preview · ${escapeHtml(report.summary?.record_count ?? 0)} returned rows</h3>
                <p><strong>Status:</strong> Draft — not official or approved. <strong>Template:</strong> ${escapeHtml(report.template_title)} v${escapeHtml(report.template_version)}. <strong>Generated:</strong> ${escapeHtml(report.generated_at)}.</p>
                <p><strong>Authorized scope:</strong> ${escapeHtml(report.scope?.departments?.join(", ") || "None")}</p>
                ${
                  report.summary?.total_persisted_records != null
                    ? `<p><strong>Total persisted records:</strong> ${escapeHtml(report.summary.total_persisted_records)}</p>`
                    : ""
                }
                ${renderReportPreview(report)}
                <ul>${(report.limitations || []).map((limitation) => `<li>${escapeHtml(limitation)}</li>`).join("")}</ul>
              </section>
            `
          : '<p class="module2-provenance">Choose a template and request a preview to see a bounded sample of matching persisted records.</p>';
  const generationMessage =
    state.reportGenerateStatus === "error"
      ? `<p class="module2-message" role="alert">${escapeHtml(state.reportGenerateError)}</p>`
      : state.reportGenerateStatus === "success"
        ? '<p class="module2-message" role="status">The server generated the draft file and the download was started. It is not official or approved.</p>'
        : "";
  const unavailableFormats = selectedTemplate.unavailable_formats || {};
  return `
    <section class="module2-section module2-reporting">
      <div class="module2-section-heading">
        <div>
          <h2>Configurable draft reports</h2>
          <p>Server-side templates use only persisted, authorized Module II faculty and research records. Generated files are drafts, not institutional or accreditation approvals.</p>
        </div>
        <button type="button" class="secondary-button" data-module2-action="retry-report-templates">Refresh templates</button>
      </div>
      <div class="module2-report-controls">
        <label>Report template
          <select data-module2-report-template>
            ${templates.map((template) => `<option value="${escapeHtml(template.id)}" ${template.id === selectedTemplate.id ? "selected" : ""}>${escapeHtml(template.title)} · v${escapeHtml(template.version)}</option>`).join("")}
          </select>
        </label>
        ${
          supportsPeriod
            ? `
                <label>Year from <input type="number" min="1900" max="2100" data-module2-report-year-from value="${escapeHtml(state.reportYearFrom)}"></label>
                <label>Year to <input type="number" min="1900" max="2100" data-module2-report-year-to value="${escapeHtml(state.reportYearTo)}"></label>
              `
            : '<p>This template does not support a reporting-period filter.</p>'
        }
        <button type="button" class="primary-button" data-module2-action="preview-report" ${state.reportPreviewStatus === "loading" || state.reportGenerating ? "disabled" : ""}>Preview</button>
      </div>
      <p class="module2-filter-error" data-module2-report-filter-error role="alert" hidden></p>
      <p>${escapeHtml(selectedTemplate.description)}</p>
      <p><strong>Limitation:</strong> ${escapeHtml(selectedTemplate.limitation)}</p>
      <p><strong>Available formats:</strong> ${formats.length ? formats.map((format) => escapeHtml(format.toUpperCase())).join(", ") : "None on this server"}</p>
      ${
        Object.keys(unavailableFormats).length
          ? `<p><strong>Unavailable formats:</strong> ${Object.entries(unavailableFormats).map(([format, reason]) => `${escapeHtml(format.toUpperCase())}: ${escapeHtml(reason)}`).join("; ")}</p>`
          : ""
      }
      ${preview}
      ${
        state.reportPreviewStatus === "success" && formats.length
          ? `
              <div class="module2-report-downloads" aria-label="Generate draft report">
                ${formats.map((format) => `<button type="button" class="secondary-button" data-module2-report-generate="${escapeHtml(format)}" ${state.reportGenerating ? "disabled" : ""}>${state.reportGenerating ? "Generating…" : `Download ${escapeHtml(format.toUpperCase())}`}</button>`).join("")}
              </div>
              ${generationMessage}
            `
          : generationMessage
      }
    </section>
  `;
}

function renderActiveView(state) {
  const databaseNotice = renderDatabaseConfigurationNotice(state.capabilityState);
  if (databaseNotice && state.view !== "overview") {
    return databaseNotice;
  }
  if (state.view === "overview") {
    return renderOverview(state);
  }
  if (state.view === "faculty") {
    return state.facultyDetail
      ? renderFacultyDetail(state.facultyDetail)
      : renderFacultyList(state);
  }
  if (state.view === "research") {
    return renderResearchRecords(state);
  }
  if (state.view === "statistics") {
    return renderStatistics(state);
  }
  if (state.view === "data-quality") {
    return renderDataQuality(state);
  }
  if (state.view === "exports") {
    return renderExportDatasets(state);
  }
  if (state.view === "reporting") {
    return renderReporting(state);
  }
  return '<p class="module2-message">This Module II area is unavailable.</p>';
}

export function createModule2Controller(
  container,
  capabilityState,
  api = {
    downloadModule2Export,
    generateModule2Report,
    getModule2DataQuality,
    getModule2ExportDatasets,
    getModule2Faculty,
    getModule2FacultyDetail,
    getModule2ReportTemplates,
    getModule2ResearchRecords,
    getModule2ResearchStatistics,
    previewModule2Report,
  },
  onRetryCapabilities = () => {},
) {
  const state = {
    capabilityState,
    view: "overview",
    researchType: "publications",
    facultyItems: [],
    facultyQuery: "",
    facultyOffset: 0,
    facultyDetail: null,
    facultyDetailId: null,
    facultyLoadedKey: null,
    researchItems: [],
    researchQuery: "",
    yearFrom: "",
    yearTo: "",
    researchOffset: 0,
    researchLoadedKey: null,
    statistics: null,
    statsStatus: "idle",
    statsError: null,
    statsReceivedAt: "",
    statsPending: false,
    statsRequestVersion: 0,
    qualityReport: null,
    qualityStatus: "idle",
    qualityError: null,
    qualityCategory: "all",
    qualityOffset: 0,
    qualityLoadedKey: null,
    qualityPendingKey: null,
    qualityPendingRequestId: null,
    qualityRequestVersion: 0,
    exportMetadata: null,
    exportStatus: "idle",
    exportError: null,
    exportPending: new Set(),
    exportMetadataPending: false,
    exportMetadataRequestVersion: 0,
    reportTemplates: null,
    reportTemplatesStatus: "idle",
    reportTemplatesError: null,
    reportTemplateId: "",
    reportYearFrom: "",
    reportYearTo: "",
    reportPreview: null,
    reportPreviewStatus: "idle",
    reportPreviewError: null,
    reportGenerateStatus: "idle",
    reportGenerateError: null,
    reportGenerating: false,
    reportRequestVersion: 0,
    requestVersion: 0,
    facultyPendingKey: null,
    researchPendingKey: null,
    active: false,
  };

  function contentElement() {
    return container.querySelector("#module2-content");
  }

  function setContent(markup, busy = false) {
    const content = contentElement();
    if (!content || !state.active) {
      return;
    }
    content.innerHTML = markup;
    content.setAttribute("aria-busy", String(busy));
  }

  function render() {
    if (!state.active) {
      return;
    }
    container.innerHTML = renderModule2Page(state.capabilityState);
    const views = availableViews(state.capabilityState);
    if (!views.length) {
      return;
    }
    container.querySelectorAll("[data-module2-view]").forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.module2View === state.view),
      );
    });
    setContent(renderActiveView(state));
  }

  function isCurrent(requestVersion, view) {
    return (
      state.active &&
      state.requestVersion === requestVersion &&
      state.view === view
    );
  }

  async function loadStatistics(force = false) {
    if (!hasPermission(state.capabilityState, STATISTICS_PERMISSION)) {
      return;
    }
    if (!force && state.statsStatus !== "idle") {
      return;
    }
    if (state.statsPending) {
      return;
    }
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      state.statsStatus = "error";
      state.statsError = new APIError("Database profile is not configured.", 503);
      if (state.view === "overview") {
        setContent(renderOverview(state));
      } else if (state.view === "statistics") {
        setContent(renderStatistics(state));
      }
      return;
    }
    state.statsStatus = "loading";
    state.statsError = null;
    state.statsPending = true;
    const requestVersion = ++state.statsRequestVersion;
    if (state.view === "overview") {
      setContent(renderOverview(state), true);
    } else if (state.view === "statistics") {
      setContent(renderStatistics(state), true);
    }
    try {
      const response = await api.getModule2ResearchStatistics();
      if (!state.active || state.statsRequestVersion !== requestVersion) {
        return;
      }
      state.statistics = response;
      state.statsStatus = "success";
      state.statsReceivedAt = new Date().toLocaleString();
    } catch (error) {
      if (!state.active || state.statsRequestVersion !== requestVersion) {
        return;
      }
      state.statsStatus = "error";
      state.statsError = error;
    } finally {
      if (state.active && state.statsRequestVersion === requestVersion) {
        state.statsPending = false;
      }
    }
    if (
      state.active &&
      state.statsRequestVersion === requestVersion &&
      ["overview", "statistics"].includes(state.view)
    ) {
      setContent(state.view === "overview" ? renderOverview(state) : renderStatistics(state));
    }
  }

  async function loadFaculty(force = false) {
    if (!hasPermission(state.capabilityState, FACULTY_PERMISSION)) {
      return;
    }
    const key = `faculty:${state.facultyQuery}:${state.facultyOffset}`;
    if (state.facultyPendingKey === key) {
      return;
    }
    if (!force && state.facultyLoadedKey === key) {
      setContent(renderFacultyList(state));
      return;
    }
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      setContent(renderDatabaseConfigurationNotice(state.capabilityState));
      return;
    }
    const requestVersion = ++state.requestVersion;
    const view = state.view;
    state.facultyPendingKey = key;
    setContent('<p class="module2-message" role="status">Loading faculty profiles…</p>', true);
    try {
      const response = await api.getModule2Faculty({
        query: state.facultyQuery,
        limit: PAGE_SIZE,
        offset: state.facultyOffset,
      });
      if (!isCurrent(requestVersion, view)) {
        return;
      }
      if (!Array.isArray(response?.items)) {
        throw new TypeError("The faculty API response is invalid.");
      }
      state.facultyItems = response.items;
      state.facultyLoadedKey = key;
      state.facultyPendingKey = null;
      setContent(renderFacultyList(state));
    } catch (error) {
      if (!isCurrent(requestVersion, view)) {
        return;
      }
      state.facultyPendingKey = null;
      setContent(renderLoadError(error, "faculty profiles", "retry"));
    }
  }

  async function loadResearch(force = false) {
    if (!hasPermission(state.capabilityState, RESEARCH_PERMISSION)) {
      return;
    }
    const key = `research:${state.researchType}:${state.researchQuery}:${state.yearFrom}:${state.yearTo}:${state.researchOffset}`;
    if (state.researchPendingKey === key) {
      return;
    }
    if (!force && state.researchLoadedKey === key) {
      setContent(renderResearchRecords(state));
      return;
    }
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      setContent(renderDatabaseConfigurationNotice(state.capabilityState));
      return;
    }
    const requestVersion = ++state.requestVersion;
    const view = state.view;
    state.researchPendingKey = key;
    setContent('<p class="module2-message" role="status">Loading research records…</p>', true);
    const filters = {
      query: state.researchQuery,
      year_from: state.yearFrom ? Number(state.yearFrom) : undefined,
      year_to: state.yearTo ? Number(state.yearTo) : undefined,
      limit: PAGE_SIZE,
      offset: state.researchOffset,
    };
    try {
      const response = await api.getModule2ResearchRecords(
        state.researchType,
        filters,
      );
      if (!isCurrent(requestVersion, view)) {
        return;
      }
      if (!Array.isArray(response?.items)) {
        throw new TypeError("The research API response is invalid.");
      }
      state.researchItems = response.items;
      state.researchLoadedKey = key;
      state.researchPendingKey = null;
      setContent(renderResearchRecords(state));
    } catch (error) {
      if (!isCurrent(requestVersion, view)) {
        return;
      }
      state.researchPendingKey = null;
      setContent(renderLoadError(error, "research records", "retry"));
    }
  }

  async function loadExportMetadata(force = false) {
    if (!canAccessExports(state.capabilityState)) {
      return;
    }
    if (!force && state.exportStatus !== "idle") {
      return;
    }
    if (state.exportMetadataPending) {
      return;
    }
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      state.exportStatus = "error";
      state.exportError = new APIError("Database profile is not configured.", 503);
      setContent(renderExportDatasets(state));
      return;
    }
    const requestVersion = ++state.exportMetadataRequestVersion;
    state.exportMetadataPending = true;
    state.exportStatus = "loading";
    state.exportError = null;
    setContent(renderExportDatasets(state), true);
    try {
      const response = await api.getModule2ExportDatasets();
      if (
        !state.active ||
        state.exportMetadataRequestVersion !== requestVersion
      ) {
        return;
      }
      if (!Array.isArray(response?.datasets) || !Array.isArray(response?.formats)) {
        throw new TypeError("The export discovery response is invalid.");
      }
      state.exportMetadata = response;
      state.exportStatus = "success";
    } catch (error) {
      if (
        !state.active ||
        state.exportMetadataRequestVersion !== requestVersion
      ) {
        return;
      }
      state.exportStatus = "error";
      state.exportError = error;
    } finally {
      if (
        state.active &&
        state.exportMetadataRequestVersion === requestVersion
      ) {
        state.exportMetadataPending = false;
      }
    }
    if (
      state.active &&
      state.exportMetadataRequestVersion === requestVersion &&
      state.view === "exports"
    ) {
      setContent(renderExportDatasets(state));
    }
  }

  async function loadReportTemplates(force = false) {
    if (!hasPermission(state.capabilityState, REPORTS_PERMISSION)) {
      return;
    }
    if (!force && state.reportTemplatesStatus !== "idle") {
      return;
    }
    if (state.reportTemplatesStatus === "loading") {
      return;
    }
    const requestVersion = ++state.reportRequestVersion;
    state.reportTemplatesStatus = "loading";
    state.reportTemplatesError = null;
    setContent(renderReporting(state), true);
    try {
      const response = await api.getModule2ReportTemplates();
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      if (
        !Array.isArray(response?.templates) ||
        response.templates.some(
          (template) =>
            typeof template?.id !== "string" ||
            typeof template?.title !== "string" ||
            !Array.isArray(template.supported_formats),
        )
      ) {
        throw new TypeError("The report-template response is invalid.");
      }
      state.reportTemplates = response;
      state.reportTemplateId =
        response.templates.find((template) => template.id === state.reportTemplateId)?.id ||
        response.templates[0]?.id ||
        "";
      state.reportTemplatesStatus = "success";
    } catch (error) {
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      state.reportTemplatesStatus = "error";
      state.reportTemplatesError = error;
    }
    if (
      state.active &&
      state.view === "reporting" &&
      state.reportRequestVersion === requestVersion
    ) {
      setContent(renderReporting(state));
    }
  }

  function reportFiltersFromControls(templateId) {
    const template = state.reportTemplates?.templates?.find(
      (item) => item.id === templateId,
    );
    if (!template) {
      return null;
    }
    const supportsPeriod =
      Array.isArray(template.filters) && template.filters.includes("year_from");
    const yearFrom = supportsPeriod
      ? container.querySelector("[data-module2-report-year-from]")?.value || ""
      : "";
    const yearTo = supportsPeriod
      ? container.querySelector("[data-module2-report-year-to]")?.value || ""
      : "";
    const fromNumber = yearFrom ? Number(yearFrom) : null;
    const toNumber = yearTo ? Number(yearTo) : null;
    const filterError = container.querySelector(
      "[data-module2-report-filter-error]",
    );
    if (
      (fromNumber != null &&
        (!Number.isInteger(fromNumber) ||
          fromNumber < 1900 ||
          fromNumber > 2100)) ||
      (toNumber != null &&
        (!Number.isInteger(toNumber) || toNumber < 1900 || toNumber > 2100)) ||
      (fromNumber != null && toNumber != null && fromNumber > toNumber)
    ) {
      if (filterError) {
        filterError.textContent =
          "Enter years from 1900 to 2100 and ensure the start year is not later than the end year.";
        filterError.hidden = false;
      }
      return null;
    }
    if (filterError) {
      filterError.textContent = "";
      filterError.hidden = true;
    }
    state.reportTemplateId = templateId;
    state.reportYearFrom = yearFrom;
    state.reportYearTo = yearTo;
    return {
      template_id: templateId,
      year_from: fromNumber ?? undefined,
      year_to: toNumber ?? undefined,
    };
  }

  async function previewReport() {
    if (!hasPermission(state.capabilityState, REPORTS_PERMISSION)) {
      return;
    }
    const templateId =
      container.querySelector("[data-module2-report-template]")?.value ||
      state.reportTemplateId;
    const filters = reportFiltersFromControls(templateId);
    if (!filters) {
      return;
    }
    const requestVersion = ++state.reportRequestVersion;
    state.reportPreviewStatus = "loading";
    state.reportPreviewError = null;
    state.reportGenerateStatus = "idle";
    state.reportGenerateError = null;
    setContent(renderReporting(state), true);
    try {
      const response = await api.previewModule2Report(filters);
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      if (
        response?.template_id !== templateId ||
        response.status !== "DRAFT_NOT_OFFICIAL" ||
        !Number.isSafeInteger(response.summary?.record_count) ||
        !Array.isArray(response.columns) ||
        !Array.isArray(response.preview_rows) ||
        !Array.isArray(response.scope?.departments) ||
        !Array.isArray(response.limitations)
      ) {
        throw new TypeError("The report preview response is invalid.");
      }
      state.reportPreview = response;
      state.reportPreviewStatus = "success";
    } catch (error) {
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      state.reportPreviewStatus = "error";
      state.reportPreviewError = error;
    }
    if (
      state.active &&
      state.view === "reporting" &&
      state.reportRequestVersion === requestVersion
    ) {
      setContent(renderReporting(state));
    }
  }

  async function generateReport(format) {
    if (!hasPermission(state.capabilityState, REPORTS_PERMISSION)) {
      return;
    }
    const templateId =
      container.querySelector("[data-module2-report-template]")?.value ||
      state.reportTemplateId;
    const template = state.reportTemplates?.templates?.find(
      (item) => item.id === templateId,
    );
    if (
      !template ||
      !template.supported_formats.includes(format) ||
      state.reportGenerating
    ) {
      return;
    }
    const filters = reportFiltersFromControls(templateId);
    if (!filters) {
      return;
    }
    const requestVersion = ++state.reportRequestVersion;
    state.reportGenerating = true;
    state.reportGenerateStatus = "idle";
    state.reportGenerateError = null;
    setContent(renderReporting(state), true);
    try {
      const blob = await api.generateModule2Report({ ...filters, format });
      if (!(blob instanceof Blob) || blob.size === 0) {
        throw new TypeError("The generated report download is invalid.");
      }
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `departmentai-draft-${templateId}.${format}`;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      state.reportGenerateStatus = "success";
    } catch (error) {
      if (
        !state.active ||
        state.view !== "reporting" ||
        state.reportRequestVersion !== requestVersion
      ) {
        return;
      }
      state.reportGenerateStatus = "error";
      state.reportGenerateError =
        error instanceof APIError
          ? error.message
          : "The report could not be generated or downloaded.";
    } finally {
      if (state.reportRequestVersion === requestVersion) {
        state.reportGenerating = false;
      }
    }
    if (
      state.active &&
      state.view === "reporting" &&
      state.reportRequestVersion === requestVersion
    ) {
      setContent(renderReporting(state));
    }
  }

  async function loadDataQuality(force = false) {
    if (!hasPermission(state.capabilityState, DATA_QUALITY_PERMISSION)) {
      return;
    }
    const category =
      state.qualityCategory === "all" ? undefined : state.qualityCategory;
    const key = `quality:${category || "all"}:${state.qualityOffset}`;
    if (state.qualityPendingKey === key) {
      return;
    }
    if (!force && state.qualityLoadedKey === key) {
      setContent(renderDataQuality(state));
      return;
    }
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      state.qualityStatus = "error";
      state.qualityError = new APIError("Database profile is not configured.", 503);
      setContent(renderDataQuality(state));
      return;
    }
    const requestId = ++state.qualityRequestVersion;
    state.qualityPendingKey = key;
    state.qualityPendingRequestId = requestId;
    state.qualityStatus = "loading";
    state.qualityError = null;
    setContent(renderDataQuality(state), true);
    try {
      const response = await api.getModule2DataQuality({
        category,
        limit: PAGE_SIZE,
        offset: state.qualityOffset,
      });
      if (
        !state.active ||
        state.view !== "data-quality" ||
        state.qualityRequestVersion !== requestId
      ) {
        return;
      }
      if (
        !response ||
        !response.summary ||
        !Array.isArray(response.issues) ||
        !Number.isSafeInteger(response.total)
      ) {
        throw new TypeError("The data-quality API response is invalid.");
      }
      state.qualityReport = response;
      state.qualityLoadedKey = key;
      state.qualityStatus = "success";
    } catch (error) {
      if (
        !state.active ||
        state.view !== "data-quality" ||
        state.qualityRequestVersion !== requestId
      ) {
        return;
      }
      state.qualityStatus = "error";
      state.qualityError = error;
    } finally {
      if (state.qualityPendingRequestId === requestId) {
        state.qualityPendingKey = null;
        state.qualityPendingRequestId = null;
      }
    }
    if (
      state.active &&
      state.view === "data-quality" &&
      state.qualityRequestVersion === requestId
    ) {
      setContent(renderDataQuality(state));
    }
  }

  function loadCurrentView(force = false) {
    if (state.capabilityState.capabilities?.database_profile_configured === false) {
      if (state.view === "overview") {
        state.statsStatus = "error";
        state.statsError = new APIError("Database profile is not configured.", 503);
        setContent(renderOverview(state));
      } else {
        setContent(renderDatabaseConfigurationNotice(state.capabilityState));
      }
      return;
    }
    if (state.view === "overview") {
      return loadStatistics(force);
    } else if (state.view === "faculty") {
      return loadFaculty(force);
    } else if (state.view === "research") {
      return loadResearch(force);
    } else if (state.view === "statistics") {
      return loadStatistics(force);
    } else if (state.view === "exports") {
      return loadExportMetadata(force);
    } else if (state.view === "reporting") {
      return loadReportTemplates(force);
    } else if (state.view === "data-quality") {
      return loadDataQuality(force);
    }
  }

  function selectView(view) {
    if (!availableViews(state.capabilityState).some((item) => item.id === view)) {
      return;
    }
    if (state.view === "data-quality" && view !== "data-quality") {
      state.qualityRequestVersion += 1;
      state.qualityPendingKey = null;
      state.qualityPendingRequestId = null;
    }
    if (state.view === "reporting" && view !== "reporting") {
      state.reportRequestVersion += 1;
      state.reportGenerating = false;
      if (state.reportTemplatesStatus === "loading") {
        state.reportTemplatesStatus = "idle";
      }
      if (state.reportPreviewStatus === "loading") {
        state.reportPreviewStatus = "idle";
      }
    }
    state.view = view;
    state.requestVersion += 1;
    state.facultyPendingKey = null;
    state.researchPendingKey = null;
    if (view === "faculty") {
      state.facultyDetail = null;
    }
    render();
    if (view === "overview") {
      if (state.statsStatus === "idle") {
        return loadCurrentView();
      }
    } else if (view === "statistics") {
      if (state.statsStatus === "idle") {
        return loadCurrentView();
      }
    } else if (view === "exports") {
      if (state.exportStatus === "idle") {
        return loadCurrentView();
      }
    } else {
      return loadCurrentView();
    }
  }

  async function openFacultyDetail(facultyId) {
    if (!Number.isSafeInteger(facultyId) || facultyId <= 0) {
      return;
    }
    state.facultyDetail = null;
    state.facultyDetailId = facultyId;
    state.requestVersion += 1;
    const requestVersion = state.requestVersion;
    const view = state.view;
    setContent('<p class="module2-message" role="status">Loading authorized faculty profile…</p>', true);
    try {
      const response = await api.getModule2FacultyDetail(facultyId);
      if (!isCurrent(requestVersion, view)) {
        return;
      }
      if (!response || typeof response !== "object" || Array.isArray(response)) {
        throw new TypeError("The faculty profile response is invalid.");
      }
      state.facultyDetail = response;
      setContent(renderFacultyDetail(response));
    } catch (error) {
      if (isCurrent(requestVersion, view)) {
        setContent(renderLoadError(error, "faculty profile", "retry"));
      }
    }
  }

  async function downloadDataset(datasetName, button) {
    const dataset = state.exportMetadata?.datasets?.find(
      (item) => item?.name === datasetName,
    );
    if (!dataset || state.exportPending.has(datasetName)) {
      return;
    }
    const formatInput = Array.from(
      container.querySelectorAll("[data-module2-format]"),
    ).find((input) => input.dataset.module2Format === datasetName);
    const format = formatInput?.value;
    if (!state.exportMetadata.formats.includes(format)) {
      return;
    }
    state.exportPending.add(datasetName);
    if (button) {
      button.disabled = true;
      button.textContent = "Preparing…";
    }
    try {
      const blob = await api.downloadModule2Export(datasetName, format);
      if (!(blob instanceof Blob)) {
        throw new TypeError("The export download response is invalid.");
      }
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${datasetName}.${format}`;
      link.hidden = true;
      document.body.append(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      if (state.active && state.view === "exports") {
        setContent(renderLoadError(error, "export download", "retry-exports"));
      }
    } finally {
      state.exportPending.delete(datasetName);
      if (state.active && state.view === "exports") {
        const downloadButton = container.querySelector(
          `[data-module2-download="${datasetName}"]`,
        );
        if (downloadButton) {
          downloadButton.disabled = false;
          downloadButton.textContent = "Download";
        }
      }
    }
  }

  function handleClick(event) {
    const viewButton = event.target.closest("[data-module2-view]");
    if (viewButton) {
      selectView(viewButton.dataset.module2View);
      return true;
    }
    const typeButton = event.target.closest("[data-module2-record-type]");
    if (typeButton) {
      const nextType = typeButton.dataset.module2RecordType;
      if (Object.hasOwn(RESEARCH_TYPES, nextType)) {
        state.researchType = nextType;
        state.researchOffset = 0;
        loadCurrentView(true);
      }
      return true;
    }
    const facultyButton = event.target.closest("[data-module2-faculty-id]");
    if (facultyButton) {
      void openFacultyDetail(Number(facultyButton.dataset.module2FacultyId));
      return true;
    }
    const exportButton = event.target.closest("[data-module2-download]");
    if (exportButton) {
      void downloadDataset(exportButton.dataset.module2Download, exportButton);
      return true;
    }
    const reportButton = event.target.closest("[data-module2-report-generate]");
    if (reportButton) {
      void generateReport(reportButton.dataset.module2ReportGenerate);
      return true;
    }
    const action = event.target.closest("[data-module2-action]")?.dataset.module2Action;
    if (!action) {
      return false;
    }
    if (action === "retry-capabilities") {
      onRetryCapabilities();
      return true;
    }
    if (action === "retry-report-templates") {
      state.reportTemplatesStatus = "idle";
      return loadReportTemplates(true);
    } else if (action === "preview-report") {
      return previewReport();
    }
    if (action === "retry") {
      if (state.view === "faculty" && state.facultyDetailId) {
        void openFacultyDetail(state.facultyDetailId);
      } else {
        loadCurrentView(true);
      }
    } else if (action === "retry-statistics") {
      state.statsStatus = "idle";
      loadStatistics(true);
    } else if (action === "retry-exports") {
      state.exportStatus = "idle";
      loadExportMetadata(true);
    } else if (action === "retry-data-quality" || action === "refresh-data-quality") {
      state.qualityStatus = "idle";
      state.qualityOffset = 0;
      loadDataQuality(true);
    } else if (action === "apply-quality-filter") {
      const category = container.querySelector(
        "[data-module2-quality-category]",
      )?.value;
      if (
        category !== "all" &&
        !Object.hasOwn(QUALITY_CATEGORY_LABELS, category)
      ) {
        return true;
      }
      state.qualityCategory = category;
      state.qualityOffset = 0;
      loadDataQuality(true);
    } else if (
      action === "quality-previous" ||
      action === "quality-next"
    ) {
      state.qualityOffset = Math.max(
        0,
        Math.min(
          MAX_OFFSET,
          state.qualityOffset +
            (action.endsWith("next") ? PAGE_SIZE : -PAGE_SIZE),
        ),
      );
      loadDataQuality(true);
    } else if (action === "refresh-faculty") {
      loadFaculty(true);
    } else if (action === "search-faculty") {
      const input = container.querySelector("[data-module2-faculty-query]");
      state.facultyQuery = input?.value?.trim() || "";
      state.facultyOffset = 0;
      loadFaculty(true);
    } else if (action === "apply-research-filters") {
      const query = container.querySelector("[data-module2-research-query]")?.value;
      const yearFrom = container.querySelector("[data-module2-year-from]")?.value;
      const yearTo = container.querySelector("[data-module2-year-to]")?.value;
      const fromNumber = yearFrom ? Number(yearFrom) : null;
      const toNumber = yearTo ? Number(yearTo) : null;
      const filterError = container.querySelector("[data-module2-filter-error]");
      if (
        (fromNumber != null && (!Number.isInteger(fromNumber) || fromNumber < 1900 || fromNumber > 2100)) ||
        (toNumber != null && (!Number.isInteger(toNumber) || toNumber < 1900 || toNumber > 2100)) ||
        (fromNumber != null && toNumber != null && fromNumber > toNumber)
      ) {
        if (filterError) {
          filterError.textContent = "Enter years from 1900 to 2100 and ensure the start year is not later than the end year.";
          filterError.hidden = false;
        }
        return true;
      }
      state.researchQuery = query?.trim() || "";
      state.yearFrom = yearFrom || "";
      state.yearTo = yearTo || "";
      state.researchOffset = 0;
      loadResearch(true);
    } else if (action === "refresh-research") {
      loadResearch(true);
    } else if (action === "faculty-previous" || action === "faculty-next") {
      state.facultyOffset = Math.max(
        0,
        Math.min(
          MAX_OFFSET,
          state.facultyOffset + (action.endsWith("next") ? PAGE_SIZE : -PAGE_SIZE),
        ),
      );
      loadFaculty(true);
    } else if (action === "research-previous" || action === "research-next") {
      state.researchOffset = Math.max(
        0,
        Math.min(
          MAX_OFFSET,
          state.researchOffset + (action.endsWith("next") ? PAGE_SIZE : -PAGE_SIZE),
        ),
      );
      loadResearch(true);
    } else if (action === "back-to-faculty") {
      state.facultyDetail = null;
      state.requestVersion += 1;
      setContent(renderFacultyList(state));
    } else {
      return false;
    }
    return true;
  }

  function start() {
    state.active = true;
    if (!hasAccessToken()) {
      state.capabilityState = { status: "unauthenticated" };
    }
    render();
    if (availableViews(state.capabilityState).length) {
      loadCurrentView();
    }
  }

  function dispose() {
    state.active = false;
    state.requestVersion += 1;
    state.statsRequestVersion += 1;
    state.exportMetadataRequestVersion += 1;
    state.reportRequestVersion += 1;
  }

  return {
    start,
    dispose,
    handleClick,
    selectView,
    setFacultySearch(query) {
      state.facultyQuery = typeof query === "string" ? query.trim() : "";
      state.facultyOffset = 0;
      return loadFaculty(true);
    },
    state,
  };
}
