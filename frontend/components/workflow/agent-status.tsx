import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const humanStates = new Set(["awaiting_quote_approval", "awaiting_human_selection", "awaiting_reservation_approval"]);
const warningStates = new Set(["refused", "unavailable", "unclear", "no_answer", "failed"]);

export function AgentStatus({ status, outcome }: { status: string; outcome?: string }) {
  const label = status === "completed" ? (outcome === "confirmed" ? "Completed" : "Human review required") : status.replaceAll("_", " ");
  const tone = status === "completed" && outcome === "confirmed" ? "border-emerald-200 bg-emerald-50" : warningStates.has(outcome ?? "") ? "border-amber-300 bg-amber-50" : humanStates.has(status) ? "border-primary/30 bg-primary/5" : "bg-card";
  return <Card className={cn("flex items-center justify-between gap-4 p-5", tone)}><div><p className="eyebrow">SupplyScout Agent</p><p className="mt-1 text-sm text-muted-foreground">Current state</p><p className="mt-1 text-lg font-semibold capitalize">{label}</p></div><Badge>{humanStates.has(status) ? "Human action required" : status === "completed" && outcome === "confirmed" ? "Complete" : "Agent status"}</Badge></Card>;
}
