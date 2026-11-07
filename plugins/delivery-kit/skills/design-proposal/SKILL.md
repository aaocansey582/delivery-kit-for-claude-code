---
name: design-proposal
description: Evaluate one subsystem (for example payments, authentication, notifications, data import, multi-tenancy) with the ECC architect, security-reviewer, database-reviewer and planner agents, and consolidate their verified findings into one implementation proposal, without implementing anything. Use when the user wants a subsystem assessed, redesigned or planned, or asks for an implementation plan or proposal for a risky area, even if they don't mention agents.
---

# Design Proposal

Run three ECC specialist agents over one subsystem, verify what they report, and have the planner turn it into one proposal the user can approve. Nothing gets implemented. The value is in the consolidation: agents repeat each other, contradict each other, and sometimes invent things, so treat their reports as leads.

## 1. Scope

Subsystem and focus: `$ARGUMENTS`

- If it names a subsystem and a concern (for example `payments refunds`, `auth sessions`), centre the evaluation on the concern, but read enough of the surrounding flow to see how it connects.
- If it names only a subsystem, cover its whole flow from entry point to final state.
- If it's empty, ask which subsystem.

If [references/](references/) has a focus file for the subsystem (for example [payments.md](references/payments.md)), read it: it holds the agent focus lists and severity examples for that domain.

State the scope in one line at the top of the proposal.

## 2. Gather context first

Run `delivery-kit profile show` and `delivery-kit brief --read-only`. Then read just enough to brief the agents well and to judge their output:

- `paths.plans` and `paths.docs` for the subsystem: which phases are built, in progress or on hold. Don't propose work on something on hold unless the user asks; list it under "Out of scope".
- `paths.deployment_rules`.
- The code. If the profile shows a code graph, find it with `graphify query "<subsystem> flow"` and `graphify explain "<core service>"`, then confirm the file list against the code. Otherwise grep for the subsystem's names.

Never read secret files. If a setting matters, name it and ask the user.

## 3. Wave 1: three reviewers in parallel

Spawn `ecc:architect`, `ecc:security-reviewer` and `ecc:database-reviewer` in one message. Start each prompt with the brief, then: "You are reviewing the <subsystem> of this project. Code: <files>. Plans and docs: <docs>. Return at most ~800 words: findings first, then recommendations." Then the agent's focus:

- **architect:** module boundaries; whether abstractions (for example a provider or gateway interface) really are swappable; the subsystem's state machine (states, allowed transitions, where they are enforced); sync vs async vs reconciliation; idempotency design; coupling; and where the code departs from the plans. End with a recommended target design in a few bullets.
- **security-reviewer:** authenticity of inbound callbacks or webhooks; tampering with amounts, ids or roles supplied by the client; IDOR on lookups; permissions and `project.scope_boundaries`; secrets and personal data in logs, errors or responses; SSRF or unsafe URL building; redirect validation; throttling.
- **database-reviewer:** transaction boundaries across the multi-step flow (with Prisma, interactive `$transaction` and that every query inside uses `tx`); row locking against double-processing; unique constraints on external references and idempotency keys (nullable columns in unique rules); numeric precision for money or quantities; audit and ledger rows; migration safety under `paths.deployment_rules`; indexes for reconciliation or reporting queries.

Replace these with the focus file's lists where one exists.

If an `ecc:*` agent type isn't available, spawn `general-purpose` and start its prompt with "Read `~/.claude/plugins/cache/ecc/ecc/*/agents/<name>.md` and adopt it as your role." If that file doesn't exist either, tell the user ECC isn't installed and ask whether to continue without it.

## 4. Verify and merge (you)

1. **Verify.** Open the cited line for every High or Critical claim and anything surprising. Drop claims that don't hold; downgrade ones you can't confirm to Suspected. Don't drop a claim only because one agent made it.
2. **De-duplicate** and record which agents raised each finding (`arch`, `sec`, `db`). Agreement raises confidence; say so.
3. **Resolve conflicts.** Where agents disagree, decide what you recommend and why, and keep the disagreement visible.
4. **Rate severity** using step 7.

## 5. Wave 2: the planner

Spawn `ecc:planner` with the brief, the verified findings and the target design. Ask for phased steps, each giving: files touched, the change, whether it needs a migration (and whether that's safe under the deploy rules), the tests that prove it, dependencies, and risk. Integrity and security fixes ship before refactors; each step fits one PR.

Check the plan: drop steps for on-hold work, merge steps that are too small, split steps that mix a migration with a behaviour change, and make sure every Critical or High finding is covered.

## 6. Don't implement

This skill produces a proposal only. Don't edit code, docs or migrations, and don't create branches. If the user approves, they will ask for the implementation separately (for example with `/delivery-kit:feature-lifecycle`).

## 7. Severity

Use the focus file's scale if there is one. Otherwise:

- **Critical:** an operation completes without its required confirmation; tampering with values the server should own; one user reading or changing another's data across `project.scope_boundaries`; `project.sensitive_data` lost, duplicated or corrupted.
- **High:** double-processing under concurrency; missing idempotency on external references; secrets or personal data leaking; a writable endpoint missing a permission or scope check.
- **Medium:** non-atomic multi-step writes, reconciliation gaps, provider coupling that blocks a switch, a migration unsafe under the deploy rules.
- **Low:** naming, duplicated logic, stale docs, missing indexes on cold paths.

## 8. The proposal

```
**Scope:** …   **Agents:** architect, security-reviewer, database-reviewer, planner   **Graph:** used|not available

## Current architecture
≤10 lines, plus a Mermaid sequenceDiagram of the flow as the code actually runs it.

## Findings
### Critical / High / Medium / Low
**N. <claim>** — Confirmed|Suspected · raised by arch/sec/db
[file:LINE](path/to/file#LLINE) — what goes wrong, under what conditions.

## Proposed design
Target design in bullets, where it differs from the code and the plans, and how agent disagreements were resolved.

## Implementation plan
Phase → numbered steps (files · change · migration? · tests · depends on · risk), each referencing the findings it fixes.

## Deploy and migration notes

## Test plan
New and changed tests per phase, including concurrency and replay cases.

## Decisions needed
Questions only the user can answer.

## Out of scope
On-hold work and anything deliberately left out.
```

Number the findings, keep links relative to the repo root, and keep it to about 2,000 words plus the diagram. End by offering to save the proposal under `paths.docs`, or to start a phase once the user approves.
