# Cloud hosting (Cloudflare) - tradeoffs, not a plan

*Written 2026-09-14, in response to a stated eventual goal: host a
real-data version of GridPilot on Cloudflare Pages for the school to use
remotely.* No infrastructure exists yet and none is proposed here - this
is a decision record, the same discipline `docs/privacy-threat-model.md`
and `docs/packaging.md` apply to every other non-obvious choice in this
project, so that decision is made deliberately later, not backed into as
a side effect of an unrelated task.

## 1. This is a governance decision first, an engineering decision second

`docs/privacy-threat-model.md`'s trust-boundary diagram states plainly:
*"Nothing in this tool talks to the network beyond localhost. No cloud
API calls exist anywhere in the codebase today."* That sentence is true
by construction - there is no code path that could violate it even by
accident. Hosting real student and staff data on Cloudflare makes it
false by design, not by omission. That is not a bug to fix in the
trust-boundary diagram; it is a different diagram, and it changes what
this project can honestly say about itself.

Concretely, before any engineering starts:

- **Brisbane Catholic Education data-residency and processing
  requirements.** The project already carries one honest caveat about
  this - the working directory currently syncs to BCE's own OneDrive
  tenant, "the school's own managed tenant, presumably with its own
  compliance posture." Deliberately hosting off-premises on a
  third-party (Cloudflare) is a materially different question from data
  that happens to sync to a tenant the school already controls, and
  needs its own answer, not an extension of the OneDrive one.
- **A data processing agreement with Cloudflare**, and confirmation of
  which region their infrastructure keeps the data in.
- **Whether affected staff/students (or their guardians) need to be
  told** their timetable data is processed by a third-party cloud
  provider, per whatever privacy notice BCE already issues.

None of this is something an engineering session can resolve. It's listed
first because skipping it and shipping a working prototype is the
easiest way to end up with a technically-fine system nobody was allowed
to build.

## 2. What breaks technically, named plainly

- **No auth or session model exists at all.** `docs/privacy-threat-model.md`:
  *"There is no user table, no login, no session concept anywhere in the
  schema or API"* - a deliberate choice for a tool one person runs on
  their own machine. `actor`/`reviewed_by` fields are free-text names
  typed at the time, not authenticated identity. A hosted, remotely
  reachable service needs real authentication before it needs anything
  else - a free-text name field is not access control.
- **SQLite is single-writer, with a per-machine default location.**
  `docs/packaging.md` already flags this as an open question even for
  the *desktop* packaging path: `%LOCALAPPDATA%\GridPilot` is
  per-machine, per-user - "if the school wants the working database on a
  shared/synced drive instead... that's a one-line change... worth
  deciding before this goes to more than one machine." A hosted service
  reachable by multiple people simultaneously is a harder version of the
  same question this project has not yet had to answer once.
- **The CP-SAT solver (OR-Tools) is a native binary.** Cloudflare Pages
  Functions and Workers run on V8 isolates - they cannot execute
  `ortools`, full stop. This is not a configuration problem; it rules out
  Pages Functions as the backend host regardless of any other decision
  here.
- **Ollama is assumed local.** `docs/ai-advisor.md`'s brief constraint is
  "Ollama only, local inference" - both `privacy-threat-model.md` and
  `packaging.md` treat "the same local Ollama call" as an invariant that
  survives packaging. Hosting breaks the localhost assumption outright.
  The options are a remote-but-still-self-hosted Ollama instance (a real
  server to run and secure) or a hosted LLM API - the latter is a
  genuine renegotiation of "local-only AI," not a deployment detail, and
  should be decided in writing, not discovered mid-build.
- **No encryption at rest.** Currently justified by "a school-managed
  device [with] disk encryption already in place at the OS level" -
  `privacy-threat-model.md` says as much and flags it would need
  revisiting "if this ever runs somewhere that assumption doesn't hold."
  A cloud host is exactly that somewhere.
- **No redacted support-bundle capability.** Deferred previously because
  "nobody has needed to debug it remotely yet." A hosted deployment makes
  remote debugging the normal case, not the exception - this gap stops
  being theoretical the moment hosting happens.

## 3. A realistic shape, if this proceeds

Cloudflare **Pages** on its own cannot host this application - it's
static hosting plus lightweight edge functions, and the backend needs a
real, always-on server process. A shape that could actually work:

- **Static frontend on Cloudflare Pages** - `frontend/dist`, built the
  same way `docs/packaging.md` Phase 1 already builds it for the
  single-process desktop path. This part is genuinely low-risk; nothing
  about the frontend assumes localhost (`frontend/src/api.ts`'s `BASE =
  "/api"` is already a relative path).
- **The FastAPI/SQLite/OR-Tools backend on Cloudflare Containers** (their
  newer product for running arbitrary Docker images) **or a plain
  VPS/VM** behind Pages - not Workers, not Pages Functions. This is a
  real containerization + deployment task, not a config change.
- **`TT_SOURCE_DIR`/`TT_DATA_DIR`/`TT_OUTPUT_DIR`** already exist as the
  seam for pointing ingestion and the working database at a location
  other than a local folder - the natural place to redirect at a
  non-local store, whatever that ends up being (a managed Postgres
  instead of SQLite is a likely accompanying change, given the
  single-writer constraint above).

## 4. Recommended sequencing, if the school decides to proceed

1. **Governance sign-off first** (section 1) - a precondition, not step
   one of a build.
2. **Add real auth/session handling and a multi-writer-safe data layer,
   validated on a normal server, before touching Cloudflare at all.**
   Proving the harder architectural change (no-auth → real auth,
   single-writer SQLite → something that tolerates concurrent access)
   works on infrastructure this project already understands is safer
   than debugging it and a new hosting provider simultaneously.
3. **Containerize the backend** and confirm the OR-Tools solver runs
   correctly in that container - this is the one hard technical
   constraint from section 2 with no workaround, so confirm it early.
4. **Decide Ollama's fate explicitly, in writing** - remote self-hosted
   instance vs. a hosted LLM API vs. dropping AI-explanation entirely for
   the hosted deployment. Whichever is chosen changes a privacy
   commitment this project has held since its first commit; it deserves
   a decision, not a default.
5. Only then, deploy the frontend to Cloudflare Pages and point it at the
   now-hosted backend.

## What this document is not

Not a timeline, not a cost estimate, not an architecture diagram for a
system that doesn't exist yet, and not permission to start any of the
above. It exists so that when this is prioritized, the real questions are
already written down instead of discovered one at a time during the
build - the same reason `docs/roadmap-v3.md` exists for the rest of this
project's backlog.
