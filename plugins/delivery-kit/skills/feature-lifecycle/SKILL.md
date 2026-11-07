---
name: feature-lifecycle
description: Run a fix or feature through the full engineering lifecycle (Understand → Plan → Implement → Test → Review → Ship) with ECC agents, Plan Mode, test-first development, a convention-aware review, and hooks that block stopping, committing or pushing while code is untested, unreviewed, or newer than the code graph. Use whenever the user asks to implement, fix, build, add or change something in the codebase, for example "fix the score delete bug" or "add refund support", even if they don't mention a lifecycle.
---

# Feature Lifecycle

Take one fix or feature from "what's there today" to "ready to ship", with an approval gate after planning and checks that the hooks enforce after testing and review.

Request: `$ARGUMENTS`

## 0. Load the project profile

Run `delivery-kit profile show` and read the result. It tells you:

- the stack (`project.stack`, for example `nextjs`, `express`, `prisma`)
- the code paths and docs
- the targeted test command (`tests.command`), or one command per part of a full-stack repo (`tests.suites`)
- the type-check and lint commands (`tests.checks`)
- the data layer (`data.orm`, `data.schema`, `data.migrations`, `data.check_command`)
- the commit format, and whether a code graph exists

If there is no `.delivery-kit.json`, say so once and suggest `delivery-kit profile init`, which detects the stack and writes one. Then carry on with the defaults.

Run `delivery-kit brief --read-only` and keep its output: it's the project brief that starts every agent prompt in the read-only phases. Use `delivery-kit brief` (without `--read-only`) for agents that may write.

Work out whether this is a `fix` or a `feature`, choose a short slug, and start:

```
delivery-kit lifecycle start <fix|feature> <slug>
```

This creates `<lifecycle.state_dir>/<slug>/` (gitignored), where the plan goes. Move between phases with `delivery-kit lifecycle phase <name>` so the user can follow along with `status`. Only one lifecycle can be active at a time. If one is already active, ask the user whether to finish it or abort it. The session that runs `start` owns the lifecycle and only that session is gated; other sessions keep only the commit and PR format rules. If `status` shows no `owner` (for example after resuming in a new session), run `delivery-kit lifecycle claim`.

For a small, obvious change (a one-line fix with a clear test), keep Understand and Plan short, but don't skip Test or Review.

## How the hooks hold you to this

- Any edit to a file matching `paths.code` (and not `paths.exclude`) marks the work as untested. With `tests.suites`, it marks only the suite whose `paths` contain the file (for example `web` for `apps/web/…`), and only a passing run of **that** suite clears it. `delivery-kit lifecycle status` lists `untested_suites`. A change that spans the web app and the API needs both suites run.
- If a code graph exists, the same edit marks the graph stale. Only a successful `graph.update_command` (default `graphify update .`) clears it.
- Stopping while code is untested, or while the review has open Critical/High findings, is blocked once with a reason. If you really have to stop (for example to ask the user a question), say why plainly.
- `git commit`, `git push` and `gh pr create` are denied until the code is tested, the graph is current, and a review with zero open Critical/High has been recorded.
- Always, even with no lifecycle active: commit messages and PR bodies must follow `git.commit` and `git.pr` in the profile. Those project rules override any default attribution instructions.
- `LIFECYCLE_GATE=off` turns off the lifecycle checks (not the format rules). Suggest it only if the user asks.

Don't satisfy the hooks in ways that defeat their purpose, such as running an unrelated test to clear the untested mark. Run the tests that cover what you changed.

## ECC agents

Every ECC agent prompt starts with the project brief, then: the task, the relevant files, and "Return at most ~700 words."

If an `ecc:*` agent type isn't available, spawn `general-purpose` with "Read `~/.claude/plugins/cache/ecc/ecc/*/agents/<name>.md` and adopt it as your role" at the top of the prompt. If ECC isn't installed, do that phase's work yourself and tell the user (`delivery-kit doctor` checks for it).

Treat agent output as leads. Verify anything you act on by reading the cited code.

## 1. Understand (read-only)

Output: a short note covering the affected files, the code path, cross-module dependencies, existing tests and relevant docs.

- If the profile shows a code graph, start there: `graphify query "<the request in your own words>"`, then `graphify affected "<main symbol>"` for the blast radius and `graphify path "<A>" "<B>"` for how two modules connect. Read raw files only for the lines the graph located. Don't assume the graph is current; check what it says against the code.
- Read the files in `paths.conventions`, any matching `paths.plans`, the relevant `paths.api_docs`, and the code path itself.
- Spawn `ecc:code-explorer` to trace the path, its callers and its tests. For a change that spans several modules, run `/delivery-kit:architecture-assessment <modules>` instead.
- For a fix, pin down the failing input or state precisely enough to write a test for it.
- For a change to a high-risk subsystem (payments, auth, data migration), use `/delivery-kit:design-proposal <subsystem>` as the Understand and Plan phases, then continue from Implement.

Don't edit anything in this phase.

## 2. Plan (Plan Mode)

Output: a reviewed technical plan that the user approves.

Enter Plan Mode. Spawn these in one message so they run in parallel:

- `ecc:architect`, always: design, layering, fit with the existing modules.
- `ecc:database-reviewer`, if models, schemas, constraints or migrations change.
- `ecc:security-reviewer`, if authentication, permissions, tenancy or scope boundaries (`project.scope_boundaries`), payments or personal data are involved.

Give their verified output to `ecc:planner` and ask for ordered, PR-sized steps. The plan covers:

1. Requirements and acceptance criteria. For a fix, the exact failing case.
2. Design, and where it touches other modules.
3. Data changes: models, constraints, and migrations that are safe under the project's deploy rules (`paths.deployment_rules`, if set). With Prisma: the `schema.prisma` change, the migration name, and whether the generated `migration.sql` needs hand-editing (renames, `NOT NULL` with a backfill, `CREATE INDEX CONCURRENTLY`). See the Migrations section of `${CLAUDE_PLUGIN_ROOT}/skills/api-review/references/stacks/prisma.md`.
4. API contract changes and the doc updates they need in `paths.api_docs` / `paths.docs`.
5. Tests: the failing (red) test(s) to write first for each step.
6. Ordered implementation steps.
7. Deploy notes, and any new settings or environment variables. Name them and ask the user for values; never read secret files.

Present it with ExitPlanMode. The user's approval is the gate. Once approved, save the plan to the lifecycle's `plan.md` and run `phase implement`.

## 3–4. Implement and Test (test first)

Output: working code with passing targeted tests.

For each plan step:

1. Write the failing test first and run it with the command of the suite that owns the file (`tests.suites`, or `tests.command`). Confirm it fails for the expected reason.
2. Implement the smallest change that makes it pass. `ecc:tdd-guide` can help design tests for larger features; use the profile's test commands, not the generic ones ECC skills suggest. ECC's pattern skills are useful references for the stack: `prisma-patterns`, `nextjs-turbopack`, `react-patterns`, `backend-patterns`, `typescript-patterns`, `django-patterns`.
3. Re-run that test, then the test files covering the changed code, until they pass.

Follow the house rules in the brief and the conventions files. Use Edit/Write, not shell heredocs. Update the API docs alongside the code.

Data changes:

- **Prisma:** edit `data.schema`, then create the migration with `prisma migrate dev --name <name>` against the local development database only. Read the generated `migration.sql` and hand-edit it if it drops and re-adds a renamed column, adds `NOT NULL` without a default, or creates an index on a large table. Run `prisma generate` if the client isn't regenerated automatically.
- **Never**, in any environment, run `prisma migrate reset`, `prisma db push --force-reset` or `--accept-data-loss`. Never run `prisma migrate deploy` or `db push` against a shared database. If a reset seems necessary, stop and ask the user.
- **Other ORMs:** use the project's migration command, and check it with `data.check_command`.

When all steps are done, run `phase test`, then:

- every suite in `untested_suites`, plus the tests for each module you touched
- the quality checks in `tests.checks` (type-check, lint). A type error is a failing test.
- `data.check_command`, if the data layer changed

Offer, but don't start without asking, a background full-suite run (`tests.full_suite.command`, on its own lane via `tests.lane_command` if the project uses lanes) and the end-to-end tests (`tests.e2e_command`).

If a code graph exists, run the update command (`graph.update_command`), then `graphify query` for one of the new symbols to confirm the graph reflects the change.

If the plan turns out to be wrong, stop, explain why, and go back to Plan Mode with a revised plan. Don't quietly change course.

## 5. Review

Output: review findings, and corrections for them.

Run `phase review`, then:

- `/delivery-kit:api-review` on the branch diff, if endpoints changed. It brings in the ECC reviewers for the stack and merges their findings.
- `ecc:react-reviewer` for changed React and Next.js UI code (components, hooks, client state).
- `ecc:code-reviewer` for changed code outside the endpoints (background jobs, queues, CLI scripts, migrations).
- `ecc:architect` again if the change touches more than one module, comparing what was built with the approved plan.
- `ecc:silent-failure-hunter` for integrations, payments, or anything with broad exception handling.

Fix every Critical and High finding, re-run the affected tests, then record the result:

```
delivery-kit lifecycle review --open-high <number of Critical/High still open>
```

Leave a Critical or High open only if the user explicitly agrees, and then list it under Ship. Medium and Low findings go to the user as a list; fix them only if they're cheap and inside the plan's scope.

## 6. Ship

Output: a ship summary, with the change ready for the user to commit.

Run `phase ship` and work through [references/ship-checklist.md](references/ship-checklist.md). Then give the user:

- What changed and why, linking to the main files.
- The tests run, with results.
- The review outcome: what was fixed, and what's left at Medium/Low.
- Migration, deploy and configuration notes.
- A suggested commit message in the profile's format.

Commit, push or open a PR only when the user asks. If you're on `git.main_branch` or `git.integration_branch`, suggest a branch first. Then end the lifecycle:

```
delivery-kit lifecycle end
```

`end` refuses while code is untested, the graph is stale, or a Critical/High is open. Use `end --abort` only if the user abandons the change.
