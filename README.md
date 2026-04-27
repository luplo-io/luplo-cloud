# luplo-cloud

CLI (`lps`) for the hosted [luplo](https://pypi.org/project/luplo/) cloud.
Log in, manage access keys, and wire the luplo MCP server into your editor.

## Install

    uv tool install luplo luplo-cloud
    # or:  pipx install luplo-cloud
    # or:  pip install luplo luplo-cloud

## Auth model

Two ways the CLI authenticates, used in different scenarios:

| Token              | How obtained          | Where it lives             | Used by                |
|--------------------|-----------------------|----------------------------|------------------------|
| OAuth (browser)    | `lps login`           | OS keyring                 | Desktop / interactive  |
| API key (`lupk_…`) | Issued in the web app | `LUPLO_CLOUD_API_KEY` env  | Servers / CI / IaC     |

`lps mcp-config` picks the API key when `LUPLO_CLOUD_API_KEY` is set, otherwise
falls back to the OAuth token in the keyring. API keys are scoped to a single
organization (and optionally a subset of projects) at issuance — least
privilege by default.

## Quickstart — Desktop (interactive)

```bash
lps login                                # browser opens, OAuth → tokens → keyring
lps mcp-config | tee ~/.claude.json      # or paste into Claude Desktop config
```

Default Claude config locations:
- macOS Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux Claude Desktop: `~/.config/Claude/claude_desktop_config.json`
- Claude Code: `~/.claude.json` (global), or run `claude mcp add ...` (project)

## Quickstart — Server / CI (headless)

No browser, no keyring backend required.

```bash
# 1) Issue a key in the web app:
#    https://app.luplo.io/settings/api-keys → "+ New API key"
#    Pick org, scope (all projects or specific), expiry (≤ 365 days).
#    The raw lupk_... is shown ONCE — copy it now.

# 2) Inject the key on the server (e.g. /etc/environment, systemd EnvironmentFile,
#    or your secret manager).
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

## Commands

- `lps login` — browser-based OAuth, tokens stored in OS keyring
- `lps logout` — revoke the local refresh token + clear keyring
- `lps whoami` — print the email and actor_id of the authenticated principal
- `lps mcp-config` — emit a `mcpServers` JSON entry; bearer is the API key if
  `LUPLO_CLOUD_API_KEY` is set, otherwise the OAuth token

## License

MIT — see [LICENSE](LICENSE).
