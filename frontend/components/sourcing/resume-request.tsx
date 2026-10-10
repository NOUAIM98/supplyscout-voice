"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ResumeRequest() {
  const router = useRouter();
  const [requestId, setRequestId] = useState("");
  useEffect(() => {
    setRequestId(window.localStorage.getItem("supplyscout:last-request-id") ?? "");
  }, []);
  function submit(event: FormEvent) {
    event.preventDefault();
    const id = requestId.trim();
    if (!id) return;
    window.localStorage.setItem("supplyscout:last-request-id", id);
    router.push(`/requests/${encodeURIComponent(id)}`);
  }
  return <form onSubmit={submit} className="mt-6 rounded-xl border bg-card p-5">
    <Label htmlFor="resume-request-id">Resume a request</Label>
    <div className="mt-2 flex gap-2"><Input id="resume-request-id" value={requestId} onChange={event => setRequestId(event.target.value)} placeholder="Paste a request ID" /><Button type="submit" variant="outline" disabled={!requestId.trim()}>Open <ArrowRight className="size-4" /></Button></div>
  </form>;
}
