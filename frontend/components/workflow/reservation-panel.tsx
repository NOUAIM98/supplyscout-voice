"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, PhoneCall, ShieldCheck } from "lucide-react";
import type { ReservationOutcome, SourcingRequest, SupplierQuote } from "@/lib/types";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ReservationPanel({ request, quote, reviewed, outcome, reference, previewing, approving, onReview, onApprove }: { request: SourcingRequest; quote: SupplierQuote; reviewed: boolean; outcome?: ReservationOutcome; reference?: string | null; previewing: boolean; approving: boolean; onReview: () => void; onApprove: () => void }) {
  const [confirming, setConfirming] = useState(false);
  if (!reviewed) return <Card className="border-primary/25"><CardContent className="flex flex-col items-start justify-between gap-4 p-6 sm:flex-row sm:items-center"><div><p className="eyebrow">Next human decision</p><h2 className="mt-2 text-2xl font-semibold">Review the reservation request</h2><p className="mt-2 text-sm text-muted-foreground">Selection is recorded. Review the exact scope before approving a separate supplier contact.</p></div><Button onClick={onReview} disabled={previewing}>{previewing ? "Preparing…" : "Review reservation"}</Button></CardContent></Card>;
  if (outcome && outcome !== "pending_approval") {
    const confirmed = outcome === "confirmed";
    return <Card className={confirmed ? "border-emerald-200 bg-emerald-50" : "border-amber-300 bg-amber-50"}><CardHeader><div className="flex items-center gap-3">{confirmed ? <CheckCircle2 className="size-6 text-emerald-700" /> : <AlertTriangle className="size-6 text-amber-700" />}<div><p className="eyebrow">Reservation result · Demo</p><CardTitle className="mt-1">{confirmed ? "Reservation confirmed" : "Human review required"}</CardTitle></div></div></CardHeader><CardContent className="text-sm"><p><strong>Supplier:</strong> {quote.supplier_name}</p><p className="mt-2"><strong>Selected quote:</strong> {quote.unit_price ?? "Unknown"} {quote.currency ?? ""}</p><p className="mt-2 capitalize"><strong>Status:</strong> {outcome.replaceAll("_", " ")}</p>{reference && <p className="mt-2"><strong>Reservation reference:</strong> {reference}</p>}<p className="mt-4 text-muted-foreground">No payment or purchase was made.</p></CardContent></Card>;
  }
  return <Card className="border-primary/30"><CardHeader><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Second approval gate</p><CardTitle className="mt-2">Reservation preview</CardTitle></div><Badge>Demo provider</Badge></div></CardHeader><CardContent><dl className="grid gap-4 text-sm sm:grid-cols-2">{[["Selected supplier", quote.supplier_name], ["Selected quote price", quote.unit_price ? `${quote.unit_price} ${quote.currency}` : "Unknown"], ["Requested reference", request.requested_reference], ["Quantity", request.quantity], ["Current availability", quote.in_stock === "yes" ? `${quote.quantity_available ?? "Unknown"} available` : quote.in_stock], ["Reservation purpose", "Request the supplier to hold the selected part"]].map(([label, value]) => <div key={String(label)}><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 font-medium">{value}</dd></div>)}</dl><div className="mt-6 rounded-lg border bg-muted/40 p-4 text-sm"><p className="flex gap-2 font-semibold"><ShieldCheck className="size-4 text-primary" /> Safety restrictions</p><p className="mt-2">SupplyScout has not contacted the supplier for reservation yet.</p><p className="mt-1">No payment or purchase will be made.</p></div><Button className="mt-5" onClick={() => setConfirming(true)} disabled={approving}><PhoneCall className="size-4" /> Approve reservation call</Button>{confirming && <div role="dialog" aria-modal="true" aria-labelledby="reservation-confirm-title" className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-5"><Card className="max-w-lg"><CardHeader><CardTitle id="reservation-confirm-title">Approve reservation call?</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-muted-foreground">SupplyScout will contact the selected supplier to request a reservation only. No payment or purchase will be made.</p><div className="mt-6 flex justify-end gap-3"><Button variant="outline" onClick={() => setConfirming(false)}>Cancel</Button><Button onClick={() => { setConfirming(false); onApprove(); }} disabled={approving}>Approve reservation call</Button></div></CardContent></Card></div>}</CardContent></Card>;
}

export function ReservationStage({ quote, ...props }: { quote: SupplierQuote | null } & Omit<React.ComponentProps<typeof ReservationPanel>, "quote">) {
  return quote ? <ReservationPanel quote={quote} {...props} /> : null;
}

export function ReservationError({ message }: { message: string }) { return <Alert>{message}</Alert>; }
