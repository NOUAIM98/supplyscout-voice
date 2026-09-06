import { PhoneCall } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function ApprovalPanel({ ready, pending, onApprove }: { ready: boolean; pending: boolean; onApprove: () => void }) {
  return <Card className="overflow-hidden border-primary/25"><div className="grid lg:grid-cols-[1fr_auto]"><div className="p-6"><p className="eyebrow text-primary">Human approval required</p><h2 className="mt-2 text-2xl font-semibold">Ready to request supplier quotes?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">This demo generates three fictional supplier responses. Approval is explicit and is never triggered automatically.</p></div><div className="flex items-center border-t bg-primary/5 p-6 lg:border-l lg:border-t-0"><Button size="lg" disabled={pending || !ready} onClick={onApprove}><PhoneCall className="size-4" /> {pending ? "Requesting…" : "Approve supplier quote calls"}</Button></div></div></Card>;
}
