# Module 02 — MCP Tool Governance: connecting through Agent Manager

**Duration:** 15 min

Module 01 governed *what the model says and costs*. This module puts
Agent Manager in front of the *tool calls* too: instead of each agent
talking straight to the Accounts MCP server, calls are routed through
Agent Manager's **MCP gateway**, secured with a default **API Key**. No
AgentID, no per-tool scopes or roles yet — this module is only about
standing the gateway up and proving the same unmodified MCP server is
now reachable only through it. Per-agent, per-tool access control is
[Module 03, Part B](../03-agentid-and-oauth2/03-2-AgentID/README.md).

This is where the demo moves each agent from **direct MCP mode**
(`MCP_GATEWAY_URL` unset, calls go straight to the MCP server) to
**gateway mode** (`MCP_GATEWAY_URL` + `MCP_GATEWAY_API_KEY` set — calls
routed through Agent Manager, authenticated with an `x-api-key` header —
a different header name than the LLM gateway's `API-Key`). Both modes
are the same
[`agents/customer_support`](../agents/customer_support) /
[`agents/account_assistant`](../agents/account_assistant) code — the
switch is entirely in which env vars are set, see `_build_mcp_client()`
in each agent's `agent.py`.

## Prerequisites

- Module 01 done: both agents registered in Agent Manager, LLM-governed.
- The Accounts MCP server running locally and exposed via a tunnel (e.g.
  `ngrok`), so Agent Manager's MCP gateway can reach it:

  ```bash
  cd mcp_server
  pip install -r requirements.txt
  python server.py
  # → http://localhost:8001/mcp

  ngrok http 8001
  # → note the https forwarding URL, e.g. https://abcd1234.ngrok.io
  ```

## Step 1 — Confirm the gap (direct MCP, no gateway)

With both agents running in direct mode (as in the repo README), call
either one with a prompt that reaches the MCP server:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What accounts does customer cust-1 have?", "session_id": "gap-1"}'
```

This succeeds by talking straight to `MCP_SERVER_URL` — Agent Manager
isn't in the path at all yet.

## Step 2 — Register the MCP server at the org level

1. In the console, go to your **organization** (top-left → **Go to
   organization**), then open **MCP Servers** in the sidebar.
2. Click **Register MCP Server** and fill in:
   - **Name** — e.g. `AccountsMCP`
   - **Handle** — a unique identifier, e.g. `accountsmcp` (auto-fills
     from Name if left blank)
3. Under **Endpoints**, click **Add Endpoint** and fill in:
   - **Endpoint Name** — `main`
   - **MCP Server Endpoint URL** — the ngrok URL from the prerequisites
     (`https://<your-subdomain>.ngrok.io/mcp`)
   - Click **Add Endpoint** again inside the panel to confirm it — the
     console does a live connectivity check and shows the detected
     tool count if the URL is reachable.
4. Click **Create**.
5. Open the new server and confirm on its **Overview** tab that
   **Auth Type** shows **API Key** — this is the default scheme, no
   extra setup needed. Note the header name this scheme validates —
   `x-api-key` — it's different from the LLM gateway's `API-Key`
   header.

## Step 3 — Bind each deployed agent to the MCP server

For each agent (Customer Support and Account Assistant), open the agent
in Agent Manager and follow these steps:

1. Go to the agent's project, open the agent, then click **Configure**
   in the sidebar → **Tool Configurations** tab.
2. Click **Add Tool Configuration** and pick the MCP server registered
   in Step 2 (`AccountsMCP`).
3. The dialog shows **Environment Variable Names** the platform will
   inject — by default derived from the server name (e.g.
   `ACCOUNTSMCP_URL` / `ACCOUNTSMCP_API_KEY`). This agent's code reads
   `MCP_GATEWAY_URL` and `MCP_GATEWAY_API_KEY` instead (see
   `_build_mcp_client()` in `agent.py`), so **override both names** to:
   - `MCP_GATEWAY_URL`
   - `MCP_GATEWAY_API_KEY`
4. Click **Save**.

Agent Manager injects the actual URL and API key values into the
running agent at runtime under those names — no manual `.env` edit, no
redeploy of code, same pattern as binding an LLM provider in Module 01.
Repeat for the Account Assistant agent. Both agents end up with the
same API key, since neither has its own identity yet.

Locally (outside Agent Manager), the equivalent is setting
`MCP_GATEWAY_URL` and `MCP_GATEWAY_API_KEY` by hand in each agent's
`.env` — see `_build_mcp_client()` in each agent's `agent.py`: when
`MCP_GATEWAY_API_KEY` is set, the agent sends it directly as an
`x-api-key` header rather than minting an AgentID token. Note this is a
different header name than the LLM gateway's `API-Key` — the MCP
server's default security scheme validates `x-api-key`.

## Step 4 — Confirm the connection, both agents unrestricted

If either agent is running as a Platform-Hosted Agent (step 3), swap the
`localhost` URLs below for its Agent Manager endpoint instead — open the
agent's page in the console and copy the URL shown on its environment's
**Endpoint** field.

```bash
# Customer Support Agent — now via the gateway
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Please open a new savings account for customer cust-2.", "session_id": "gate-1"}'

# Account Assistant Agent — same gateway, same key
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is the status of the loan application for customer cust-2?", "session_id": "gate-2"}'
```

Both succeed. The point of this module is only that both agents now
reach the MCP server exclusively through Agent Manager, authenticated —
nothing here yet stops either agent from calling any tool. That gap
(Customer Support able to call `open_account` / `transfer_money`) is
closed in Module 03, once each agent gets its own AgentID identity.

## What changed and what didn't

| | Before this module | After |
|---|---|---|
| Agent code | Unmodified | Unmodified |
| MCP calls | Direct to the MCP server, unauthenticated | Through Agent Manager's MCP gateway, `x-api-key` header authenticated |
| Tool access | Any agent, any tool | Still any agent, any tool — access control comes in Module 03 |

## Going further

- `_build_mcp_client()` in each agent's `agent.py` — where the
  direct-vs-gateway mode switch lives.
- See the [repo README's "Notes / things to verify" section](../README.md#notes--things-to-verify-against-your-agent-manager-instance)
  for caveats on this connectivity path.

---

Previous: [Module 01 — LLM Governance](../01-llm-governance/README.md) ·
Next: [Module 03, Part A — OAuth2](../03-agentid-and-oauth2/03-1-OAuth2/README.md)
