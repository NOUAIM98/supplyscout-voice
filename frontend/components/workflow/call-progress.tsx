import { LoaderCircle, PhoneCall } from "lucide-react";
import type { CallAttempt, RuntimeInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const activeStatuses = new Set(["queued", "calling", "in_progress"]);
const terminalStatuses = new Set(["completed", "confirmed", "refused", "unavailable", "unclear", "no_answer", "failed"]);

export function hasActiveCalls(attempts: CallAttempt[]): boolean {
  return attempts.some(attempt => activeStatuses.has(attempt.status));
}

export function allCallsTerminal(attempts: CallAttempt[]): boolean {
  return attempts.length > 0 && attempts.every(attempt => terminalStatuses.has(attempt.status));
}

export function RuntimeBadge({ runtime }: { runtime?: RuntimeInfo }) {
  const live = runtime?.call_provider_mode === "calle" && runtime.live_calls_enabled;
  return <Badge><span className="status-dot mr-2" />{live ? "Live CALL-E" : "Demo supplier responses"}</Badge>;
}

export function CallProgress({ attempts }: { attempts: CallAttempt[] }) {
  if (!attempts.length) return null;
  const completed = attempts.filter(attempt => terminalStatuses.has(attempt.status)).length;
  const reservation = attempts.some(attempt => attempt.call_type === "reservation");
  const active = hasActiveCalls(attempts);
  return <Card className="flex items-center justify-between gap-4 border-primary/25 p-5"><div className="flex items-center gap-3">{active ? <LoaderCircle className="size-5 animate-spin text-primary" /> : <PhoneCall className="size-5 text-primary" />}<div><p className="font-semibold">{reservation && active ? "Contacting selected supplier…" : active ? "Waiting for supplier responses" : "Supplier calls updated"}</p><p className="mt-1 text-sm text-muted-foreground">{completed} of {attempts.length} completed</p></div></div><Badge>{active ? "Live progress" : "Terminal"}</Badge></Card>;
}
