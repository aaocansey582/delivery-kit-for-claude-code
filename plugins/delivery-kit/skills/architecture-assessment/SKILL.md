---
name: architecture-assessment
description: Read-only architectural assessment of a codebase — how its modules fit together, how requests flow, the data model across modules, and structural weaknesses with security and performance concerns — checked against the project's own docs and its code graph. Use when the user asks to investigate, map, explain or assess the architecture of the codebase or an area of it (a service, a set of modules, a concern such as auth or deploys), or asks where the design is weak, even if they don't name this skill. For endpoint-level review use api-review instead.
---

# Architecture Assessment

A read-only investigation of how the system is built and where its structure is weak. Projects usually document their intended architecture, so the value is in checking that documentation against the code and finding what it misses. Don't restate generic framework advice.

## 1. Load the project and pick the scope

Run `delivery-kit profile show` and `delivery-kit brief --read-only`. Keep the brief for the agent prompts.

Scope: `$ARGUMENTS`

- If it names an area (a directory, one or more modules, or a concern such as "auth" or "deploys"), investigate that.
- If it's empty, investigate the main code paths in `paths.code`, with one short section on how other parts of the repo (for example a frontend) talk to them.
- If the scope is too large to cover with evidence, say which parts you covered in depth and which you only skimmed.

State the scope in one line at the top of the report so the user can correct it.

## 2. Use the code graph first

If the profile shows a code graph:

- Check it's current before trusting it: compare its build time (file timestamp of `<graph.dir>/graph.json`) with `git log -1 --format=%cd -- <paths.code>`. If the code is newer, say so, and offer to run `graph.update_command` (it's AST-only and makes no API calls).
- Use `<graph.dir>/wiki/index.md` if it exists for broad navigation, and `graphify god-nodes` for the architectural hubs.
- Use `graphify query "<question>"`, `graphify path "<A>" "<B>"` and `graphify explain "<concept>"` for focused questions. Read `<graph.dir>/GRAPH_REPORT.md` only when those don't surface enough.
- Read raw source only for lines the graph or an earlier read already located.

Treat the graph as a map, not as evidence. Every finding still cites code you read.

## 3. Read the docs

Read what the project says about itself: the files in `paths.conventions`, `paths.deployment_rules`, the `paths.docs` and `paths.api_docs` for the scope, and any `paths.plans` or ADRs.

Treat these as claims to verify. Summarise the documented architecture in a few lines and spend the report on what the code confirms, contradicts, or does that the docs don't mention.

## 4. Bring in the ECC agents

After reading the docs, spawn these in one message so they run in parallel while you trace request flows yourself:

- `ecc:architect`: modules, layering, cross-module dependencies and cycles, coupling and duplication.
- `ecc:database-reviewer`: the data model, constraints that protect invariants, invariants enforced only in application code, query patterns that degrade with data size.
- `ecc:security-reviewer`: cross-cutting security only: auth and token handling, permission registry gaps, scope checks that some paths skip, throttling, secrets, file storage, background job safety.

For a narrow scope, spawn only the agent that matches it, or none.

Start every prompt with the brief, then: "You are assessing the architecture. Scope: <scope>. The documented architecture is: <your ≤10-line summary>. Treat those docs as claims to check against the code. Do not run tests or management commands. Return findings first, at most ~800 words."

If an `ecc:*` agent type isn't available, spawn `general-purpose` and start its prompt with "Read `~/.claude/plugins/cache/ecc/ecc/*/agents/<name>.md` and adopt it as your role." If ECC isn't installed, do the whole assessment yourself and say so.

## 5. Investigate

1. **Modules.** For each module in scope (in a monorepo, each app and package): what it owns, its layers, and which other modules it imports from. Point out dependency cycles, and modules that reach into another module's internals instead of its public services. (`graphify path` and `graphify affected` make this fast.)
2. **Request flow.** Trace one or two representative requests end to end: route → authentication → authorization → validation → service → data access → response → error handling. Also trace one async path (a background job, queue consumer, webhook or scheduled task) and how it's registered. By stack:
   - **Next.js:** `middleware.ts` (and what its matcher skips) → Server Component data loading or route handler or Server Action → data access. Show where the server/client boundary sits, which modules are server-only, and what each cache layer (`fetch` cache, `unstable_cache` / `"use cache"`, revalidation) holds.
   - **Express:** the `app.use` chain in order → router → per-route middleware → handler → error middleware.
   - **Full stack:** how the frontend reaches the backend: Server Actions, its own route handlers, or a separate API. Note the shared packages (types, validation schemas, the database client) and whether both sides really use them.
3. **Data model.** Map the relationships, especially those that cross modules, as one Mermaid `erDiagram` per area. With Prisma, build it from `data.schema` (models, `@relation`, `@unique` / `@@unique`, `@@index`, `onDelete`). Note the constraints that protect important invariants, and the invariants that rely only on application code. Check which apps import the database client directly: in a monorepo, more than one writer to the same tables is a coupling risk.
4. **Architectural weaknesses.** Coupling, business logic in the wrong layer, duplicated logic across modules, inconsistent patterns, docs that disagree with the code, and migration or deploy patterns that break `paths.deployment_rules`.
5. **Security and performance.** Cross-cutting concerns only. Leave single-endpoint defects to `/delivery-kit:api-review` and mention it where an area needs one.

## 6. Merge, verify and evidence

1. **Verify.** Open the cited line for every agent finding at Medium or above. Drop claims that don't hold; mark the rest Confirmed or Suspected.
2. **De-duplicate** and note who raised each one (`you`, `arch`, `db`, `sec`).
3. **Drop out-of-scope findings**: generic advice and single-endpoint defects.
4. **Keep the diagrams yours**: build the `erDiagram` from models you've read.

Every finding cites code as a markdown link with a line number relative to the repo root, and says what goes wrong in this codebase and under what conditions.

## 7. Severity

- **Critical:** authentication bypass, data exposure across `project.scope_boundaries`, privilege escalation, silent corruption of `project.sensitive_data`.
- **High:** a structural gap that lets a whole class of writes skip a permission, scope or audit guard; a deploy or migration pattern that will cause downtime or data loss.
- **Medium:** coupling or duplication that makes changes risky, invariants enforced only in application code, a query pattern that degrades with data size on hot paths.
- **Low:** inconsistent conventions, stale docs, dead modules that confuse readers.

## 8. Report

Leave out any section with nothing to say.

1. **Scope**: one line, plus which agents ran and whether the graph was used (and current).
2. **Architecture summary**: at most ten lines: what the docs claim and whether the code matches.
3. **Modules**: a table: module, responsibility, depends on, notes.
4. **Request flow**: the traced paths as short numbered steps with code links.
5. **Data model**: the Mermaid diagrams, then notable constraints and invariants that lack one.
6. **Findings**: numbered, grouped by severity, each with Confirmed or Suspected, who raised it, a code link, what goes wrong, and a one-line direction.
7. **Docs out of date**: where the docs disagree with the code.

Keep it to about 1,500 words plus diagrams. Cut low-value findings before cutting evidence.

## 9. Don't modify anything

Don't edit, create or delete files, run migrations or commands that write, or run the test suite. Reading code, `git log`, `grep` and graph queries are fine (`graph.update_command` only if the user agrees). End by offering to fix specific findings by number, or to run `/delivery-kit:api-review` on an area that needs it.
