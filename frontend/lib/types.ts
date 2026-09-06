export type YesNoUnknown = "yes" | "no" | "unknown";

export interface SourcingRequestInput {
  vehicle_make: string;
  vehicle_model: string;
  vehicle_year: number;
  part_name: string;
  requested_reference: string;
  quantity: number;
  max_budget: string;
  currency: string;
  needed_by: string;
}

export interface SourcingRequest extends SourcingRequestInput {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowState {
  sourcing_request_id: string;
  workflow_status: string;
  quote_call_approved: boolean;
  quotes: string[];
  ranking: string[];
  recommended_quote_id: string | null;
  selected_quote_id: string | null;
  knowledge_chunk_ids: string[];
  reservation_approved: boolean;
  reservation_result: ReservationResult | null;
  errors: string[];
}

export type ReservationOutcome = "pending_approval" | "calling" | "confirmed" | "refused" | "unavailable" | "unclear" | "no_answer" | "failed";

export interface ReservationResult {
  outcome: ReservationOutcome;
  supplier_reference: string | null;
}

export interface ActivityEvent {
  id: string;
  event_type: string;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  title: string;
  source_type: string;
  source_ref: string;
  snippet: string;
}

export interface ContextPreview {
  mode: string;
  chunks: KnowledgeChunk[];
  task_context: string;
  call_started: boolean;
}

export interface SupplierQuote {
  id: string;
  supplier_id: string;
  supplier_name: string;
  exact_reference_confirmed: YesNoUnknown;
  offered_reference: string | null;
  in_stock: YesNoUnknown;
  manufacturer_or_brand: string | null;
  condition: string;
  quantity_available: number | null;
  unit_price: string | null;
  currency: string | null;
  tax_included: YesNoUnknown;
  warranty_months: number | null;
  pickup_available_today: YesNoUnknown;
  delivery_eta: string | null;
  quote_valid_until: string | null;
  supplier_notes: string | null;
}

export interface RankingEntry {
  rank: number;
  quote_id: string;
  supplier_id: string;
  supplier_name: string;
  reasons: string[];
}

export interface RankingResponse {
  sourcing_request_id: string;
  recommended_supplier_id: string;
  recommended_supplier_name: string;
  explanation: string;
  ranking: RankingEntry[];
}
