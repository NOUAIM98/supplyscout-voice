import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NewRequestForm } from "./new-request-form";
import { WorkflowStepper } from "@/components/workflow/workflow-stepper";
import { QuoteComparison } from "@/components/quotes/quote-comparison";
import { RankingPanel } from "@/components/quotes/ranking-panel";
import { ApprovalPanel } from "@/components/workflow/approval-panel";
import type { RankingResponse, SupplierQuote } from "@/lib/types";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const quote = (overrides: Partial<SupplierQuote> = {}): SupplierQuote => ({
  id: "q1", supplier_id: "s1", supplier_name: "Supplier A", exact_reference_confirmed: "yes",
  offered_reference: "TEST-ALT-CLIO-2019-001", in_stock: "yes", manufacturer_or_brand: null,
  condition: "new", quantity_available: 1, unit_price: "145.00", currency: "EUR",
  tax_included: "unknown", warranty_months: 12, pickup_available_today: "yes",
  delivery_eta: null, quote_valid_until: null, supplier_notes: null, ...overrides,
});

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
