# luplo-cloud

CLI for the hosted [luplo](https://pypi.org/project/luplo/) cloud. Log in, manage access keys, and wire the luplo MCP server into your editor.

## Install

    pip install luplo luplo-cloud

## Quickstart

### Interactive login

    lps login

Opens a browser to https://app.luplo.io/login and stores tokens in your OS keyring.

### Headless / server use

Issue an access key at https://app.luplo.io/settings/api-keys, then:

    export LUPLO_SAAS_API_KEY=lupk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    lps whoami    # uses the api key, no browser needed

### MCP setup

    lps mcp-config

Outputs a Claude Desktop / Claude Code MCP config snippet.

## License

MIT — see [LICENSE](LICENSE).
