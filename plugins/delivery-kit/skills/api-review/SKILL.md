---
name: api-review
description: Review backend API endpoints (routes, handlers or views, request/response schemas or serializers, services, permissions, queries, tests) against the project's own conventions, with ECC stack and security/database reviewer agents, and report verified findings by severity. Use whenever the user asks to review, audit, sanity-check or look over an API, endpoint, view, serializer, controller, service, module or branch/PR in the backend, even if they don't say "API review".
---

# API Review

A read-only review of backend endpoints. The goal is to find real defects (wrong behaviour, security gaps, data-integrity risks), not to restate generic framework advice. Every finding points at code and says what concretely goes wrong.

## 1. Load the project and pick the target

Run `delivery-kit profile show` and `delivery-kit brief --read-only`. Keep the brief for the agent prompts.

Target: `$ARGUMENTS`

- If it names a module, path, endpoint or service, review that.
- If it's empty, review what the current branch changes compared with `git.main_branch` (`git diff <main>...HEAD --stat`, plus uncommitted changes). If there is no diff, review the most recent commits that touched `paths.code`.
- If you still can't tell what to review, ask instead of guessing.

State the target in one line at the top of the report so the user can correct it.

If the profile shows a code graph, use it to map the target before reading source: `graphify query "<endpoint or feature>"` for the files involved and `graphify affected "<changed symbol>"` for callers the diff doesn't show. Confirm what it says against the code.

Follow each endpoint the whole way down: route → middleware → handler → input validation → service → data access and schema → response → tests. Most real bugs sit in the service and data layers. What counts as an endpoint depends on the stack:

- **Next.js:** route handlers (`app/**/route.ts`), every exported Server Action (`"use server"`), `pages/api/**`, and `middleware.ts`.
- **Express and similar:** routers and the `app.use` chain that runs before them.
- **Django and similar:** URL patterns → views → serializers.

## 2. Know the house rules

Read only the parts that apply. These define what "correct" means in this project:

- The files in `paths.conventions` (layering, response envelope, error mapping, permission model).
- `paths.api_docs`: the published endpoint docs. Docs that no longer match the code count as a finding.
- `paths.deployment_rules`, if a migration is in scope.
- `data.schema` (for example `prisma/schema.prisma`) for the models behind the target.
- A checklist for **each** entry in `project.stack` that has one in [references/stacks/](references/stacks/): [nextjs.md](references/stacks/nextjs.md), [express.md](references/stacks/express.md), [prisma.md](references/stacks/prisma.md), [django-drf.md](references/stacks/django-drf.md). A full-stack project usually needs several. If none matches, use the general checklist in step 4 alone.

## 3. Bring in the ECC reviewers

Once the target is fixed and you've listed its files, spawn these in one message so they run in parallel with your own pass:

- The stack reviewer(s) for the code in the target:

  | Stack in the target | Reviewer |
  |---|---|
  | `nextjs` | `ecc:react-reviewer` (Server/Client Components, Server Actions, hooks) and `ecc:typescript-reviewer` (route handlers, server code) |
  | `express`, `fastify`, `nestjs`, `hono`, other Node | `ecc:typescript-reviewer` |
  | `django`, `django-drf` | `ecc:django-reviewer` |
  | `fastapi` | `ecc:fastapi-reviewer` |
  | other | `ecc:python-reviewer`, `ecc:go-reviewer`, `ecc:java-reviewer`, `ecc:php-reviewer`, `ecc:ruby-reviewer`, `ecc:rust-reviewer` or `ecc:csharp-reviewer`, by language |

  Give each one the matching stack checklist from step 2.
- `ecc:security-reviewer`: authentication, permissions, tenancy and ownership scope (`project.scope_boundaries`), IDOR, injection, secrets or personal data in responses and logs, and for Next.js the server/client boundary and `NEXT_PUBLIC_*` variables.
- `ecc:database-reviewer`: constraints, transactions and locking, races, N+1 queries, indexes, migrations. With Prisma, give it `data.schema`, the relevant `migration.sql` files and [prisma.md](references/stacks/prisma.md).

Skip the agents for a small target (roughly under 300 lines, or one small file) unless the user asks. Your own pass is enough there.

Start every prompt with the brief, then the agent's focus and the file list, then: "For every finding, say what goes wrong and with what input or state. Skip style nits. At most ~600 words."

If an `ecc:*` agent type isn't available, spawn `general-purpose` and start its prompt with "Read `~/.claude/plugins/cache/ecc/ecc/*/agents/<name>.md` and adopt it as your role." If ECC isn't installed, carry on with your own pass and say so in the report.

## 4. What to check (your own pass)

Places to look, not boxes to tick. Leave out areas where you found nothing. You own items 2, 9 and 10, and everything that depends on the house rules; agents rarely catch those.

1. **Authentication and authorization.** Does every method require authentication and the right permission? Is object-level access (tenant, ownership, assignment) enforced for every method, not only the main one? Can one scope's data be read or changed from another?
2. **State and lifecycle guards.** When one operation checks status (active, closed, published, approved), do its sibling operations check it too? A missing guard on delete or single-item update next to a guarded batch operation is a typical bug.
3. **Validation.** Field bounds, duplicates, list size caps. Do the batch path and the single-item path apply the same rules?
4. **Service layer and transactions.** Is business logic where the conventions say it belongs? Is each multi-step write (save + audit + recalculation) atomic?
5. **Integrity and concurrency.** Do unique constraints actually hold (on PostgreSQL, a nullable column in a unique rule doesn't stop duplicates when NULL)? Can a read-then-write race produce an integrity error, duplicates or lost updates?
6. **Queries.** N+1 queries from relation access in loops, per-row queries in uploads. Query-count tests with a single parent object hide per-parent N+1s.
7. **Pagination and filtering.** Do list endpoints follow the project's pagination rules? Are filters validated and scoped by permissions?
8. **Errors.** Domain errors rather than bare not-found or value errors, correct status codes, no unhandled path that ends in a 500, accurate failure messages in batch results.
9. **Audit trail.** Is every change to `project.sensitive_data` recorded where the project keeps audit logs, including derived changes?
10. **Tests.** For each finding, is there a test that would have caught it? List missing coverage separately: denial paths, guards on sibling operations, query counts with several parents.

## 5. Merge and verify

1. **Verify.** Open the cited line for every agent finding at Medium or above. Drop findings that don't hold; keep ones you can't fully confirm, marked Suspected.
2. **Drop noise.** Generic advice, style comments, and anything that contradicts the house rules.
3. **De-duplicate.** Merge duplicates into one finding and note who raised it (`you`, `stack`, `sec`, `db`). Independent agreement is worth stating.
4. **Re-rate** everything on the scale below.

## 6. Severity

- **Critical:** authentication bypass, data exposure across `project.scope_boundaries`, privilege escalation, silent corruption of `project.sensitive_data`.
- **High:** a missing permission, scope or state guard on a write; a data-integrity hole (duplicates, writes with no audit record); a common path that ends in a 500.
- **Medium:** non-atomic multi-step writes, races that need concurrent requests, inconsistent validation between paths, N+1 on a hot path, missing pagination.
- **Low:** N+1 on small sets, misleading messages, log noise, duplicated logic, docs that no longer match the code.

If a finding depends on a race or behaviour you haven't confirmed, still report it, but say so.

## 7. Verifying with tests (optional)

Reading the code is the default. If running something would settle a doubtful finding, run only targeted tests, using the suite that covers the file (`tests.suites`, or `tests.command`). Never run the full suite or end-to-end tests, never run commands that write to a database, and never read secret files.

## 8. Report

```
**Target:** <what was reviewed>   **Reviewers:** you + stack, sec, db (or "you only")

## Overall
2–4 sentences: what's solid, and where the risk is concentrated.

## Critical / ## High / ## Medium / ## Low
**N. <one-line claim>** — Confirmed|Suspected · raised by you/stack/sec/db
[file:LINE](path/to/file#LLINE)
What goes wrong, with what input or state, and the suggested fix in one or two sentences.

## Missing tests
- <test that is missing> (covers finding N)

## Dropped agent findings
One line: how many were dropped and why.
```

Leave out empty severity sections, number the findings, and make links relative to the repo root.

## 9. Don't modify files

This is a review. Don't edit, create or delete files, or run migrations, unless the user explicitly asks. End by offering to fix specific findings by number.
