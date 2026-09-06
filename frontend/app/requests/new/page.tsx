import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { NewRequestForm } from "@/components/sourcing/new-request-form";
import { Card, CardContent } from "@/components/ui/card";

export default function NewRequestPage() {
  return <main className="mx-auto max-w-4xl px-5 py-10 lg:px-8 lg:py-14">
    <Link href="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" /> Back to overview</Link>
    <div className="mb-8 mt-8"><p className="eyebrow">New sourcing request</p><h1 className="mt-3 text-4xl font-semibold tracking-[-.035em]">Define what the team needs.</h1><p className="mt-3 text-muted-foreground">Specific references and constraints produce clearer supplier conversations.</p></div>
    <Card><CardContent className="p-6 sm:p-8"><NewRequestForm /></CardContent></Card>
  </main>;
}
