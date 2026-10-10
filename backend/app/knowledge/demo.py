import json

from sqlalchemy import select

from ..db.models import KnowledgeChunk
from .embeddings import EmbeddingProvider
from .repository import KnowledgeRepository

DEMO_REFERENCE = "TEST-ALT-CLIO-2019-001"

DEMO_KNOWLEDGE = [
    ("part_reference_note", "demo:clio:reference:v1", "Fictional demo reference",
     "TEST-ALT-CLIO-2019-001 is the exact requested fictional demo reference for "
     "the 2019 Renault Clio alternator scenario; it is not a real OEM compatibility claim."),
    ("vehicle_compatibility", "demo:clio:compatibility:v1", "Compatibility confirmation policy",
     "For the Renault Clio alternator quote, prefer explicit exact reference confirmation "
     "over inferred vehicle compatibility. Ask a short clarification when uncertain."),
    ("substitution_rule", "demo:clio:substitution:v1", "Alternative reference policy",
     "For TEST-ALT-CLIO-2019-001 Renault Clio alternator substitution, an alternative "
     "reference must not be treated as an exact match unless explicitly confirmed."),
    ("procurement_policy", "demo:quote:safety:v1", "Quote collection only",
     "During quote collection do not purchase, pay, order, reserve, or commit. "
     "Supplier selection and a separate reservation approval remain human decisions."),
    ("call_policy", "demo:quote:uncertainty:v1", "Unknown supplier facts remain unknown",
     "Unknown supplier facts must remain unknown. Ask the supplier about stock, price, "
     "warranty and delivery; never infer these from reference or policy knowledge."),
]


def demo_context_preview(requested_reference: str | None, top_k: int = 4) -> dict:
    """Return bounded, in-memory demo context without requiring embeddings or a service."""
    chunks = []
    for source_type, source_ref, title, content in DEMO_KNOWLEDGE:
        reference_specific = source_type in {"part_reference_note", "substitution_rule"}
        if reference_specific and requested_reference != DEMO_REFERENCE:
            continue
        chunks.append({
            "id": source_ref,
            "source_type": source_type,
            "source_ref": source_ref,
            "title": title,
            "snippet": content[:240],
            "scope": "reference_specific" if reference_specific else "general",
            "content": content,
        })
        if len(chunks) == top_k:
            break
    public_chunks = [{key: value for key, value in chunk.items() if key != "content"}
                     for chunk in chunks]
    task_context = (
        "Curated fictional demo context only, not live supplier evidence. Confirm facts "
        "with the supplier. Unknown stays unknown. Do not purchase, pay, order, reserve "
        "or commit.\n<knowledge_context>"
        f"{json.dumps(chunks, ensure_ascii=False)}</knowledge_context>"
    )
    return {"mode": "demo", "chunks": public_chunks, "task_context": task_context,
            "call_started": False}


def seed_demo(repository: KnowledgeRepository, embeddings: EmbeddingProvider) -> int:
    """Explicit, idempotent seed. Never imports real-call artifacts or quotes."""
    added = 0
    for kind, ref, title, content in DEMO_KNOWLEDGE:
        existing = repository.session.scalar(
            select(KnowledgeChunk).where(KnowledgeChunk.source_ref == ref)
        )
        reference = DEMO_REFERENCE if kind in {"part_reference_note", "substitution_rule"} else None
        if existing:
            if reference and existing.metadata_json.get("requested_reference") != reference:
                existing.metadata_json = {
                    **existing.metadata_json,
                    "requested_reference": reference,
                }
            continue
        repository.add_chunk(
            source_type=kind, source_ref=ref, title=title, content=content,
            embedding=embeddings.embed_documents([content])[0],
            metadata_json={
                "curated": True,
                "demo": True,
                **({"requested_reference": reference} if reference else {}),
            },
        )
        added += 1
    return added
