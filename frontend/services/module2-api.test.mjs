import assert from "node:assert/strict";

import {
  clearAccessToken,
  downloadModule2Export,
  generateModule2Report,
  getModule2Capabilities,
  getModule2DataQuality,
  getModule2ExportDatasets,
  getModule2Faculty,
  getModule2FacultyDetail,
  getModule2ReportTemplates,
  getModule2ResearchRecords,
  getModule2ResearchStatistics,
  previewModule2Report,
  setAccessToken,
} from "./api.js";

const originalFetch = globalThis.fetch;
const requests = [];
globalThis.fetch = async (url, options) => {
  const parsedUrl = new URL(url);
  requests.push({
    path: parsedUrl.pathname,
    query: parsedUrl.searchParams,
    authorization: options.headers.Authorization,
    method: options.method || "GET",
    body: options.body ? JSON.parse(options.body) : null,
  });
  if (
    parsedUrl.pathname.endsWith("/download") ||
    parsedUrl.pathname === "/module2/reports/generate"
  ) {
    return new Response(new Uint8Array([37, 80, 68, 70]), {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    });
  }
  const response = {
    "/module2/capabilities": {
      permissions: ["module2.faculty.read"],
      departments: ["Synthetic Department"],
      database_profile_configured: true,
    },
    "/module2/faculty": { items: [], limit: 50, offset: 0 },
    "/module2/faculty/27": { id: 27, full_name: "Synthetic Faculty" },
    "/module2/research/records/publications": {
      record_type: "publications",
      items: [],
      limit: 50,
      offset: 0,
    },
    "/module2/research/statistics": {
      counts: { publications: 0, projects: 0, achievements: 0 },
    },
    "/module2/data-quality/issues": {
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
    },
    "/module2/export/datasets": {
      datasets: [],
      formats: ["csv"],
      max_rows: 10_000,
    },
    "/module2/reports/templates": {
      templates: [
        {
          id: "faculty_directory",
          title: "Configurable Draft — Faculty Directory",
          supported_formats: ["docx", "xlsx", "pdf"],
        },
      ],
    },
    "/module2/reports/preview": {
      template_id: "publications_summary",
      status: "DRAFT_NOT_OFFICIAL",
      summary: { record_count: 0 },
      columns: [],
      preview_rows: [],
      scope: { departments: ["Synthetic Department"] },
      limitations: [],
    },
  }[parsedUrl.pathname];
  return new Response(JSON.stringify(response), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

try {
  setAccessToken("module2-test-token");
  const baseUrl = "http://module2-api.test";

  await getModule2Capabilities(baseUrl);
  await getModule2Faculty({ query: "Robotics", limit: 20, offset: 40 }, baseUrl);
  await getModule2FacultyDetail(27, baseUrl);
  await getModule2ResearchRecords(
    "publications",
    { query: "paper", year_from: 2020, year_to: 2025, limit: 10, offset: 0 },
    baseUrl,
  );
  await getModule2ResearchStatistics(baseUrl);
  await getModule2DataQuality(
    { category: "faculty", limit: 20, offset: 40 },
    baseUrl,
  );
  await getModule2ExportDatasets(baseUrl);
  const download = await downloadModule2Export(
    "faculty_profiles",
    "pdf",
    1000,
    baseUrl,
  );
  await getModule2ReportTemplates(baseUrl);
  const preview = await previewModule2Report(
    { template_id: "publications_summary", year_from: 2020, year_to: 2025 },
    baseUrl,
  );
  const report = await generateModule2Report(
    { template_id: "faculty_directory", format: "docx" },
    baseUrl,
  );

  assert.ok(download instanceof Blob);
  assert.ok(report instanceof Blob);
  assert.equal(preview.status, "DRAFT_NOT_OFFICIAL");
  assert.equal(requests.length, 11);
  assert.ok(requests.every((item) => item.authorization === "Bearer module2-test-token"));
  const facultyRequest = requests.find((item) => item.path === "/module2/faculty");
  assert.equal(facultyRequest.query.get("query"), "Robotics");
  assert.equal(facultyRequest.query.get("limit"), "20");
  assert.equal(facultyRequest.query.get("offset"), "40");
  assert.equal(facultyRequest.query.has("department"), false);
  const researchRequest = requests.find((item) =>
    item.path.endsWith("/records/publications"),
  );
  assert.equal(researchRequest.query.get("year_from"), "2020");
  assert.equal(researchRequest.query.get("year_to"), "2025");
  const qualityRequest = requests.find((item) =>
    item.path.endsWith("/data-quality/issues"),
  );
  assert.equal(qualityRequest.query.get("category"), "faculty");
  assert.equal(qualityRequest.query.get("limit"), "20");
  assert.equal(qualityRequest.query.get("offset"), "40");
  assert.equal(qualityRequest.query.has("department"), false);
  const exportRequest = requests.find((item) =>
    item.path.endsWith("/export/faculty_profiles/download"),
  );
  assert.equal(exportRequest.path, "/module2/export/faculty_profiles/download");
  assert.equal(exportRequest.query.get("format"), "pdf");
  assert.equal(exportRequest.query.get("limit"), "1000");
  const templateRequest = requests.find((item) =>
    item.path.endsWith("/reports/templates"),
  );
  assert.equal(templateRequest.method, "GET");
  const previewRequest = requests.find((item) =>
    item.path.endsWith("/reports/preview"),
  );
  assert.equal(previewRequest.method, "POST");
  assert.deepEqual(previewRequest.body, {
    template_id: "publications_summary",
    year_from: 2020,
    year_to: 2025,
  });
  assert.equal("department" in previewRequest.body, false);
  const generateRequest = requests.find((item) =>
    item.path.endsWith("/reports/generate"),
  );
  assert.equal(generateRequest.path, "/module2/reports/generate");
  assert.equal(generateRequest.method, "POST");
  assert.deepEqual(generateRequest.body, {
    template_id: "faculty_directory",
    format: "docx",
  });

  await assert.rejects(
    getModule2ResearchRecords("patents", {}, baseUrl),
    /Unsupported Module II research record type/,
  );
  assert.equal(requests.length, 11);
  console.log("Module II API client tests passed: authenticated requests, exact endpoints, scoped parameters, and binary exports");
} finally {
  clearAccessToken();
  globalThis.fetch = originalFetch;
}
