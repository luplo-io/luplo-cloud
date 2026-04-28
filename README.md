# luplo-cloud

Single-install bundle for luplo on the hosted cloud. Pulls in
[luplo](https://pypi.org/project/luplo/) (the OSS engine) and adds `lps`,
the cloud companion for log-in, API keys, workspace bootstrap, and editor
wiring. After installing this package you have two binaries:

| Binary | Source       | Role |
|--------|--------------|------|
| **`lp`**  | `luplo`        | The luplo CLI / stdio MCP server. Talks to local Postgres by default, or — when `.luplo` declares `type = "remote"` — through the hosted cloud HTTP API. 23 MCP tools. |
| **`lps`** | `luplo-cloud`  | Cloud-only commands: `login`, `logout`, `whoami`, `init`, `mcp-config`. |

## Install

    uv tool install luplo-cloud
    # or:  pipx install luplo-cloud
    # or:  pip install luplo-cloud

`luplo` (which provides `lp`) is pulled in transitively — no separate
install step.

## Three deployment modes

luplo runs in one of three modes. You pick by how `.luplo` is configured
(or by env var). The MCP tool surface is the same in all three; only the
data path changes.

| Mode | Where data lives | How it's reached | Auth | Set up by |
|------|-------------------|-------------------|------|-----------|
| **Local**  | Your Postgres    | `lp` → psycopg pool → PG (no HTTP)            | none  | `lp init` (creates `.luplo` with `type="local"`) |
| **Remote** | Hosted luplo cloud | `lp` → HTTPS → `api.luplo.io`                 | OAuth or API key | `lps login` + `lps init` |
| **Cloud /mcp direct** | Hosted luplo cloud | Claude Desktop/Code → HTTPS → `api.luplo.io/mcp` (FastMCP, no `lp` process) | OAuth or API key | `lps login` + `lps mcp-config` |

If you're a single dev with your own Postgres → **Local**. If you're a team
on the hosted cloud and want `lp` to operate as if data were local →
**Remote**. If you just want Claude to talk to your cloud project with no
local process → **Cloud /mcp direct**.

## Auth model (cloud paths only)

| Token              | How obtained          | Where it lives             | Used by                |
|--------------------|-----------------------|----------------------------|------------------------|
| OAuth (browser)    | `lps login`           | OS keyring                 | Desktop / interactive  |
| API key (`lupk_…`) | Issued in the web app | `LUPLO_CLOUD_API_KEY` env  | Servers / CI / IaC     |

API keys are scoped to a single organization (and optionally a subset of
projects) at issuance — least privilege by default.

`lp` and `lps` agree on token resolution priority for cloud paths:
**`LUPLO_CLOUD_API_KEY` env wins**, then the OS keyring entry written by
`lps login`. So a single `lps login` is enough for `lp mcp` in remote mode
to start working — no env-var copy/paste.

## Quickstart — Desktop, hosted cloud (most common)

```bash
lps login                                # browser opens; OAuth tokens → keyring
cd /path/to/your/project
lps init                                 # picker: org + project → writes ./.luplo
lp mcp                                   # 23-tool stdio MCP server, remote mode
```

`lps init` writes a `.luplo` TOML in the current directory like:

```toml
[backend]
type = "remote"
server_url = "https://api.luplo.io"

[project]
id = "<project-id>"
name = "Your project"
```

The file is safe to commit — it has no secrets. Subsequent `lp` calls in
this directory automatically read the binding.

`lps init` flag matrix:

```bash
lps init                                  # full picker
lps init --org <org-id>                   # org locked, project picker
lps init --org <org-id> --project <id>    # non-interactive, bind existing
lps init --org <org-id> --new-project foo # non-interactive, create new
lps init --force                          # overwrite an existing .luplo
```

## Quickstart — Cloud `/mcp` direct (no local process)

If you want Claude Desktop / Code to hit the cloud directly without
running an `lp` process:

```bash
lps login                                # if you don't already have a key
lps mcp-config | tee ~/.claude.json      # emits {"mcpServers": {"luplo": {url, transport, auth}}}
```

Default Claude config locations:
- macOS Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux Claude Desktop: `~/.config/Claude/claude_desktop_config.json`
- Claude Code: `~/.claude.json` (global), or `claude mcp add …` (project)

## Quickstart — Server / CI (headless)

No browser, no keyring backend required.

```bash
# 1) Issue a key in the web app:
#    https://app.luplo.io/settings/api-keys → "+ New API key"
#    Pick org, scope (all projects or specific), expiry (≤ 365 days).
#    The raw lupk_... is shown ONCE — copy it now.

# 2) Inject the key (e.g. /etc/environment, systemd EnvironmentFile, or
#    your secret manager).
export LUPLO_CLOUD_API_KEY=lupk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 3) Smoke test.
lps whoami                               # prints email + actor_id

# 4a) Emit a Claude config that uses the key as bearer.
lps mcp-config | tee ~/.claude.json

# 4b) Or wire MCP directly via Claude Code (no config file edit).
claude mcp add --scope user --transport http luplo \
  https://api.luplo.io/mcp \
  --header "Authorization: Bearer $LUPLO_CLOUD_API_KEY"
```

## Configuration

| Env var                    | Default                    | Purpose                         |
|----------------------------|----------------------------|---------------------------------|
| `LUPLO_CLOUD_API_KEY`      | (unset)                    | Headless bearer (`lupk_...`)    |
| `LUPLO_CLOUD_SERVER_URL`   | `https://api.luplo.io`     | API base — override for staging |
| `LUPLO_CLOUD_APP_URL`      | `https://app.luplo.io`     | Web app base — override for staging |
| `LUPLO_DB_URL`             | `postgresql://localhost/luplo` | Local-mode DB (used by `lp` when `.luplo` says `type="local"` or no `.luplo` is found) |

## Commands

`lps` (this package):
- `lps login` — browser-based OAuth, tokens stored in OS keyring
- `lps logout` — revoke the local refresh token + clear keyring
- `lps whoami` — print the email + actor_id of the authenticated principal
- `lps init` — write a `.luplo` workspace file binding cwd to a cloud project
- `lps mcp-config` — emit a `mcpServers` JSON entry pointing at cloud `/mcp`

`lp` (from the bundled `luplo` package — see
[the luplo README](https://github.com/luplo-io/luplo) for the full list):
- `lp mcp` — start the stdio MCP server (local or remote, per `.luplo`)
- `lp init`, `lp items`, `lp work`, `lp brief`, `lp impact`, `lp check`, … (23 MCP tools as CLI subcommands too)

## License

MIT — see [LICENSE](LICENSE). The bundled `luplo` package is AGPL-3.0-or-later;
its terms apply to *its* code, not to this MIT package.
