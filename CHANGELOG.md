# Changelog

## 0.5.0 — 2026-10-07 (Minicon fork)

- New `get_portfolio_overview` tool: every property at once, with change versus the previous period and top query/page
- Tool failures set `isError` (upstream #53)
- OAuth tokens load with their granted scopes; only `invalid_grant` moves the token aside; new `GSC_READ_ONLY` (upstream #56)
- Blocking API calls run in worker threads (upstream PR #52); optional args accept null (upstream PR #58); `mcp>=1.27.2` (upstream PR #40)
- `MCP_TRANSPORT=http` serves streamable HTTP; `MCP_AUTH_TOKEN` bearer auth and `/healthz` for network transports
- `compare_search_periods` gains `search_type`; `has_more` fixed for row limits above the API cap

## 2026-04-13

- Bump all Python dependencies to their latest minor/patch versions via `uv lock --upgrade` (thanks @Herriaan, #24)
  - google-api-python-client 2.163.0 -> 2.194.0
  - google-auth 2.38.0 -> 2.49.2
  - google-auth-httplib2 0.2.0 -> 0.3.1
  - google-auth-oauthlib 1.2.1 -> 1.3.1
  - mcp 1.3.0 -> 1.27.2
  - pydantic 2.10.6 -> 2.13.4
  - plus various transitive dependencies
