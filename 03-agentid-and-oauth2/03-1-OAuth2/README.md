# Module 03, Part A — OAuth2: from an open endpoint to a signed-in guest

**Duration:** 20 min

Modules 01 and 02 governed what the model says and costs, and put a
gateway (API-Key secured) in front of MCP calls — but neither one
restricts who can call `/chat`. This part puts an identity provider in
front of it — first at the Agent Manager layer, then in the web client
guests actually use — without touching a line of the agent's code.

Part B — per-agent, per-tool access control via AgentID — is a separate
module: [03-2-AgentID](../03-2-AgentID/README.md).

## Prerequisites

- An [Asgardeo](https://asgardeo.io) account (free tier is enough).
- Modules 01–02 done: the Customer Support Agent LLM-governed and
  reachable through Agent Manager's MCP gateway.

## Step 1 — Create an Asgardeo organization

1. Sign up at [asgardeo.io](https://asgardeo.io) and create an
   organization if you don't have one already.
2. Note the organization name — it becomes part of every endpoint you use
   below, in the form `https://api.asgardeo.io/t/<org-name>`.

## Step 2 — Register Asgardeo as a key manager in Agent Manager

Agent Manager doesn't issue tokens itself — it validates tokens issued by
a key manager you register.

1. Log in to the Agent Manager console.
2. Go to the **organization level** (not a specific project) → **Gateways**.
3. Open the **default gateway** and click to add a **Key Manager**.
4. Provide Asgardeo's well-known endpoint:

   ```
   https://api.asgardeo.io/t/<org-name>/oauth2/token/.well-known/openid-configuration
   ```

   Agent Manager reads issuer, JWKS, and token endpoint details from this
   document — nothing else needs to be typed in by hand.
5. Save. The key manager should show as active before you continue.

## Step 3 — Deploy the Customer Support Agent as a Platform-Hosted Agent

If it isn't already registered as a Platform-Hosted Agent (as opposed to
an Externally-Hosted Agent that Agent Manager merely proxies to) — see
the pattern in the
[tutorial-3 lab, module 01](https://github.com/wso2con/2026-NBO-AI-tutorial-3/blob/main/01-build-deploy/README.md)
if you need the general build/deploy flow:

1. **Add Agent → Platform-Hosted Agent → Source Code**, pointing at
   [`agents/customer_support`](../../agents/customer_support).
2. Configure env vars as in Modules 01–02 (`OPENAI_API_KEY` or
   `LLM_GATEWAY_*`; `MCP_SERVER_URL` or `MCP_GATEWAY_URL`).
3. Deploy.

This step only matters if the agent has been running purely locally up
to now — every Platform-Hosted Agent automatically gets an AgentID
identity on deployment, which the AgentID module keys tool policy on.

## Step 4 — Confirm the gap (no auth)

With the agent deployed but no security scheme configured on its Agent
Manager listener yet:

```bash
curl -N -X POST "$AGENT_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message": "What accounts does customer cust-1 have?", "session_id": "demo-1"}'
```

This succeeds with no credentials at all. Keep this response in mind —
step 6 repeats the exact same call.

## Step 5 — Enable OAuth2 on the deployed agent

1. Open the agent's **Deploy** page → **Development** environment →
   **Configurations and Secrets** → **Configure**.
2. Select **OAuth2** as the security scheme and pick the key manager you
   registered in step 2.
3. **Save.**

## Step 6 — Recheck invoking (now fails)

Run the identical `curl` from step 4 against the deployed agent's
gateway URL, still with no token:

```bash
curl -N -X POST "$AGENT_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message": "What accounts does customer cust-1 have?", "session_id": "demo-1"}'
```

Expect a `401`. Same request, same agent code, same conversation history
model — the only thing that changed is a configuration toggle at the
gateway. That's the point to narrate: authorization moved out of the
agent and into the platform in front of it.

## Step 7 — Register a single-page app in Asgardeo

The webapp guests use needs its own OAuth2 client.

1. In the Asgardeo console, go to **Applications** → **New Application** →
   **Single-Page Application**.
2. Set the redirect URL to match the web client's dev origin, e.g.
   `http://localhost:5174`.
3. Copy the **Client ID** — you'll need it next. SPAs use the
   authorization-code-with-PKCE flow, so there's no client secret to copy.

## Step 8 — Configure the web client for login

The support web client at
[`webclient-support`](webclient-support) already has Asgardeo sign-in
wired in via `@asgardeo/auth-react` (see
[`src/authConfig.js`](webclient-support/src/authConfig.js)) — configure it
with the values from step 7:

```bash
cd webclient-support
npm install
cp .env.example .env
```

Edit `.env`:

```bash
VITE_ASGARDEO_BASE_URL=https://api.asgardeo.io/t/<org-name>
VITE_ASGARDEO_CLIENT_ID=<client-id-from-step-7>
VITE_ASGARDEO_SIGN_IN_REDIRECT_URL=http://localhost:5174
VITE_ASGARDEO_SIGN_OUT_REDIRECT_URL=http://localhost:5174
VITE_AGENT_BASE_URL=<agent-url-from-step-5>
```

```bash
npm run dev
# → http://localhost:5174
```

## Step 9 — Verify

Open `http://localhost:5174`. The `SignInGate` component (see
[`src/components/SignInGate.jsx`](webclient-support/src/components/SignInGate.jsx))
blocks the chat pane until Asgardeo sign-in completes. Sign in, and the
same "What accounts does customer cust-1 have?" prompt that failed with a
bare `401` in step 6 now succeeds — this time carrying the access token
Asgardeo issued to the browser session as a `Bearer` header on every
`/chat` call (see
[`src/lib/streamChat.js`](webclient-support/src/lib/streamChat.js)).

## What changed and what didn't

| | Before this module | After |
|---|---|---|
| Agent code | Unmodified | Unmodified |
| Who can call `/chat` | Anyone | Only a caller with a valid Asgardeo-issued token |
| Where that's enforced | Nowhere | Agent Manager's gateway, via the key manager |
| Web client | No identity | Signs in via Asgardeo, forwards the token |

This module only proves a caller is *authenticated* — it says nothing
about what a given *agent* is allowed to do once its own AgentID makes an
MCP call. That's [03-2-AgentID](../03-2-AgentID/README.md).

## Going further

- `_build_mcp_client()` in each agent's `agent.py` — where the
  direct-vs-gateway mode switch lives.
- See the [repo README's "Notes / things to verify" section](../../README.md#notes--things-to-verify-against-your-agent-manager-instance)
  for caveats on this connectivity path.

---

Previous: [Module 02 — MCP Tool Governance](../../02-mcp-tool-governance/README.md) ·
Next: [Module 03, Part B — AgentID](../03-2-AgentID/README.md)
