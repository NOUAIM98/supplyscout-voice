"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, CircleDollarSign, PackageSearch, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ContextPanel } from "@/components/sourcing/context-panel";
import { WorkflowStepper } from "@/components/workflow/workflow-stepper";
import { ApprovalPanel } from "@/components/workflow/approval-panel";
import { QuoteComparison } from "@/components/quotes/quote-comparison";
import { RankingPanel } from "@/components/quotes/ranking-panel";

export function RequestDetail({ id }: { id: string }) {
  const client = useQueryClient();
  const request = useQuery({ queryKey: ["request", id], queryFn: () => api.getRequest(id) });
  const workflow = useQuery({ queryKey: ["workflow", id], queryFn: () => api.getWorkflow(id) });
  const context = useQuery({ queryKey: ["context", id], queryFn: () => api.getContextPreview(id) });
  const preview = useQuery({ queryKey: ["quote-preview", id], queryFn: () => api.getQuotePreview(id), enabled: context.isSuccess });
  const approved = Boolean(preview.data?.quote_call_approved || workflow.data?.quote_call_approved);
  const quotes = useQuery({ queryKey: ["quotes", id], queryFn: () => api.getQuotes(id), enabled: approved });
  const ranking = useQuery({ queryKey: ["ranking", id], queryFn: () => api.getRanking(id), enabled: Boolean(quotes.data?.length) });
  const approve = useMutation({ mutationFn: () => api.approveQuoteCalls(id), onSuccess: data => { client.setQueryData(["quotes", id], data); return Promise.all([client.invalidateQueries({ queryKey: ["workflow", id] }), client.invalidateQueries({ queryKey: ["ranking", id] })]); } });
  const select = useMutation({ mutationFn: (quoteId: string) => api.selectQuote(id, quoteId), onSuccess: data => { client.setQueryData(["workflow", id], data); } });
  const error = request.error || workflow.error || context.error || preview.error || approve.error || select.error;
  if (request.isLoading) return <DetailSkeleton />;
  if (!request.data) return <main className="mx-auto max-w-7xl px-5 py-10"><Alert>{error?.message ?? "Request not found"}</Alert></main>;
  const status = workflow.data?.workflow_status ?? preview.data?.workflow_status ?? request.data.status;
  const visibleStatus = workflow.data?.selected_quote_id ? "supplier selected" : status.replaceAll("_", " ");
  return <main className="mx-auto max-w-7xl space-y-8 px-5 py-10 lg:px-8 lg:py-12">
    <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><div className="flex flex-wrap items-center gap-3"><p className="eyebrow">Sourcing request</p><Badge><span className="status-dot mr-2" /> Demo supplier responses</Badge></div><h1 className="mt-3 text-4xl font-semibold tracking-[-.035em]">{request.data.part_name} for {request.data.vehicle_year} {request.data.vehicle_make} {request.data.vehicle_model}</h1><p className="mt-3 font-mono text-sm text-muted-foreground">{request.data.requested_reference}</p></div><Badge className="w-fit bg-card px-3 py-2">{visibleStatus}</Badge></div>
    <WorkflowStepper status={status} />
    {error && <Alert>{error.message}</Alert>}
    <div className="grid gap-6 lg:grid-cols-[1.4fr_.6fr]">
      <div>{context.data ? <ContextPanel context={context.data} /> : <PanelSkeleton />}</div>
      <Card><CardHeader><p className="eyebrow">Call brief</p><CardTitle className="mt-2 text-xl">What the agent will ask</CardTitle></CardHeader><CardContent><dl className="space-y-4 text-sm">{[[PackageSearch, "Item", `${request.data.quantity} × ${request.data.part_name}`],[CircleDollarSign, "Budget", `${request.data.max_budget} ${request.data.currency}`],[CalendarDays, "Deadline", request.data.needed_by]].map(([Icon, label, value]) => { const I = Icon as typeof PackageSearch; return <div key={String(label)} className="flex gap-3"><I className="mt-0.5 size-4 text-primary" /><div><dt className="text-muted-foreground">{String(label)}</dt><dd className="mt-1 font-medium">{String(value)}</dd></div></div>})}</dl><div className="mt-6 border-t pt-5"><p className="flex gap-2 text-sm font-semibold"><ShieldCheck className="size-4 text-primary" /> Safety restrictions</p><p className="mt-2 text-sm leading-6 text-muted-foreground">SupplyScout will not order, purchase, pay, or reserve during this step.</p></div></CardContent></Card>
    </div>
    {!approved && <ApprovalPanel ready={preview.isSuccess} pending={approve.isPending} onApprove={() => approve.mutate()} />}
    {quotes.data && quotes.data.length > 0 && <><div className="space-y-6">{ranking.data ? <RankingPanel ranking={ranking.data} selectedQuoteId={workflow.data?.selected_quote_id ?? null} /> : <PanelSkeleton />}<QuoteComparison quotes={quotes.data} selectedQuoteId={workflow.data?.selected_quote_id ?? null} selectingId={select.variables} onSelect={quoteId => select.mutate(quoteId)} /></div>{workflow.data?.selected_quote_id && <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900"><CheckCircle2 className="size-5" /><div><p className="font-semibold">Selected supplier</p><p className="text-sm">Decision recorded. Reservation actions arrive in Phase F2.</p></div></div>}</>}
  </main>;
}

function DetailSkeleton() { return <main className="mx-auto max-w-7xl space-y-6 px-5 py-10"><Skeleton className="h-24 w-2/3" /><Skeleton className="h-16 w-full" /><div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-96" /><Skeleton className="h-96" /></div></main>; }
function PanelSkeleton() { return <Card><CardContent className="space-y-4 p-6"><Skeleton className="h-5 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></CardContent></Card>; }
