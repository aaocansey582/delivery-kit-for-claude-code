# Troubleshooting

Start with `delivery-kit doctor` and `delivery-kit lifecycle status`.

## The skills don't appear in the `/` menu

- Run `/plugin` and check that `delivery-kit` is installed and enabled. Restart Claude Code after installing or updating.
- Check that the manifest is valid: `claude plugin validate /path/to/delivery-kit`.

## "delivery-kit: command not found"

The plugin's `bin/` folder is only on PATH inside Claude Code's Bash tool. In your own terminal, run the script directly:

```bash
python3 -I /path/to/delivery-kit/plugins/delivery-kit/scripts/delivery_kit_main.py doctor
```

Or add an alias for `plugins/delivery-kit/bin/delivery-kit`.

## Claude can't commit: "code changed since the last passing test run"

A lifecycle is active and a code file changed after the last passing test run.

- Run the targeted tests for what changed, using `tests.command`.
- If the tests pass but the flag doesn't clear, the command didn't match `tests.match`, or the output didn't match `tests.pass_pattern`. Run `delivery-kit profile check`, and compare the `last_test` entry in `delivery-kit lifecycle status` with your patterns.
- If you edited only non-code files and still see this, add them to `paths.exclude`.
- In a monorepo, the message names the suites still untested (for example `in suite(s) web, api`). Run each one; a passing API run doesn't clear the web app. If a suite's own command doesn't clear it, its `match` doesn't recognise how you ran it. The generated patterns need the package folder or name plus `vitest`/`jest`/`mocha` or a `npm|pnpm|yarn|bun … test` script in the same command.

## The type-check or lint fails but the gate let me commit

`tests.checks` are part of the Ship checklist, not the hook gate: Claude runs them and reports failures, but the hook only tracks tests. Treat a reported type error as a blocker.

## `prisma migrate status` fails in `data.check_command`

It needs `DATABASE_URL` to reach a development database. Start the database, or remove `migrate status` from `data.check_command` and keep `prisma validate`.

## "the code graph is older than your changes"

Run `graphify update .` (or your `graph.update_command`). If the update fails, fix that first; a failed update doesn't clear the flag. To keep the graph guidance without this gate, set `graph.require_before_ship` to `false`.

## "no review recorded" or open Critical/High findings

Run the Review phase, fix the findings, then `delivery-kit lifecycle review --open-high 0`. If you and Claude agree to ship with a finding open, record the real number and end with `--abort`. Don't record `0` for findings that are still open.

## Commits blocked in a session that isn't running a lifecycle

That's the format rule, not the lifecycle gate: the message breaks `git.commit` in the profile. The deny message names the rule. Change the message or the rule.

## A lifecycle from an old session is stuck

```bash
delivery-kit lifecycle status        # see the slug and owner
delivery-kit lifecycle claim         # take it over in this session
delivery-kit lifecycle end --abort   # or abandon it
```

## Two copies of the gate run

If the project still has an older `.claude/hooks/lifecycle_gate.py` wired into `.claude/settings.json`, both run. Remove the old hook entries and skills; see [setup](setup.md#remove-duplicates-from-older-setups).

## Turning things off temporarily

- `LIFECYCLE_GATE=off`: lifecycle gates off for this session's environment. Format rules stay on.
- `"lifecycle": {"enabled": false}` in `.claude/delivery-kit.local.json`: off for you only.
- `/plugin disable delivery-kit@delivery-kit`: everything off.
