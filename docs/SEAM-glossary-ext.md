# Glossary Extension — Worker Seam Contract

This doc is the contract between the substrate scope (this codebase) and
the worker scope (next). Workers must read/write only the tables and
formats described here. They MUST NOT modify substrate code.

## Tables

### `jobs` (workers consume)

Generic queue, scoped per worker via `job_type`. Schema:

| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | uuid string |
| `job_type` | `text NOT NULL` | e.g. `glossary.extract`, `glossary.embed` |
| `status` | `text NOT NULL DEFAULT 'pending'` | CHECK in `('pending','running','done','failed')` |
| `fail_count` | `integer NOT NULL DEFAULT 0` | bumped on each failed claim |
| `fail_reason` | `text` | last error string |
| `status_changed_at` | `timestamptz NOT NULL DEFAULT now()` | bookkeeping |
| `kv` | `jsonb NOT NULL DEFAULT '{}'::jsonb` | job payload (see schemas below) |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | enqueue time |
| `updated_at` | `timestamptz NOT NULL DEFAULT now()` | DAO-managed; no trigger |

Indexes:
- `idx_jobs_pending ON (created_at) WHERE status = 'pending'` — partial, FIFO claim
- `idx_jobs_type_status ON (job_type, status)` — admin queries
- `uq_jobs_dedup_key_active UNIQUE ON ((kv->>'dedup_key'), job_type) WHERE status IN ('pending','running') AND kv ? 'dedup_key'` — substrate dedup

### `glossary_term_embeddings` (workers write)

| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | uuid string |
| `project_id` | `text NOT NULL REFERENCES projects(id)` | FK to OSS |
| `surface` | `text NOT NULL` | display form |
| `normalized` | `text NOT NULL` | lookup key |
| `model_id` | `text NOT NULL` | e.g. `baai/bge-m3` |
| `vector` | `vector(1024)` | nullable; populated by embed worker |
| `linked_term_id` | `text REFERENCES glossary_terms(id)` | optional back-link to confirmed term |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

Constraints:
- `UNIQUE (project_id, normalized, model_id)` — one embedding per term per model

### `glossary_suggestions` (workers write candidate rows)

| Column | Type | Notes |
|---|---|---|
| `id` | `text` PK | uuid string |
| `project_id` | `text NOT NULL REFERENCES projects(id)` | |
| `kind` | `text NOT NULL` | CHECK `('pair','term')` |
| `candidate_surface` | `text NOT NULL` | display form |
| `candidate_normalized` | `text NOT NULL` | lookup key |
| `target_group_id` | `text REFERENCES glossary_groups(id)` | required for `kind='pair'`, NULL for `kind='term'` |
| `similarity` | `double precision` | cosine similarity for pair candidates; NULL for term |
| `source_item_id` | `text REFERENCES items(id)` | provenance |
| `context_snippet` | `text` | provenance excerpt |
| `extracted_by_model` | `text NOT NULL` | e.g. `qwen/qwen3.6-35b-a3b` |
| `extracted_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `reserved_by` | `uuid REFERENCES actors(id)` | substrate-only (lease) |
| `reserved_at` | `timestamptz` | substrate-only |
| `consumed_at` | `timestamptz` | substrate-only (decision committed) |
| `consumed_decision` | `text` | substrate-only; CHECK in `('alias','canonical_replace','sibling','create','reject')` |

Indexes:
- `idx_suggestions_available ON (project_id, kind, similarity DESC NULLS LAST) WHERE consumed_at IS NULL AND reserved_at IS NULL` — partial
- `idx_suggestions_leased ON (reserved_by, reserved_at) WHERE reserved_at IS NOT NULL AND consumed_at IS NULL` — partial

## Job payload schemas

- `glossary.extract`: `{"item_id": str, "project_id": str}`
- `glossary.embed`: `{"surface": str, "normalized": str, "project_id": str, "candidate_id": str | null}`

## Worker responsibilities (out of this scope)

1. Consume `jobs.status='pending'` rows via `FOR UPDATE SKIP LOCKED`.
2. For `glossary.extract`: load item body, call OpenRouter
   `qwen/qwen3.6-35b-a3b` to extract candidate terms, filter by:
   - `ts_stat` frequency floor (configurable)
   - dedupe against `glossary_terms WHERE status IN ('canonical','alias')`
   - dedupe against `glossary_rejections`
   - existing rows in `glossary_suggestions` for same project + normalized
3. For each surviving candidate, enqueue `glossary.embed` job.
4. For `glossary.embed`: call OpenRouter `baai/bge-m3`, upsert
   `glossary_term_embeddings`, then compute pgvector cosine against the
   project's existing embeddings; if any pair >= 0.85 similarity, INSERT
   `glossary_suggestions` rows with `kind='pair'` and `target_group_id`
   set; otherwise INSERT with `kind='term'` and `target_group_id NULL`.
5. On job success: `status='done'`. On failure: `status='failed'`,
   `fail_count++`, `fail_reason` set.

## Substrate guarantees

- Substrate writes only `reserved_*` and `consumed_*` columns on
  `glossary_suggestions`. Workers MUST NOT touch those.
- Substrate reads `jobs` only for diagnostics; workers own the lifecycle.

## API key access (worker-scope, but seam clarified here)

OpenRouter calls (`qwen/qwen3.6-35b-a3b`, `baai/bge-m3`) require BYO API
keys per organisation. Keys live encrypted in the **SaaS DB**'s
`api_keys` table (`luplo-cloud/api/src/luplo_saas/domains/api_keys/`),
which is a different Postgres instance from the OSS DB where the
glossary substrate lives.

The worker process MUST therefore hold two database handles:

| Env | Purpose | Access mode |
|---|---|---|
| `LUPLO_DB_URL` (OSS DB) | jobs, suggestions, embeddings, glossary tables | read + write |
| `LUPLO_SAAS_DB_URL` (SaaS DB) | api_keys, org_projects | read-only |

Suggested pattern:

```python
# In the worker process bootstrap:
oss_pool = AsyncConnectionPool(os.environ["LUPLO_DB_URL"], min_size=2, max_size=8)
saas_pool = AsyncConnectionPool(
    os.environ["LUPLO_SAAS_DB_URL"], min_size=1, max_size=4,
)

async def fetch_openrouter_key_for_project(project_id: str) -> str:
    async with saas_pool.connection() as conn:
        # Resolve org_id from org_projects, then api_keys (read-only).
        ...
```

The worker MUST NOT write to the SaaS DB. Key issuance and rotation stay
the responsibility of the api repo's existing `api_keys` flow.

## Empty-queue behavior

Until workers exist, `glossary_suggestions` is empty. The `lps glossary
suggest` CLI prints "No pending suggestions." and exits 0. The MCP
tools (`glossary_link`, `glossary_add_group`, `glossary_link_sibling`)
work without workers — they are direct user actions.
