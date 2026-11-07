# Requirements

## Required

| Requirement | Why | Check |
|---|---|---|
| Claude Code with plugin support | Loads the skills, hooks and `bin/` command | `claude --version`; `/plugin` opens the plugin manager |
| Python 3.9+ as `python3` | Hooks and the `delivery-kit` CLI. Standard library only, no `pip install` | `python3 --version` |
| Git | Diff-based review targets, branch checks, gitignore checks | `git --version` |
| A POSIX shell (`sh`) | The `bin/delivery-kit` wrapper | Linux, macOS and WSL have one. On native Windows, run Claude Code inside WSL or Git Bash |
| The ECC plugin | The skills delegate to ECC agents: `ecc:architect`, `ecc:planner`, `ecc:code-explorer`, `ecc:code-reviewer`, `ecc:security-reviewer`, `ecc:database-reviewer`, `ecc:silent-failure-hunter`, `ecc:tdd-guide`, and a stack reviewer such as `ecc:django-reviewer` | `delivery-kit doctor` |

delivery-kit declares ECC as a dependency (`"dependencies": ["ecc@ecc"]` in its `plugin.json`). Claude Code can only resolve that if the ECC marketplace is already added, so add it before installing delivery-kit (see [setup](setup.md#1-install-ecc)). If ECC is missing anyway, the skills still run, but Claude does the agents' work alone and says so in its report, so reviews are shallower.

## Optional

| Tool | What it adds |
|---|---|
| [Graphify](graphify.md) (`graphifyy` on PyPI) | A code knowledge graph. Skills query it before searching source, subagent briefs tell agents to use it, and the lifecycle gate keeps it current before shipping |
| GitHub CLI (`gh`) | `gh pr create`; the PR-format hook checks PR bodies passed to it |
| Node.js and your package manager | For Next.js, Express and other JavaScript projects: the test, type-check, lint and Prisma commands run through them. `delivery-kit doctor` checks for `node` when the stack is JavaScript |
| Prisma CLI (a `prisma` dev dependency) | For `data.check_command` (`prisma validate`, `prisma migrate status`) and migrations. `migrate status` needs `DATABASE_URL` to reach a development database |
| Docker | Only if your project's test command runs in a container |

## Project prerequisites

The plugin adapts to the project through `.delivery-kit.json`. You get the most from it when the project has:

- A **targeted test command** that accepts a path or test id (for example `npx vitest run {target}`, `pnpm exec jest {target}` or `pytest {target} -q`). In a monorepo, one per app or package.
- **Type-check and lint scripts** for TypeScript projects (`tsc --noEmit`, `next lint` or ESLint), so "done" includes them.
- **Conventions written down** (`CLAUDE.md`, an architecture doc). The skills judge code against them, so the reviews only know the rules that are written down somewhere.
- **API docs** in the repo, if you want the review to flag docs that no longer match the code.

None of these is mandatory. With no profile at all, the plugin runs on [defaults](configuration.md#defaults).
