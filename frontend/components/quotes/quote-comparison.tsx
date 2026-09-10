import { Check, HelpCircle, X } from "lucide-react";
import type { SupplierQuote, YesNoUnknown } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function KnownValue({ value }: { value: YesNoUnknown }) {
  if (value === "unknown") return <span className="inline-flex items-center gap-1 text-amber-700"><HelpCircle className="size-3.5" /> Unknown</span>;
  return value === "yes" ? <span className="inline-flex items-center gap-1 text-emerald-700"><Check className="size-3.5" /> Yes</span> : <span className="inline-flex items-center gap-1 text-red-700"><X className="size-3.5" /> No</span>;
}
const plain = (value: string | number | null) => value ?? <span className="text-amber-700">Unknown</span>;

export function QuoteComparison({ quotes, selectedQuoteId, selectionAllowed, selectingId, onSelect }: { quotes: SupplierQuote[]; selectedQuoteId: string | null; selectionAllowed: boolean; selectingId?: string; onSelect: (id: string) => void }) {
  return <section aria-labelledby="quotes-heading"><div className="mb-5"><p className="eyebrow">Comparable offers</p><h2 id="quotes-heading" className="mt-2 text-2xl font-semibold">Supplier quotes</h2></div><div className="grid gap-4 lg:grid-cols-3">{quotes.map(quote => <Card key={quote.id} className={selectedQuoteId === quote.id ? "border-primary ring-1 ring-primary" : ""}><CardHeader><CardTitle className="text-lg">{quote.supplier_name}</CardTitle><p className="font-mono text-xs text-muted-foreground">{quote.offered_reference ?? "Reference unknown"}</p></CardHeader><CardContent><dl className="space-y-3 text-sm">{[
    ["Exact reference", <KnownValue key="r" value={quote.exact_reference_confirmed} />], ["In stock", <KnownValue key="s" value={quote.in_stock} />],
    ["Unit price", quote.unit_price ? `${quote.unit_price} ${quote.currency}` : plain(null)], ["Warranty", quote.warranty_months == null ? plain(null) : `${quote.warranty_months} months`],
    ["Pickup today", <KnownValue key="p" value={quote.pickup_available_today} />], ["Delivery", plain(quote.delivery_eta)], ["Condition", plain(quote.condition === "unknown" ? null : quote.condition)],
  ].map(([label, value]) => <div key={String(label)} className="flex items-center justify-between gap-4 border-b pb-3 last:border-0"><dt className="text-muted-foreground">{label}</dt><dd className="text-right font-medium">{value}</dd></div>)}</dl>
  <Button className="mt-5 w-full" variant={selectedQuoteId === quote.id ? "outline" : "default"} disabled={!selectionAllowed || selectedQuoteId === quote.id || selectingId === quote.id} onClick={() => onSelect(quote.id)}>{selectedQuoteId === quote.id ? "Selected supplier" : !selectionAllowed ? "Selection locked" : selectingId === quote.id ? "Selecting…" : "Select this supplier"}</Button></CardContent></Card>)}</div></section>;
}
