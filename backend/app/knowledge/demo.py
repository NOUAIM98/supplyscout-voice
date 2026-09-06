from sqlalchemy import select

from ..db.models import KnowledgeChunk
from .embeddings import EmbeddingProvider
from .repository import KnowledgeRepository

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


def seed_demo(repository: KnowledgeRepository, embeddings: EmbeddingProvider) -> int:
    """Explicit, idempotent seed. Never imports real-call artifacts or quotes."""
    added = 0
    for kind, ref, title, content in DEMO_KNOWLEDGE:
        if repository.session.scalar(select(KnowledgeChunk.id).where(KnowledgeChunk.source_ref == ref)):
            continue
        repository.add_chunk(
            source_type=kind, source_ref=ref, title=title, content=content,
            embedding=embeddings.embed_documents([content])[0],
            metadata_json={"curated": True, "demo": True},
        )
        added += 1
    return added
