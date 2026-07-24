# On-Wheels Detailing CRM

**Full-stack booking & customer management system for a multi-state mobile auto detailing business.**

🔗 **Live:** [onwheelsdetailing.com](https://onwheelsdetailing.com) &nbsp;|&nbsp; 📋 **Book:** [api.onwheelsdetailing.com](https://api.onwheelsdetailing.com)

---

## Overview

A production CRM powering On-Wheels Detailing — a mobile auto detailing business operating across Harris County, Texas and Metro Detroit, Michigan. Customers browse services, submit bookings with deposit agreements, and receive automated SMS follow-ups. The business owner manages everything through a secure dashboard.

Built from scratch with zero frameworks on the backend — just Python's standard library, SQLite, and a Cloudflare Pages frontend.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | HTML5, CSS3, Vanilla JS — served via Cloudflare Pages |
| **Backend** | Python 3 (`http.server`), `ThreadingHTTPServer` |
| **Database** | SQLite (WAL mode, foreign keys, `busy_timeout`) |
| **Reverse Proxy** | Nginx (rate limiting, HSTS, security headers) |
| **Payments** | Stripe Payment Links ($50 / $100 deposits) |
| **Infrastructure** | DigitalOcean droplet (Ubuntu 24.04), systemd, Cloudflare DNS |
| **SEO** | Schema.org JSON-LD, Open Graph, canonical URLs, sitemap.xml, IndexNow |
| **Monitoring** | Cron-based gateway watchdog, audit logging, DB backups |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Cloudflare                         │
│  ┌─────────────────┐    ┌─────────────────────────┐ │
│  │  Pages (static)  │    │  DNS (api subdomain)    │ │
│  │  onwheelsdetailing│    │  SSL (Flexible)        │ │
│  │  .com            │    │  _redirects (301)       │ │
│  └────────┬────────┘    └───────────┬─────────────┘ │
└───────────┼─────────────────────────┼───────────────┘
            │                         │
            │  Book Now CTA           │ HTTPS
            ▼                         ▼
     api.onwheelsdetailing.com
            │
     ┌──────▼──────────────────────────────────┐
     │         DigitalOcean Droplet             │
     │  ┌──────────────────────────────────┐   │
     │  │  Nginx (port 80)                 │   │
     │  │  • Rate limiting (5r/s burst 10) │   │
     │  │  • HSTS, X-Frame-Options        │   │
     │  │  • Bot protection                │   │
     │  └──────────────┬───────────────────┘   │
     │                 │ reverse proxy         │
     │  ┌──────────────▼───────────────────┐   │
     │  │  Python HTTP Server (port 5050)  │   │
     │  │  • ThreadingHTTPServer           │   │
     │  │  • API key auth (dual-tier)      │   │
     │  │  • PII redaction                 │   │
     │  │  • Audit logging                 │   │
     │  └──────────────┬───────────────────┘   │
     │                 │                       │
     │  ┌──────────────▼───────────────────┐   │
     │  │  SQLite (WAL mode)               │   │
     │  │  customers / vehicles / services │   │
     │  │  appointments / payments / f-ups │   │
     │  └──────────────────────────────────┘   │
     └──────────────────────────────────────────┘
```

---

## Features

### Customer-Facing
- **Service area filtering** — Mobile areas show interior services only; shop locations unlock the full catalog
- **Dynamic pricing** — Tiered by vehicle size (Sedan / SUV-Hatchback / Large SUV-Truck)
- **Deposit system** — Hidden until needed. Per-service deposit amounts with Stripe payment links and a nonrefundable agreement checkbox (auditable timestamp)
- **Confirmation screen** — Green checkmark, server message, "Book Another" flow
- **Timezone-aware UI** — EST/CST labels update dynamically when the customer selects their service area
- **Privacy-first** — Phone numbers masked to last 4 digits in API responses, emails stripped entirely. Privacy policy footer on every page.

### Business Dashboard
- **Cookie-based auth** — HttpOnly, SameSite=Strict, 30-day expiry. No token in URL after first visit
- **Pipeline view** — New Leads → Confirmed → Completed with deposit status per appointment
- **Appointment management** — Status lifecycle with auto-created follow-ups (Booking Confirmation, 24hr Reminder, Post-Service Check-in)
- **Deposit audit trail** — Timestamped agreement records for dispute resolution

### Security (Defense-in-Depth)
- **Dual-tier API key auth** — Read key for dashboard/appointments, Admin key for mutations. Enforced via `hmac.compare_digest` (timing-attack safe)
- **PII redaction** — Emails dropped, phones masked, Stripe links removed from all public API surfaces
- **Input sanitization** — All form fields stripped, truncated, XSS-safe. Path traversal blocked on static files
- **Rate limiting** — Nginx (5r/s API, 2r/min bookings) + in-app (30r/min general, 5r/min bookings)
- **Audit logging** — Every request logged with IP, path, auth level, event type
- **No hardcoded secrets** — Keys loaded from environment only; `.env` is `.gitignore`d

### SEO
- **Schema.org LocalBusiness JSON-LD** on the homepage
- **Open Graph tags** on every page (title, description, image, URL)
- **Canonical URLs** using clean paths (Cloudflare Pages strips `.html`)
- **`_redirects`** file for 301 server-side redirects (`/book` → booking form)
- **Sitemap.xml** with correct `lastmod` dates and priorities
- **IndexNow protocol** — Automated submission script notifies search engines within minutes of deployment
- **Bing-compliant** title/description lengths
- **Local SEO** — Metro Detroit, Port Huron, St. Clair, Macomb County geo-targeted keywords

---

## Project Structure

```
on-wheels_detailing-crm/
├── index.html                  # Landing page (Cloudflare Pages)
├── about.html                  # Company story & timeline
├── services.html               # Service catalog with tiered pricing
├── gallery.html                # Before/after photo gallery
├── contact.html                # Contact info & estimate request guide
├── book.html                   # Redirect → booking form (meta + JS fallback)
├── _redirects                  # Cloudflare Pages HTTP 301 rules
├── sitemap.xml                 # SEO sitemap
├── indexnow-submit.py          # IndexNow submission script
├── f9533a...txt                # IndexNow key file
│
├── crm/                        # Backend (server WorkingDirectory)
│   ├── crm.py                  # SQLite CRUD, timezone helpers, Stripe links
│   ├── server.py               # HTTP server — API, booking form, dashboard
│   ├── followup_checker.py     # SMS follow-up message generator
│   ├── templates/
│   │   ├── booking.html        # Booking form with service cards, deposit flow
│   │   └── dashboard.html      # Business dashboard
│   └── static/
│       └── style.css           # System-aware light/dark theme
│
├── crm.py                      # Root copy (git-tracked, synced for deployment)
├── server.py                   # Root copy
├── followup_checker.py         # Root copy
├── templates/                  # Root copy
│   ├── booking.html
│   └── dashboard.html
├── static/style.css            # Root copy
└── start.sh                    # Local dev launcher
```

---

## Key Design Decisions

**Zero-framework backend.** The entire server is ~540 lines of Python stdlib. No Flask, no Django, no dependencies. `ThreadingHTTPServer` handles concurrency. SQLite with WAL mode handles concurrent reads. This was a deliberate choice — the 1GB droplet has limited resources, and framework overhead would compete with the database.

**Hardcoded standard time.** Texas and Michigan have different DST schedules. Rather than deal with DST transitions, all times display as EST/CST year-round. The business owner explicitly chose consistency over dynamic switching.

**Root + crm/ mirror.** The systemd unit runs from `WorkingDirectory=/opt/onwheels/crm`. Git tracks files at the repo root, but the server reads from `crm/`. Both copies are kept in sync. This prevents path-resolution bugs while keeping the repo structure flat for tooling.

**Deposits are per-service, not price-based.** Each service declares its own `deposit_amount` (NULL, 50, or 100). No fragile price-threshold logic. The booking form's JS reads `data-deposit` attributes and toggles the agreement checkbox dynamically.

**Multi-vehicle deduplication.** A customer who books two vehicles for the same day gets one Booking Confirmation + one 24hr Reminder — not one per vehicle. The follow-up system checks for sibling appointments before inserting.

---

## Local Development

```bash
# Clone
git clone https://github.com/T-Thomas1/on-wheels_detailing-crm.git
cd on-wheels_detailing-crm

# Start the CRM backend
cd crm
python3 server.py
# → http://localhost:5050         (booking form)
# → http://localhost:5050/dashboard?token=onwheels2024

# For production, set environment variables:
export ONWHEELS_API_KEY="your-read-key"
export ONWHEELS_ADMIN_KEY="your-admin-key"
```

The frontend is static HTML — open any `.html` file in a browser, or serve with `python3 -m http.server`.

---

## Deployment

```bash
# On the droplet:
cd /opt/onwheels && git pull origin master
cp templates/booking.html crm/templates/
cp server.py crm/
cp crm.py crm/
cp followup_checker.py crm/
find /opt/onwheels -name '__pycache__' -exec rm -rf {} + 2>/dev/null
systemctl restart onwheels

# Verify:
curl -s -o /dev/null -w '%{http_code}' https://api.onwheelsdetailing.com/
# → 200
```

Cloudflare Pages auto-deploys on every push to `master`.

---

## License

Proprietary — built for and operated by On-Wheels Detailing.  
Developed by TaSain Thomas | [onwheelsdetailing.com](https://onwheelsdetailing.com)
