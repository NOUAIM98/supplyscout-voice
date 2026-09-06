"use client";

import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import type { SourcingRequestInput } from "@/lib/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const today = new Date().toISOString().slice(0, 10);
const initial: SourcingRequestInput = { vehicle_make: "Renault", vehicle_model: "Clio", vehicle_year: 2019, part_name: "Alternator", requested_reference: "TEST-ALT-CLIO-2019-001", quantity: 1, max_budget: "180", currency: "EUR", needed_by: today };

const fields: Array<{ key: keyof SourcingRequestInput; label: string; type?: string; min?: number }> = [
  { key: "vehicle_make", label: "Make" }, { key: "vehicle_model", label: "Model" },
  { key: "vehicle_year", label: "Year", type: "number", min: 1886 },
  { key: "part_name", label: "Part name" }, { key: "requested_reference", label: "Requested reference" },
  { key: "quantity", label: "Quantity", type: "number", min: 1 },
  { key: "max_budget", label: "Maximum budget", type: "number", min: 1 },
  { key: "currency", label: "Currency" }, { key: "needed_by", label: "Needed by", type: "date" },
];

export function NewRequestForm() {
  const router = useRouter();
  const [form, setForm] = useState(initial);
  const mutation = useMutation({ mutationFn: api.createRequest, onSuccess: (request) => router.push(`/requests/${request.id}`) });
  function submit(event: FormEvent) { event.preventDefault(); mutation.mutate(form); }
  return <form onSubmit={submit} className="space-y-8">
    {mutation.error && <Alert>{mutation.error.message}</Alert>}
    <fieldset className="space-y-4"><legend className="mb-4 text-lg font-semibold">Vehicle</legend><div className="field-grid">{fields.slice(0, 3).map(field => <Field key={field.key} field={field} form={form} setForm={setForm} />)}</div></fieldset>
    <fieldset className="space-y-4 border-t pt-7"><legend className="mb-4 text-lg font-semibold">Part</legend><div className="field-grid">{fields.slice(3, 6).map(field => <Field key={field.key} field={field} form={form} setForm={setForm} />)}</div></fieldset>
    <fieldset className="space-y-4 border-t pt-7"><legend className="mb-4 text-lg font-semibold">Constraints</legend><div className="field-grid">{fields.slice(6).map(field => <Field key={field.key} field={field} form={form} setForm={setForm} />)}</div></fieldset>
    <div className="flex items-center justify-between gap-4 border-t pt-6"><p className="text-sm text-muted-foreground">You will review context and the call brief before approving supplier calls.</p><Button type="submit" size="lg" disabled={mutation.isPending}>{mutation.isPending ? "Creating…" : "Create request"}<ArrowRight className="size-4" /></Button></div>
  </form>;
}

function Field({ field, form, setForm }: { field: typeof fields[number]; form: SourcingRequestInput; setForm: React.Dispatch<React.SetStateAction<SourcingRequestInput>> }) {
  const id = field.key;
  return <div className={field.key === "requested_reference" ? "sm:col-span-2" : ""}><Label htmlFor={id}>{field.label}</Label><Input id={id} className="mt-2" type={field.type ?? "text"} min={field.min} required value={form[id]} onChange={e => setForm(current => ({ ...current, [id]: field.type === "number" && id !== "max_budget" ? Number(e.target.value) : e.target.value }))} /></div>;
}
