import assert from "node:assert/strict";

let role = "STUDENT";
const calls = [];
const stored = new Map();
globalThis.sessionStorage = {
  getItem: (key) => stored.get(key) ?? null,
  setItem: (key, value) => stored.set(key, String(value)),
  removeItem: (key) => stored.delete(key),
};
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, options });
  if (String(url).endsWith("/auth/login")) {
    return new Response(
      JSON.stringify({
        access_token: "synthetic-test-token",
        token_type: "bearer",
        expires_in: 1800,
        user: {
          username: "synthetic.student",
          role,
          subject_identifier: "SYNTHETIC-STUDENT",
          programme_identity_status:
            role === "STUDENT" ? "NOT_CONFIGURED" : null,
          verified_programme: null,
        },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }
  if (String(url).endsWith("/auth/me")) {
    return new Response(
      JSON.stringify({
        username: "synthetic.student",
        role,
        subject_identifier: "SYNTHETIC-STUDENT",
        programme_identity_status:
          role === "STUDENT" ? "NOT_CONFIGURED" : null,
        verified_programme: null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }
  return new Response(null, { status: 204 });
};

const { loginUser, getCurrentUser, logoutUser } = await import(
  `file://${process.cwd()}/frontend/services/auth.js`
);
const formData = new FormData();
formData.set("username", "synthetic.student");
formData.set("password", "synthetic-password");

const user = await loginUser("STUDENT", formData);
assert.equal(user.role, "STUDENT");
assert.equal(getCurrentUser().identifier, "SYNTHETIC-STUDENT");
assert.equal(getCurrentUser().programmeIdentityStatus, "NOT_CONFIGURED");
assert.equal(getCurrentUser().verifiedProgramme, null);
assert.equal(stored.get("departmentai.access-token"), "synthetic-test-token");

const { request, clearAccessToken } = await import(
  `file://${process.cwd()}/frontend/services/api.js?v=session-persistence`
);
await request("/protected-test", {}, "http://127.0.0.1:8000");
assert.equal(
  calls.at(-1).options.headers.Authorization,
  "Bearer synthetic-test-token",
);

const { restoreSession } = await import(
  `file://${process.cwd()}/frontend/services/auth.js?reload-simulation`
);
const restored = await restoreSession();
assert.equal(restored.username, "synthetic.student");
assert.equal(restored.programmeIdentityStatus, "NOT_CONFIGURED");
assert.equal(calls.at(-1).url, "http://127.0.0.1:8000/auth/me");

await logoutUser();
assert.equal(getCurrentUser(), null);
assert.equal(calls.at(-1).url, "http://127.0.0.1:8000/auth/logout");
assert.equal(stored.has("departmentai.access-token"), false);
clearAccessToken();
const callCountAfterLogout = calls.length;
const { restoreSession: restoreWithoutToken } = await import(
  `file://${process.cwd()}/frontend/services/auth.js?no-token-simulation`
);
assert.equal(await restoreWithoutToken(), null);
assert.equal(calls.length, callCountAfterLogout);

role = "OFFICIAL";
await assert.rejects(
  () => loginUser("STUDENT", formData),
  /not assigned to the selected workspace/,
);
assert.equal(calls.at(-1).url, "http://127.0.0.1:8000/auth/logout");

console.log("auth service tests passed: server role, reload restoration, logout revocation");
