# On-Wheels Detailing — Security Implementation Plan

> Defense-in-depth across Cloudflare → Nginx → Python app → SQLite.
> Status markers: [✓] shipped · [→] build with new site · [•] future hardening.
> Last updated 2026-09-03.

---

## 1. Threat model — what we're defending against

| Category | Attack | Blast radius |
|----------|--------|--------------|
| **Hacking** | XSS, SQLi, auth bypass, secret leak, dependency vuln | customer PII, business data |
| **Pinging / scanning** | recon, path fuzzing, server fingerprinting | information leak, map attack surface |
| **Requesting** | booking spam, form abuse, brute-force | wasted time, polluted pipeline |
| **DDoS** | volumetric, slowloris, API hammering | availability |
| **IP** | spoofed X-Forwarded-For → rate-limit bypass, geo abuse | control-plane bypass |

---

## 2. Current controls (already shipped) [✓]

Application (`server.py`):
- API-key gate, dual-tier (`read` / `admin`), `X-API-Key` header, **constant-time
  compare** (`hmac.compare_digest`).
- Public-path whitelist (`/`, `/book`, `/api/book`, `/api/services`, `/static/`);
  everything else requires a key.
- Rate limiting: 30 req/60s generic, **5 bookings/60s/IP**.
- Input sanitization (`sanitize_input`: strip + truncate + length cap), 10 KB
  body cap, phone ≥10 digits, date ∈ Thu/Sat/Sun.
- PII redaction (email + payment_link stripped, phone → last 4).
- Audit log (`AUTH_FAIL`, `AUTH_DENIED`, `AUTH_OK`, `RATE_LIMIT`, `BOOK_FAIL`, `BOOK_OK`).
- Security headers on JSON: `nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`,
  `Referrer-Policy`, `Cache-Control: no-store`.
- Secrets from environment only (no hardcoded keys).
- Parameterized SQL (prepared statements / `?` placeholders).
- Stripe for payments (PCI offloaded).

Cloudflare Pages (`_headers`):
- HSTS preload, `X-Frame-Options: DENY`, `Permissions-Policy` (camera/mic/geo off).

---

## 3. Gaps → fixes (prioritized)

### P0 — ship with the new site [→]

**G1. CORS (the blocker).** No `Access-Control-Allow-Origin` today. Add to
`json_response()` + an `OPTIONS` preflight handler. Allowlist exactly:
`https://www.onwheelsdetailing.com`, the CF Pages preview domain, and
`http://localhost:4321` (dev). Never `*`.

**G2. X-Forwarded-For spoofing.** `_client_ip()` trusts `XFF` unconditionally.
If the Python port were ever exposed directly, an attacker sets `XFF` to
bypass rate limits. Fix: in Nginx, `real_ip_header X-Forwarded-For` +
`set_real_ip_from <CF ranges>` and **strip** any client-supplied `XFF` before
forwarding. Only trust `XFF` when the direct peer is the loopback/Nginx socket.

**G3. Bot/spam on booking.** Add **Cloudflare Turnstile** (invisible CAPTCHA)
to the wizard; verify the token server-side in `/api/book`. Plus a honeypot
field (hidden input; reject if filled).

**G4. Content-Security-Policy.** CF Pages `_headers` has HSTS + frame + permissions
but **no CSP**. Add a strict CSP for the Astro site (default-src 'self'; script
from 'self' + CF Turnstile + Stripe; img 'self' + data:; connect-src 'self' +
api origin). Astro's SSG output is static, so CSP is easy to keep tight.

### P1 — soon after launch

**G5. Nginx hardening** (droplet): `server_tokens off`, `limit_req` (zone for
`/api/book`), `limit_conn`, custom 404 (no verbose errors), disable directory
listing, only allow methods GET/POST/HEAD.

**G6. Cloudflare WAF rules**: rate-limit rule on `/api/*`; block obvious bots;
(optional) **geo-fence API to US** — run by owner.

**G7. Secret hygiene**: rotate the **leaked PAT in `tasain-portfolio/.git/config`**;
add **gitleaks** to CI so no future key/secret is committed; confirm CF Pages
build env exposes no secrets to the client bundle.

**G8. Dependency patching**: pin Node 22.12+ for Astro 7; monthly `npm audit`
+ Python `pip-audit` (or `uv`); keep the droplet OS patched.

### P2 — growth hardening [•]

**G9. SQLite → Postgres** when >100 appt/month (per architecture-vision §5) —
enables row-level concerns + concurrent writes.

**G10. Error tracking** (Sentry) for the Astro islands; **uptime monitor**
(CF health check / UptimeRobot) on both `www` and `api`.

---

## 4. Booking-flow security stack (target)

```
Browser
  └─ TLS (Cloudflare, force Full/Strict)
  └─ Turnstile token (human check) ──┐
  └─ honeypot (bots)                 ├─ POST /api/book
Cloudflare edge                       │
  └─ DDoS mitigation + WAF + rate rules
  └─ US geo-fence (optional)
Nginx (droplet)
  └─ limit_req / limit_conn (per-IP)
  └─ real_ip (fix XFF) + strip client XFF
  └─ server_tokens off
Python app
  └─ CORS allowlist (new) + OPTIONS preflight
  └─ Turnstile server-side verify (new)
  └─ rate limit 5/60s/IP + sanitize + validate
  └─ audit log every AUTH/RATE/BOOK event
SQLite
  └─ WAL + busy_timeout (concurrency safe)
```

---

## 5. Monitoring & response

- **Audit log** is the tripwire. Alert (via Hermes → Telegram) on:
  - `AUTH_FAIL` / `AUTH_DENIED` spike (>5 in a window) → probing.
  - `RATE_LIMIT` spike on `/api/book` → bot run.
  - `BOOK_FAIL` (invalid JSON / oversize) → fuzzing.
- **Backups**: SQLite snapshot already on Hermes cron (per ops). Keep.
- **Response runbook**: block IP at CF → verify logs → patch → post-mortem note.

---

## 6. Decisions to sign off before build

1. **Cloudflare Turnstile** on the booking form — yes/no?
2. **Geo-fence API to US** — yes/no (any non-US traffic ever expected)?
3. **CSP strictness** — OK to lock the site to self + CF + Stripe origins?
