# 0001. Initial architecture

## Context

v0 lets a company upload documents and ask questions about them, with answers
that cite their sources. It must keep each company's data isolated and be
buildable and deployable by one developer in a short time frame.

## Decisions

1. **Django REST Framework as the single backend.** It provides the ORM,
   migrations, auth and admin out of the box. A second service (FastAPI) was
   considered and rejected for now: it doubles deployment and configuration
   work without a clear benefit at this size.
2. **PostgreSQL with pgvector** for both relational data and embeddings.
   Keeping them together lets one query filter by organization and rank by
   similarity. A dedicated vector database was rejected to avoid another
   service to operate.
3. **Row-level multi-tenancy.** Every query is scoped by organization.
   Isolation is enforced in one place and covered by tests.
4. **Docker for local development and CI**, so every environment runs the same
   PostgreSQL version with the same extensions.

## Consequences

- Isolation bugs would leak data between companies, so scoping needs
  dedicated tests.
- pgvector is enough for a moderate number of chunks. A much larger corpus
  would require index tuning or a dedicated vector store.