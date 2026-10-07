# CLAUDE.md

Context for AI coding assistants (Claude, Cursor, Copilot, etc.) working in this repo.

## What this is

MCP server that connects Google Search Console to AI assistants.
Single file: `gsc_server.py` (~2,100 lines). Built with FastMCP — no custom framework.

## Running locally

```bash
uv sync
uv run python gsc_server.py
```

## Auth

Two modes, tried in order:

1. **OAuth (default):** Place `client_secrets.json` in the repo root. On first run, a browser window opens for Google login. Token saved to `token.json` (gitignored), auto-refreshes when expired.
2. **Service account:** Set `GSC_CREDENTIALS_PATH` to the path of your service account JSON key file.

Set `GSC_SKIP_OAUTH=true` to force service account mode and skip OAuth entirely.

## Key environment variables

| Variable | Default | Description |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `http` (streamable HTTP at `/mcp`) or `sse` for remote/Docker/network use |
| `MCP_HOST` | `127.0.0.1` | Host to bind when `MCP_TRANSPORT=sse` |
| `MCP_PORT` | `3001` | Port to bind when `MCP_TRANSPORT=sse` |
| `GSC_DATA_STATE` | `all` | `all` = matches GSC dashboard; `final` = confirmed data only (2–3 day lag) |
| `GSC_ALLOW_DESTRUCTIVE` | `false` | Set `true` to enable `add_site`, `delete_site`, `delete_sitemap` |
| `GSC_CREDENTIALS_PATH` | — | Path to service account JSON key file |
| `GSC_OAUTH_CLIENT_SECRETS_FILE` | `client_secrets.json` | Path to OAuth client secrets file |
| `GSC_SKIP_OAUTH` | `false` | Set `true` to skip OAuth and use service account only |
| `GSC_READ_ONLY` | `false` | Set `true` to request `webmasters.readonly`; write tools refuse to run |
| `MCP_AUTH_TOKEN` | — | Bearer token for the `http`/`sse` transports (`/healthz` stays open) |

## Adding a new tool

1. Add an `@_tool` decorated async function anywhere in `gsc_server.py`
2. Use `get_gsc_service()` for auth — it handles OAuth and service account automatically
3. Run API calls as `await _execute(request)`, never `request.execute()` — the client
   library is blocking and would stall the event loop. Synchronous helpers that a tool
   already hands to a worker thread (`_inspect_single_url`, `_summarise_property`, ...)
   call `.execute()` directly and build their own service.
4. Return `json.dumps(result)` not formatted text strings (LLMs work better with structured data)
5. Return failures as `_err("...")`. `_tool` reports them to MCP clients with `isError`
   set, while direct callers (tests, other tools) still receive the message string.

```python
@_tool
async def my_new_tool(site_url: str) -> str:
    """One-line description shown to the AI as the tool's purpose."""
    try:
        service = get_gsc_service()
        result = await _execute(service.someApi().someMethod(siteUrl=site_url))
        return json.dumps(result)
    except Exception as e:
        if "404" in str(e):
            return _site_not_found_error(site_url)
        return _err(f"Error: {str(e)}")
```

## Running tests

```bash
pytest test_gsc_server.py -v
```

No credentials needed — all Google API calls are mocked with `unittest.mock`.

## Docker

```bash
docker build -t mcp-gsc .
docker run -e MCP_AUTH_TOKEN=change-me -v /path/to/data:/data -p 3001:3001 mcp-gsc
```
