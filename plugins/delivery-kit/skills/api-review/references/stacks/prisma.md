# Prisma checklist

Use when `project.stack` includes `prisma` (or `data.orm` is `prisma`). Give this list to `ecc:database-reviewer` along with `data.schema`. ECC's `prisma-patterns` skill holds general patterns; this list is for defects.

## Data exposure
- Queries returned to clients use `select` (or a mapper) rather than returning whole models. Without it, password hashes, tokens and internal fields go out with the response. `include` returns every scalar of the related model too.
- `omit` (Prisma 5.13+/6) or a global omit for sensitive fields, if the project uses it, isn't overridden by a later `select`.

## Authorization in queries
- `findUnique({ where: { id } })` followed by a separate ownership check is fine; `update` / `delete` by id alone is not. Use `updateMany({ where: { id, ownerId } })` and check `count`, or check ownership in the same transaction.
- Nested writes (`connect`, `connectOrCreate`, `set`) can attach records the user doesn't own; check where the connected ids come from.
- Mass assignment: `data: req.body` / `data: input` passes through fields like `role` or `ownerId`.

## Queries
- N+1: a `findMany` followed by per-row queries in a loop or `Promise.all(map(...))`; use `include`, `select` with relations, or one `findMany({ where: { id: { in } } })`.
- `findMany` without `take` on a table that grows; cursor pagination for large sets.
- `$queryRawUnsafe` / `$executeRawUnsafe` with interpolated input is SQL injection. `$queryRaw` with the tagged template is parameterised; `Prisma.raw()` inside it isn't.
- Filters on columns without an index (`@@index`) on hot paths.

## Transactions and concurrency
- Multi-step writes (create order + decrement stock + record payment) run in `prisma.$transaction(async (tx) => …)`, and every query inside uses `tx`, not `prisma`. Using `prisma` inside the callback escapes the transaction.
- Read-then-write on balances, counters or statuses: use atomic updates (`{ increment: 1 }`), a conditional `updateMany` with the expected state in `where`, or `SELECT … FOR UPDATE` via `$queryRaw` inside the transaction. Prisma has no `select_for_update` equivalent.
- `upsert` is not race-free without a unique constraint on the `where` fields; concurrent upserts can raise `P2002`.
- `P2002` (unique violation), `P2025` (record not found) and `P2003` (foreign key) are mapped to 409/404/400, not surfaced as 500s.
- Interactive transactions have a timeout (default 5s); long work inside them fails under load.

## Schema
- Money uses `Decimal` (`@db.Decimal(p, s)`), not `Float`. Arithmetic on `Prisma.Decimal` uses its methods, not JavaScript numbers.
- Uniqueness that matters is enforced with `@unique` / `@@unique`, not only checked in code. On PostgreSQL a nullable column in `@@unique` doesn't prevent duplicates when it's NULL.
- `onDelete` on relations is deliberate: `Cascade` on a parent can delete financial or audit rows.
- Soft-delete fields are filtered everywhere they need to be (a Prisma extension or middleware, or every query).

## Migrations
- Each migration in `data.migrations` is reviewed as SQL (`migration.sql`), not only as a schema diff.
- Unsafe with old and new code running side by side: `DROP COLUMN`, `DROP TABLE`, renames (Prisma generates drop + add, which loses data unless hand-edited to `RENAME`), `ALTER COLUMN … SET NOT NULL` without a default or backfill, narrowing a type, removing an enum value still written by running code.
- `CREATE INDEX` on a large PostgreSQL table locks writes; hand-edit to `CREATE INDEX CONCURRENTLY` (in its own migration, since it can't run inside a transaction).
- Data backfills are separate, idempotent steps, not mixed into a schema change.
- Shared environments use `prisma migrate deploy`; `prisma migrate dev`, `prisma db push` and `prisma migrate reset` are for local databases only.

## Client lifecycle
- One `PrismaClient` per process (a module singleton, with the `globalThis` pattern in Next.js dev). A client per request exhausts connections.
- Serverless deployments use a pooler (PgBouncer, Prisma Accelerate, Neon/Supabase pooling) and set `connection_limit` appropriately.
- `prisma generate` runs in the build, so the client matches the schema in production.
