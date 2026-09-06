import { Check, Circle, UserRound } from "lucide-react";
import type { ActivityEvent } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const labels: Record<string, string> = {
  request_created: "Request created",
  knowledge_retrieved: "Knowledge retrieved",
  preview_generated: "Call preview prepared",
  quote_calls_approved: "Quote calls approved",
  supplier_call_completed: "Supplier response received",
  quotes_normalized: "Quotes normalized",
  recommendation_generated: "Recommendation generated",
  offer_selected: "Supplier selected",
  reservation_preview_prepared: "Reservation preview prepared",
  reservation_approved: "Reservation approved",
  reservation_call_completed: "Reservation response received",
  reservation_outcome_stored: "Reservation outcome recorded",
  workflow_completed: "Workflow completed",
};

export function AgentActivity({ events }: { events: ActivityEvent[] }) {
  const visible = events.filter(event => labels[event.event_type]);
  return <Card><CardHeader><p className="eyebrow">Activity</p><CardTitle className="mt-2 text-xl">Agent timeline</CardTitle></CardHeader><CardContent><ol className="space-y-3">{visible.map((event, index) => <li key={event.id} className="flex gap-3 text-sm"><span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border bg-card">{index === visible.length - 1 ? <Circle className="size-2 fill-primary text-primary" /> : <Check className="size-3 text-emerald-700" />}</span><div><p className="font-medium">{labels[event.event_type]}</p><time className="text-xs text-muted-foreground" dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time></div></li>)}</ol>{visible.length === 0 && <p className="text-sm text-muted-foreground">No activity recorded yet.</p>}<p className="mt-5 flex gap-2 border-t pt-4 text-xs text-muted-foreground"><UserRound className="size-4" /> Human approvals are shown as recorded decisions, not agent reasoning.</p></CardContent></Card>;
}
