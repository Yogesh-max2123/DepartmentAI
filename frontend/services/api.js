const API_BASE_URL = "http://127.0.0.1:8000";

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

  if (
    requestOptions.body !== undefined &&
    !(requestOptions.body instanceof FormData)
  ) {
    headers["Content-Type"] = "application/json";
  }

  requestOptions.headers = headers;

  let response;

  try {
    response = await fetch(`${baseUrl}${endpoint}`, requestOptions);
  } catch {
    throw new APIError("Unable to connect to the backend.", 0, null);
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
    throw new APIError(message, response.status, data);
  }

  if (hasJsonBody && data === null) {
    return undefined;
  }

  return data;
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
