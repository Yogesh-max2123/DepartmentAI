import assert from "node:assert/strict";

import { renderStudentDashboard } from "./student-dashboard.js";

const unverified = renderStudentDashboard({
  role: "STUDENT",
  programmeIdentityStatus: "NOT_CONFIGURED",
  verifiedProgramme: "PHD",
});
assert.match(unverified, /Programme identity is not verified/);
assert.match(unverified, /no approved student-profile provisioning source/i);
assert.doesNotMatch(unverified, /Verified programme: PHD/);

const verified = renderStudentDashboard({
  role: "STUDENT",
  programmeIdentityStatus: "VERIFIED",
  verifiedProgramme: "M.Tech",
});
assert.match(verified, /Verified programme: M\.Tech/);

console.log("student dashboard tests passed: verified and unverified programme states render safely");
