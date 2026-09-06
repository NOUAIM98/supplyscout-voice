import type {
  ContextPreview,
  RankingResponse,
  SourcingRequest,
  SourcingRequestInput,
  SupplierQuote,
  WorkflowState,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? "SupplyScout API request failed", response.status);
  }
  return response.json();
}

export const api = {
  createRequest: (payload: SourcingRequestInput) =>
    request<SourcingRequest>("/api/v1/sourcing-requests", { method: "POST", body: JSON.stringify(payload) }),
  getRequest: (id: string) => request<SourcingRequest>(`/api/v1/sourcing-requests/${id}`),
  getWorkflow: (id: string) => request<WorkflowState>(`/api/v1/sourcing-requests/${id}/workflow`),
  getContextPreview: (id: string) => request<ContextPreview>(`/api/v1/sourcing-requests/${id}/context-preview`, { method: "POST" }),
  getQuotePreview: (id: string) => request<WorkflowState>(`/api/v1/sourcing-requests/${id}/quote-preview`, { method: "POST" }),
  approveQuoteCalls: (id: string) => request<SupplierQuote[]>(`/api/v1/sourcing-requests/${id}/approve-quote-calls`, { method: "POST" }),
  getQuotes: (id: string) => request<SupplierQuote[]>(`/api/v1/sourcing-requests/${id}/quotes`),
  getRanking: (id: string) => request<RankingResponse>(`/api/v1/sourcing-requests/${id}/ranking`),
  selectQuote: (id: string, quoteId: string) => request<WorkflowState>(`/api/v1/sourcing-requests/${id}/select-quote`, { method: "POST", body: JSON.stringify({ quote_id: quoteId }) }),
};
