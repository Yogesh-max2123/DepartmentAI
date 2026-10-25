import assert from "node:assert/strict";

import {
  renderRoleDashboard,
  renderRoleWorkspacePage,
} from "./role-workspaces.js";
import { renderSidebar } from "../components/layout/sidebar.js";

for (const role of ["OFFICIAL", "DUGC"]) {
  const dashboard = renderRoleDashboard(role, {
    identifier: '<script>alert("x")</script>',
  });
  assert.match(dashboard, /Workspace/);
  assert.match(dashboard, /server-verified credentials and record assignments/i);
  assert.doesNotMatch(dashboard, /<script>alert/);
  assert.match(dashboard, /data-page="applications"/);

  for (const page of [
    "applications",
    "application-processing",
    "committee",
    "decision-history",
  ]) {
    const markup = renderRoleWorkspacePage(role, page);
    assert.match(markup, /data-role-application-lookup/);
    assert.doesNotMatch(markup, /Retrieved ordinance context/i);
    if (page === "applications") {
      assert.match(markup, /id="role-application-list"/);
    }
    assert.doesNotMatch(markup, /role selection is not authentication/i);
  }
  const lookupTitle =
    role === "OFFICIAL" ? "Application lookup" : "Assigned application lookup";
  assert.match(renderRoleWorkspacePage(role, "applications"), /role-application-list/);
  if (role === "OFFICIAL") {
    const applicationsPage = renderRoleWorkspacePage(role, "applications");
    assert.match(applicationsPage, /Unassigned submissions/);
    assert.match(applicationsPage, /first Official to claim/i);
    assert.match(applicationsPage, /official-unassigned-list/);
  }

  const auditPage = renderRoleWorkspacePage(role, "audit");
  assert.match(auditPage, /Audit view unavailable/);
  assert.match(auditPage, /visibility policy/i);
  assert.match(renderRoleWorkspacePage(role, "settings"), /data-action="logout"/);

  const sidebar = renderSidebar("dashboard", { role });
  const expectedPages =
    role === "OFFICIAL"
      ? ["dashboard", "assistant", "applications", "application-processing", "committee", "audit", "settings"]
      : ["dashboard", "assistant", "applications", "committee", "decision-history", "audit", "settings"];
  for (const page of expectedPages) {
    assert.match(sidebar, new RegExp(`data-page="${page}"`));
  }
}

console.log("role workspace tests passed: role queues and authenticated-record policies render safely");
