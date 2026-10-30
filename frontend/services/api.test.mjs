import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";

const {
  request,
  APIError,
  analyzeApplicationReadiness,
  askQuestion,
  createApplication,
  submitApplication,
  getUnassignedOfficialApplications,
  claimOfficialApplication,
  getAuditLogs,
  getCommitteeReviews,
  getDeficiencies,
  getEligibility,
  getEligibilityResults,
  getOrdinanceRetrieval,
  getStatusHistory,
  extractApplicationDocument,
  generateApplicationAnalysis,
  getApplicationDocuments,
  processApplication,
  classifyApplicationDocument,
  uploadApplicationDocument,
  updateApplicationStatus,
  updateApplication,
  assignApplicationToCommittee,
  updateCommitteeDecision,
  validateApplicationDocument,
  API_BASE_URL,
  getApplication,
  getApplicationAnalysis,
  getApplicationReadiness,
} = await import(`file://${process.cwd()}/frontend/services/api.js`);

assert.equal(API_BASE_URL, "http://127.0.0.1:8000");

await assert.rejects(
  () => getApplication(1, "http://127.0.0.1:1"),
  (error) =>
    error instanceof APIError &&
    error.status === 0 &&
    error.message === "Unable to connect to the backend.",
);

globalThis.DEPARTMENTAI_API_BASE_URL = "https://api.example.test/";
const configuredApi = await import(
  `file://${process.cwd()}/frontend/services/api.js?configured`
);
assert.equal(configuredApi.API_BASE_URL, "https://api.example.test");

globalThis.DEPARTMENTAI_API_BASE_URL = "javascript:alert(1)";
await assert.rejects(
  () => import(`file://${process.cwd()}/frontend/services/api.js?invalid`),
  /absolute HTTP\(S\) URL/,
);

const originalLocation = globalThis.location;
globalThis.location = { protocol: "https:" };
globalThis.DEPARTMENTAI_API_BASE_URL = "http://api.example.test";
await assert.rejects(
  () => import(`file://${process.cwd()}/frontend/services/api.js?mixed-content`),
  /must use HTTPS when the frontend uses HTTPS/,
);
if (originalLocation === undefined) {
  delete globalThis.location;
} else {
  globalThis.location = originalLocation;
}
delete globalThis.DEPARTMENTAI_API_BASE_URL;

let applicationRequest;
let assistantRequest;
let documentUploadRequest;
let aiAnalysisRequest;
const documentApiRequests = [];
const workflowApiRequests = [];

const startServer = () =>
  new Promise((resolve) => {
    const server = createServer((req, res) => {
      const replyWithRequest = (responseBody) => {
        let requestBody = "";
        req.on("data", (chunk) => {
          requestBody += chunk;
        });
        req.on("end", () => {
          workflowApiRequests.push({
            method: req.method,
            url: req.url,
            body: requestBody ? JSON.parse(requestBody) : null,
          });
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify(responseBody));
        });
      };

      if (req.url === "/applications/2" && req.method === "GET") {
        replyWithRequest({
          id: 2,
          application_number: "APP-2026-00002",
          applicant_identifier: "STUDENT-MOCK",
          application_type: "Academic Review",
          title: null,
          description: null,
          status: "DRAFT",
          submitted_at: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        });
        return;
      }

      if (req.url === "/applications/2" && req.method === "PATCH") {
        replyWithRequest({
          id: 2,
          application_number: "APP-2026-00002",
          application_type: "Updated academic request",
          title: "Updated title",
          description: "Updated description",
          status: "DRAFT",
        });
        return;
      }

      if (req.url === "/applications/2/readiness" && req.method === "GET") {
        replyWithRequest({
          application_id: 2,
          readiness_status: "RULES_UNRESOLVED",
          is_stale: false,
          required_documents: null,
        });
        return;
      }

      if (req.url === "/applications/2/analysis" && req.method === "GET") {
        replyWithRequest({
          schema_version: 1,
          application_id: 2,
          analysis_status: "RULES_UNRESOLVED",
          freshness_status: "CURRENT",
          readiness: {
            readiness_status: "RULES_UNRESOLVED",
            is_stale: false,
          },
          eligibility: { analysis_status: "NOT_GENERATED", results: [] },
          eligibility_freshness: "NOT_TRACKED",
          advisory: true,
          formal_decision: false,
        });
        return;
      }

      if (
        req.url === "/applications/2/readiness/analyze" &&
        req.method === "POST"
      ) {
        replyWithRequest({
          application_id: 2,
          readiness_status: "RULES_UNRESOLVED",
          required_documents: null,
          deficiency_count: null,
        });
        return;
      }

      if (
        req.url === "/official/applications/unassigned?limit=20&offset=0" &&
        req.method === "GET"
      ) {
        replyWithRequest({
          items: [
            {
              id: 2,
              application_number: "APP-2026-00002",
              status: "SUBMITTED",
            },
          ],
          limit: 20,
          offset: 0,
        });
        return;
      }

      if (
        req.url === "/applications/2/submit" &&
        req.method === "POST"
      ) {
        replyWithRequest({
          application_id: 2,
          old_status: "DRAFT",
          new_status: "SUBMITTED",
          history_id: 2,
        });
        return;
      }

      if (
        req.url === "/applications/2/claim" &&
        req.method === "POST"
      ) {
        replyWithRequest({
          application_id: 2,
          official_user_id: 4,
          assigned_at: "2026-01-02T00:00:00Z",
        });
        return;
      }

      if (req.url === "/applications/2/ordinance-retrieval") {
        replyWithRequest({ application_id: 2, query: "Academic Review", results: [] });
        return;
      }

      if (req.url === "/applications/2/eligibility") {
        replyWithRequest({
          application_id: 2,
          requirements_analyzed: 0,
          results: [],
        });
        return;
      }

      if (req.url === "/applications/2/eligibility/results") {
        replyWithRequest({
          application_id: 2,
          analysis_status: "NOT_GENERATED",
          requirements_analyzed: 0,
          results_count: 0,
          results: [],
          advisory: true,
        });
        return;
      }

      if (req.url === "/applications/2/deficiencies") {
        replyWithRequest({
          application_id: 2,
          deficiencies_detected: 0,
          deficiencies: [],
        });
        return;
      }

      if (req.url === "/applications/2/status-history") {
        replyWithRequest({
          application_id: 2,
          history: [
            {
              id: 1,
              old_status: null,
              new_status: "DRAFT",
              changed_by: "SYSTEM",
              reason: "Application created.",
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        });
        return;
      }

      if (req.url === "/applications/2/status" && req.method === "PATCH") {
        replyWithRequest({
          application_id: 2,
          old_status: "DRAFT",
          new_status: "SUBMITTED",
          changed_by: "STAFF-01",
          reason: "Submitted for review.",
          history_id: 2,
        });
        return;
      }

      if (req.url === "/applications/2/process" && req.method === "POST") {
        replyWithRequest({ application_id: 2, status: "PROCESSING" });
        return;
      }

      if (req.url === "/applications/2/committee" && req.method === "POST") {
        replyWithRequest({
          id: 3,
          application_id: 2,
          committee_type: "DUGC",
          review_status: "PENDING",
          assigned_at: "2026-01-02T00:00:00Z",
        });
        return;
      }

      if (req.url === "/applications/2/committee-reviews") {
        replyWithRequest({
          application_id: 2,
          reviews: [
            {
              id: 3,
              application_id: 2,
              committee_type: "DUGC",
              assigned_at: "2026-01-02T00:00:00Z",
              review_status: "COMPLETED",
              decision: "APPROVED",
              decision_reason: "Requirements met.",
              decided_by: "COMMITTEE-01",
              decided_at: "2026-01-03T00:00:00Z",
            },
          ],
        });
        return;
      }

      if (
        req.url === "/committee-reviews/3/decision" &&
        req.method === "PATCH"
      ) {
        replyWithRequest({
          review: { id: 3, decision: "APPROVED" },
          application_status: "APPROVED",
          status_history_id: 4,
        });
        return;
      }

      if (req.url === "/applications/2/audit-logs") {
        replyWithRequest({
          application_id: 2,
          audit_logs: [
            {
              id: 1,
              application_id: 2,
              actor_type: "SYSTEM",
              actor_id: "SYSTEM",
              action: "APPLICATION_CREATED",
              details: { application_number: "APP-2026-00002" },
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        });
        return;
      }

      if (req.url === "/json") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
        return;
      }

      if (req.url === "/empty") {
        res.writeHead(204);
        res.end();
        return;
      }

      if (req.url === "/validation-error") {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ detail: "Invalid input." }));
        return;
      }

      if (req.url === "/readiness-conflict") {
        res.writeHead(409, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            detail: {
              code: "ANALYSIS_PENDING",
              message: "The latest readiness analysis is stale.",
            },
          }),
        );
        return;
      }

      if (req.url === "/ask" && req.method === "POST") {
        let requestBody = "";
        req.on("data", (chunk) => {
          requestBody += chunk;
        });
        req.on("end", () => {
          assistantRequest = JSON.parse(requestBody);
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              answer: "Test answer.",
              sources: [],
            }),
          );
        });
        return;
      }

      if (req.url === "/applications" && req.method === "POST") {
        let requestBody = "";
        req.on("data", (chunk) => {
          requestBody += chunk;
        });
        req.on("end", () => {
          applicationRequest = {
            method: req.method,
            contentType: req.headers["content-type"],
            body: JSON.parse(requestBody),
          };
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              id: 1,
              application_number: "APP-2026-00001",
              status: "DRAFT",
              created_at: "2026-01-01T00:00:00Z",
            }),
          );
        });
        return;
      }

      if (req.url === "/applications/2/documents" && req.method === "POST") {
        const chunks = [];
        req.on("data", (chunk) => chunks.push(chunk));
        req.on("end", () => {
          documentUploadRequest = {
            method: req.method,
            contentType: req.headers["content-type"],
            body: Buffer.concat(chunks).toString("utf8"),
          };
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              id: 7,
              application_id: 2,
              file_name: "test-document.pdf",
              document_type: "MARKSHEET",
              file_path: "documents/applications/APP-TEST/test-document.pdf",
              file_size: 8,
              mime_type: "application/pdf",
              upload_status: "UPLOADED",
              uploaded_at: "2026-01-01T00:00:00Z",
            }),
          );
        });
        return;
      }

      if (req.url === "/applications/2/documents" && req.method === "GET") {
        documentApiRequests.push({ method: req.method, url: req.url });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ application_id: 2, documents: [] }));
        return;
      }

      if (req.url === "/applications/2/documents/7/validate") {
        documentApiRequests.push({ method: req.method, url: req.url });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            valid: true,
            document_id: 7,
            application_id: 2,
            file_name: "test-document.pdf",
            file_size: 8,
            mime_type: "application/pdf",
            reason: "Document passed basic validation.",
          }),
        );
        return;
      }

      if (req.url === "/applications/2/documents/7/extract") {
        documentApiRequests.push({ method: req.method, url: req.url });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            extraction_id: 11,
            document_id: 7,
            extraction_status: "COMPLETED",
            confidence: 1,
            text_length: 8,
            extracted_text: "Test text",
          }),
        );
        return;
      }

      if (req.url === "/applications/2/documents/7/classify") {
        documentApiRequests.push({ method: req.method, url: req.url });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            document_id: 7,
            application_id: 2,
            file_name: "test-document.pdf",
            document_type: "MARKSHEET",
          }),
        );
        return;
      }

      if (req.url === "/applications/2/ai-analysis" && req.method === "POST") {
        let bodyLength = 0;
        req.on("data", (chunk) => { bodyLength += chunk.length; });
        req.on("end", () => {
          aiAnalysisRequest = {
            method: req.method,
            url: req.url,
            bodyLength,
          };
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(
            JSON.stringify({
              analysis_id: 1,
              application_id: 2,
              analysis_type: "APPLICATION_ANALYSIS",
              documents_analyzed: 1,
              requirements_analyzed: 0,
              eligibility_results: 0,
              deficiencies: 0,
              ordinance_results: 5,
              analysis: "APPLICATION SUMMARY:\nTest summary.",
              model: "gemini-3.5-flash-lite",
              created_at: "2026-10-17T00:00:00",
            }),
          );
        });
        return;
      }

      if (req.url === "/network-error") {
        req.socket.destroy();
        return;
      }

      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "Not found." }));
    });

    server.listen(0, "127.0.0.1", () => resolve(server));
  });

const server = await startServer();
const address = server.address();
const baseUrl = `http://127.0.0.1:${address.port}`;

try {
  const jsonResponse = await request("/json", {}, baseUrl);
  assert.deepEqual(jsonResponse, { ok: true });

  const emptyResponse = await request("/empty", {}, baseUrl);
  assert.equal(emptyResponse, null);

  await assert.rejects(
    request("/validation-error", {}, baseUrl),
    (error) =>
      error instanceof APIError &&
      error.status === 400 &&
      error.message === "Invalid input.",
  );

  await assert.rejects(
    request("/readiness-conflict", {}, baseUrl),
    (error) =>
      error instanceof APIError &&
      error.status === 409 &&
      error.message === "The latest readiness analysis is stale." &&
      error.details.detail.code === "ANALYSIS_PENDING",
  );

  await assert.rejects(
    request("/missing", {}, baseUrl),
    (error) =>
      error instanceof APIError &&
      error.status === 404 &&
      error.message === "Not found.",
  );

  await assert.rejects(
    request("/network-error", {}, baseUrl),
    (error) =>
      error instanceof APIError &&
      error.message === "Unable to connect to the backend.",
  );

  const askResponse = await askQuestion(
    "What is eligibility?",
    [{ role: "user", message: "Previous question" }],
    baseUrl,
    "MTECH",
  );
  assert.deepEqual(askResponse, {
    answer: "Test answer.",
    sources: [],
  });
  assert.deepEqual(assistantRequest, {
    question: "What is eligibility?",
    conversation_history: [
      { role: "user", message: "Previous question" },
    ],
    programme: "MTECH",
  });

  const applicationResponse = await createApplication(
    {
      applicant_identifier: "STUDENT-01",
      application_type: "Academic Review",
      title: null,
      description: null,
    },
    baseUrl,
  );
  assert.deepEqual(applicationResponse, {
    id: 1,
    application_number: "APP-2026-00001",
    status: "DRAFT",
    created_at: "2026-01-01T00:00:00Z",
  });
  assert.deepEqual(applicationRequest, {
    method: "POST",
    contentType: "application/json",
    body: {
      applicant_identifier: "STUDENT-01",
      application_type: "Academic Review",
      title: null,
      description: null,
    },
  });
  const applicationRecord = await getApplication(2, baseUrl);
  assert.equal(applicationRecord.application_number, "APP-2026-00002");
  assert.equal(applicationRecord.status, "DRAFT");
  const updatedApplication = await updateApplication(
    2,
    {
      application_type: "Updated academic request",
      title: "Updated title",
      description: "Updated description",
    },
    baseUrl,
  );
  assert.equal(updatedApplication.status, "DRAFT");
  assert.deepEqual(workflowApiRequests.at(-1), {
    method: "PATCH",
    url: "/applications/2",
    body: {
      application_type: "Updated academic request",
      title: "Updated title",
      description: "Updated description",
    },
  });
  const savedReadiness = await getApplicationReadiness(2, baseUrl);
  assert.equal(savedReadiness.readiness_status, "RULES_UNRESOLVED");
  const savedAnalysis = await getApplicationAnalysis(2, baseUrl);
  assert.equal(savedAnalysis.schema_version, 1);
  assert.equal(savedAnalysis.eligibility_freshness, "NOT_TRACKED");
  const analyzedReadiness = await analyzeApplicationReadiness(2, baseUrl);
  assert.equal(analyzedReadiness.deficiency_count, null);
  const submittedApplication = await submitApplication(2, baseUrl);
  assert.equal(submittedApplication.new_status, "SUBMITTED");
  const unassignedApplications = await getUnassignedOfficialApplications(
    {},
    baseUrl,
  );
  assert.equal(unassignedApplications.items[0].status, "SUBMITTED");
  const claimedApplication = await claimOfficialApplication(2, baseUrl);
  assert.equal(claimedApplication.application_id, 2);
  assert.deepEqual(
    workflowApiRequests.slice(-6).map(({ method, url }) => ({ method, url })),
    [
      { method: "GET", url: "/applications/2/readiness" },
      { method: "GET", url: "/applications/2/analysis" },
      { method: "POST", url: "/applications/2/readiness/analyze" },
      { method: "POST", url: "/applications/2/submit" },
      {
        method: "GET",
        url: "/official/applications/unassigned?limit=20&offset=0",
      },
      { method: "POST", url: "/applications/2/claim" },
    ],
  );

  const uploadForm = new FormData();
  uploadForm.append(
    "file",
    new Blob(["pdf-test"], { type: "application/pdf" }),
    "test-document.pdf",
  );
  uploadForm.append("document_type", "MARKSHEET");

  const documentResponse = await uploadApplicationDocument(
    2,
    uploadForm,
    baseUrl,
  );
  assert.equal(documentResponse.file_name, "test-document.pdf");
  assert.equal(documentResponse.upload_status, "UPLOADED");
  assert.equal(documentUploadRequest.method, "POST");
  assert.match(
    documentUploadRequest.contentType,
    /^multipart\/form-data; boundary=/,
  );
  assert.match(
    documentUploadRequest.body,
    /name="file"; filename="test-document\.pdf"/,
  );
  assert.match(documentUploadRequest.body, /name="document_type"/);
  assert.match(documentUploadRequest.body, /MARKSHEET/);
  assert.doesNotMatch(documentUploadRequest.contentType, /application\/json/);

  const documentList = await getApplicationDocuments(2, baseUrl);
  assert.deepEqual(documentList, { application_id: 2, documents: [] });
  const validation = await validateApplicationDocument(2, 7, baseUrl);
  assert.equal(validation.valid, true);
  const extraction = await extractApplicationDocument(2, 7, baseUrl);
  assert.equal(extraction.extraction_status, "COMPLETED");
  const classification = await classifyApplicationDocument(2, 7, baseUrl);
  assert.equal(classification.document_type, "MARKSHEET");
  assert.deepEqual(documentApiRequests, [
    { method: "GET", url: "/applications/2/documents" },
    { method: "GET", url: "/applications/2/documents/7/validate" },
    { method: "POST", url: "/applications/2/documents/7/extract" },
    { method: "POST", url: "/applications/2/documents/7/classify" },
  ]);

  const ordinance = await getOrdinanceRetrieval(2, baseUrl);
  assert.equal(ordinance.application_id, 2);
  assert.deepEqual(ordinance.results, []);
  const eligibility = await getEligibility(2, baseUrl);
  assert.equal(eligibility.application_id, 2);
  assert.deepEqual(eligibility.results, []);
  const savedEligibility = await getEligibilityResults(2, baseUrl);
  assert.equal(savedEligibility.analysis_status, "NOT_GENERATED");
  assert.equal(savedEligibility.advisory, true);
  const deficiencies = await getDeficiencies(2, baseUrl);
  assert.equal(deficiencies.application_id, 2);
  assert.deepEqual(deficiencies.deficiencies, []);

  // M09 — generateApplicationAnalysis
  const analysisResponse = await generateApplicationAnalysis(2, baseUrl);
  assert.equal(aiAnalysisRequest.method, "POST");
  assert.equal(aiAnalysisRequest.url, "/applications/2/ai-analysis");
  assert.equal(aiAnalysisRequest.bodyLength, 0, "POST body must be empty");
  assert.equal(analysisResponse.analysis_id, 1);
  assert.equal(analysisResponse.application_id, 2);
  assert.equal(analysisResponse.analysis_type, "APPLICATION_ANALYSIS");
  assert.equal(analysisResponse.model, "gemini-3.5-flash-lite");
  assert.equal(typeof analysisResponse.analysis, "string");
  assert.equal(analysisResponse.documents_analyzed, 1);
  assert.equal(analysisResponse.ordinance_results, 5);

  const statusHistory = await getStatusHistory(2, baseUrl);
  assert.equal(statusHistory.application_id, 2);
  assert.equal(statusHistory.history[0].new_status, "DRAFT");

  const statusUpdate = await updateApplicationStatus(
    2,
    {
      new_status: "SUBMITTED",
      changed_by: "STAFF-01",
      reason: "Submitted for review.",
    },
    baseUrl,
  );
  assert.equal(statusUpdate.new_status, "SUBMITTED");

  const processResponse = await processApplication(2, baseUrl);
  assert.equal(processResponse.status, "PROCESSING");

  const assignment = await assignApplicationToCommittee(
    2,
    { committee_type: "DUGC" },
    baseUrl,
  );
  assert.equal(assignment.committee_type, "DUGC");

  const reviews = await getCommitteeReviews(2, baseUrl);
  assert.equal(reviews.reviews[0].decision, "APPROVED");

  const decision = await updateCommitteeDecision(
    3,
    {
      decision: "APPROVED",
      decision_reason: "Requirements met.",
      decided_by: "COMMITTEE-01",
    },
    baseUrl,
  );
  assert.equal(decision.application_status, "APPROVED");

  const auditLogs = await getAuditLogs(2, baseUrl);
  assert.equal(auditLogs.audit_logs[0].action, "APPLICATION_CREATED");

  assert.deepEqual(workflowApiRequests, [
    {
      method: "GET",
      url: "/applications/2",
      body: null,
    },
    {
      method: "PATCH",
      url: "/applications/2",
      body: {
        application_type: "Updated academic request",
        title: "Updated title",
        description: "Updated description",
      },
    },
    {
      method: "GET",
      url: "/applications/2/readiness",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/analysis",
      body: null,
    },
    {
      method: "POST",
      url: "/applications/2/readiness/analyze",
      body: null,
    },
    {
      method: "POST",
      url: "/applications/2/submit",
      body: null,
    },
    {
      method: "GET",
      url: "/official/applications/unassigned?limit=20&offset=0",
      body: null,
    },
    {
      method: "POST",
      url: "/applications/2/claim",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/ordinance-retrieval",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/eligibility",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/eligibility/results",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/deficiencies",
      body: null,
    },
    {
      method: "GET",
      url: "/applications/2/status-history",
      body: null,
    },
    {
      method: "PATCH",
      url: "/applications/2/status",
      body: {
        new_status: "SUBMITTED",
        changed_by: "STAFF-01",
        reason: "Submitted for review.",
      },
    },
    {
      method: "POST",
      url: "/applications/2/process",
      body: null,
    },
    {
      method: "POST",
      url: "/applications/2/committee",
      body: { committee_type: "DUGC" },
    },
    {
      method: "GET",
      url: "/applications/2/committee-reviews",
      body: null,
    },
    {
      method: "PATCH",
      url: "/committee-reviews/3/decision",
      body: {
        decision: "APPROVED",
        decision_reason: "Requirements met.",
        decided_by: "COMMITTEE-01",
      },
    },
    {
      method: "GET",
      url: "/applications/2/audit-logs",
      body: null,
    },
  ]);

  console.log(
    "api contract tests passed: JSON, multipart, application readiness, documents, academic review, M09, and M11-M13 helpers",
  );
} finally {
  server.close();
  await once(server, "close");
}
