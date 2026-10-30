const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const ACCESS_TOKEN_STORAGE_KEY = "departmentai.access-token";
const ACCESS_TOKEN_STORAGE_KEYS = [
  ACCESS_TOKEN_STORAGE_KEY,
  "departmentai.access-token.session",
];

function readStoredAccessToken() {
  const storageTargets = [globalThis.localStorage, globalThis.sessionStorage];

  for (const storage of storageTargets) {
    if (!storage) {
      continue;
    }

    for (const key of ACCESS_TOKEN_STORAGE_KEYS) {
      try {
        const token = storage.getItem(key);
        if (typeof token === "string" && token.trim()) {
          return token;
        }
      } catch {
        // Ignore storage access failures so the app can continue safely.
      }
    }
  }

  return null;
}

function writeStoredAccessToken(token) {
  const storageTargets = [globalThis.localStorage, globalThis.sessionStorage];

  for (const storage of storageTargets) {
    if (!storage) {
      continue;
    }

    for (const key of ACCESS_TOKEN_STORAGE_KEYS) {
      try {
        if (token) {
          storage.setItem(key, token);
        } else {
          storage.removeItem(key);
        }
      } catch {
        // Ignore storage write failures so the app can continue safely.
      }
    }
  }
}

let accessToken = readStoredAccessToken();

export function setAccessToken(token) {
  accessToken = typeof token === "string" && token ? token : null;
  writeStoredAccessToken(accessToken);
}

export function clearAccessToken() {
  accessToken = null;
  writeStoredAccessToken(null);
}

export function hasAccessToken() {
  return typeof accessToken === "string" && accessToken.length > 0;
}

function resolveApiBaseUrl() {
  const configuredUrl = globalThis.DEPARTMENTAI_API_BASE_URL;

  if (configuredUrl == null) {
    return DEFAULT_API_BASE_URL;
  }

  if (typeof configuredUrl !== "string") {
    throw new Error(
      "DEPARTMENTAI_API_BASE_URL must be an absolute HTTP(S) URL.",
    );
  }

  const trimmedUrl = configuredUrl.trim();
  if (!trimmedUrl) {
    return DEFAULT_API_BASE_URL;
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(trimmedUrl);
  } catch {
    throw new Error(
      "DEPARTMENTAI_API_BASE_URL must be an absolute HTTP(S) URL.",
    );
  }

  if (
    !["http:", "https:"].includes(parsedUrl.protocol) ||
    parsedUrl.username ||
    parsedUrl.password ||
    parsedUrl.search ||
    parsedUrl.hash
  ) {
    throw new Error(
      "DEPARTMENTAI_API_BASE_URL must be an absolute HTTP(S) URL without credentials, query, or fragment.",
    );
  }

  if (
    globalThis.location?.protocol === "https:" &&
    parsedUrl.protocol !== "https:"
  ) {
    throw new Error(
      "DEPARTMENTAI_API_BASE_URL must use HTTPS when the frontend uses HTTPS.",
    );
  }

  return parsedUrl.href.replace(/\/+$/, "");
}

const API_BASE_URL = resolveApiBaseUrl();

export class APIError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.details = details;
  }
}

export async function request(endpoint, options = {}, baseUrl = API_BASE_URL) {
  const requestOptions = { ...options };
  const responseType = requestOptions.responseType;
  delete requestOptions.responseType;
  const headers = {
    ...(requestOptions.headers || {}),
  };

  if (accessToken) {
    headers.Authorization = ["Bearer", accessToken].join(" ");
  }

  if (
    requestOptions.body !== undefined &&
    !(requestOptions.body instanceof FormData)
  ) {
    headers["Content-Type"] = "application/json";
  }

  requestOptions.headers = headers;

  let response;

  try {
    requestOptions.signal ??= AbortSignal.timeout(15000);
    response = await fetch(`${baseUrl}${endpoint}`, requestOptions);
  } catch (error) {
    const message =
      error?.name === "TimeoutError" || error?.name === "AbortError"
        ? "The backend request timed out."
        : "Unable to connect to the backend.";
    throw new APIError(message, 0, null);
  }

  const contentType = response.headers.get("content-type") || "";
  const hasJsonBody = contentType.includes("application/json");
  let data = null;

  if (response.status !== 204) {
    try {
      if (responseType === "blob" && response.ok) {
        data = await response.blob();
      } else {
        data = hasJsonBody ? await response.json() : await response.text();
      }
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      (typeof detail === "string" ? detail : detail?.message) ||
      (typeof data === "string" ? data : "The backend request failed.");
    if (response.status === 401 && accessToken) {
      clearAccessToken();
      if (typeof globalThis.dispatchEvent === "function" && globalThis.CustomEvent) {
        globalThis.dispatchEvent(
          new CustomEvent("departmentai:session-expired"),
        );
      }
    }
    throw new APIError(message, response.status, data);
  }

  if (hasJsonBody && data === null) {
    return undefined;
  }

  return data;
}

export async function login(username, password, baseUrl = API_BASE_URL) {
  return request(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ username, password }),
    },
    baseUrl,
  );
}

export async function logout(baseUrl = API_BASE_URL) {
  return request("/auth/logout", { method: "POST" }, baseUrl);
}

export async function getAuthenticatedUser(baseUrl = API_BASE_URL) {
  return request("/auth/me", {}, baseUrl);
}

export async function getModule2Capabilities(baseUrl = API_BASE_URL) {
  return request("/module2/capabilities", {}, baseUrl);
}

export async function getModule2Faculty(
  { query, limit = 50, offset = 0 } = {},
  baseUrl = API_BASE_URL,
) {
  const parameters = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (typeof query === "string" && query.trim()) {
    parameters.set("query", query.trim());
  }
  return request(`/module2/faculty?${parameters}`, {}, baseUrl);
}

export async function getModule2FacultyDetail(facultyId, baseUrl = API_BASE_URL) {
  return request(`/module2/faculty/${encodeURIComponent(facultyId)}`, {}, baseUrl);
}

const MODULE2_RESEARCH_TYPES = new Set([
  "publications",
  "projects",
  "achievements",
]);

export async function getModule2ResearchRecords(
  recordType,
  { query, year_from, year_to, limit = 50, offset = 0 } = {},
  baseUrl = API_BASE_URL,
) {
  if (!MODULE2_RESEARCH_TYPES.has(recordType)) {
    throw new Error("Unsupported Module II research record type.");
  }
  const parameters = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (typeof query === "string" && query.trim()) {
    parameters.set("query", query.trim());
  }
  if (year_from != null) {
    parameters.set("year_from", String(year_from));
  }
  if (year_to != null) {
    parameters.set("year_to", String(year_to));
  }
  return request(
    `/module2/research/records/${recordType}?${parameters}`,
    {},
    baseUrl,
  );
}

export async function getModule2ResearchStatistics(baseUrl = API_BASE_URL) {
  return request("/module2/research/statistics", {}, baseUrl);
}

export async function getModule2DataQuality(
  { category, limit = 50, offset = 0 } = {},
  baseUrl = API_BASE_URL,
) {
  const parameters = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (typeof category === "string" && category.trim()) {
    parameters.set("category", category.trim());
  }
  return request(`/module2/data-quality/issues?${parameters}`, {}, baseUrl);
}

export async function getModule2ExportDatasets(baseUrl = API_BASE_URL) {
  return request("/module2/export/datasets", {}, baseUrl);
}

export async function downloadModule2Export(
  dataset,
  format,
  limit = 1000,
  baseUrl = API_BASE_URL,
) {
  const parameters = new URLSearchParams({
    format,
    limit: String(limit),
  });
  return request(
    `/module2/export/${encodeURIComponent(dataset)}/download?${parameters}`,
    { responseType: "blob" },
    baseUrl,
  );
}

export async function getModule2ReportTemplates(baseUrl = API_BASE_URL) {
  return request("/module2/reports/templates", {}, baseUrl);
}

export async function previewModule2Report(
  { template_id, year_from, year_to } = {},
  baseUrl = API_BASE_URL,
) {
  return request(
    "/module2/reports/preview",
    {
      method: "POST",
      body: JSON.stringify({ template_id, year_from, year_to }),
    },
    baseUrl,
  );
}

export async function generateModule2Report(
  { template_id, year_from, year_to, format } = {},
  baseUrl = API_BASE_URL,
) {
  return request(
    "/module2/reports/generate",
    {
      method: "POST",
      body: JSON.stringify({ template_id, year_from, year_to, format }),
      responseType: "blob",
    },
    baseUrl,
  );
}

export async function listApplications(
  { limit = 20, offset = 0 } = {},
  baseUrl = API_BASE_URL,
) {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request(`/applications?${query}`, {}, baseUrl);
}

export async function downloadApplicationDocument(
  applicationId,
  documentId,
  baseUrl = API_BASE_URL,
) {
  const headers = accessToken
    ? { Authorization: ["Bearer", accessToken].join(" ") }
    : {};
  let response;
  try {
    response = await fetch(
      `${baseUrl}/applications/${applicationId}/documents/${documentId}/download`,
      {
        headers,
        signal: AbortSignal.timeout(15000),
      },
    );
  } catch (error) {
    const message =
      error?.name === "TimeoutError" || error?.name === "AbortError"
        ? "The backend request timed out."
        : "Unable to connect to the backend.";
    throw new APIError(message, 0, null);
  }
  if (!response.ok) {
    let details = null;
    try {
      details = await response.json();
    } catch {
      details = null;
    }
    if (response.status === 401 && accessToken) {
      clearAccessToken();
      if (typeof globalThis.dispatchEvent === "function" && globalThis.CustomEvent) {
        globalThis.dispatchEvent(
          new CustomEvent("departmentai:session-expired"),
        );
      }
    }
    throw new APIError(
      details?.detail || "Unable to download this document.",
      response.status,
      details,
    );
  }
  return {
    blob: await response.blob(),
    fileName:
      response.headers
        .get("content-disposition")
        ?.match(/filename="?([^";]+)"?/i)?.[1] || "document",
  };
}

export async function askQuestion(
  question,
  conversationHistory = [],
  baseUrl = API_BASE_URL,
  programme = "UG",
) {
  return request(
    "/ask",
    {
      method: "POST",
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory,
        programme,
      }),
    },
    baseUrl,
  );
}

export async function getGovernanceConfiguration() {
  return request("/governance/configuration");
}

export async function getApplicationGovernanceMeetings(applicationId) {
  return request(`/governance/applications/${applicationId}/meetings`);
}

export async function approveApplicationGovernanceMeeting(
  applicationId,
  meetingId,
) {
  return request(
    `/governance/applications/${applicationId}/meetings/${meetingId}/approve`,
    { method: "POST" },
  );
}

export async function respondToApplicationGovernanceMeeting(
  applicationId,
  meetingId,
  response,
) {
  return request(
    `/governance/applications/${applicationId}/meetings/${meetingId}/response`,
    {
      method: "POST",
      body: JSON.stringify({ response }),
    },
  );
}

export async function getGovernanceIntegrations() {
  return request("/governance/integrations");
}

export async function listGovernanceMeetings(committeeType = "") {
  const query = committeeType
    ? `?committee_type=${encodeURIComponent(committeeType)}`
    : "";
  return request(`/governance/meetings${query}`);
}

export async function createGovernanceMeeting(meeting, idempotencyKey) {
  return request("/governance/meetings", {
    method: "POST",
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
    body: JSON.stringify(meeting),
  });
}

export async function submitGovernanceAvailability(availability) {
  return request("/governance/availability", {
    method: "POST",
    body: JSON.stringify(availability),
  });
}

export async function getGovernanceCandidateSlots({
  committeeType,
  rangeStart,
  rangeEnd,
  durationMinutes,
  excludeMeetingId = null,
}) {
  const parameters = {
    committee_type: committeeType,
    range_start: rangeStart,
    range_end: rangeEnd,
    duration_minutes: String(durationMinutes),
  };
  if (Number.isSafeInteger(excludeMeetingId) && excludeMeetingId > 0) {
    parameters.exclude_meeting_id = String(excludeMeetingId);
  }
  const query = new URLSearchParams(parameters);
  return request(`/governance/meetings/slots?${query}`);
}

export async function getGovernanceMeeting(meetingId) {
  return request(`/governance/meetings/${meetingId}`);
}

export async function getGovernanceMeetingNotice(meetingId) {
  return request(`/governance/meetings/${meetingId}/notice`);
}

export async function updateGovernanceMeetingAgenda(meetingId, agenda) {
  return request(`/governance/meetings/${meetingId}/agenda`, {
    method: "PATCH",
    body: JSON.stringify({ agenda }),
  });
}

export async function selectGovernanceMeetingSlot(meetingId, start) {
  return request(`/governance/meetings/${meetingId}/slot`, {
    method: "PATCH",
    body: JSON.stringify({ proposed_slot_start: start }),
  });
}

export async function approveGovernanceMeeting(meetingId) {
  return request(`/governance/meetings/${meetingId}/approve`, {
    method: "POST",
  });
}

export async function respondToGovernanceMeeting(meetingId, response) {
  return request(`/governance/meetings/${meetingId}/response`, {
    method: "POST",
    body: JSON.stringify({ response }),
  });
}

export async function addGovernanceMeetingRecord(meetingId, record) {
  return request(`/governance/meetings/${meetingId}/records`, {
    method: "POST",
    body: JSON.stringify(record),
  });
}

export async function getGovernanceMinutes(meetingId) {
  return request(`/governance/meetings/${meetingId}/minutes`);
}

export async function createManualGovernanceMinutes(meetingId) {
  return request(`/governance/meetings/${meetingId}/minutes`, {
    method: "POST",
  });
}

export async function generateGovernanceMinutes(meetingId) {
  return request(`/governance/meetings/${meetingId}/minutes/generate`, {
    method: "POST",
  });
}

export async function saveGovernanceMinutes(meetingId, versionId, content) {
  return request(`/governance/meetings/${meetingId}/minutes/${versionId}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export async function submitGovernanceMinutes(versionId) {
  return request(`/governance/minutes/${versionId}/submit`, {
    method: "POST",
  });
}

export async function commentOnGovernanceMinutes(versionId, comment) {
  return request(`/governance/minutes/${versionId}/comments`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export async function approveGovernanceMinutes(versionId) {
  return request(`/governance/minutes/${versionId}/approve`, {
    method: "POST",
  });
}

export async function createApplication(data, baseUrl = API_BASE_URL) {
  return request(
    "/applications",
    {
      method: "POST",
      body: JSON.stringify(data),
    },
    baseUrl,
  );
}

export async function updateApplication(
  applicationId,
  data,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
    baseUrl,
  );
}

export async function submitApplication(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/submit`,
    { method: "POST" },
    baseUrl,
  );
}

export async function getApplicationReadiness(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(`/applications/${applicationId}/readiness`, {}, baseUrl);
}

export async function getApplicationAnalysis(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(`/applications/${applicationId}/analysis`, {}, baseUrl);
}

export async function analyzeApplicationReadiness(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/readiness/analyze`,
    { method: "POST" },
    baseUrl,
  );
}

export async function runYogeshApplicationAdvisory(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/yogesh-advisory`,
    { method: "POST" },
    baseUrl,
  );
}

export async function getUnassignedOfficialApplications(
  { limit = 20, offset = 0 } = {},
  baseUrl = API_BASE_URL,
) {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return request(`/official/applications/unassigned?${query}`, {}, baseUrl);
}

export async function claimOfficialApplication(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/claim`,
    { method: "POST" },
    baseUrl,
  );
}

export async function getApplication(applicationId, baseUrl = API_BASE_URL) {
  return request(`/applications/${applicationId}`, {}, baseUrl);
}

export async function uploadApplicationDocument(
  applicationId,
  formData,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/documents`,
    {
      method: "POST",
      body: formData,
    },
    baseUrl,
  );
}

export async function getApplicationDocuments(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(`/applications/${applicationId}/documents`, {}, baseUrl);
}

export async function validateApplicationDocument(
  applicationId,
  documentId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/documents/${documentId}/validate`,
    {},
    baseUrl,
  );
}

export async function extractApplicationDocument(
  applicationId,
  documentId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/documents/${documentId}/extract`,
    { method: "POST" },
    baseUrl,
  );
}

export async function classifyApplicationDocument(
  applicationId,
  documentId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/documents/${documentId}/classify`,
    { method: "POST" },
    baseUrl,
  );
}

export async function getOrdinanceRetrieval(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/ordinance-retrieval`,
    {},
    baseUrl,
  );
}

export async function getEligibility(applicationId, baseUrl = API_BASE_URL) {
  return request(`/applications/${applicationId}/eligibility`, {}, baseUrl);
}

export async function getEligibilityResults(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/eligibility/results`,
    {},
    baseUrl,
  );
}

export async function getDeficiencies(applicationId, baseUrl = API_BASE_URL) {
  return request(`/applications/${applicationId}/deficiencies`, {}, baseUrl);
}

export async function updateApplicationStatus(
  applicationId,
  data,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
    baseUrl,
  );
}

export async function getStatusHistory(applicationId, baseUrl = API_BASE_URL) {
  return request(`/applications/${applicationId}/status-history`, {}, baseUrl);
}

export async function assignApplicationToCommittee(
  applicationId,
  data,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/committee`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
    baseUrl,
  );
}

export async function getCommitteeReviews(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/committee-reviews`,
    {},
    baseUrl,
  );
}

export async function updateCommitteeDecision(
  reviewId,
  data,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/committee-reviews/${reviewId}/decision`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
    baseUrl,
  );
}

export async function getAuditLogs(applicationId, baseUrl = API_BASE_URL) {
  return request(`/applications/${applicationId}/audit-logs`, {}, baseUrl);
}

export async function generateApplicationAnalysis(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/ai-analysis`,
    { method: "POST" },
    baseUrl,
  );
}

export async function processApplication(
  applicationId,
  baseUrl = API_BASE_URL,
) {
  return request(
    `/applications/${applicationId}/process`,
    { method: "POST" },
    baseUrl,
  );
}

export { API_BASE_URL };
