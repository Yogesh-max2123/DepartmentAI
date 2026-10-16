import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";

const {
  request,
  APIError,
  askQuestion,
  createApplication,
  extractApplicationDocument,
  getApplicationDocuments,
  classifyApplicationDocument,
  uploadApplicationDocument,
  validateApplicationDocument,
} = await import(`file://${process.cwd()}/frontend/services/api.js`);

let applicationRequest;
let documentUploadRequest;
const documentApiRequests = [];

const startServer = () =>
  new Promise((resolve) => {
    const server = createServer((req, res) => {
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

      if (req.url === "/ask" && req.method === "POST") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            answer: "Test answer.",
            sources: [],
          }),
        );
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
  );
  assert.deepEqual(askResponse, {
    answer: "Test answer.",
    sources: [],
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

  console.log(
    "api contract tests passed: JSON, multipart, and document helpers",
  );
} finally {
  server.close();
  await once(server, "close");
}
