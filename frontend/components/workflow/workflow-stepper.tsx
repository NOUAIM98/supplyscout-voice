import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  ["Request", ["request_created"]],
  ["Knowledge context", ["context_retrieval", "call_preview", "awaiting_quote_approval"]],
  ["Call preview", ["call_preview", "awaiting_quote_approval"]],
  ["Supplier calls", ["supplier_calls_dispatched", "quotes_normalized", "ranked", "awaiting_human_selection"]],
  ["Quotes", ["quotes_normalized", "ranked", "awaiting_human_selection"]],
  ["Decision", ["awaiting_human_selection", "reservation_preview", "awaiting_reservation_approval"]],
  ["Reservation", ["reservation_preview", "awaiting_reservation_approval", "reservation_call"]],
  ["Completed", ["completed"]],
] as const;
const order = ["request_created", "context_retrieval", "call_preview", "awaiting_quote_approval", "supplier_calls_dispatched", "quotes_normalized", "ranked", "awaiting_human_selection", "reservation_preview", "awaiting_reservation_approval", "reservation_call", "completed"];

export function WorkflowStepper({ status }: { status: string }) {
  const current = order.indexOf(status);
  return <ol aria-label="Sourcing workflow" className="grid gap-2 sm:grid-cols-4 xl:grid-cols-8">
    {steps.map(([label, statuses], index) => {
      const active = statuses.includes(status as never);
      const stepStart = order.indexOf(statuses[0]);
      const complete = current > stepStart && !active;
      return <li key={label} className={cn("flex items-center gap-3 rounded-lg border bg-card px-3 py-3 text-sm", active && "border-primary/50 bg-primary/5", complete && "text-muted-foreground")}>
        <span className={cn("grid size-6 shrink-0 place-items-center rounded-full border font-mono text-[11px]", active && "border-primary bg-primary text-primary-foreground", complete && "border-foreground bg-foreground text-background")}>{complete ? <Check className="size-3" /> : active ? index + 1 : <Circle className="size-2 fill-current" />}</span>{label}
      </li>;
    })}
  </ol>;
}
