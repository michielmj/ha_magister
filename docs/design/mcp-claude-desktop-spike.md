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
- **Isolation holds only for the coach API.** The coach tools only reach the children linked to the user, but the
  user's token is a normal HA token. A non-admin HA user can still read all entity states over HA's REST/WebSocket
  API and in the app, including the calendars of all children, whose event descriptions contain teacher names and
  codes. Treat the token (and the user's HA login) as access to that data.

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
`npx mcp-remote http://homeassistant.local:8123/api/mcp --header "Authorization:${AUTH_HEADER}" --allow-http` with `AUTH_HEADER=Bearer <token>` in the entry's `env`.
Check the flags of the installed version.) The token is created on the student's HA profile (Security, Long-lived
access tokens) and is stored in plain text in the Claude config on that computer.

Security of (b):
- The long-lived token sits in plain text in `claude_desktop_config.json`. The same caveat applies: besides the coach
  API, that token can read all entity states over HA's REST/WebSocket API (all children's calendars, with teacher names
  and codes in the event descriptions). Isolation holds only for the coach API.
- `http://` on the LAN sends the bearer token unencrypted. Use HTTPS where available (reverse proxy or Nabu Casa).
- Phase B's README privacy section must carry both points (isolation only for the coach API; HTTPS recommended).

## Settings in HA (both options)
1. A non-admin HA user per student.
2. Integration "Model Context Protocol Server" (HA 2026.10.4): adding it exposes all LLM APIs with require admin on. Change it under **Configure**: turn **Expose all LLM APIs** off and press Submit (the form reopens with the API list), select only "Magister huiswerkcoach" in the API picker (label "Control Home Assistant", nl "Beheer Home Assistant", shown only when "Expose all" is off), turn **Require an administrator account** off, and press Submit again. Leaving "Expose all LLM APIs" on gives students Assist via /api/mcp. Turning it off does not remove Assist fully: `/api/mcp/assist` stays open to every HA user (non-admin included) for the entities exposed to Assist (Settings, Voice assistants, Expose).
3. Magister, Configure, AI-coach: enable per child and link the user.

## Live test outcome (2026-11-15, M12)
The PM connected Claude to the coach through the remote connector (option a) and the Architect ran a read and write
test as a parent. Everything worked.
- **Remote connector, Authentication "Sign in now", OAuth client "Use Claude's published identity"** (the default, no
  headers): works once the reverse-proxy settings are correct (`http: use_x_forwarded_for: true` and `trusted_proxies`
  with the proxy network, e.g. `172.30.33.0/24` for the NGINX add-on). **Before that it failed with "Couldn't
  register"**: HA built its login metadata (`/.well-known/oauth-authorization-server`) from the internal address of the
  proxy instead of the public one.
- **Fallback:** "Use your own OAuth client" with Client ID `https://claude.ai/` and no secret. HA accepts a client ID on
  the same host as the return address.
- Also needed: the user must not have "Local access only" on, and "Require an administrator account"
  must be off in the MCP Server (saved with the last Submit); otherwise Claude shows "Couldn't reload tools from the
  server".
- With several Magister logins, the coach must be enabled and linked in each one.
- Restoring a label a parent's AI had disabled works (M11 decision 1 stays).
- Not tested: the bearer-header connector and the local bridge (option b).
- Rough edges found, fixed in 1.7.1 (M12): too many old overdue items, cancelled lessons counted as overdue, and an
  unclear `not_linked` for a linked user whose coach is off (now `coach_not_enabled`).

## Open points for the PM test
1. Does Claude desktop's remote connector complete HA's OAuth (CIMD) or fail for lack of registration? **Answered:** it works with the published identity once the proxy settings are right (see above).
2. Does the bearer-header connector work and is a long-lived token acceptable?
3. `mcp-proxy` flags and token handling in the installed version.
4. Do tool annotations (destructive on delete/remove) trigger a confirmation in Claude?

Recommendation (updated after the live test): document (a), the remote connector, first, and (b) as the alternative for
a HA that is not reachable over HTTPS from the internet.
