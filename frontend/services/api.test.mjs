import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";

const { request, APIError, askQuestion, createApplication } = await import(
  `file://${process.cwd()}/frontend/services/api.js`
);

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
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            id: 1,
            application_number: "APP-2026-00001",
            status: "DRAFT",
            created_at: "2026-01-01T00:00:00Z",
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
    { applicant_identifier: "S1", application_type: "UG" },
    baseUrl,
  );
  assert.deepEqual(applicationResponse, {
    id: 1,
    application_number: "APP-2026-00001",
    status: "DRAFT",
    created_at: "2026-01-01T00:00:00Z",
  });

  console.log("api contract tests: 6 passed");
} finally {
  server.close();
  await once(server, "close");
}
