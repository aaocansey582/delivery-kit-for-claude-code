# Setup

Setup has five steps: install ECC, add this marketplace, install the plugin, configure each project, and verify.

## 1. Install ECC

delivery-kit depends on the `ecc` plugin from the `ecc` marketplace. Add that marketplace first so the dependency can be resolved. In Claude Code:

```text
/plugin marketplace add https://github.com/affaan-m/everything-claude-code.git
/plugin install ecc@ecc
```

Restart Claude Code, then run `/plugin` and confirm `ecc` is enabled.

## 2. Add the delivery-kit marketplace

This repository is its own marketplace. Add it from wherever your team hosts it:

```text
/plugin marketplace add <git-url-of-this-repo>
```

You can also add it from a local checkout, which is useful while developing the plugin:

```text
/plugin marketplace add /path/to/delivery-kit
```

## 3. Install the plugin

```text
/plugin install delivery-kit@delivery-kit
```

Choose the scope when prompted:

- **User:** available in every project on your machine.
- **Project:** recorded in the repo's `.claude/settings.json`, so teammates are prompted to install it when they open the repo. Use this if `.claude/settings.json` is committed.

Restart Claude Code. `/delivery-kit:feature-lifecycle` and the other skills now appear in the `/` menu.

To try the plugin without installing it, start Claude Code with `claude --plugin-dir /path/to/delivery-kit/plugins/delivery-kit`.

## 4. Configure a project

From the project root, ask Claude to run, or run yourself with the plugin's `bin/` on your PATH:

```bash
delivery-kit profile init
```

This detects the stack and writes `.delivery-kit.json`. It reads `package.json` and the workspaces, the lockfile, the test runners, TypeScript and lint scripts, the Prisma schema, `manage.py`, commitlint and your branches. For a pnpm monorepo with a Next.js app and an Express API it produces something like:

```
Wrote /repo/.delivery-kit.json (detected: nextjs, express, prisma, typescript).
note: Fill in project.sensitive_data and project.scope_boundaries: they decide what counts as Critical in reviews.
```

with a test suite for each app (`cd apps/web && pnpm exec vitest run {target}`, `cd apps/api && pnpm exec jest {target}`), the type-check and lint commands, and the Prisma schema and migrations. Use `--print` to preview it without writing anything.

Review what it wrote and fill in what it can't know:

| Field | Set it to |
|---|---|
| `project.summary` | Adjust the generated one if it misses something important (hosting, queues, other services) |
| `project.sensitive_data`, `project.scope_boundaries` | What counts as Critical, for example `["orders", "payment records"]` and `["organisation", "user"]` |
| `paths.conventions` | The docs the reviews judge code against |
| `agents.house_rules` | Rules every subagent should follow, for example "Every Server Action checks the session itself" |
| `git.commit`, `git.pr` | Your commit and PR rules, if detection didn't find them |
| `guards.protected_paths` | Only if another team owns part of the repo; leave it empty otherwise |

Every field is described in the [configuration reference](configuration.md), and [examples/](../examples/) has complete profiles.

Then validate it:

```bash
delivery-kit profile check
```

Personal overrides that shouldn't be committed (for example a different container name) go in `.claude/delivery-kit.local.json`, which is merged on top of the shared profile.

### Gitignore

Add the lifecycle state folder to `.gitignore`. It holds per-developer state and plans:

```gitignore
.claude/lifecycle/
.claude/delivery-kit.local.json
```

Commit `.delivery-kit.json` so the whole team shares the same rules.

### Remove duplicates from older setups

If the project already has copies of these skills or a hand-wired lifecycle hook in `.claude/` (for example `.claude/skills/lifecycle` or `.claude/hooks/lifecycle_gate.py` in `.claude/settings.json`), remove them once the plugin works. Otherwise both copies run and each one gates commits.

## 5. Verify

```bash
delivery-kit doctor
```

```
ok   python >= 3.9: 3.12.3
ok   ECC plugin installed: ecc
ok   profile present: /repo/.delivery-kit.json
ok   profile valid: ok
ok   test command set: docker exec my-service-api pytest <path> -q
ok   graphify installed: /home/me/.local/bin/graphify
ok   code graph built: graphify-out/graph.json
ok   lifecycle state gitignored: .claude/lifecycle/
```

`FAIL` rows need fixing. `??` rows are optional or couldn't be checked.

For a quick end-to-end check, ask Claude for a trivial fix. It should run `delivery-kit lifecycle start`, and `delivery-kit lifecycle status` should show the lifecycle with your session as `owner`. Abort it with `delivery-kit lifecycle end --abort`.

## Updating

```text
/plugin marketplace update delivery-kit
```

Then restart Claude Code. The [changelog](../CHANGELOG.md) lists what changed in each version.

## Uninstalling

```text
/plugin uninstall delivery-kit@delivery-kit
```

`.delivery-kit.json` and the lifecycle folder stay in your repositories; delete them if you no longer need them.
