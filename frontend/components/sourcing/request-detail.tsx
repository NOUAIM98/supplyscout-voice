"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CircleDollarSign, PackageSearch, ShieldCheck } from "lucide-react";
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
import { AgentActivity } from "@/components/workflow/agent-activity";
import { AgentStatus } from "@/components/workflow/agent-status";
import { ReservationStage } from "@/components/workflow/reservation-panel";
import { CallProgress, RuntimeBadge, hasActiveCalls } from "@/components/workflow/call-progress";

export function RequestDetail({ id }: { id: string }) {
  const client = useQueryClient();
  const runtime = useQuery({ queryKey: ["runtime"], queryFn: api.getRuntime, staleTime: 60_000 });
  const request = useQuery({ queryKey: ["request", id], queryFn: () => api.getRequest(id) });
  const workflow = useQuery({ queryKey: ["workflow", id], queryFn: () => api.getWorkflow(id) });
  const context = useQuery({ queryKey: ["context", id], queryFn: () => api.getContextPreview(id) });
  const preview = useQuery({ queryKey: ["quote-preview", id], queryFn: () => api.getQuotePreview(id), enabled: context.isSuccess });
  const approved = Boolean(preview.data?.quote_call_approved || workflow.data?.quote_call_approved);
  const quotes = useQuery({ queryKey: ["quotes", id], queryFn: () => api.getQuotes(id), enabled: approved });
  const ranking = useQuery({ queryKey: ["ranking", id], queryFn: () => api.getRanking(id), enabled: Boolean(quotes.data?.length) });
  const activity = useQuery({ queryKey: ["activity", id], queryFn: () => api.getActivity(id) });
  const live = runtime.data?.call_provider_mode === "calle" && runtime.data.live_calls_enabled;
  const attempts = useQuery({ queryKey: ["call-attempts", id], queryFn: () => api.getCallAttempts(id), enabled: Boolean(live && approved) });
  const activeCalls = hasActiveCalls(attempts.data ?? []);
  useQuery({ queryKey: ["call-sync", id], enabled: Boolean(live && activeCalls), refetchInterval: query => hasActiveCalls(query.state.data?.attempts ?? []) ? 4000 : false, queryFn: async () => { const data = await api.syncCalls(id); client.setQueryData(["workflow", id], data.workflow); client.setQueryData(["call-attempts", id], data.attempts); if (["awaiting_human_selection", "completed"].includes(data.workflow.workflow_status)) { await Promise.all([client.invalidateQueries({ queryKey: ["quotes", id] }), client.invalidateQueries({ queryKey: ["ranking", id] }), client.invalidateQueries({ queryKey: ["activity", id] })]); } return data; } });
  const approve = useMutation({ retry: false, mutationFn: () => api.approveQuoteCalls(id), onSuccess: data => { client.setQueryData(["quotes", id], data); return Promise.all([client.invalidateQueries({ queryKey: ["workflow", id] }), client.invalidateQueries({ queryKey: ["ranking", id] }), client.invalidateQueries({ queryKey: ["activity", id] }), client.invalidateQueries({ queryKey: ["call-attempts", id] })]); } });
  const select = useMutation({ mutationFn: (quoteId: string) => api.selectQuote(id, quoteId), onSuccess: data => { client.setQueryData(["workflow", id], data); return client.invalidateQueries({ queryKey: ["activity", id] }); } });
  const reservationPreview = useMutation({ mutationFn: () => api.getReservationPreview(id), onSuccess: data => { client.setQueryData(["workflow", id], data); return client.invalidateQueries({ queryKey: ["activity", id] }); } });
  const reservationApproval = useMutation({ retry: false, mutationFn: () => api.approveReservation(id), onSuccess: data => { client.setQueryData(["workflow", id], data); return Promise.all([client.invalidateQueries({ queryKey: ["request", id] }), client.invalidateQueries({ queryKey: ["activity", id] }), client.invalidateQueries({ queryKey: ["call-attempts", id] })]); } });
  const error = request.error || workflow.error || context.error || preview.error || approve.error || select.error || reservationPreview.error || reservationApproval.error;
  if (request.isLoading) return <DetailSkeleton />;
  if (!request.data) return <main className="mx-auto max-w-7xl px-5 py-10"><Alert>{error?.message ?? "Request not found"}</Alert></main>;
  const status = workflow.data?.workflow_status ?? preview.data?.workflow_status ?? request.data.status;
  const selectedQuote = quotes.data?.find(quote => quote.id === workflow.data?.selected_quote_id);
  const reservationResult = workflow.data?.reservation_result;
  const visibleStatus = status.replaceAll("_", " ");
  return <main className="mx-auto max-w-7xl space-y-8 px-5 py-10 lg:px-8 lg:py-12">
    <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><div className="flex flex-wrap items-center gap-3"><p className="eyebrow">Sourcing request</p><RuntimeBadge runtime={runtime.data} /></div><h1 className="mt-3 text-4xl font-semibold tracking-[-.035em]">{request.data.part_name} for {request.data.vehicle_year} {request.data.vehicle_make} {request.data.vehicle_model}</h1><p className="mt-3 font-mono text-sm text-muted-foreground">{request.data.requested_reference}</p></div><Badge className="w-fit bg-card px-3 py-2">{visibleStatus}</Badge></div>
    <WorkflowStepper status={status} />
    <AgentStatus status={status} outcome={reservationResult?.outcome} />
    {live && <CallProgress attempts={attempts.data ?? []} />}
    {error && <Alert>{error.message}</Alert>}
    <div className="grid gap-6 lg:grid-cols-[1.4fr_.6fr]">
      <div>{context.data ? <ContextPanel context={context.data} /> : <PanelSkeleton />}</div>
      <Card><CardHeader><p className="eyebrow">Call brief</p><CardTitle className="mt-2 text-xl">What the agent will ask</CardTitle></CardHeader><CardContent><dl className="space-y-4 text-sm">{[[PackageSearch, "Item", `${request.data.quantity} × ${request.data.part_name}`],[CircleDollarSign, "Budget", `${request.data.max_budget} ${request.data.currency}`],[CalendarDays, "Deadline", request.data.needed_by]].map(([Icon, label, value]) => { const I = Icon as typeof PackageSearch; return <div key={String(label)} className="flex gap-3"><I className="mt-0.5 size-4 text-primary" /><div><dt className="text-muted-foreground">{String(label)}</dt><dd className="mt-1 font-medium">{String(value)}</dd></div></div>})}</dl><div className="mt-6 border-t pt-5"><p className="flex gap-2 text-sm font-semibold"><ShieldCheck className="size-4 text-primary" /> Safety restrictions</p><p className="mt-2 text-sm leading-6 text-muted-foreground">SupplyScout will not order, purchase, pay, or reserve during this step.</p></div></CardContent></Card>
    </div>
    {!approved && <ApprovalPanel ready={preview.isSuccess} pending={approve.isPending} onApprove={() => approve.mutate()} />}
    {quotes.data && quotes.data.length > 0 && <div className="space-y-6">{ranking.data ? <RankingPanel ranking={ranking.data} selectedQuoteId={workflow.data?.selected_quote_id ?? null} /> : <PanelSkeleton />}<QuoteComparison quotes={quotes.data} selectedQuoteId={workflow.data?.selected_quote_id ?? null} selectingId={select.variables} onSelect={quoteId => select.mutate(quoteId)} /><ReservationStage request={request.data} quote={selectedQuote ?? null} reviewed={reservationPreview.isSuccess || status === "completed"} outcome={reservationResult?.outcome} reference={reservationResult?.supplier_reference} previewing={reservationPreview.isPending} approving={reservationApproval.isPending} onReview={() => reservationPreview.mutate()} onApprove={() => reservationApproval.mutate()} /></div>}
    {activity.data && <AgentActivity events={activity.data} />}
  </main>;
}

function DetailSkeleton() { return <main className="mx-auto max-w-7xl space-y-6 px-5 py-10"><Skeleton className="h-24 w-2/3" /><Skeleton className="h-16 w-full" /><div className="grid gap-6 lg:grid-cols-2"><Skeleton className="h-96" /><Skeleton className="h-96" /></div></main>; }
function PanelSkeleton() { return <Card><CardContent className="space-y-4 p-6"><Skeleton className="h-5 w-40" /><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></CardContent></Card>; }
