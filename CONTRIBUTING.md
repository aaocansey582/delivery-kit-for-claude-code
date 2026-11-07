# Contributing

## Develop locally

Run Claude Code against your checkout without installing:

```bash
claude --plugin-dir /path/to/delivery-kit/plugins/delivery-kit
```

Validate the manifests and components:

```bash
claude plugin validate .
claude plugin validate plugins/delivery-kit
```

## Tests

The hooks and CLI use only the Python standard library. Their tests build throwaway projects in a temporary folder:

```bash
python3 -I plugins/delivery-kit/tests/test_gate.py
```

Add a case for every hook behaviour you change, including the allow case next to each deny.

## Rules for changes

- **Stay generic.** Nothing project-specific in skills, hooks or defaults. If a behaviour differs between projects, make it a profile field with a safe default, and document it in [docs/configuration.md](docs/configuration.md).
- **Hooks fail open.** A hook that can't load the profile or hits an error must allow the action and log to stderr.
- **No dependencies.** Hooks run on every tool call; keep them standard-library Python and fast.
- **Skills reference profile fields, not paths.** Write `paths.api_docs`, not `api/docs/endpoints/`.
- **Bump versions together.** `plugins/delivery-kit/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `scripts/delivery_kit/__init__.py`, and an entry in [CHANGELOG.md](CHANGELOG.md).

## Adding a stack checklist

Add `plugins/delivery-kit/skills/api-review/references/stacks/<stack>.md` with checks specific to that framework, and list the stack in the configuration reference.

## Adding a design-proposal focus

Add `plugins/delivery-kit/skills/design-proposal/references/<subsystem>.md` with the flow to cover, the agent focus lists, the severity examples, and what the test plan must include. Use [payments.md](plugins/delivery-kit/skills/design-proposal/references/payments.md) as the model.
