const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const ACCESS_TOKEN_STORAGE_KEY = "departmentai.access-token";
let accessToken = globalThis.sessionStorage?.getItem(ACCESS_TOKEN_STORAGE_KEY) ?? null;

export function setAccessToken(token) {
  accessToken = typeof token === "string" && token ? token : null;
  if (accessToken) {
    globalThis.sessionStorage?.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
  } else {
    globalThis.sessionStorage?.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }
}

export function clearAccessToken() {
  accessToken = null;
  globalThis.sessionStorage?.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function hasAccessToken() {
  return accessToken !== null;
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
      data = hasJsonBody ? await response.json() : await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const message =
      data?.detail ||
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
) {
  return request(
    "/ask",
    {
      method: "POST",
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory,
      }),
    },
    baseUrl,
  );
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
