# Spike: connecting the Claude desktop app to the AI coach (M10)

Status: Phase A result. "Verified" = read in the installed HA 2026.10.4 source or tested in `tests/test_coach_mcp.py`;
"PM test" = needs a real Claude desktop app and a real HA instance.

## What is verified (HA side)
- The coach is an LLM API `magister_coach` ("Magister huiswerkcoach"). HA's `mcp_server` serves registered LLM APIs
  on `POST /api/mcp` (Streamable HTTP, stateless; selected APIs, option "require admin") and on `/api/mcp/<api_id>`.
- `/api/mcp/<api_id>` needs an **admin** user for every API except Assist. The main `/api/mcp` is open to any
  authenticated user when "require admin" is off. Tested: a non-admin linked user lists tools, calls `add_subtask`
  and reads the prompt via `/api/mcp`; `/api/mcp/magister_coach` gives 401 for that user; with "require admin" on,
  `/api/mcp` gives 401 as well.
- The tools get `context.user_id` from the authenticated request. An unlinked user is served but gets
  `not_linked` errors and no data (tested).
- The server is **single-config-entry**: set "LLM APIs" to only "Magister huiswerkcoach" (otherwise students also get
  every other selected API, e.g. Assist tools).
- HA auth: bearer access tokens (also long-lived tokens). OAuth2 authorization code + PKCE (S256) at `/auth/authorize`
  and `/auth/token`; discovery at `/.well-known/oauth-authorization-server` and, since this HA version,
  `/.well-known/oauth-protected-resource` (RFC 9728, also in the `WWW-Authenticate` header of a 401). Client ids are
  URLs (IndieAuth); a redirect URI on another host is accepted only if the client_id page lists it
  (link tag or Client ID Metadata Document, advertised as `client_id_metadata_document_supported`).
  There is **no dynamic client registration** endpoint (`registration_endpoint`).

## Option (a): remote connector to `https://<ha>/api/mcp` with HA login
Public docs (support.claude.com, custom connectors): the connector URL must be on standard HTTPS port 443, Claude connects
**from Anthropic's cloud** (so HA must be reachable from the internet, or Anthropic's IP ranges allow-listed),
callback `https://claude.ai/api/mcp/auth_callback`, OAuth client options: Claude's published identity, register
automatically, or own client id/secret. Settings: Authentication "Sign in now".
- Likely to work only if Claude's published identity is a client-id-metadata-document client that HA accepts
  (HA advertises support). **PM test.** If Claude falls back to dynamic registration, it fails (HA has none).
- Alternative inside option (a): a header-based connector with "Request headers" `Authorization: Bearer <long-lived token
  of the student's user>` (no OAuth). Docs say this is supported for bearer-token servers. **PM test.**
- Needs: HA externally reachable over HTTPS on 443 (Nabu Casa Cloud URL or reverse proxy). Not suitable for HA at home only.
- Security: every OAuth login grants the student's HA user; keep the user non-admin and limit it to the coach
  (HA users cannot be restricted to one endpoint; the same user can use the HA app, so use a dedicated user).

## Option (b): local bridge with a long-lived token (home network)
Claude Desktop supports local stdio MCP servers in `claude_desktop_config.json` (docs: separate mechanism, local network;
not available in claude.ai or cloud sessions). Bridge a stdio client to HA's Streamable HTTP endpoint with `mcp-proxy`
(or `mcp-remote`). Not verified here. **PM test.**

```json
{
  "mcpServers": {
    "magister": {
      "command": "mcp-proxy",
      "args": [
        "--transport", "streamablehttp",
        "http://homeassistant.local:8123/api/mcp"
      ],
      "env": { "API_ACCESS_TOKEN": "<long-lived token of the student's HA user>" }
    }
  }
}
```
(`mcp-proxy` from `sparfenyuk/mcp-proxy` reads `API_ACCESS_TOKEN` and sends `Authorization: Bearer`; alternatively
`npx mcp-remote http://homeassistant.local:8123/api/mcp --header "Authorization: Bearer <token>" --allow-http`.
Check the flags of the installed version.) The token is created on the student's HA profile (Security, Long-lived
access tokens) and is stored in plain text in the Claude config on that computer.

## Settings in HA (both options)
1. A non-admin HA user per student.
2. Integration "Model Context Protocol Server": LLM APIs = only "Magister huiswerkcoach", **require admin = off**.
3. Magister, Configure, AI-coach: enable per child and link the user.

## Open points for the PM test
1. Does Claude desktop's remote connector complete HA's OAuth (CIMD) or fail for lack of registration?
2. Does the bearer-header connector work and is a long-lived token acceptable?
3. `mcp-proxy` flags and token handling in the installed version.
4. Do tool annotations (destructive on delete/remove) trigger a confirmation in Claude?

Recommendation: document (b) first (works on the home network, only needs a token), (a) as "if HA is reachable over HTTPS".
