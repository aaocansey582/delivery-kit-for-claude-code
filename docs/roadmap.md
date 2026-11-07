# Roadmap

The roadmap comes from recurring work in real sessions: the commands and requests that were repeated most often across a team's Claude Code history.

## 0.1: Foundation (this release)

- Plugin and marketplace manifests, the `delivery-kit` CLI and the project profile.
- Skills: `feature-lifecycle`, `api-review`, `architecture-assessment`, `design-proposal`.
- Hooks: lifecycle gate (tests, review, graph freshness) and the commit/PR format rules.
- Graphify integration.
- Next.js, Express and Prisma support: stack detection (`profile init`), per-suite test tracking for monorepos, quality checks, the `data` section, and review checklists.

## 0.2: Guard hooks

| Hook | Behaviour |
|---|---|
| `secrets-guard` | Deny Read, Grep and Bash access to `guards.secret_files` |
| `protected-branch-guard` | Deny commit and push on protected branches, and deny force-push |
| `path-guard` | Opt-in. Off by default, so full-stack projects edit every layer freely. A project lists paths in `guards.protected_paths`, each with a mode: `warn` (allow and remind), `ask` (confirm first) or `deny`. Use it when another team owns a part of the repo, for example a frontend built from the API docs |
| `migration-safety` | After a migration is written, flag unsafe changes against `paths.deployment_rules`: drops, renames (including Prisma's drop + add), `NOT NULL` without a default, non-concurrent indexes, removed enum values. Prisma (`migration.sql`) and Django rulesets |
| `destructive-command-guard` | Deny `prisma migrate reset`, `prisma db push --force-reset` / `--accept-data-loss`, `prisma migrate deploy` with a non-local `DATABASE_URL`, and `DROP DATABASE` / `TRUNCATE` through `psql` |
| `read-only-mode` | Deny edits while an audit skill is running |

## 0.3: Shipping and docs

- `ship-changes`: commit, PR, merge and team-handoff messages in the project's format, plus printed (never run) branch promotion commands.
- `api-docs-sync`: update `paths.api_docs` from the diff and run the docs build and link check.
- `targeted-test-runner` agent: picks tests from the diff, runs them on a lane, and returns only the summary.
- `docs-drift-check` and `session-context` hooks.

## 0.4: Audits, planning and operations

- `code-audit`: read-only audits in `security`, `flow`, `performance` and `root-cause` modes.
- `work-breakdown`: phased tasks for parallel sessions, with separate test lanes and a PR message per phase.
- `endpoint-scaffold`: a new endpoint following the project's layering and permission checklist.
- `environment-diagnostics`: diagnostic commands for a server, and interpretation of their output.
- `plain-explanation`: short plain-language explanations with optional diagrams.
- `convention-reviewer` agent.

## 1.0

- `claude plugin eval` suites for every skill.
- More stack checklists: NestJS, Fastify, tRPC, Drizzle.
