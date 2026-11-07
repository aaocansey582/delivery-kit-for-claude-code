# Focus: payments

Use when the subsystem is payments, checkout, a payment gateway, callbacks/webhooks, payment allocation, reconciliation or refunds.

## Flow to cover

Initiation → gateway → callback or verification → allocation to bills or orders → order status and fulfilment. With a narrower focus (`refunds`, `webhooks`, `checkout`, `allocation`, `reconciliation`), centre on it but trace how it connects.

## Agent focus

- **architect:** boundaries between billing and ordering modules; whether the gateway abstraction is really gateway-agnostic; the payment state machine; synchronous verification vs callbacks vs a reconciliation job; idempotency design.
- **security-reviewer:** callback authenticity (signature checks, replay, trusting gateway-supplied amounts); amount or currency tampering (is the price always computed on the server?); IDOR on payment, order and bill lookups; permissions and scope on payment endpoints; secrets and personal data in logs; SSRF in the gateway client; return/redirect URL validation; throttling on initiate and verify.
- **database-reviewer:** transaction boundaries around confirm → allocate → order status; row locking against double-processing when a callback and a verification run at once; unique constraints on gateway references and idempotency keys; decimal money fields and rounding; ledger and audit rows; indexes for reconciliation queries.

## Severity

- **Critical:** a payment marked paid without gateway confirmation; amount tampering; one user reading or changing another's payment; money allocated twice or lost.
- **High:** double-processing under concurrent callbacks; missing idempotency on gateway references; secrets or personal data leaking; a writable payment endpoint missing a permission or scope check.
- **Medium:** non-atomic multi-step writes, reconciliation gaps, gateway coupling that blocks a gateway switch, an unsafe migration.
- **Low:** naming, duplicated logic, stale docs, missing indexes on cold paths.

## Test plan must include

Concurrent callback and verification for the same payment, callback replay, tampered amount, and a partial-allocation case.
