/**
 * INTELLI-CREDIT API Service Layer
 * Central typed API client connecting to all FastAPI backend endpoints.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Auth Token ──
let authToken: string | null = null;
export const setAuthToken = (token: string | null) => { authToken = token; };

// ── Base Fetch ──
async function request<T = any>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const headers: Record<string, string> = {
        ...(options.headers as Record<string, string> || {}),
    };

    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }

    // Don't set Content-Type for FormData (browser will set multipart boundary)
    if (!(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API Error ${res.status}`);
    }

    return res.json();
}

function get<T = any>(path: string) {
    return request<T>(path);
}

function post<T = any>(path: string, body?: any) {
    return request<T>(path, {
        method: "POST",
        body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
    });
}

function patch<T = any>(path: string, body?: any) {
    return request<T>(path, {
        method: "PATCH",
        body: JSON.stringify(body),
    });
}

function put<T = any>(path: string, body?: any) {
    return request<T>(path, {
        method: "PUT",
        body: JSON.stringify(body),
    });
}

function del<T = any>(path: string) {
    return request<T>(path, {
        method: "DELETE",
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// PRE-QUALIFICATION (Stage 0)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const preQual = {
    check: (data: any) => post("/api/pre-qual/check", data),
    getSectorWeights: () => get("/api/pre-qual/sector-weights"),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// APPLICATIONS (Core CRUD)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const applications = {
    list: (params?: { stage?: string; page?: number; page_size?: number }) => {
        const query = new URLSearchParams();
        if (params?.stage) query.set("stage", params.stage);
        if (params?.page) query.set("page", String(params.page));
        if (params?.page_size) query.set("page_size", String(params.page_size));
        const qs = query.toString();
        return get(`/api/applications${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => get(`/api/applications/${id}`),
    create: (data: any) => post("/api/applications", data),
    update: (id: string, data: any) => patch(`/api/applications/${id}`, data),
    transitionStage: (id: string, data: any) => patch(`/api/applications/${id}/stage`, data),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DOCUMENTS (Stage 1)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const documents = {
    upload: (formData: FormData) => post("/api/documents/upload", formData),
    list: (applicationId: string) => get(`/api/documents/${applicationId}`),
    getStatus: (documentId: string) => get(`/api/documents/${documentId}/status`),
    getCompleteness: (applicationId: string) => get(`/api/documents/${applicationId}/completeness`),
    verify: (data: any) => patch("/api/documents/verify", data),
    getChecklist: (loanType: string) => get(`/api/documents/checklist/${loanType}`),
    delete: (documentId: string) => del(`/api/documents/${documentId}`),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FIELD VISIT (Stage 3)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const fieldVisit = {
    submit: (data: any) => post("/api/field-visit", data),
    get: (applicationId: string) => get(`/api/field-visit/${applicationId}`),
    update: (visitId: string, data: any) => put(`/api/field-visit/${visitId}`, data),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// ANALYSIS (Stage 4 — 6-Tab Workspace)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const analysis = {
    getFinancial: (appId: string) => get(`/api/analysis/${appId}/financial`),
    getGST: (appId: string) => get(`/api/analysis/${appId}/gst`),
    getBanking: (appId: string) => get(`/api/analysis/${appId}/banking`),
    getResearch: (appId: string) => get(`/api/analysis/${appId}/research`),
    triggerResearch: (appId: string) => post(`/api/analysis/${appId}/research/trigger`),
    getRiskTimeline: (appId: string) => get(`/api/analysis/${appId}/timeline`),
    runWhatIf: (appId: string, data: any) => post(`/api/analysis/${appId}/what-if`, data),
    triggerFullAnalysis: (appId: string) => post(`/api/analysis/${appId}/run-all`),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CAM (Stage 4-5)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const cam = {
    generate: (appId: string) => post(`/api/cam/generate/${appId}`),
    get: (appId: string) => get(`/api/cam/${appId}`),
    download: (appId: string, format: string = "docx") => get(`/api/cam/${appId}/download?format=${format}`),
    updateContent: (camId: string, content: any) => put(`/api/cam/${camId}/content`, content),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// RISK SCORING (Stage 5)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const riskScore = {
    compute: (appId: string, includeShap: boolean = true) =>
        post(`/api/risk-score/compute/${appId}?include_shap=${includeShap}`),
    get: (appId: string) => get(`/api/risk-score/${appId}`),
    getPolicyChecks: (appId: string) => get(`/api/risk-score/${appId}/policy-checks`),
    getRateRecommendation: (appId: string) => get(`/api/risk-score/${appId}/rate-recommendation`),
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// DECISIONS (Stages 5-6)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export const decisions = {
    submit: (appId: string, data: any) => post(`/api/decisions/${appId}`, data),
    get: (appId: string) => get(`/api/decisions/${appId}`),
    getDecisionPack: (appId: string) => get(`/api/decisions/${appId}/decision-pack`),
    generateSanctionLetter: (appId: string, data: any) => post(`/api/decisions/${appId}/sanction-letter`, data),
};
