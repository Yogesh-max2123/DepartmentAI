import assert from "node:assert/strict";

import {
  clearAccessToken,
  runYogeshApplicationAdvisory,
  setAccessToken,
} from "./api.js";

const originalFetch = globalThis.fetch;
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({ url, options });
  return {
    ok: true,
    status: 200,
    headers: {
      get: () => "application/json",
    },
    json: async () => ({ status: "COMPLETED", advisory: true }),
  };
};

try {
  setAccessToken("synthetic-session-token");
  const result = await runYogeshApplicationAdvisory(
    42,
    "http://127.0.0.1:8002",
  );
  assert.deepEqual(result, { status: "COMPLETED", advisory: true });
  assert.equal(
    calls[0].url,
    "http://127.0.0.1:8002/applications/42/yogesh-advisory",
  );
  assert.equal(calls[0].options.method, "POST");
  assert.equal(
    calls[0].options.headers.Authorization,
    "Bearer synthetic-session-token",
  );
  assert.equal(calls[0].options.body, undefined);
} finally {
  clearAccessToken();
  globalThis.fetch = originalFetch;
}
