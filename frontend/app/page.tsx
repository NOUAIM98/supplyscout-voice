import Link from "next/link";
import { ArrowRight, CheckCircle2, FileSearch, PhoneCall, Scale, ShieldCheck } from "lucide-react";

const steps = [
  ["01", "Request", "Define the exact part and constraints."],
  ["02", "AI context", "Retrieve policy and reference guidance."],
  ["03", "Supplier calls", "Contact suppliers only after approval."],
  ["04", "Compare", "Normalize every known and unknown fact."],
  ["05", "Decide", "Rank consistently; keep the choice human."],
];

export default function Home() {
  return <main>
    <section className="mx-auto grid max-w-7xl gap-12 px-5 py-16 lg:grid-cols-[1.15fr_.85fr] lg:px-8 lg:py-24">
      <div className="max-w-3xl">
        <p className="eyebrow mb-5">Procurement call operations</p>
        <h1 className="text-5xl font-semibold leading-[1.04] tracking-[-.045em] sm:text-6xl">Turn supplier phone calls into structured procurement decisions.</h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-muted-foreground">SupplyScout calls approved suppliers, collects live quote information, and turns conversations into comparable structured offers.</p>
        <Link href="/requests/new" className="mt-9 inline-flex h-12 items-center gap-2 rounded-md bg-primary px-6 text-sm font-semibold text-primary-foreground hover:bg-primary/90">New sourcing request <ArrowRight className="size-4" /></Link>
      </div>
      <div className="relative overflow-hidden rounded-2xl border bg-foreground p-7 text-background shadow-xl shadow-slate-900/10">
        <div className="absolute right-0 top-0 h-36 w-36 rounded-bl-full bg-primary/70" />
        <p className="eyebrow !text-slate-400">Control plane</p>
        <div className="mt-14 space-y-6">
          <div className="flex gap-4"><ShieldCheck className="mt-1 size-5 text-blue-400" /><div><p className="font-medium">Human approval before calls</p><p className="mt-1 text-sm leading-6 text-slate-400">Every supplier conversation starts with an explicit decision.</p></div></div>
          <div className="flex gap-4"><FileSearch className="mt-1 size-5 text-blue-400" /><div><p className="font-medium">Evidence stays traceable</p><p className="mt-1 text-sm leading-6 text-slate-400">Context, source references, and uncertainty remain visible.</p></div></div>
          <div className="flex gap-4"><Scale className="mt-1 size-5 text-blue-400" /><div><p className="font-medium">Recommendation stays separate</p><p className="mt-1 text-sm leading-6 text-slate-400">SupplyScout ranks each offer. Your team makes the final selection.</p></div></div>
        </div>
      </div>
    </section>
    <section className="border-y bg-card">
      <div className="mx-auto max-w-7xl px-5 py-14 lg:px-8">
        <div className="mb-8 flex items-center gap-3"><PhoneCall className="size-5 text-primary" /><h2 className="text-xl font-semibold">From request to decision</h2></div>
        <ol className="grid gap-px overflow-hidden rounded-xl border bg-border md:grid-cols-5">
          {steps.map(([number, title, text]) => <li key={number} className="bg-card p-5"><span className="font-mono text-xs text-primary">{number}</span><h3 className="mt-8 font-semibold">{title}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p></li>)}
        </ol>
        <p className="mt-5 flex items-center gap-2 text-sm text-muted-foreground"><CheckCircle2 className="size-4" /> Demo mode uses fictional supplier responses. No real calls are placed from this workspace.</p>
      </div>
    </section>
  </main>;
}
