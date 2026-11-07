# Next.js checklist

Use when `project.stack` includes `nextjs`. Covers the App Router (`app/`) and the Pages Router (`pages/api/`). ECC's `nextjs-turbopack` and `react-patterns` skills hold general patterns; this list is for defects.

## Entry points to find

- Route handlers: `app/**/route.ts` (`GET`, `POST`, … exports).
- Server Actions: functions with `"use server"` (inline or in a module). **Every exported Server Action is a public POST endpoint**, callable directly with crafted arguments, whether or not a form uses it.
- Pages API routes: `pages/api/**`.
- `middleware.ts` and its `config.matcher`.
- Server Components that read data directly (they're entry points too: their data access needs the same checks).

## Authorization
- Each route handler and Server Action checks the session itself. Middleware alone is not enough: matchers miss paths, and middleware can be bypassed for some request types. Don't rely on the UI hiding a button.
- Server Actions re-check authorization and ownership on every call, and validate their arguments (for example with zod). Arguments come from the client even when typed in TypeScript.
- Object access is scoped: a lookup by an id from params or arguments also filters by the owner or tenant (`where: { id, userId }`), not only by id.
- Layouts don't protect their child routes on their own: a layout's auth check doesn't run for a route handler or a Server Action under it.

## Server/client boundary
- Server-only modules (database client, secrets, admin SDKs) are never imported into `"use client"` files. Look for the `server-only` package on modules that must not leak.
- Props passed from Server to Client Components are serialized to the browser: check for whole database rows (password hashes, tokens, internal flags) passed as props.
- Only `NEXT_PUBLIC_*` env vars reach the browser. Nothing secret is prefixed `NEXT_PUBLIC_`, and server code doesn't expect public vars to be secret.
- Values returned from Server Actions are sent to the client: same field-leak check as props.

## Data and caching
- `fetch` caching and `revalidate` / `unstable_cache` / `"use cache"`: user-specific data must not be cached in a shared cache, or one user sees another's data.
- After a mutation, the relevant `revalidatePath` / `revalidateTag` is called; otherwise users see stale data.
- `cookies()`, `headers()` or `searchParams` in a page make it dynamic; check that pages meant to be static don't depend on them by accident, and that per-user pages aren't statically generated.
- Waterfalls: sequential `await`s for independent data in a Server Component, where `Promise.all` would do.

## Input and output
- Route handlers validate the body, query and params; `request.json()` throws on bad JSON and should become a 400, not a 500.
- Errors returned to the client don't include stack traces or database messages.
- Redirects built from user input (`redirect(searchParams.get("next"))`) are validated against an allowlist (open redirect).
- `dangerouslySetInnerHTML` only with sanitized content.

## Runtime
- Edge runtime routes don't import Node-only modules (most database drivers, `fs`, `crypto` from Node).
- The database client is a module-level singleton so hot reload and serverless invocations don't exhaust connections.

## Tests
- Route handlers and Server Actions have tests for the unauthenticated, wrong-owner and invalid-input cases, not only the happy path.
