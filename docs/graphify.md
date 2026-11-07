# Graphify integration

[Graphify](https://github.com/Graphify-Labs/graphify), by Safi Shamsi and the Graphify contributors ([graphify.com](https://graphify.com), [docs](https://docs.graphify.com), Apache-2.0, published on PyPI as [`graphifyy`](https://pypi.org/project/graphifyy/)), turns a codebase into a knowledge graph. It builds `graphify-out/graph.json`, a `GRAPH_REPORT.md`, and optionally a wiki, all describing modules, communities, hub ("god") nodes and cross-file relationships. Claude can then ask the graph a scoped question instead of grepping the whole tree. That's faster and uses far fewer tokens, especially in subagents that start with no context.

delivery-kit doesn't install or replace Graphify. It works with your Graphify setup:

| Where | What delivery-kit does |
|---|---|
| Subagent briefs | When a graph exists, `delivery-kit brief` tells every agent to run `graphify query` before its first grep or source read, to use `path`, `explain` and `affected`, to read raw files only for located lines, and not to assume the graph is current |
| `feature-lifecycle` | Understand starts with `graphify query` and `graphify affected` for the blast radius. After implementing, Claude runs the update command and confirms a new symbol appears. Shipping is blocked while the graph is older than the edits |
| `architecture-assessment` | Checks the graph's age against the last code commit, then uses the wiki, `god-nodes`, `query`, `path` and `explain` before reading source |
| `api-review`, `design-proposal` | Use `query` and `affected` to find the files and callers in scope |
| `delivery-kit doctor` | Reports whether `graphify` is installed and whether a graph has been built |

## The rules it enforces

These match the Graphify guidance teams usually put in `CLAUDE.md`:

1. Use the graph when investigating architecture and cross-module dependencies.
2. Query the graph before broad source searches.
3. After structural code changes, update the graph.
4. Before completing a feature, verify the graph reflects the change.
5. Never assume the graph is current without checking.

Rules 1, 2 and 5 are in the briefs and skills. Rules 3 and 4 are also enforced by the lifecycle gate (`graph_stale`).

## Install Graphify

```bash
pip install graphifyy        # or: pipx install graphifyy
graphify install             # installs the /graphify skill for Claude Code
```

Then build the first graph from Claude Code in the project:

```text
/graphify
```

The first build uses an LLM for semantic extraction. After that, `graphify update .` refreshes the graph from the code with AST parsing only, at no API cost, and is what the lifecycle runs.

Graphify can also install its own integrations, which complement delivery-kit:

- **Claude Code hooks** from `graphify install` that nudge Claude toward the graph before grep and file reads.
- **Git hooks**: `graphify hook install` rebuilds the graph on commit, checkout, merge and rebase. `graphify hook status` checks them.

delivery-kit doesn't duplicate these. If you use Graphify's git hooks, the graph also stays current outside Claude sessions.

## Commands the skills use

| Command | Purpose |
|---|---|
| `graphify query "<question>"` | Scoped subgraph for a question |
| `graphify path "<A>" "<B>"` | Shortest relationship between two nodes |
| `graphify explain "<concept>"` | One node and its neighbours, in plain language |
| `graphify affected "<X>"` | Reverse traversal: what depends on X |
| `graphify god-nodes` | The most connected nodes (architectural hubs) |
| `graphify update .` | Re-extract code and refresh the graph without an LLM |

`query`, `path` and `explain` exit with 3 when a name is ambiguous (they list the candidates) and 4 when nothing matches. The skills retry with a candidate name rather than falling back to a broad grep.

## Configuration

```json
"graph": {
  "provider": "graphify",
  "dir": "graphify-out",
  "update_command": "graphify update .",
  "update_match": "\\bgraphify\\s+update\\b",
  "require_before_ship": true
}
```

- Set `"provider": ""` to switch the integration off.
- Set `"require_before_ship": false` to keep the graph guidance without the ship gate. That suits teams that rely on Graphify's git hooks for updates.
- The integration only activates when `<dir>/graph.json` exists, so a project without a graph is unaffected.

## Committing the graph

Whether to commit `graphify-out/` is a team choice:

- **Gitignored:** each developer builds their own graph and nothing churns in diffs.
- **Committed:** everyone shares one graph. `graph.json` is rewritten whole on every build, so expect large diffs in PRs; don't treat them as noise. Graphify ships a git merge driver (`graphify merge-driver`) for conflicts.

Either way, keep `graphify-out/cache/` out of Git.
