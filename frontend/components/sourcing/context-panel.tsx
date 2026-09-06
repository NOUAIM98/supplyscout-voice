import { BookOpen, ExternalLink } from "lucide-react";
import type { ContextPreview } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ContextPanel({ context }: { context: ContextPreview }) {
  return <Card><CardHeader><div className="flex items-start justify-between gap-4"><div><p className="eyebrow">Pre-call evidence</p><CardTitle className="mt-2 text-xl">Agent context</CardTitle></div><BookOpen className="size-5 text-primary" /></div><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Supporting context retrieved before supplier calls. Live price and availability still come only from suppliers.</p></CardHeader><CardContent><div className="grid gap-3 lg:grid-cols-2">{context.chunks.map(chunk => <article key={chunk.id} className="rounded-lg border bg-background p-4"><div className="flex items-start justify-between gap-3"><h3 className="font-semibold">{chunk.title}</h3><Badge>{chunk.source_type.replaceAll("_", " ")}</Badge></div><p className="mt-3 text-sm leading-6 text-muted-foreground">{chunk.snippet}</p><p className="mt-4 flex items-center gap-2 font-mono text-xs text-muted-foreground"><ExternalLink className="size-3" /> {chunk.source_ref}</p></article>)}</div></CardContent></Card>;
}
