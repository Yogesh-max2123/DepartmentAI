const API_BASE_URL = "http://127.0.0.1:8000";

async function request(endpoint, options = {}) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    });

    let data;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {
        throw new Error(
            data?.detail || "An error occurred while communicating with the server."
        );
    }

    return data;
}

export async function askQuestion(question, conversationHistory = []) {
    return request("/ask", {
        method: "POST",
        body: JSON.stringify({
            question,
            conversation_history: conversationHistory
        })
    });
}

export async function getApplication(applicationId) {
    return request(`/applications/${applicationId}`);
}

export async function getApplicationDocuments(applicationId) {
    return request(`/applications/${applicationId}/documents`);
}

export async function getEligibility(applicationId) {
    return request(`/applications/${applicationId}/eligibility`);
}

export async function getDeficiencies(applicationId) {
    return request(`/applications/${applicationId}/deficiencies`);
}

export async function getStatusHistory(applicationId) {
    return request(`/applications/${applicationId}/status-history`);
}

export async function getAuditLogs(applicationId) {
    return request(`/applications/${applicationId}/audit-logs`);
}