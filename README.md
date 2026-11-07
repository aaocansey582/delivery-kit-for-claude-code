# delivery-kit for Claude Code

A community plugin for [Claude Code](https://claude.com/claude-code), not affiliated with or endorsed by Anthropic.

A Claude Code plugin that takes a change from request to merge with the checks a careful engineer would apply: understand the code, plan, write tests first, review, then ship. Hooks enforce the important parts, so they don't rely on the model remembering.

Everything project-specific (paths, test commands, commit format, conventions, code graph) lives in one file per repository, `.delivery-kit.json`, which `delivery-kit profile init` generates by detecting your stack. The same plugin works across projects. It's tuned for **Next.js, Express and Prisma**, including full-stack monorepos, with Django REST Framework also supported:

- Review checklists for Next.js (Server Actions, route handlers, the server/client boundary, caching), Express (middleware order, async errors, mass assignment) and Prisma (field leaks, `$transaction`, migration SQL safety).
- Separate test tracking for each part of a monorepo: a web-app edit needs the web suite to pass, an API edit needs the API suite.
- Type-check and lint as part of "done", and Prisma migration rules, including a ban on destructive commands such as `prisma migrate reset`.

## What you get

| Skill | Use it for |
|---|---|
| `/delivery-kit:feature-lifecycle` | Implementing a fix or feature: Understand → Plan (approval gate) → Implement and Test (test first) → Review → Ship |
| `/delivery-kit:api-review` | Reviewing endpoints against the project's conventions with stack, security and database reviewers |
| `/delivery-kit:architecture-assessment` | Mapping modules, request flows and the data model, and finding structural weaknesses |
| `/delivery-kit:design-proposal` | A verified, phased implementation proposal for a risky subsystem (payments, auth, …) |

Claude also picks these skills up from plain requests such as "fix the score delete bug" or "review the finance endpoints".

| Hook | What it enforces |
|---|---|
| Lifecycle gate | While a lifecycle is active: no stopping with untested code; no commit, push or PR until tests pass, the code graph is updated, and the review has no open Critical/High findings |
| Commit and PR format | Always: commit messages and PR bodies follow the rules in the profile (one line, subject pattern, forbidden trailers or footers) |

A `delivery-kit` command is added to Claude's PATH for lifecycle state, profile checks and subagent briefs.

## Requirements

- Claude Code with plugin support
- Python 3.9 or newer, available as `python3`
- Git
- The [ECC](https://github.com/affaan-m/everything-claude-code) plugin (required; it provides the reviewer, architect and planner agents)
- Node.js and your package manager, for JavaScript projects
- Optional: [Graphify](docs/graphify.md) for a queryable code graph

Details: [docs/requirements.md](docs/requirements.md).

## Quick start

```text
/plugin marketplace add https://github.com/aaocansey582/delivery-kit-for-claude-code.git
/plugin install delivery-kit@delivery-kit
```

Then, in each project:

```bash
delivery-kit profile init     # detects the stack and writes .delivery-kit.json
delivery-kit profile check    # validates it
delivery-kit doctor           # checks ECC, Python, Graphify, gitignore
```

Add the lifecycle state folder (`.claude/lifecycle/` by default) to `.gitignore`.

Full walkthrough: [docs/setup.md](docs/setup.md).

## Documentation

- [Requirements](docs/requirements.md)
- [Setup](docs/setup.md): install, configure a project, verify, update, uninstall
- [How it works](docs/how-it-works.md): skills, hooks, the lifecycle state machine, session ownership
- [Configuration reference](docs/configuration.md): every field in `.delivery-kit.json`
- [Graphify integration](docs/graphify.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Roadmap](docs/roadmap.md)
- [Contributing](CONTRIBUTING.md)

## Credits

delivery-kit is glue around two excellent projects, and wouldn't be useful without them:

- **[ECC (Everything Claude Code)](https://github.com/affaan-m/ECC)** by [Affaan Mustafa](https://x.com/affaanmustafa) ([ecc.tools](https://ecc.tools), MIT license). Its agents (architect, planner, code explorer, and the security, database and stack reviewers) do the specialist work that delivery-kit's skills coordinate and verify.
- **[Graphify](https://github.com/Graphify-Labs/graphify)** by Safi Shamsi and the Graphify contributors ([graphify.com](https://graphify.com), Apache-2.0 license). Its code knowledge graph is what the skills query before searching source.

delivery-kit doesn't bundle or modify either project. Install them from their own sources, under their own licenses. Thanks to their authors and contributors.

## Repository layout

```
.claude-plugin/marketplace.json     marketplace manifest (this repo is the marketplace)
plugins/delivery-kit/
  .claude-plugin/plugin.json        plugin manifest
  skills/                           the four skills and their references
  hooks/hooks.json                  hook wiring
  bin/delivery-kit                  CLI added to Claude's PATH
  scripts/delivery_kit/             profile loader, stack detection, lifecycle state, hooks (stdlib Python only)
  tests/test_gate.py                hook and CLI tests
examples/                           sample profiles: Next.js + Prisma, Express + Prisma, full-stack monorepo, Django
docs/                               user documentation
```
