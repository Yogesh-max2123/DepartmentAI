import assert from "node:assert/strict";

import { renderDUGCLogin } from "./dugc-login.js";
import { renderOfficialLogin } from "./official-login.js";
import { renderLoginRoleSelector } from "./login-role-selector.js";
import { renderStudentLogin } from "./student-login.js";
import { renderLoginPage } from "../../pages/login/login-page.js";

const previewForms = [
  renderStudentLogin(),
  renderOfficialLogin(),
  renderDUGCLogin(),
];

for (const form of previewForms) {
  assert.match(form, /type="password"/);
  assert.match(form, /name="username"/);
  assert.match(form, /Sign in/);
}

const roleSelector = renderLoginRoleSelector();
assert.match(roleSelector, /server verifies the account role/i);
assert.doesNotMatch(roleSelector, /workspace preview/i);
assert.match(renderLoginPage(), /Do not enter institutional credentials/);
assert.match(renderLoginPage(), /disabled for the institutional profile/i);

console.log("login form tests passed: credential fields are present and role is server-verified");
