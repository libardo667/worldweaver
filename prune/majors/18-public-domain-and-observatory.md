# Major 18: Public Domain & Observatory Portal

**Status:** Infrastructure previously configured but currently offline; public product/UI scope needs
revision before revival.

**2026-07-17 correction:** `world-weaver.org` and a named Cloudflare tunnel have existed and can be reused
as the first public ingress for a project-operated city and federation directory. They must not become a
requirement that makes one domain the owner of the commons. Other stewards need their own public URLs,
node identities, and choice of ingress provider. The observatory UI described below is stale in emphasis:
the ordinary public surface should follow VISION and Major 125's place/stoop commons rather than exposing
detailed resident activity as a surveillance product.

---

## Problem

WorldWeaver has a real domain (`world-weaver.org`, managed via Cloudflare) and a working
React client, but they aren't connected. The world is invisible to anyone who isn't running
the dev stack locally. The V5 vision requires a public-facing surface before any of the
social/stewardship layers can land.

---

## Goals

1. **Serve the React client** at `world-weaver.org` (and `www.world-weaver.org`)
2. **Route API calls** from the client to the SF backend
3. **Public read access** — the world is observable without login
4. **Low ops burden** — Cloudflare handles SSL, CDN, DDoS; we handle as little infra as
   possible

---

## Design

### Domain architecture

```
world-weaver.org          → React client (static build, Cloudflare Pages or VPS)
api.world-weaver.org      → SF backend (ww_sf, port 8000)
world.world-weaver.org    → Federation root (ww_world, port 9000) [future]
```

### Client hosting: Cloudflare Pages (recommended)

Cloudflare Pages can build and serve the Vite React app directly from the repo.

- **Build command:** `cd client && npm run build`
- **Output dir:** `client/dist`
- **Env var at build time:** `VITE_API_BASE_URL=https://api.world-weaver.org`
- Zero infra to manage; auto-deploys on push to main; free tier sufficient

Alternative: static build served from the same VPS as the backend (nginx), but
Cloudflare Pages is simpler and keeps frontend/backend concerns separate.

### Backend routing: Cloudflare Tunnel

The SF backend runs on a private machine (no public IP required). Cloudflare Tunnel
(`cloudflared`) creates an outbound-only connection to Cloudflare's edge — no ports opened
on the host.

```
cloudflared tunnel --url http://localhost:8000
```

Point `api.world-weaver.org` DNS to the tunnel. SSL terminates at Cloudflare's edge;
traffic from edge to localhost is unencrypted (trusted local).

### CORS

With client at `world-weaver.org` and API at `api.world-weaver.org`, CORS is needed.
Current `main.py` allows all origins (`*`) — fine for now. Tighten to
`https://world-weaver.org` before any authenticated endpoints go live.

### Client env var wiring

Currently the client uses a hardcoded or `.env`-configured API base URL. For production:

```
# client/.env.production
VITE_API_BASE_URL=https://api.world-weaver.org
```

---

## Observatory view (V5-M1)

The public-facing world view — "what's happening in the world right now" — is a read-only
layer on top of the existing client. No new backend endpoints required for phase 1; the
existing `/api/world/digest` and event feed endpoints are sufficient.

Key read-only surfaces to expose:
- **Live digest** — current location graph, active residents, recent events
- **Resident cards** — who lives here, what they've been doing
- **Event timeline** — world history, scrollable

Authentication is not required for read access. Write actions (sending letters, making
choices) require login — that's V5-M3 (Actor accounts).

---

## Implementation Steps

### Phase 1 — Domain live, client served

1. Build the React client: `cd client && npm install && npm run build`
2. Create a Cloudflare Pages project pointing at this repo; set build command + output dir
3. Set `VITE_API_BASE_URL=https://api.world-weaver.org` as a Pages env var
4. Verify `world-weaver.org` loads the client

### Phase 2 — API reachable

5. Install `cloudflared` on the SF machine
6. Create a named tunnel: `cloudflared tunnel create ww-sf`
7. Configure tunnel to route `api.world-weaver.org → http://localhost:8000`
8. Set Cloudflare DNS: `api.world-weaver.org CNAME <tunnel-id>.cfargotunnel.com`
9. Run `cloudflared tunnel run ww-sf` (or as a system service)
10. Verify: `curl https://api.world-weaver.org/health`

### Phase 3 — Observatory (V5-M1)

11. Add a public "Observatory" route to the client (read-only world view)
12. No login required to view; all data comes from existing read endpoints
13. Resident cards, event timeline, live digest panel

---

## Open Seams

- `world.world-weaver.org` for the federation root — not needed until multi-shard is live
- `players.world-weaver.org` for actor accounts — V5-M3
- Rate limiting on public API — add Cloudflare WAF rules when traffic warrants
- `--shard-url` flag in `seed_world.py` — allows federation to record the public URL of
  a shard (currently records localhost; tracked in FEDERATION.md Part 4)

---

## Verification

```bash
# Client
curl -I https://world-weaver.org          # → 200 with HTML

# API
curl https://api.world-weaver.org/health  # → {"ok": true, ...}

# CORS preflight
curl -H "Origin: https://world-weaver.org" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS https://api.world-weaver.org/api/world/digest
# → 200 with Access-Control-Allow-Origin header
```
