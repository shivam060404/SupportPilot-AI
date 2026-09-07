# Database operations

PostgreSQL is the system of record for tickets, approvals, audit events, and
conversation transcripts. SQLAlchemy owns sessions and repositories; Alembic
owns schema changes. The API performs a non-mutating connection check during
startup, while migrations are applied explicitly with `alembic upgrade head`.

The local Compose service exposes PostgreSQL on port `5432`, so pgAdmin or any
PostgreSQL GUI can connect with the values in `.env`. Runtime Chroma files are
kept under `data/runtime/` and are not source-controlled. A future migration
to pgvector should be considered only if filtering, transactional consistency,
or scale requires a relational vector index.
