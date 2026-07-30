# On-Wheels Detailing — Architecture & Vision

> *"A detail shop that looks like a detail shop, not a Craigslist ad."*

---

## 1. Current State

### Stack
| Layer | Technology | Scale |
|-------|-----------|-------|
| Marketing site | Cloudflare Pages (static HTML) | 5 pages, ~20MB images |
| Booking / CRM | Python `http.server` on DO 1GB droplet | SQLite, ~30 customers |
| Payments | Stripe payment links (off-site) | $50 / $100 deposits |
| DNS / CDN / SSL | Cloudflare (Flexible SSL, proxy) | ~0 latency |
| Cron / alerts | Hermes gateway → Telegram | Briefing, watchdog, backups |
| CI/CD | None — manual deploy | Git push → SCP → restart |

### What works well
- Zero-cost operations (DO $6/mo + free CF Pages)
- No framework bloat — Python stdlib only
- Stripe handles PCI compliance
- Telegram alerts give real-time awareness
- Defense-in-depth security (app + Nginx + CF)

### Pain points
- **Static HTML doesn't scale** — every new service = hand-edit HTML
- **No image pipeline** — gallery images are WebP but no CMS
- **Booking feels bare** — functional, not polished
- **No customer portal** — zero self-service after booking
- **SQLite on 1GB RAM** — fine for 30 customers, won't hold at 300
- **Domain split** — `www` (Pages) vs `api` (droplet) confuses Google

---

## 2. Design Vision — "Garage Luxury"

### Brand direction

Move from *"a guy with a buffer"* to *"a premium service you're proud to book."*

Think: **Tesla configurator meets a high-end barber shop.**

| Element | Now | Vision |
|---------|-----|--------|
| Color palette | Dark #0a0a0a + teal #00d4aa | Add warm accent (gold/amber), gradients, soft shadows |
| Typography | System font stack | Inter / Satoshi for headings, system mono for data |
| Hero | Text-only H1 | Full-bleed video loop of paint correction in action |
| Cards | Flat dark boxes | Glassmorphism with subtle blur, hover lift |
| Booking flow | Single-page form | Multi-step wizard with progress indicator |
| Mobile | Responsive grid | Mobile-first, thumb-friendly tap targets |
| Empty states | Gray text | Illustrated placeholders with brand personality |

### Homepage vision

```
┌──────────────────────────────────────────────┐
│  [VIDEO BG: water beading on ceramic coat]    │
│                                                │
│     DET A I L I N G   R E I M A G I N E D     │
│     ─────────────────────────────────────      │
│     Showroom finish. Mobile convenience.       │
│                                                │
│     [ BOOK NOW ]   [ SEE OUR WORK ]            │
│                                                │
├──────────────────────────────────────────────┤
│  Trust bar: "Serving Houston & Metro Detroit"  │
│  [5★] [50+ Vehicles] [2-Yr Ceramic Warranty]  │
├──────────────────────────────────────────────┤
│  Service cards — 3-column grid with hover      │
│  Each card: icon + name + starting price       │
│  Click → expands inline with tiered pricing    │
├──────────────────────────────────────────────┤
│  Before/After slider — interactive comparison  │
│  Pull handle left → see oxidized, right → see  │
│  mirror finish. Best sales tool on the site.   │
├──────────────────────────────────────────────┤
│  Testimonial carousel — real customer quotes   │
│  Photos of actual cars, not stock.             │
├──────────────────────────────────────────────┤
│  Footer: Hours (Thu/Sat/Sun 9-5), phone, map  │
└──────────────────────────────────────────────┘
```

### Booking wizard flow (step-by-step)

```
Step 1: WHERE ARE YOU?
  ┌─────────────────────────────────────┐
  │  [Map picker or city search]         │
  │  Select your location → auto-detects │
  │  mobile vs shop, timezone            │
  │                          [NEXT →]    │
  └─────────────────────────────────────┘

Step 2: WHAT DO YOU NEED?
  ┌─────────────────────────────────────┐
  │  Visual service picker — not radios  │
  │  [Interior] [Exterior] [Full Detail] │
  │  [Ceramic] [Paint Correction]        │
  │  Each card has before/after icon     │
  │  Price updates live as you pick      │
  │                          [NEXT →]    │
  └─────────────────────────────────────┘

Step 3: TELL US ABOUT YOUR VEHICLE
  ┌─────────────────────────────────────┐
  │  Make / Model / Year / Color         │
  │  + auto-suggest from database        │
  │  "What's the condition like?"        │
  │  [Clean] [Moderate] [Needs Work]     │
  │                          [NEXT →]    │
  └─────────────────────────────────────┘

Step 4: PICK A DAY
  ┌─────────────────────────────────────┐
  │  Visual calendar — only Thu/Sat/Sun  │
  │  available days highlighted          │
  │  Time slots as cards:                │
  │  [9am-12pm] [12pm-3pm] [3pm-5pm]    │
  │                          [NEXT →]    │
  └─────────────────────────────────────┘

Step 5: REVIEW & BOOK
  ┌─────────────────────────────────────┐
  │  Summary card:                       │
  │    Service: Interior Refresh   $150  │
  │    Mobile fee:                  $25  │
  │    ─────────────────────────────     │
  │    Estimated total:            $175  │
  │                                      │
  │  Your info (name, phone)             │
  │  [✓] I understand deposit policy     │
  │                                      │
  │  [ CONFIRM BOOKING ]                 │
  └─────────────────────────────────────┘
```

---

## 3. Service Expansion Architecture

### Current catalog (6 services, 3 categories)
```
Interior Detailing
  ├── Interior Refresh          $150/180/210
  ├── Premium Interior           $200/240/280
  └── Steam & Hot Water          $180 flat

Paint Correction & Ceramic
  ├── Polish & Protect           $375/425/475
  ├── Two-Step Correction        Quote Only
  ├── Ceramic Coating            $1,500/1,750/2,000
  └── Signature Detail           $1,150/1,350/1,600
```

### Phase 2 — Service expansions
```
Exterior Only
  ├── Hand Wash & Wax             $75/95/115
  ├── Clay Bar Decontamination    $125/150/175
  ├── Headlight Restoration       $85 flat
  └── Trim Restoration            $60 flat

Add-Ons (bolt onto any service)
  ├── Pet Hair Removal            +$40
  ├── Ozone Treatment             +$75
  ├── Windshield Coating          +$50
  └── Engine Bay Detail           +$100
```

### Data model for flexibility
```sql
-- Services table stays flat but gains:
ALTER TABLE services ADD COLUMN is_addon BOOLEAN DEFAULT 0;
ALTER TABLE services ADD COLUMN parent_category TEXT;
ALTER TABLE services ADD COLUMN tier_sedan REAL;
ALTER TABLE services ADD COLUMN tier_suv REAL;
ALTER TABLE services ADD COLUMN tier_large REAL;
ALTER TABLE services ADD COLUMN image_url TEXT;
ALTER TABLE services ADD COLUMN sort_order INTEGER;
```

The booking form loads services dynamically from `/api/services` — add a service to the DB, it appears on the form. No HTML changes needed. This is already built. The only bottleneck is the static services page which lists them manually.

---

## 4. Customer Experience Roadmap

### Phase 1 — Quick Wins (2-4 weeks)
| Feature | Effort | Impact |
|---------|--------|--------|
| **Photo upload in booking** — customer snaps their car condition | 1 day | High — sets expectations, reduces surprises |
| **Booking confirmation email** — automatic via SendGrid free tier | 1 day | Medium — feels professional |
| **SMS reminder 24hr before** — already built, verify it fires | 0 days | Medium |
| **"Book Again" with prefilled data** — detect returning phone # | 0.5 day | High — 60% of revenue is repeat |
| **Service comparison table** on services.html | 0.5 day | Medium — customers compare before booking |

### Phase 2 — Polish (1-2 months)
| Feature | Effort | Impact |
|---------|--------|--------|
| **Customer portal** — `/my-booking/<id>` with status, reschedule, cancel | 3 days | High — reduces phone calls |
| **Before/After gallery** — per-service, filterable | 2 days | High — best sales tool in detailing |
| **Google Reviews automation** — post-service email with direct review link | 0.5 day | High — SEO + trust |
| **Multi-step booking wizard** (see Section 2) | 3 days | High — conversion rate |
| **Live availability calendar** — shows booked slots | 2 days | Medium — prevents double-booking |

### Phase 3 — Growth (3-6 months)
| Feature | Effort | Impact |
|---------|--------|--------|
| **Fleet management** — corporate accounts with multi-vehicle pricing | 1 week | High — B2B revenue |
| **Subscription plans** — monthly maintenance (wash + interior refresh) | 1 week | Transformative — recurring revenue |
| **Referral program** — "Refer a friend, get $25 off" with tracking codes | 1 day | Medium |
| **Seasonal packages** — "Winter Prep" / "Summer Shine" curated bundles | 0.5 day | Medium |
| **Gift cards** — Stripe integration for digital gift cards | 1 day | Low effort, high perceived value |

---

## 5. Infrastructure Scaling Plan

### Current: SQLite → acceptable to ~500 customers
```python
# Already using:
PRAGMA journal_mode=WAL      # concurrent reads
PRAGMA busy_timeout=5000     # wait on lock, don't crash
ThreadingHTTPServer           # multi-request
```

### Growth trigger 1: 100+ appointments/month → PostgreSQL
```bash
# DO managed Postgres — $15/mo
# Migration: SQLite → Postgres via pgloader
# ~30 minutes of downtime
# Benefit: concurrent writes, JSONB for flexible service data, full-text search
```

### Growth trigger 2: 5+ concurrent bookings → proper WSGI
```python
# Replace http.server with:
# - gunicorn + Flask/FastAPI (if staying Python)
# - Or keep stdlib philosophy but add uvicorn
# Benefits: connection pooling, graceful restarts, worker processes
```

### Growth trigger 3: Image-heavy traffic → CDN origin
```
Current: images served from Cloudflare Pages (already on CDN)
Next:    dedicated image pipeline
         - Upload → auto-resize → WebP/AVIF → R2 bucket
         - Before/after sliders as pre-composited images
         - Lazy loading with blur-up placeholders
```

### Architecture at scale (Phase 3)
```
                        ┌──────────────────────┐
                        │   Cloudflare          │
                        │   (DNS + CDN + WAF)   │
                        └────┬─────┬──────┬─────┘
                             │     │      │
                    ┌────────┘     │      └─────────┐
                    ▼              ▼                 ▼
            ┌────────────┐ ┌────────────┐   ┌──────────────┐
            │ CF Pages   │ │ DO Droplet │   │ R2 Bucket    │
            │ (static)   │ │ (API)      │   │ (images)     │
            │            │ │            │   │              │
            │ Next.js or │ │ FastAPI    │   │ Before/After │
            │ Astro SSG  │ │ + Postgres │   │ + Gallery    │
            └────────────┘ └─────┬──────┘   └──────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌──────────┐ ┌──────────┐ ┌──────────┐
            │ Stripe   │ │ SendGrid │ │ Hermes   │
            │ Payments │ │ Email    │ │ Gateway  │
            └──────────┘ └──────────┘ │          │
                                      │ Telegram │
                                      │ SMS      │
                                      │ Cron     │
                                      └──────────┘
```

---

## 6. Attention-Grabbing Features

### Interactive elements that sell

**1. Paint Correction Simulator**
Embedded WebGL shader — drag a slider to "remove" swirl marks from a photo. Shows the difference between polished and unpolished paint in real time. Instant trust builder.

**2. "What's Your Car Worth?" calculator**
Simple form: enter make/model/year → pulls KBB value → shows how detailing impacts resale. "A $375 polish can add $1,500 to your trade-in." Data-driven selling.

**3. Live weather-aware booking**
Pull local weather for the booked date. "Looks like sunshine on Saturday — perfect day for a ceramic coat to cure." Small detail, big impression.

**4. Technician profile**
Photo + bio of TaSain on the about page. "Your car is worked on by one person who treats it like his own." Not a faceless crew. Trust through transparency.

**5. "While You Wait" guide**
For shop drop-offs: list of nearby coffee shops, parks, WiFi spots. "Drop your car, grab a latte at Red Owl, we'll text you when it's ready." Thoughtful UX.

---

## 7. SEO & Discovery

### Current gaps
- Gallery page is thin (595 chars text) — Google sees a skeleton
- No blog/content strategy
- `_headers` file missing (no HSTS/CSP on Pages)
- Domain split (`www` vs `api`) dilutes authority

### Content roadmap
```
/services        → comparison table + FAQ accordion
/gallery         → filterable by service type, captions on every image
/blog            → educational: "How long does ceramic coating last?"
                   "Why your black car looks dirty after one rain"
                   "The difference between wax, sealant, and ceramic"
/areas           → geo-targeted landing pages:
                   "Mobile Auto Detailing Houston TX"
                   "Ceramic Coating Detroit Metro"
                   Each with unique content + local schema
```

### Technical SEO fixes
```
_headers file:   HSTS preload, CSP, cache-control for static assets
Schema:          FAQPage, HowTo, VideoObject (for before/after)
Core Web Vitals: already fast (static HTML), maintain <2s LCP
Backlinks:       Partner with local dealerships, car clubs, detail supply shops
```

---

## 8. Revenue Expansion

### Beyond detailing
```
Product sales (drop-shipped, no inventory):
  ├── Carpro Perl (the product used on every interior)
  ├── Microfiber starter kits
  └── Ceramic coating maintenance spray
  → Affiliate links to Detailed Image / Amazon = passive income

Detailing workshops:
  ├── 2-hour "Wash Your Car Right" class ($75/person, 10 max)
  └── Record and sell as video course ($25)

Fleet contracts:
  ├── Real estate agents (3-5 cars, monthly)
  ├── Car dealerships (pre-sale prep)
  └── Rental fleets (Turo hosts)
```

---

## 9. Immediate Next Actions

Priority-ranked by impact ÷ effort:

| # | Action | Effort | Rationale |
|---|--------|--------|-----------|
| 1 | **Before/After slider on homepage** | 2h | Single biggest conversion tool in detailing |
| 2 | **Add-on services in DB + form** | 1h | Instantly expands revenue per booking |
| 3 | **Multi-step booking wizard** | 1 day | Reduces abandonment, feels premium |
| 4 | **Customer portal** (`/my-booking/<id>`) | 1 day | Self-service = fewer phone calls |
| 5 | **Google Review auto-request** | 30min | Reviews compound — 50 reviews = trust moat |
| 6 | **Blog with 3 educational posts** | 2h | SEO foundation, answers customer questions |
| 7 | **Photo upload in booking form** | 2h | Sets expectations, qualifies leads |
| 8 | **Booking confirmation email** | 1h | Completes the professional experience |
| 9 | **Service comparison table** | 30min | Helps customers choose |
| 10 | **Referral program** | 1h | Word-of-mouth is detailing's #1 channel |

---

## 10. Principles

1. **Mobile-first, always.** 80% of bookings will come from phones. Every feature ships mobile-first.

2. **Speed is a feature.** Static HTML + CDN = sub-second loads. Don't trade that for a heavy framework. If we go JS, it's Astro (zero-JS output) or HTMX (tiny, hypermedia-driven).

3. **TaSain is the brand.** No stock photos of people. Every image is real work, real cars, real results. The about page should feel like meeting the owner.

4. **Automate the tedious, elevate the personal.** Booking, reminders, reviews — automate. The actual conversation with a customer — that's where the human touch lives.

5. **SQLite until it hurts.** Premature database migration is the root of all ops pain. We have ~30 customers. PostgreSQL is a Phase 3 problem.

6. **One codebase, two surfaces.** The CRM API serves both the booking form AND the dashboard. No separate admin panel. Keep it unified.

---

*Last updated: 2026-07-29*
*Author: SAIN-API / Architecture review*
*For: TaSain — On-Wheels Detailing*
