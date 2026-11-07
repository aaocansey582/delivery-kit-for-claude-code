# Configuration reference

The profile is a JSON file named `.delivery-kit.json` at the project root. All fields are optional: anything you leave out comes from the [defaults](#defaults). Personal overrides go in `.claude/delivery-kit.local.json` with the same shape, and are merged on top. Objects merge key by key, while lists and strings replace the default.

Start from a generated profile rather than a blank file: `delivery-kit profile init` [detects the stack](#what-profile-init-detects) and writes one. Run `delivery-kit profile check` after editing. It reports invalid regexes, unknown top-level keys, missing files, and test patterns that don't match their commands.

## `project`

| Field | Type | Used for |
|---|---|---|
| `name` | string | Messages and the subagent brief |
| `summary` | string | First line of the subagent brief: what the system is, in one sentence |
| `stack` | list of strings (a single string also works) | Picks the reviewers and checklists in `api-review`. A full-stack project lists several, for example `["nextjs", "express", "prisma", "typescript"]`. Checklists exist for `nextjs`, `express`, `prisma` and `django-drf`; reviewers are mapped for those plus `fastify`, `nestjs`, `hono`, `react`, `django`, `fastapi`, `go`, `java`, `php`, `ruby`, `rust` and `csharp` |
| `sensitive_data` | list of strings | What a Critical "silent corruption" means here, for example `["orders", "payment records"]` |
| `scope_boundaries` | list of strings | What a Critical "data exposure across …" means, for example `["organisation", "user"]` |

## `paths`

Path patterns use shell-style globs relative to the project root; `*` matches across `/`.

| Field | Type | Used for |
|---|---|---|
| `code` | list of globs | Edits matching these mark the lifecycle untested |
| `exclude` | list of globs | Edits matching these never do, even inside `code` (the defaults skip `node_modules`, `.next`, `dist`, `public`, lockfiles, docs) |
| `docs` | list of paths | General docs the skills read and update |
| `api_docs` | list of paths | Endpoint docs or OpenAPI files; drift between these and the code is a finding |
| `conventions` | list of paths | The docs that define "correct" for reviews. Named in the brief |
| `deployment_rules` | path | Migration and deploy rules (for example zero-downtime constraints) |
| `plans` | list of globs | Implementation plans, so the skills don't re-plan finished or on-hold work |

## `tests`

A single-app project sets `command` and `match`. A full-stack repo where each part has its own test runner uses `suites` instead (or as well).

| Field | Type | Used for |
|---|---|---|
| `command` | string with `{target}` | The targeted test command, given to Claude and every agent |
| `match` | regex | Which Bash commands count as runs of `command`. Must match it |
| `suites` | list of [suites](#test-suites) | One test command per part of a full-stack repo, each tracked separately |
| `checks` | list of strings | Quality checks run before shipping: type-check, lint. Claude treats a failure like a failing test |
| `e2e_command` | string | End-to-end tests (for example Playwright). Offered, never run without asking, never tracked by the gate |
| `lane_command` | string with `{lane}` and `{target}` | For parallel sessions with separate test databases |
| `pass_pattern` | regex | Output that means a run passed |
| `fail_pattern` | regex | Output that means it failed (checked first) |
| `full_suite.command` | string | Offered for a background run, never started without asking |
| `full_suite.note` | string | Why to avoid it casually, for example "about 35 minutes" |

The default pass and fail patterns understand pytest, Jest, Vitest, Mocha, Playwright, `node --test` and `go test` summaries. A run with no recognisable summary changes nothing.

### Test suites

```json
"suites": [
  {
    "name": "web",
    "paths": ["apps/web/*"],
    "command": "cd apps/web && pnpm exec vitest run {target}",
    "match": "(?=[\\s\\S]*(apps/web|@acme/web))[\\s\\S]*(\\bvitest\\b|\\bpnpm\\b[^\\n;&|]*\\btest\\b)"
  }
]
```

| Field | Used for |
|---|---|
| `name` | Shown in `lifecycle status` (`untested_suites`) and in gate messages |
| `paths` | Edits under these globs mark this suite untested |
| `command` | How to run it, with `{target}` relative to where the command runs |
| `match` | Which Bash commands count as running it. The generated form needs the package's folder or name **and** a test runner in the command, so `pnpm --filter @acme/web test` counts but a run of the API's Jest suite doesn't |

An edit that matches no suite's `paths` marks the `default` suite, which any command matching `tests.match` clears.

## `data`

| Field | Type | Used for |
|---|---|---|
| `orm` | `"prisma"`, `"django"` or any label | Prisma adds migration rules to the brief and the lifecycle, including a ban on destructive Prisma commands |
| `schema` | path | The schema file the reviews and the ER diagrams are built from, for example `prisma/schema.prisma` |
| `migrations` | glob | Where migrations live, for example `prisma/migrations/*` |
| `check_command` | string | Run before shipping when the data layer changed, for example `npx prisma validate && npx prisma migrate status` (`migrate status` needs `DATABASE_URL` to reach a development database) |

## `git`

| Field | Type | Used for |
|---|---|---|
| `main_branch` | string | Default review base (`git diff <main>...HEAD`) |
| `integration_branch` | string | Treated like `main_branch` when suggesting a feature branch |
| `commit.single_line` | bool | Deny multi-line messages, several `-m` flags and heredoc bodies |
| `commit.subject_pattern` | regex | The subject must match, for example Conventional Commits |
| `commit.forbid_patterns` | list of regexes | Deny if a message or any commit argument matches, for example `"co-authored-by"` |
| `pr.forbid_patterns` | list of regexes | Deny `gh pr create/edit` if the title or body matches |

## `guards`

| Field | Type | Used for |
|---|---|---|
| `secret_files` | list of globs | Named in every brief as never-read; 0.2 adds a hook that blocks reading them. Defaults cover `.env`, `.env.local`, `.env.*.local` and nested `apps/*/.env*` |
| `secret_file_exceptions` | list of globs | Templates that are safe to read, for example `.env.example` |
| `protected_paths` | object of glob → `warn`, `ask` or `deny` | (0.2) Paths another team owns. **Empty by default:** nothing is guarded unless the project lists it, so full-stack projects aren't restricted. Example: `{"apps/mobile/*": "ask"}` |

## `lifecycle`

| Field | Type | Used for |
|---|---|---|
| `enabled` | bool | `false` turns off the lifecycle gates for this project |
| `state_dir` | path | Where `active.json` and the plan folders go. Gitignore it |

## `graph`

See [Graphify integration](graphify.md).

| Field | Type | Used for |
|---|---|---|
| `provider` | `"graphify"` or `""` | `""` disables the graph integration |
| `dir` | path | Graph output folder; the integration is active when `<dir>/graph.json` exists |
| `update_command` | string | What Claude runs to refresh the graph after code edits |
| `update_match` | regex | Which Bash commands count as a graph update |
| `require_before_ship` | bool | Block commit/push/PR while the graph is older than the edits |

## `agents`

| Field | Type | Used for |
|---|---|---|
| `house_rules` | list of strings | Short rules appended to every subagent brief, for example "Only packages/db imports PrismaClient" |

## What `profile init` detects

| It reads | To set |
|---|---|
| `pnpm-lock.yaml`, `yarn.lock`, `bun.lock(b)`, `package-lock.json`, `packageManager` | How commands run: `pnpm exec`, `yarn`, `bunx` or `npx` |
| `workspaces` in `package.json`, `pnpm-workspace.yaml` (falls back to `apps/*`, `packages/*`, `services/*`) | One test suite per workspace package that has a test runner |
| `next`, `express`, `fastify`, `@nestjs/core`, `hono`, `react` dependencies | `project.stack` and the summary; an `app/` folder adds "(App Router)" |
| `vitest`, `jest`, `mocha` | The test command and its match pattern |
| `@playwright/test` | `tests.e2e_command` |
| `typescript` or `tsconfig.json`, and `typecheck` / `lint` scripts (root scripts win in a Turborepo) | `tests.checks` |
| `prisma` / `@prisma/client` and the schema (`prisma/schema.prisma`, a `prisma/schema/` folder, or `package.json` `prisma.schema`) | The `data` section, with the database provider in the summary |
| `manage.py` and `djangorestframework` | Django stack, pytest or `manage.py test`, `makemigrations --check` |
| `origin/HEAD`, `master`/`develop` branches | `git.main_branch`, `git.integration_branch` |
| `commitlint.config.*`, `.commitlintrc*`, `@commitlint/*` | A Conventional Commits `subject_pattern` |
| `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `docs/architecture.md`, `CONTRIBUTING.md`, `openapi.*` | `paths.conventions`, `paths.api_docs` |

It never guesses `sensitive_data` or `scope_boundaries`; fill those in yourself. Preview without writing: `delivery-kit profile init --print`.

## Defaults

With no profile, the plugin behaves like this:

- Any file counts as code except docs, Markdown, `.claude/`, `.github/`, `node_modules/`, `.next/`, `dist/`, `build/`, `coverage/`, `.turbo/`, `public/`, lockfiles and `graphify-out/`.
- Common test runners are recognised: Vitest, Jest, Mocha, Playwright, `node --test`, `npm/pnpm/yarn/bun test`, pytest, tox, nox, RSpec, PHPUnit, `go test`, `cargo test`, `dotnet test`, `manage.py test`, Maven and Gradle.
- No commit or PR format rules apply.
- Lifecycle state goes in `.claude/lifecycle/`.
- The Graphify integration activates automatically if `graphify-out/graph.json` exists.

`delivery-kit profile show` prints the merged result.

## Examples

- [examples/nextjs-prisma.json](../examples/nextjs-prisma.json): a Next.js App Router app with Prisma, Vitest and Playwright.
- [examples/express-prisma.json](../examples/express-prisma.json): an Express API with Prisma and Jest, with per-lane test databases.
- [examples/fullstack-monorepo.json](../examples/fullstack-monorepo.json): a pnpm and Turborepo monorepo with a Next.js web app, an Express API, a Prisma package and shared contracts, each with its own test suite.
- [examples/django-drf-docker.json](../examples/django-drf-docker.json): Django REST Framework with tests in Docker.
- [examples/minimal.json](../examples/minimal.json): just a test command.
