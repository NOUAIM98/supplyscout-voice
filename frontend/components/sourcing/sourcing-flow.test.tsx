import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NewRequestForm } from "./new-request-form";
import { WorkflowStepper } from "@/components/workflow/workflow-stepper";
import { QuoteComparison } from "@/components/quotes/quote-comparison";
import { RankingPanel } from "@/components/quotes/ranking-panel";
import { ApprovalPanel } from "@/components/workflow/approval-panel";
import { ReservationPanel, ReservationStage } from "@/components/workflow/reservation-panel";
import { AgentActivity } from "@/components/workflow/agent-activity";
import { ContextPanel } from "@/components/sourcing/context-panel";
import { CallProgress, RuntimeBadge, allCallsTerminal, hasActiveCalls } from "@/components/workflow/call-progress";
import { queryClientDefaults } from "@/providers/query-provider";
import type { RankingResponse, SourcingRequest, SupplierQuote } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const quote = (overrides: Partial<SupplierQuote> = {}): SupplierQuote => ({
  id: "q1", supplier_id: "s1", supplier_name: "Supplier A", exact_reference_confirmed: "yes",
  offered_reference: "TEST-ALT-CLIO-2019-001", in_stock: "yes", manufacturer_or_brand: null,
  condition: "new", quantity_available: 1, unit_price: "145.00", currency: "EUR",
  tax_included: "unknown", warranty_months: 12, pickup_available_today: "yes",
  delivery_eta: null, quote_valid_until: null, supplier_notes: null, ...overrides,
});

describe("Phase G1 live progress", () => {
  const active = [{ id: "a1", call_type: "quote" as const, status: "calling", provider_call_id: "fictional-call-1" }];

  it("keeps fake mode visibly labeled as demo", () => {
    render(<RuntimeBadge runtime={{ call_provider_mode: "fake", live_calls_enabled: false }} />);
    expect(screen.getByText("Demo supplier responses")).toBeVisible();
  });

  it("labels live mode only from backend runtime metadata", () => {
    render(<RuntimeBadge runtime={{ call_provider_mode: "calle", live_calls_enabled: true }} />);
    expect(screen.getByText("Live CALL-E")).toBeVisible();
  });

  it("shows active supplier progress without claiming completion", () => {
    render(<CallProgress attempts={active} />);
    expect(screen.getByText("Waiting for supplier responses")).toBeVisible();
    expect(screen.getByText("0 of 1 completed")).toBeVisible();
  });

  it("stops polling eligibility when every call is terminal", () => {
    expect(hasActiveCalls(active)).toBe(true);
    expect(hasActiveCalls([{ ...active[0], status: "failed" }])).toBe(false);
    expect(allCallsTerminal([{ ...active[0], status: "failed" }])).toBe(true);
  });

  it("shows live reservation waiting state", () => {
    render(<CallProgress attempts={[{ ...active[0], call_type: "reservation" }]} />);
    expect(screen.getByText("Contacting selected supplier…")).toBeVisible();
    expect(screen.queryByText("Reservation confirmed")).not.toBeInTheDocument();
  });

  it("configures mutations with no automatic retry", () => {
    expect(queryClientDefaults.mutations.retry).toBe(false);
  });
});

describe("Phase E3 semantic context", () => {
  it("renders safe context provenance cards", () => {
    render(<ContextPanel context={{ mode: "postgres", call_started: false, task_context: "safe", chunks: [{ id: "k1", title: "Compatibility confirmation policy", source_type: "vehicle_compatibility", source_ref: "demo:compatibility", snippet: "Confirm the exact reference with the supplier." }] }} />);
    expect(screen.getByText("Compatibility confirmation policy")).toBeVisible();
    expect(screen.getByText("vehicle compatibility")).toBeVisible();
    expect(screen.getByText("Confirm the exact reference with the supplier.")).toBeVisible();
    expect(screen.getByText("demo:compatibility")).toBeVisible();
  });
});

const request: SourcingRequest = {
  id: "r1", vehicle_make: "Renault", vehicle_model: "Clio", vehicle_year: 2019,
  part_name: "Alternator", requested_reference: "TEST-ALT-CLIO-2019-001", quantity: 1,
  max_budget: "180.00", currency: "EUR", needed_by: "2026-09-06", status: "awaiting_reservation_approval",
  created_at: "2026-09-06T10:00:00Z", updated_at: "2026-09-06T10:00:00Z",
};

function withQuery(ui: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>{ui}</QueryClientProvider>);
}

describe("Phase F1 sourcing flow", () => {
  it("renders the demo-friendly sourcing form", () => {
    withQuery(<NewRequestForm />);
    expect(screen.getByLabelText("Make")).toHaveValue("Renault");
    expect(screen.getByLabelText("Requested reference")).toHaveValue("TEST-ALT-CLIO-2019-001");
    expect(screen.getByRole("button", { name: /create request/i })).toBeEnabled();
  });

  it("renders the current workflow without marking supplier calls complete", () => {
    render(<WorkflowStepper status="awaiting_quote_approval" />);
    expect(screen.getByText("Call preview").closest("li")).toHaveClass("border-primary/50");
    expect(screen.getByText("Supplier calls").closest("li")).not.toHaveClass("border-primary/50");
  });

  it("requires an explicit approval click", async () => {
    const onApprove = vi.fn();
    render(<ApprovalPanel ready pending={false} onApprove={onApprove} />);
    expect(onApprove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /approve supplier quote calls/i }));
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it("keeps unknown facts visible and selection manual", async () => {
    const onSelect = vi.fn();
    render(<QuoteComparison quotes={[quote({ in_stock: "unknown", warranty_months: null, delivery_eta: null })]} selectedQuoteId={null} onSelect={onSelect} />);
    expect(screen.getAllByText("Unknown").length).toBeGreaterThanOrEqual(3);
    expect(onSelect).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Select this supplier" }));
    expect(onSelect).toHaveBeenCalledWith("q1");
  });

  it("renders backend ranking without automatically selecting its recommendation", () => {
    const ranking: RankingResponse = { sourcing_request_id: "r1", recommended_supplier_id: "s1", recommended_supplier_name: "Supplier A", explanation: "Backend explanation", ranking: [
      { rank: 1, quote_id: "q1", supplier_id: "s1", supplier_name: "Supplier A", reasons: ["Exact reference confirmed."] },
      { rank: 2, quote_id: "q2", supplier_id: "s2", supplier_name: "Supplier B", reasons: ["Higher price."] },
    ] };
    render(<RankingPanel ranking={ranking} selectedQuoteId={null} />);
    expect(screen.getByText("Backend explanation")).toBeVisible();
    expect(screen.getByText("Recommended ≠ Selected")).toBeVisible();
    expect(screen.queryByText("Selected", { exact: true })).not.toBeInTheDocument();
  });
});

describe("Phase F2 reservation flow", () => {
  const props = { request, quote: quote(), reviewed: true, outcome: "pending_approval" as const, previewing: false, approving: false, onReview: vi.fn(), onApprove: vi.fn() };

  it("does not show reservation controls before supplier selection", () => {
    render(<ReservationStage {...props} quote={null} />);
    expect(screen.queryByRole("button", { name: /review reservation/i })).not.toBeInTheDocument();
  });

  it("enables reservation review after supplier selection", async () => {
    const onReview = vi.fn();
    render(<ReservationPanel {...props} reviewed={false} onReview={onReview} />);
    await userEvent.click(screen.getByRole("button", { name: /review reservation/i }));
    expect(onReview).toHaveBeenCalledOnce();
  });

  it("preview does not execute reservation", () => {
    const onApprove = vi.fn();
    render(<ReservationPanel {...props} onApprove={onApprove} />);
    expect(screen.getByText(/has not contacted the supplier for reservation yet/i)).toBeVisible();
    expect(onApprove).not.toHaveBeenCalled();
  });

  it("requires explicit second approval", () => {
    const onApprove = vi.fn();
    render(<ReservationPanel {...props} onApprove={onApprove} />);
    expect(onApprove).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /approve reservation call/i })).toBeVisible();
  });

  it("allows the confirmation dialog to cancel", async () => {
    const onApprove = vi.fn();
    render(<ReservationPanel {...props} onApprove={onApprove} />);
    await userEvent.click(screen.getByRole("button", { name: /approve reservation call/i }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onApprove).not.toHaveBeenCalled();
  });

  it("executes approval only after confirmation", async () => {
    const onApprove = vi.fn();
    render(<ReservationPanel {...props} onApprove={onApprove} />);
    await userEvent.click(screen.getByRole("button", { name: /approve reservation call/i }));
    expect(onApprove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("dialog").getElementsByTagName("button")[1]);
    expect(onApprove).toHaveBeenCalledOnce();
  });

  it("renders a confirmed reservation result", () => {
    render(<ReservationPanel {...props} outcome="confirmed" reference="FAKE-RES-A-001" />);
    expect(screen.getByText("Reservation confirmed")).toBeVisible();
    expect(screen.getByText("FAKE-RES-A-001")).toBeVisible();
  });

  it.each(["refused", "unavailable", "unclear", "no_answer", "failed"] as const)("does not present %s as success", outcome => {
    render(<ReservationPanel {...props} outcome={outcome} />);
    expect(screen.getByText("Human review required")).toBeVisible();
    expect(screen.queryByText("Reservation confirmed")).not.toBeInTheDocument();
  });

  it("shows factual agent timeline events", () => {
    render(<AgentActivity events={[{ id: "a1", event_type: "request_created", created_at: "2026-09-06T10:00:00Z" }, { id: "a2", event_type: "reservation_preview_prepared", created_at: "2026-09-06T10:01:00Z" }]} />);
    expect(screen.getByText("Request created")).toBeVisible();
    expect(screen.getByText("Reservation preview prepared")).toBeVisible();
  });

  it("keeps the recommended supplier distinct from a different selection", () => {
    const ranking: RankingResponse = { sourcing_request_id: "r1", recommended_supplier_id: "s1", recommended_supplier_name: "Supplier A", explanation: "Backend explanation", ranking: [
      { rank: 1, quote_id: "q1", supplier_id: "s1", supplier_name: "Supplier A", reasons: [] },
      { rank: 2, quote_id: "q2", supplier_id: "s2", supplier_name: "Supplier B", reasons: [] },
    ] };
    render(<RankingPanel ranking={ranking} selectedQuoteId="q2" />);
    expect(screen.getByText("Recommended", { exact: true })).toBeVisible();
    expect(screen.getByText("Selected", { exact: true })).toBeVisible();
    expect(screen.getAllByText("Recommended: Supplier A")).toHaveLength(2);
    expect(screen.getByText("Selected: Supplier B")).toBeVisible();
  });
});
