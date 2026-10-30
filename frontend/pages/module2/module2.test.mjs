import assert from "node:assert/strict";

import { renderSidebar } from "../../components/layout/sidebar.js";
import { APIError, setAccessToken } from "../../services/api.js";
import {
  createModule2Controller,
  renderModule2Page,
} from "./module2.js";

class FakePanel {
  innerHTML = "";
  attributes = {};

  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

class FakeContainer {
  innerHTML = "";
  panel = new FakePanel();
  elements = new Map();

  querySelector(selector) {
    if (selector === "#module2-content") {
      return this.panel;
    }
    return this.elements.get(selector) || null;
  }

  querySelectorAll() {
    return [];
  }
}

const capabilityState = (permissions) => ({
  status: "ready",
  capabilities: {
    permissions,
    departments: ["Synthetic Department"],
    database_profile_configured: true,
  },
});

const flush = () => new Promise((resolve) => setImmediate(resolve));
const qualityReport = (label = "Synthetic quality record") => ({
  summary: {
    record_counts: { faculty: 1 },
    records_scanned: 1,
    total_issues: 1,
    objective_issues: 1,
    potential_duplicate_findings: 0,
  },
  issues: [
    {
      id: `faculty:7:missing_required_value:full_name`,
      category: "faculty",
      record_id: 7,
      record_label: label,
      field: "full_name",
      issue_type: "missing_required_value",
      classification: "objective",
      explanation: "full_name is required by the persisted Module II schema but is blank.",
      evidence: { stored_value: "" },
      source_url: "https://example.invalid/source",
    },
  ],
  limit: 50,
  offset: 0,
  total: 1,
});
const actionClick = (action) => ({
  target: {
    closest(selector) {
      return selector === "[data-module2-action]"
        ? { dataset: { module2Action: action } }
        : null;
    },
  },
});

try {
  const module2Permission = ["module2.faculty.read"];
  assert.doesNotMatch(
    renderSidebar("dashboard", { role: "OFFICIAL" }, []),
    /data-page="module2"/,
  );
  assert.doesNotMatch(
    renderSidebar("dashboard", null, module2Permission),
    /data-page="module2"/,
  );
  assert.match(
    renderSidebar("dashboard", { role: "OFFICIAL" }, module2Permission),
    /data-page="module2"/,
  );
  assert.doesNotMatch(
    renderSidebar("dashboard", { role: "OFFICIAL" }, ["module2.faculty.chat"]),
    /data-page="module2"/,
  );

  const unauthenticatedCalls = [];
  setAccessToken(null);
  const unauthenticated = createModule2Controller(
    new FakeContainer(),
    capabilityState(module2Permission),
    {
      getModule2Faculty: async () => {
        unauthenticatedCalls.push("faculty");
        return { items: [] };
      },
    },
  );
  unauthenticated.start();
  assert.match(unauthenticated.state.capabilityState.status, /unauthenticated/);
  assert.equal(unauthenticatedCalls.length, 0);

  setAccessToken("synthetic-test-token");
  const deniedCalls = [];
  const deniedContainer = new FakeContainer();
  const denied = createModule2Controller(
    deniedContainer,
    { status: "denied", capabilities: null },
    {
      getModule2Faculty: async () => {
        deniedCalls.push("faculty");
        return { items: [{ id: 1, full_name: "Restricted record" }] };
      },
    },
  );
  denied.start();
  assert.match(deniedContainer.innerHTML, /no Module II permission grant/i);
  assert.doesNotMatch(deniedContainer.innerHTML, /Restricted record/);
  assert.equal(deniedCalls.length, 0);

  const facultyRequests = [];
  const facultyContainer = new FakeContainer();
  const faculty = createModule2Controller(
    facultyContainer,
    capabilityState(module2Permission),
    {
      getModule2Faculty: async (parameters) => {
        facultyRequests.push(parameters);
        return {
          items: [
            {
              id: 37,
              full_name: "<Synthetic Faculty>",
              designation: "Professor",
              department: "Synthetic Department",
              area_of_interest: "Robotics",
            },
          ],
          limit: 50,
          offset: 0,
        };
      },
      getModule2FacultyDetail: async () => ({
        id: 37,
        full_name: "Synthetic Faculty",
        designation: "Professor",
        department: "Synthetic Department",
        qualification: "Ph.D.",
        area_of_interest: "Robotics",
        verification_status: "VERIFIED",
      }),
    },
  );
  faculty.start();
  await faculty.selectView("faculty");
  assert.match(facultyContainer.panel.innerHTML, /&lt;Synthetic Faculty&gt;/);
  assert.match(facultyContainer.panel.innerHTML, /Robotics/);
  assert.deepEqual(facultyRequests[0], {
    query: "",
    limit: 50,
    offset: 0,
  });
  assert.doesNotMatch(facultyContainer.panel.innerHTML, /data-module2-department/);
  assert.match(facultyContainer.innerHTML, /Synthetic Department/);

  const emptyContainer = new FakeContainer();
  const emptyFaculty = createModule2Controller(
    emptyContainer,
    capabilityState(module2Permission),
    { getModule2Faculty: async () => ({ items: [], limit: 50, offset: 0 }) },
  );
  emptyFaculty.start();
  await emptyFaculty.selectView("faculty");
  assert.match(emptyContainer.panel.innerHTML, /No faculty matched this search/);

  const profileContainer = new FakeContainer();
  const profile = createModule2Controller(
    profileContainer,
    capabilityState(module2Permission),
    {
      getModule2Faculty: async () => ({ items: [] }),
      getModule2FacultyDetail: async () => ({
        id: 37,
        full_name: "Synthetic Faculty",
        department: "Synthetic Department",
        qualification: "Ph.D.",
        profile_url: "https://example.invalid/profile",
      }),
    },
  );
  profile.start();
  await profile.selectView("faculty");
  await profile.handleClick({
    target: {
      closest(selector) {
        return selector === "[data-module2-faculty-id]"
          ? { dataset: { module2FacultyId: "37" } }
          : null;
      },
    },
  });
  await flush();
  assert.match(profileContainer.panel.innerHTML, /Synthetic Faculty/);
  assert.match(profileContainer.panel.innerHTML, /Ph\.D\./);

  const researchContainer = new FakeContainer();
  const researchCalls = [];
  const research = createModule2Controller(
    researchContainer,
    capabilityState(["module2.research.read"]),
    {
      getModule2ResearchRecords: async (type, parameters) => {
        researchCalls.push({ type, parameters });
        return {
          record_type: type,
          items: [
            {
              id: 18,
              title: "Synthetic publication",
              publication_type: "Journal",
              publication_year: 2025,
              authors: "Synthetic Faculty",
              department: "Synthetic Department",
              source_url: "https://example.invalid/source",
            },
          ],
          limit: 50,
          offset: 0,
        };
      },
    },
  );
  research.start();
  await research.selectView("research");
  assert.equal(researchCalls[0].type, "publications");
  assert.equal(researchCalls[0].parameters.limit, 50);
  assert.match(researchContainer.panel.innerHTML, /Synthetic publication/);
  assert.match(researchContainer.panel.innerHTML, /Publication Year/);
  assert.match(researchContainer.panel.innerHTML, /Source Url/);
  assert.match(researchContainer.panel.innerHTML, /Projects/);
  assert.match(researchContainer.panel.innerHTML, /Achievements/);
  assert.doesNotMatch(researchContainer.panel.innerHTML, /Patents/);

  const qualityPermission = ["module2.data_quality.read"];
  assert.match(
    renderModule2Page(capabilityState(qualityPermission)),
    /data-module2-view="data-quality"/,
  );
  assert.doesNotMatch(
    renderModule2Page(capabilityState(["module2.faculty.read"])),
    /data-module2-view="data-quality"/,
  );

  const qualityContainer = new FakeContainer();
  const qualityCalls = [];
  const quality = createModule2Controller(
    qualityContainer,
    capabilityState(qualityPermission),
    {
      getModule2DataQuality: async (parameters) => {
        qualityCalls.push(parameters);
        return qualityReport();
      },
    },
  );
  quality.start();
  await quality.selectView("data-quality");
  assert.deepEqual(qualityCalls[0], {
    category: undefined,
    limit: 50,
    offset: 0,
  });
  assert.match(qualityContainer.panel.innerHTML, /Data quality review/);
  assert.match(qualityContainer.panel.innerHTML, /Synthetic quality record/);
  assert.match(qualityContainer.panel.innerHTML, /Schema\/data check/);
  assert.match(qualityContainer.panel.innerHTML, /Inspect persisted evidence/);
  assert.match(qualityContainer.panel.innerHTML, /Reviewer actions, corrections, and dismissals are not supported/);
  assert.doesNotMatch(qualityContainer.panel.innerHTML, /Mark reviewed|Dismiss issue|Correct record/);

  const emptyQualityContainer = new FakeContainer();
  const emptyQuality = createModule2Controller(
    emptyQualityContainer,
    capabilityState(qualityPermission),
    {
      getModule2DataQuality: async () => ({
        summary: {
          record_counts: { faculty: 0 },
          records_scanned: 0,
          total_issues: 0,
          objective_issues: 0,
          potential_duplicate_findings: 0,
        },
        issues: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    },
  );
  emptyQuality.start();
  await emptyQuality.selectView("data-quality");
  assert.match(emptyQualityContainer.panel.innerHTML, /No persisted records were found/);

  const cleanQualityContainer = new FakeContainer();
  const cleanQuality = createModule2Controller(
    cleanQualityContainer,
    capabilityState(qualityPermission),
    {
      getModule2DataQuality: async () => ({
        summary: {
          record_counts: { faculty: 2 },
          records_scanned: 2,
          total_issues: 0,
          objective_issues: 0,
          potential_duplicate_findings: 0,
        },
        issues: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    },
  );
  cleanQuality.start();
  await cleanQuality.selectView("data-quality");
  assert.match(cleanQualityContainer.panel.innerHTML, /No issues were detected in 2 inspected records/);

  let qualityRetryCount = 0;
  const failedQualityContainer = new FakeContainer();
  const failedQuality = createModule2Controller(
    failedQualityContainer,
    capabilityState(qualityPermission),
    {
      getModule2DataQuality: async () => {
        qualityRetryCount += 1;
        if (qualityRetryCount === 1) {
          throw new APIError("Service unavailable.", 503);
        }
        return qualityReport("Recovered quality result");
      },
    },
  );
  failedQuality.start();
  await failedQuality.selectView("data-quality");
  assert.match(failedQualityContainer.panel.innerHTML, /Retry/);
  await failedQuality.handleClick(actionClick("retry-data-quality"));
  await flush();
  assert.equal(qualityRetryCount, 2);
  assert.match(failedQualityContainer.panel.innerHTML, /Recovered quality result/);

  let resolveInitialQuality;
  const staleQualityContainer = new FakeContainer();
  staleQualityContainer.elements.set("[data-module2-quality-category]", {
    value: "faculty",
  });
  const staleQuality = createModule2Controller(
    staleQualityContainer,
    capabilityState(qualityPermission),
    {
      getModule2DataQuality: ({ category }) =>
        new Promise((resolve) => {
          if (!category) {
            resolveInitialQuality = resolve;
          } else {
            resolve(qualityReport("Newest category result"));
          }
        }),
    },
  );
  staleQuality.start();
  const initialQualityRequest = staleQuality.selectView("data-quality");
  await staleQuality.handleClick(actionClick("apply-quality-filter"));
  await flush();
  resolveInitialQuality(qualityReport("Stale all-category result"));
  await initialQualityRequest;
  assert.match(staleQualityContainer.panel.innerHTML, /Newest category result/);
  assert.doesNotMatch(staleQualityContainer.panel.innerHTML, /Stale all-category result/);

  let resolveFirstQualityView;
  let qualityViewCalls = 0;
  const reenteredQualityContainer = new FakeContainer();
  const reenteredQuality = createModule2Controller(
    reenteredQualityContainer,
    capabilityState(["module2.data_quality.read", "module2.faculty.read"]),
    {
      getModule2DataQuality: async () => {
        qualityViewCalls += 1;
        if (qualityViewCalls === 1) {
          return new Promise((resolve) => {
            resolveFirstQualityView = resolve;
          });
        }
        return qualityReport("Reentered quality view");
      },
      getModule2Faculty: async () => ({ items: [] }),
    },
  );
  reenteredQuality.start();
  const firstQualityView = reenteredQuality.selectView("data-quality");
  await reenteredQuality.selectView("faculty");
  await reenteredQuality.selectView("data-quality");
  resolveFirstQualityView(qualityReport("Stale first view"));
  await firstQualityView;
  await flush();
  assert.equal(qualityViewCalls, 2);
  assert.match(reenteredQualityContainer.panel.innerHTML, /Reentered quality view/);
  assert.doesNotMatch(reenteredQualityContainer.panel.innerHTML, /Stale first view/);

  const statsContainer = new FakeContainer();
  const stats = createModule2Controller(
    statsContainer,
    capabilityState(["module2.research.statistics.read"]),
    {
      getModule2ResearchStatistics: async () => ({
        counts: { publications: 0, projects: 2, achievements: 0 },
      }),
    },
  );
  stats.start();
  await stats.selectView("statistics");
  await flush();
  assert.match(statsContainer.panel.innerHTML, /<dd>0<\/dd>/);
  assert.match(statsContainer.panel.innerHTML, /does not provide period filters/i);
  assert.match(statsContainer.panel.innerHTML, /Received at/);

  const failedStatsContainer = new FakeContainer();
  const failedStats = createModule2Controller(
    failedStatsContainer,
    capabilityState(["module2.research.statistics.read"]),
    {
      getModule2ResearchStatistics: async () => {
        throw new APIError("Service unavailable.", 503);
      },
    },
  );
  failedStats.start();
  await flush();
  assert.match(failedStatsContainer.panel.innerHTML, /Unavailable/);
  assert.match(failedStatsContainer.panel.innerHTML, /Retry/);
  assert.doesNotMatch(failedStatsContainer.panel.innerHTML, /<dd>0<\/dd>/);

  let retryCount = 0;
  const retryContainer = new FakeContainer();
  const retryFaculty = createModule2Controller(
    retryContainer,
    capabilityState(module2Permission),
    {
      getModule2Faculty: async () => {
        retryCount += 1;
        if (retryCount === 1) {
          throw new APIError("Service unavailable.", 503);
        }
        return { items: [{ id: 55, full_name: "Recovered result" }] };
      },
    },
  );
  retryFaculty.start();
  await retryFaculty.selectView("faculty");
  assert.match(retryContainer.panel.innerHTML, /Retry/);
  await retryFaculty.handleClick(actionClick("retry"));
  await flush();
  assert.equal(retryCount, 2);
  assert.match(retryContainer.panel.innerHTML, /Recovered result/);

  let resolveFaculty;
  const pendingContainer = new FakeContainer();
  const pending = createModule2Controller(
    pendingContainer,
    capabilityState(module2Permission),
    {
      getModule2Faculty: ({ query }) =>
        new Promise((resolve) => {
          if (!query) {
            resolveFaculty = resolve;
          } else {
            resolve({
              items: [
                {
                  id: 42,
                  full_name: "Newest result",
                  department: "Synthetic Department",
                },
              ],
            });
          }
        }),
    },
  );
  pending.start();
  const oldRequest = pending.selectView("faculty");
  assert.match(pendingContainer.panel.innerHTML, /Loading faculty profiles/);
  const newRequest = pending.setFacultySearch("new");
  await newRequest;
  resolveFaculty({ items: [{ id: 41, full_name: "Stale result" }] });
  await oldRequest;
  assert.match(pendingContainer.panel.innerHTML, /Newest result/);
  assert.doesNotMatch(pendingContainer.panel.innerHTML, /Stale result/);

  const noDatabaseCalls = [];
  const noDatabaseContainer = new FakeContainer();
  const noDatabase = createModule2Controller(
    noDatabaseContainer,
    {
      status: "ready",
      capabilities: {
        permissions: ["module2.faculty.read"],
        departments: ["Synthetic Department"],
        database_profile_configured: false,
      },
    },
    {
      getModule2Faculty: async () => {
        noDatabaseCalls.push("faculty");
        return { items: [] };
      },
    },
  );
  noDatabase.start();
  await noDatabase.selectView("faculty");
  assert.match(noDatabaseContainer.panel.innerHTML, /database profile is not configured/i);
  assert.equal(noDatabaseCalls.length, 0);

  const overviewContainer = new FakeContainer();
  const overview = createModule2Controller(
    overviewContainer,
    capabilityState(["module2.faculty.read"]),
    {},
  );
  overview.start();
  assert.match(overviewContainer.panel.innerHTML, /Student supervision:<\/strong> unavailable/);
  assert.match(overviewContainer.panel.innerHTML, /Faculty chatbot:<\/strong> unavailable/);
  assert.doesNotMatch(overviewContainer.panel.innerHTML, /module2\/export\/ui/);
  assert.doesNotMatch(overviewContainer.innerHTML, /data-module2-view="supervision"/);
  assert.doesNotMatch(overviewContainer.innerHTML, /data-module2-view="chatbot"/);

  const exportContainer = new FakeContainer();
  const exportState = capabilityState([
    "module2.export.faculty_profiles",
  ]);
  const exports = createModule2Controller(exportContainer, exportState, {
    getModule2ExportDatasets: async () => ({
      datasets: [
        { name: "faculty_profiles", columns: ["id", "full_name"] },
      ],
      formats: ["csv", "xlsx"],
      max_rows: 10_000,
    }),
    downloadModule2Export: async () => new Blob(["synthetic"]),
  });
  exports.start();
  await exports.selectView("exports");
  assert.match(exportContainer.panel.innerHTML, /faculty_profiles/);
  assert.match(exportContainer.panel.innerHTML, /CSV/);
  assert.doesNotMatch(
    renderModule2Page(capabilityState(["module2.faculty.read"])),
    /Reports &amp; exports/,
  );
  assert.match(
    renderModule2Page(capabilityState(["module2.reports.generate"])),
    /data-module2-view="reporting"/,
  );
  assert.doesNotMatch(
    renderModule2Page(capabilityState(["module2.faculty.read"])),
    /data-module2-view="reporting"/,
  );

  const reportResponse = (name = "<Synthetic report row>") => ({
    template_id: "publications_summary",
    template_title: "Configurable Draft — Publications Summary",
    template_version: "1.0",
    status: "DRAFT_NOT_OFFICIAL",
    generated_at: "2026-10-28T00:00:00+00:00",
    scope: { departments: ["Synthetic Department"] },
    filters: { year_from: 2020, year_to: 2025 },
    summary: { record_count: 1 },
    columns: [{ key: "title", label: "Title" }],
    preview_rows: [{ title: name }],
    limitations: ["This is not an approved report."],
  });
  const reportContainer = new FakeContainer();
  reportContainer.elements.set("[data-module2-report-template]", {
    value: "publications_summary",
  });
  reportContainer.elements.set("[data-module2-report-year-from]", {
    value: "2020",
  });
  reportContainer.elements.set("[data-module2-report-year-to]", {
    value: "2025",
  });
  const reportCalls = [];
  const reports = createModule2Controller(
    reportContainer,
    capabilityState(["module2.reports.generate"]),
    {
      getModule2ReportTemplates: async () => ({
        templates: [
          {
            id: "publications_summary",
            title: "Configurable Draft — Publications Summary",
            version: "1.0",
            description: "Persisted publications.",
            filters: ["year_from", "year_to"],
            supported_formats: ["docx", "xlsx", "pdf"],
            unavailable_formats: {},
            limitation: "Records are not externally verified.",
          },
        ],
      }),
      previewModule2Report: async (parameters) => {
        reportCalls.push(["preview", parameters]);
        return reportResponse();
      },
      generateModule2Report: async (parameters) => {
        reportCalls.push(["generate", parameters]);
        return new Blob(["synthetic report"]);
      },
    },
  );
  reports.start();
  await reports.selectView("reporting");
  assert.match(reportContainer.panel.innerHTML, /Configurable draft reports/);
  assert.match(reportContainer.panel.innerHTML, /Year from/);
  await reports.handleClick(actionClick("preview-report"));
  assert.deepEqual(reportCalls[0], [
    "preview",
    {
      template_id: "publications_summary",
      year_from: 2020,
      year_to: 2025,
    },
  ]);
  assert.match(reportContainer.panel.innerHTML, /DRAFT_NOT_OFFICIAL/);
  assert.match(reportContainer.panel.innerHTML, /Download DOCX/);
  assert.match(reportContainer.panel.innerHTML, /&lt;Synthetic report row&gt;/);
  assert.doesNotMatch(reportContainer.panel.innerHTML, /<Synthetic report row>/);
  assert.match(reportContainer.panel.innerHTML, /not an approved report/i);

  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;
  const downloadedFiles = [];
  globalThis.document = {
    body: {
      append(link) {
        downloadedFiles.push(link);
      },
    },
    createElement() {
      return {
        click() {
          this.clicked = true;
        },
        remove() {},
      };
    },
  };
  globalThis.window = { setTimeout() {} };
  URL.createObjectURL = () => "blob:synthetic";
  URL.revokeObjectURL = () => {};
  try {
    await reports.handleClick({
      target: {
        closest(selector) {
          return selector === "[data-module2-report-generate]"
            ? { dataset: { module2ReportGenerate: "docx" } }
            : null;
        },
      },
    });
  } finally {
    globalThis.document = originalDocument;
    globalThis.window = originalWindow;
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
  }
  assert.deepEqual(reportCalls[1], [
    "generate",
    {
      template_id: "publications_summary",
      year_from: 2020,
      year_to: 2025,
      format: "docx",
    },
  ]);
  assert.equal(downloadedFiles.length, 1);
  assert.equal(
    downloadedFiles[0].download,
    "departmentai-draft-publications_summary.docx",
  );
  assert.match(reportContainer.panel.innerHTML, /download was started/i);

  let resolveOldPreview;
  const staleReportContainer = new FakeContainer();
  staleReportContainer.elements.set("[data-module2-report-template]", {
    value: "publications_summary",
  });
  const staleReports = createModule2Controller(
    staleReportContainer,
    capabilityState([
      "module2.reports.generate",
      "module2.faculty.read",
    ]),
    {
      getModule2ReportTemplates: async () => ({
        templates: [
          {
            id: "publications_summary",
            title: "Draft Publications",
            version: "1.0",
            description: "Persisted publications.",
            filters: [],
            supported_formats: ["pdf"],
            unavailable_formats: {},
            limitation: "Draft.",
          },
        ],
      }),
      previewModule2Report: () =>
        new Promise((resolve) => {
          resolveOldPreview = resolve;
        }),
      getModule2Faculty: async () => ({ items: [] }),
    },
  );
  staleReports.start();
  await staleReports.selectView("reporting");
  const oldReportRequest = staleReports.handleClick(actionClick("preview-report"));
  await staleReports.selectView("faculty");
  resolveOldPreview(reportResponse("Stale report response"));
  await oldReportRequest;
  assert.doesNotMatch(staleReportContainer.panel.innerHTML, /Stale report response/);

  let resolveFirstTemplateRequest;
  let templateRequestCount = 0;
  const reenteredReportContainer = new FakeContainer();
  const reenteredReports = createModule2Controller(
    reenteredReportContainer,
    capabilityState([
      "module2.reports.generate",
      "module2.faculty.read",
    ]),
    {
      getModule2ReportTemplates: () => {
        templateRequestCount += 1;
        if (templateRequestCount === 1) {
          return new Promise((resolve) => {
            resolveFirstTemplateRequest = resolve;
          });
        }
        return Promise.resolve({
          templates: [
            {
              id: "faculty_directory",
              title: "Current faculty template",
              version: "1.0",
              description: "Current report templates.",
              filters: [],
              supported_formats: ["pdf"],
              unavailable_formats: {},
              limitation: "Draft.",
            },
          ],
        });
      },
      getModule2Faculty: async () => ({ items: [] }),
    },
  );
  reenteredReports.start();
  const firstTemplateRequest = reenteredReports.selectView("reporting");
  await reenteredReports.selectView("faculty");
  await reenteredReports.selectView("reporting");
  resolveFirstTemplateRequest({
    templates: [
      {
        id: "stale_template",
        title: "Stale template",
        version: "1.0",
        description: "Stale.",
        filters: [],
        supported_formats: ["pdf"],
      },
    ],
  });
  await firstTemplateRequest;
  assert.equal(templateRequestCount, 2);
  assert.match(reenteredReportContainer.panel.innerHTML, /Current faculty template/);
  assert.doesNotMatch(reenteredReportContainer.panel.innerHTML, /Stale template/);

  setAccessToken(null);
  console.log("Module II frontend tests passed: authorization, reporting, previews, scoped filters, stale responses, unavailable states, and exports");
} finally {
  setAccessToken(null);
}
