# Changelog

## 0.1.0 (unreleased)

- First release: the `feature-lifecycle`, `api-review`, `architecture-assessment` and `design-proposal` skills.
- Lifecycle gate hooks (untested code, open Critical/High review findings, stale code graph) with per-session ownership.
- Commit and PR format rules from the project profile.
- `delivery-kit` CLI: `lifecycle`, `brief`, `profile show|check|init`, `doctor`.
- Graphify integration.
- Next.js, Express and Prisma support: `profile init` detects the stack, package manager, workspaces, test runners, TypeScript/lint scripts, the Prisma schema and commitlint; per-suite test tracking for monorepos; `tests.checks`, `tests.e2e_command` and the `data` section; review checklists for Next.js, Express and Prisma; Prisma rules in briefs and the lifecycle.
- `project.stack` accepts a list.
