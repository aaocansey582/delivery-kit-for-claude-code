# Express checklist

Use when `project.stack` includes `express`. ECC's `backend-patterns` and `typescript-patterns` skills hold general patterns; this list is for defects.

## Routing and middleware order
- Map the middleware chain for the route: `app.use` order matters. Auth, rate limiting and body parsing must be registered **before** the routers they protect. A router mounted above `app.use(authenticate)` is public.
- Per-route middleware arrays include the auth and permission checks on every method (`router.get`, `.post`, `.patch`, `.delete`), not only the first one written.
- `router.param` / `:id` handlers that load objects also check ownership, or every route using `:id` must.
- The error-handling middleware (four arguments: `err, req, res, next`) is registered last, and there is exactly one that formats responses.

## Async errors
- Express 4 doesn't catch rejected promises from async handlers: they hang the request or crash the process unless wrapped (`express-async-errors`, an `asyncHandler` wrapper, or `next(err)`). Express 5 forwards them. Check the version in `package.json` before reporting.
- No `res.send` after `next(err)`, and no code path that sends two responses ("headers already sent").
- Unhandled promise rejections in background work started from a request (fire-and-forget `someAsync()` without `await` or `.catch`).

## Input
- Body, query and params are validated (zod, joi, express-validator, celebrate) before use. `req.query` values can be strings, arrays or objects; `?id[]=1` turns a string into an array.
- No mass assignment: `prisma.user.update({ data: req.body })` or `Object.assign(model, req.body)` lets clients set `role`, `ownerId`, `balance`.
- `express.json({ limit })` is set to something sensible; file uploads (multer) limit size and type.
- Path traversal in anything that builds file paths from input (`res.sendFile`, `fs`).

## Security middleware
- `helmet` (or equivalent headers), CORS restricted to known origins with `credentials` only where needed, not `origin: "*"` with credentials.
- Rate limiting on auth, password reset and expensive endpoints.
- Cookies for sessions are `httpOnly`, `secure` in production, with a deliberate `sameSite`; CSRF protection when cookie auth is used with state-changing requests.
- `app.set("trust proxy", …)` set correctly behind a proxy, otherwise rate limits and IP logs see the proxy's address.
- JWTs are verified with a fixed algorithm list and expiry; secrets aren't hardcoded.

## Responses and logging
- Responses use the project's envelope consistently; errors don't leak stack traces or database messages in production.
- Logs don't include tokens, passwords or full request bodies with personal data.

## Tests
- Supertest (or similar) tests cover 401/403 per method, invalid input (400), and not-found for another owner's id (404 or 403, as the project chooses).
