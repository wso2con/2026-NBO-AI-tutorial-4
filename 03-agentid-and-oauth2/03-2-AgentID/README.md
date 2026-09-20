# Module 03, Part B — AgentID: per-agent, per-tool access control

**Duration:** 20 min

Module 02 connected both agents to the MCP server through Agent
Manager's gateway, secured with one shared API key — nothing there stops
an agent from calling a tool it has no business calling. The Customer
Support Agent can still steer itself into `open_account` or
`transfer_money` on the same Accounts MCP server the Account Assistant
uses. This module closes that gap: each agent gets its own **AgentID**
identity, and Agent Manager's MCP gateway enforces a per-agent, per-tool
policy in front of the same unmodified MCP server — replacing the shared
API key from Module 02 with per-agent client-credentials.

This is the second half of Module 03. Part A — putting an identity
provider in front of a caller — is a separate module:
[03-1-OAuth2](../03-1-OAuth2/README.md).

## Prerequisites

- Module 02 done: both agents connected to the Accounts MCP server
  through Agent Manager's gateway on the shared API key.
- The Customer Support Agent and the Account Assistant Agent both
  deployed as Platform-Hosted Agents — see
  [03-1-OAuth2, step 3](../03-1-OAuth2/README.md#step-3--deploy-the-customer-support-agent-as-a-platform-hosted-agent)
  for the pattern, pointing at
  [`agents/customer_support`](../../agents/customer_support) and
  [`agents/account_assistant`](../../agents/account_assistant)
  respectively. (Part A's OAuth2 setup on the Customer Support Agent
  itself is not required for this module.)
- The [`webclient`](webclient) side-by-side console, used for the live
  demo below:

  ```bash
  cd webclient
  npm install
  cp .env.example .env   # optional — set default agent URLs, see below
  npm run dev
  # → http://localhost:5173
  ```

  It has one view: Customer Support and Account Assistant side by side,
  a single input that sends the same prompt to both, and a URL field per
  pane (defaulting to `:8000` and `:8002`, or to
  `VITE_CUSTOMER_SUPPORT_URL` / `VITE_ACCOUNT_ASSISTANT_URL` from `.env`
  if set — see `webclient/.env.example`) with a live health chip that
  reads each agent's `mcp_governed` flag off `/health`.

  **If an agent is deployed as a Platform-Hosted Agent** rather than run
  locally, either set its Agent Manager endpoint in `.env` before
  starting the dev server, or paste it into the matching URL field on the
  page and blur it to trigger a health check — both are live-editable
  regardless of the `.env` default. Same applies to the `curl` fallback
  commands below — swap `http://localhost:8000` / `:8002` for the
  deployed endpoint.

## Step 1 — Side-by-side: the gap, live

With both agents still on Module 02's shared API key, open the web
client and send the same risky prompt to both panes at once — either the
shared input or the pre-built chips:

> "Please open a new savings account for customer cust-2."

Both panes show it succeeding. Neither agent's identity is
distinguishable to the MCP server — they're both using the same key.

<details>
<summary>Or via curl</summary>

```bash
# Customer Support Agent (port 8000) reaching into account actions
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Please open a new savings account for customer cust-2.", "session_id": "gap-1"}'

# Account Assistant Agent (port 8002) — same MCP server, no restriction either way
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is the status of the loan application for customer cust-2?", "session_id": "gap-2"}'
```

</details>

## Step 2 — Find each agent's AgentID

1. In Agent Manager, open the Customer Support Agent's page and note its
   **Agent ID**.
2. Do the same for the Account Assistant Agent.

These identifiers are what tool policy gets attached to in step 5 — not
the agent's display name.

## Step 3 — Change the MCP server's authentication to OAuth2

1. Go to **organization level** → **MCP Servers** → open the server
   registered in Module 02.
2. Change the authentication type from **API Key** to **OAuth2**. This
   is what makes per-AgentID policy possible — a shared key can't carry
   per-agent identity, an OAuth2 client-credentials grant can.

## Step 4 — Create scopes for each tool

For each tool the Accounts MCP server exposes, create a scope:

| Tool | Scope |
|---|---|
| `list_accounts` | `accounts:read` |
| `check_balance` | `accounts:read` |
| `get_loan_status` | `loans:read` |
| `open_account` | `accounts:write` |
| `transfer_money` | `accounts:write` |

Grouping read-only account lookups under one scope and the two
money-moving/account-creating actions under another is enough to
demonstrate the split; add finer-grained scopes if your policy needs to
separate them further.

## Step 5 — Create AgentID roles

1. Go to **organization level** → **Agent ID**.
2. Create two roles:
   - **customer-support-role** — scoped to `accounts:read` and
     `loans:read` only.
   - **account-assistant-role** — scoped to `accounts:read` and
     `accounts:write`.
3. Assign **customer-support-role** to the Customer Support Agent's
   AgentID (from step 2), and **account-assistant-role** to the Account
   Assistant's.

## Step 6 — Switch each agent from the shared API key to its own AgentID

With the MCP server now on OAuth2 (step 3) and each agent's AgentID
assigned a role (step 5), Agent Manager automatically swaps what it
injects into each deployed agent: `MCP_GATEWAY_API_KEY` is withdrawn and
replaced with that agent's own `AMP_AGENTID_CLIENT_ID` /
`AMP_AGENTID_CLIENT_SECRET` / `AMP_AGENTID_TOKEN_ENDPOINT` /
`AMP_AGENTID_SCOPES` — `MCP_GATEWAY_URL` stays the same. No redeploy, no
manual step beyond steps 3 and 5 above; each agent gets its **own**
client-credentials, matching the AgentID it was just assigned a role
under.

Locally (outside Agent Manager), the equivalent is editing each agent's
`.env` by hand — don't share one agent's `.env` with the other:

```bash
cd agents/customer_support
# in .env: remove MCP_GATEWAY_API_KEY, fill in this agent's own
# AMP_AGENTID_CLIENT_ID / AMP_AGENTID_CLIENT_SECRET /
# AMP_AGENTID_TOKEN_ENDPOINT / AMP_AGENTID_SCOPES (MCP_GATEWAY_URL stays
# the same as Module 02)
python main.py                                    # http://localhost:8000

cd ../account_assistant
# same fields in .env, but the Account Assistant's OWN client_id/secret
PORT=8002 python main.py                          # http://localhost:8002
```

At startup each agent mints its own access token via client-credentials
grant, scoped to `MCP_GATEWAY_URL` (RFC 8707 `resource` parameter), and
uses it as a Bearer token on every MCP call — see `_build_mcp_client()` /
`_mint_agentid_token()` in each agent's `agent.py`: with
`MCP_GATEWAY_API_KEY` unset, the agent falls through to minting an
AgentID token instead of sending a static `x-api-key` header.

## Step 7 — Demo the side-by-side, governed

Back in the web client (refresh the health chips first — they should
still read `mcp governed` on both panes, now via AgentID instead of the
shared key), send the exact same prompt from step 1 to both agents
again:

> "Please open a new savings account for customer cust-2."

This time the two panes diverge: Account Assistant still succeeds,
Customer Support is denied. That divergence is the demo — the identical
prompt that succeeded on both panes in step 1 is now denied on one of
them, purely because the Customer Support Agent's AgentID role has no
`accounts:write` scope. No code change in either agent between step 1
and here, only which env vars are set.

<details>
<summary>Or via curl</summary>

```bash
# Customer Support Agent — in-scope, still works
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is the status of the loan application for customer cust-2?", "session_id": "amp-1"}'

# Customer Support Agent — out-of-scope, now denied
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Please open a new savings account for customer cust-2.", "session_id": "amp-2"}'

# Account Assistant Agent — in-scope, still works
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Open a new checking account for customer cust-1.", "session_id": "amp-3"}'
```

</details>

## What changed and what didn't

| | Before this module (Module 02) | After |
|---|---|---|
| Agent code | Adds `_mint_agentid_token()` / AgentID client-credentials support to `_build_mcp_client()` | Unmodified from here on — the demo steps (1–7) only ever change which env vars are set |
| MCP auth | One shared API key, no per-agent identity | Per-agent AgentID client-credentials, Bearer-authenticated |
| Tool access | Any agent, any tool | Per-AgentID role, per-tool scope |
| Customer Support calling `open_account`/`transfer_money` | Succeeds | Denied |

The AgentID-minting code (`_mint_agentid_token()`, and the
`MCP_GATEWAY_API_KEY`-unset fallback in `_build_mcp_client()`) already
ships in `agent.py` going into this module — it isn't written during the
steps above. What steps 1–7 do is entirely configuration: swap the MCP
server to OAuth2, assign AgentID roles, and let Agent Manager swap which
env vars it injects. That's the "Unmodified from here on" in the table —
no line of `agent.py` changes between step 1 and step 7.

## Module 03 end to end

| | Part A (OAuth2) | Part B (AgentID/MCP, this module) |
|---|---|---|
| Identity belongs to | The human/caller signed in via Asgardeo | Each deployed agent itself |
| Enforced on | The agent's own `/chat` endpoint | The MCP gateway's tool calls |
| Denies | Unauthenticated callers | Out-of-scope tool calls, per agent |

Together, Modules 01–03 cover what the model says and costs, connecting
to tools through a gateway, who can call an agent, and which tools that
agent is allowed to use once it's calling them.

## Going further

- `_mint_agentid_token()` / `_build_mcp_client()` in each agent's
  `agent.py` — where the AgentID token is minted and attached, and where
  the direct-vs-gateway mode switch lives.
- See the [repo README's "Notes / things to verify" section](../../README.md#notes--things-to-verify-against-your-agent-manager-instance)
  for caveats on this policy path (denial error shape, what was and
  wasn't confirmed against a live gateway at last test).

---

Previous: [Module 03, Part A — OAuth2](../03-1-OAuth2/README.md) ·
Next: [Module 04 — Agent Catalog](../../04-agent-catalog/README.md)
