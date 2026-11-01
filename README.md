# itoolbox-backend

**API services for the IToolbox Ecosystem Platform.**

> One login, one dashboard, every tool.

This repo is one of four. The data never leaves its source: the platform reaches
it through the Zetaris data harness, locally first, governed in place, and moves
to cloud infrastructure only where compute demands it.

| Repo | Contains |
| --- | --- |
| **itoolbox-backend** (this) | FastAPI service, Alembic migrations, the BantAI agent |
| `itoolbox-frontend` | Next.js web app |
| `itoolbox-zetaris-platform` | The Zetaris data harness: query engine, catalog, API |
| `itoolbox-data-platform` | TimescaleDB, JupyterLab and the ingestion jobs that load BantAI's data |

---

## BantAI

Project BantAI, from *bantay* ("guard"), was built with a clear purpose: to make
information accessible, responses faster, and conversations more meaningful.

- **Empowering the public and private sector**
- **Timely information**
- **Enhancing human engagement**

| Pillar | What it does | Status |
| --- | --- | --- |
| **AI Knowledge Base with the Conversational Agent** | BantAI as an AI chat assistant: empowers teams with AI-driven insights to accelerate response times | Built: `modules/agent` |
| **BantAI Intelligent Workflow Automation** | Intelligent workflow orchestration and automation | Planned |
| **BantAI Strategic Intelligence** | Predictive insights and automated reports: advanced intelligence, predictive analytics and automated insights | Planned |

BantAI's data so far is `WEATHER`, loaded hourly from OpenWeather by
`itoolbox-data-platform`. The public sources to add next, from PAGASA, DOST, LGUs
and others, are in that repo's `DATA_SOURCES.md`.

---

## Tech stack

| | |
| --- | --- |
| **Framework** | FastAPI (Python), served by Uvicorn (`--reload` in dev) |
| **Validation / config** | Pydantic v2 (`pydantic[email]`), `pydantic-settings` |
| **DB / ORM** | SQLAlchemy 2.0 async (`asyncpg`), plain Postgres via Docker locally |
| **Migrations** | Alembic, run automatically on startup |
| **Auth** | Local HS256 JWTs (`python-jose`, `bcrypt`); accounts provisioned by an admin |
| **Data harness** | Zetaris platform API, read-only, over `httpx` |
| **Models** | NVIDIA Nemotron and xAI Grok through the `openai` SDK (both are OpenAI-compatible); Anthropic Claude through the `anthropic` SDK |
| **API contract** | FastAPI's OpenAPI schema, exported to `contract/openapi.api.json` and consumed by `itoolbox-frontend` via `openapi-typescript` |

---

## Layout

```text
apps/
  api/            Platform API — auth, admin, harness, agent modules
    modules/
      auth/       Sign-in, current user, password change
      admin/      User provisioning (admin only)
      harness/    Zetaris client and the read-only SQL guard
      agent/      The investigating agent: tools, model providers, event stream
scripts/
  export_openapi.py   Writes contract/openapi.api.json
contract/         Generated OpenAPI schema — the API contract for itoolbox-frontend
```

The app uses **flat imports** (`from config import get_settings`), so it runs with
`apps/api` as the working directory — it is not a package.

---

## Running locally

Zetaris first, then this stack. Each is its own compose project, and Docker Desktop
lists them together by the `itoolbox_` prefix (`itoolbox_zetaris-platform`,
`itoolbox_backend`, ...):

```bash
(cd ../itoolbox-zetaris-platform && docker compose up -d)   # ui :3001, api :8888
cp .env.example .env                               # then fill it in, see below
docker compose up -d                               # postgres :5435, api :8100
```

| Port | Service | Repo |
| --- | --- | --- |
| 8100 | platform API (`/docs`) | itoolbox-backend |
| 5435 | Postgres (platform tables) | itoolbox-backend |
| 3100 | web | itoolbox-frontend |
| 3001 | Zetaris UI | itoolbox-zetaris-platform |
| 8888 | Zetaris API | itoolbox-zetaris-platform |
| 5436 | TimescaleDB (analysis) | itoolbox-data-platform |
| 8890 | JupyterLab | itoolbox-data-platform |
Every port binds to `127.0.0.1`. Teammates reach the API through Tailscale Serve
on the host, not through the LAN.

The API container runs with `--reload` and `apps/api` bind-mounted, so edits take
effect without a rebuild. Requirement changes need `docker compose up -d --build`.

### `.env`

| Setting | |
| --- | --- |
| `JWT_SECRET` | Required. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | First super_admin, created on startup while there are no users. Change the password after signing in. |
| `ZETARIS_API_KEY` | The agent's key into Zetaris. Create one in Zetaris (`POST /api/v1.0/auth/api-key`) so this file never holds a Zetaris password. |
| `NVIDIA_API_KEY`, `XAI_API_KEY`, `ANTHROPIC_API_KEY` | One per model. A model without its key stays in the picker, marked unavailable. |

### Accounts

There is no public sign-up. Sign in as the seeded super_admin, then create
teammates' accounts with `POST /api/v1/admin/users` (roles: `admin`, `analyst`,
`viewer`).

---

## The agent: BantAI

`POST /api/v1/agent/ask` investigates a question and streams every step as
server-sent events: the agent's progress notes, each tool call, each query's
rows, then a Markdown answer in which every claim cites the query behind it
(`[E1]`, `[E2]`, ...). The event types and their order are documented in
`apps/api/modules/agent/schemas.py`; the schema is `AgentEvent` in the contract.

**Tools.** The agent has four, all through the harness: `list_sources`,
`list_tables`, `describe_table`, `run_sql`. Every successful query becomes
numbered evidence, stored with the investigation and replayable from
`GET /api/v1/agent/investigations/{id}`.

**Read-only by construction.** `run_sql` passes through
`modules/harness/guard.py`, which refuses anything but a single SELECT before it
reaches Zetaris; Zetaris's query endpoint refuses non-SELECT statements as well.

**Models.** Every option is a real LLM; there is no scripted agent. The picker offers:

| id | Provider | Notes |
| --- | --- | --- |
| `nemotron` | NVIDIA, OpenAI-compatible API | Default. Model id in `NVIDIA_MODEL`. |
| `meterless` | NVIDIA Nemotron through [Meterless](https://meterless.ai) Nightshift | Nightshift is a desktop runtime on this machine serving an OpenAI-compatible API on `127.0.0.1:8088`. It holds the NVIDIA key; the API sends `METERLESS_RUNTIME_TOKEN` and `meterless-app: bantai`. Model id in `METERLESS_MODEL`. |
| `gpt` | OpenAI | Model id in `OPENAI_MODEL`. |
| `grok` | xAI, OpenAI-compatible API | Model id in `XAI_MODEL`. |
| `claude` | Anthropic | `claude-opus-5-5` with adaptive thinking at `ANTHROPIC_EFFORT`. Progress notes between tool calls stream as status events (`display: "updates"`), and server-side fallbacks (`fallbacks: "default"`) re-run a request the model's safety classifiers decline on Anthropic's recommended fallback model. |

`GET /api/v1/agent/models/{id}/check` sends the model one tiny real request, so
it also catches a valid key on an account without credits. Run it after setting
a key; it costs a few tokens.

---

## The API contract

`contract/openapi.api.json` is generated from the app and **committed**. It is the
source of truth for the TypeScript types in `itoolbox-frontend`.

```bash
python scripts/export_openapi.py           # regenerate after changing routes or models
python scripts/export_openapi.py --check   # CI guard: fails if the committed schema is stale
```

The exporter is hermetic: it injects placeholder settings and never connects to
a database or to Zetaris. Without a local Python environment, run it in the image:

```bash
docker run --rm -v "$PWD:/repo" -w /repo itoolbox-api python scripts/export_openapi.py
```

Regenerate and commit whenever you change a route or a response model, then run
`npm run gen:types` in `itoolbox-frontend`.
