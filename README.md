# SupplyScout Voice

SupplyScout Voice is a standalone CALL-E hackathon web application for sourcing urgent automotive parts from approved suppliers.

## System Architecture

![SupplyScout Voice High-Level System Architecture](docs/diagrams/supplyscout-high-level-architecture.png)

- Next.js on Vercel provides the user and human-control interface.
- FastAPI is the server-side application boundary, with the SupplyScout Procurement Agent orchestrated by LangGraph inside the backend.
- LangChain supports model interaction, structured outputs, context construction, and retrieval without owning business state.
- PostgreSQL with pgvector stores authoritative application data and a limited curated RAG context; Redis and RQ workers coordinate asynchronous supplier calls.
- CALL-E remains the essential AI phone-call runtime for human-approved supplier calls and structured webhook results.
- Deterministic Python logic compares quotes using the allowed factors; the user approves quote calls, chooses the supplier, and separately approves reservation.
