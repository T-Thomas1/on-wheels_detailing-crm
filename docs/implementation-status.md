# Implementation Status

> What's built, what's pending, and the decisions locked for the On-Wheels
> rebuild. Last updated 2026-09-03.

---

## 1. Done (committed to `development`)

### Marketing site — `site/` (Astro 7.3 + TS + Tailwind 4)
- 9 pages: Home, Services, Tinting, Undercoating, Gallery, Locations, About,
  Book, 404 — all build clean, all serve HTTP 200.
- Brand tokens locked (navy `#0d2e48`, cream `#f1eed9`, orange `#e6863a`,
  gold `#edb760`), FH Oscar Condensed display font.
- Header (Services dropdown + mobile menu) + Footer (SAIN API credit, phone,
  email, Facebook, Instagram, MI + TX location lines).
- Interactive islands: **before/after slider**, **tint shade simulator**
  (50%→5% VLT), **5-step booking wizard** (fails open to "call to book").
- Schema.org: `AutoDetailing` (home), `FAQPage` (tinting, undercoating).
- SEO plumbing: auto sitemap, `robots.txt`, `_redirects` (`/book.html`→`/book`),
  `_headers` (HSTS/frame/nosniff), IndexNow URL list updated.

### CRM — `server.py` / `crm.py` (additive, idempotent)
- CORS allowlist (`www` + apex + `localhost:4321` + `*.pages.dev`) + OPTIONS
  preflight. Never `*`.
- Seeded 5 services (3 GEOShield tint tiers + Fluid Film/Woolwax) + widened
  `services.category` CHECK via copy-preserving table rebuild.
- Verified against a **copy** of the DB: no data loss, idempotent, allow/deny
  logic passes. Real `crm/onwheels.db` untouched.

---

## 2. Pending (before 2027 go-live)

| Item | Notes |
|------|-------|
| Real before/after pairs | home `BeforeAfter` currently uses demo images |
| Real testimonials | 3 sample cards on home → replace with real quotes |
| GEOShield + product brand logos | "Products we trust" strip is text-only |
| Tint pricing | films seeded as `Quote Only` (cert pending) |
| CSP header | deferred — test with islands + Turnstile (security-plan G4) |
| Cloudflare Turnstile key | wire into `BookingWizard` submit |
| Booking payload schema | new column on `appointments` for film/shade + undercoat product |
| Texas landing page | geo-targeted Houston page + LocalBusiness schema |
| Image dedup | pick canonical `images/` location, remove the other |

---

## 3. Decisions locked (in `docs/brand-content.md`)

- Tinting nested under Services (not top-level nav).
- Owner-centric theme: TaSain IS the brand.
- Products shown as brand trust strip, not a chemical spec dump.
- Fluid Film vs Woolwax comparison is the one product A/B.
- Stack: Astro 7 + TS + Tailwind 4 + Cloudflare Pages + existing Python CRM.
- US-only customers → geo-fence API to US; Turnstile approved.
- **Work sits on `development`; no push/deploy until 2027.**

---

## 4. Known caveats / follow-ups

1. **Duplicate code layout** — root `server.py`/`crm.py` AND a `crm/` package
   exist and have drifted: root `server.py` still returns `products_used` in
   `/api/services`; `crm/server.py` already strips it. **Confirm which layout
   the droplet runs** so we can treat one as canonical.
2. **Local DB is empty** — `crm/onwheels.db` has 0 customers; real data is on
   the droplet. The migration is copy-preserving, but the real data-integrity
   proof happens at deploy.
3. **Leaked PAT** — a GitHub token sits in plaintext in
   `~/tasain-portfolio/.git/config` remote URL. Rotate it.
