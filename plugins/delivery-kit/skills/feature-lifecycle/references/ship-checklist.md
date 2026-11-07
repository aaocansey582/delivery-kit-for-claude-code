# Ship checklist

Work through each item that applies and report anything that fails in the ship summary.

## Diff
- [ ] Read `git status` and the full `git diff` (plus `git diff <main_branch>...HEAD` on a branch). Every hunk belongs to the plan.
- [ ] No stray files: debug output, scratch scripts, secret files (`guards.secret_files`), local databases, coverage output, uploaded media.
- [ ] No unrelated formatting churn (formatter hooks can reformat whole files; revert hunks that aren't part of the change).
- [ ] No leftover debug statements, and no code that breaks the house rules in the brief.

## Quality checks
- [ ] Every command in `tests.checks` (type-check, lint) passes. Report the output of any that fail.

## Data and migrations
- [ ] `data.check_command` passes: no missing migrations (Django `makemigrations --check`, Prisma `validate` + `migrate status`).
- [ ] Prisma: every changed `schema.prisma` has a matching migration folder under `data.migrations`, and the generated client is up to date (`prisma generate`).
- [ ] Each new migration is safe under `paths.deployment_rules`: add before you remove, nullable or defaulted new columns, no rename or drop in the same release as the code change. For Prisma, read each `migration.sql`: renames generated as drop + add, `SET NOT NULL` without a backfill, and non-concurrent indexes on large tables need hand-editing.
- [ ] Data migrations and backfills are idempotent and reversible, or say why not.
- [ ] No destructive command was run against a shared database (`migrate reset`, `db push --accept-data-loss`).
- [ ] Any new release, seed or sync step is listed in the deploy notes.

## API contract and docs
- [ ] `paths.api_docs` match the new requests, responses, status codes and permissions.
- [ ] Consumer-facing guides in `paths.docs` are updated where a flow changes.
- [ ] New permissions or roles are registered wherever the project registers them.
- [ ] Docs contain no exploitable security details if they're published.

## Code graph
- [ ] If the project has a code graph, `graph.update_command` ran after the last code edit, and `graphify query` for a new symbol returns it. (`delivery-kit lifecycle status` shows `graph_stale: false`.)

## Configuration and deploy
- [ ] New settings or environment variables are named with what they do. Values come from the user; secret files were not read. In Next.js, nothing secret is prefixed `NEXT_PUBLIC_`, and new public variables are listed because they're baked in at build time.
- [ ] New background jobs or schedules are registered and safe to retry.
- [ ] Anything that needs ordering at deploy time (migration before code, a backfill, a feature flag) is spelled out.

## Tests and review
- [ ] `delivery-kit lifecycle status` shows `untested: false` and a review with `open_high: 0`.
- [ ] The tests for every touched module pass, in every affected suite. Full-suite and end-to-end status stated: run, not run, or running in the background.

## Commit (only when the user asks)
- [ ] On a feature or fix branch, not the main or integration branch, unless the user says otherwise.
- [ ] Message in the profile's format (`git.commit`); PR body free of `git.pr.forbid_patterns`.
