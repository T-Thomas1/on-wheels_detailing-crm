# On-Wheels Detailing — Marketing Site (Astro 7)

The new marketing site for On-Wheels Detailing. Static-first, built to the
brand guidelines (navy / cream / orange / gold). This is the site that will
replace the current hand-written HTML on Cloudflare Pages for the 2027 rollout.

## Stack

- **Astro 7.3** (SSG — zero-JS by default, islands for interactivity)
- **TypeScript**
- **Tailwind CSS 4** (brand tokens in `src/styles/global.css` `@theme`)
- Cloudflare Pages (deploy target) — no framework runtime, pure static output
- Vanilla TS islands (no React/Alpine) for the tint simulator, before/after
  slider, and booking wizard

## Run it

```bash
cd site
npm install        # first time only (already installed on this box)
npm run dev        # http://localhost:4321  (hot reload — for review)
npm run build      # static output to dist/
npm run preview    # serve the built dist/
```

## Structure

```
site/
  astro.config.mjs      # site URL, Tailwind vite plugin, sitemap
  src/
    styles/global.css   # brand tokens + fonts + placeholder styles
    layouts/BaseLayout.astro   # HTML shell, meta/OG, header + footer
    components/
      Header.astro      # nav + Services dropdown + mobile menu
      Footer.astro      # SAIN API credit + contact/social links + locations
      Placeholder.astro # labeled upload-slot for missing images
      BeforeAfter.astro # draggable before/after comparison slider
      TintSimulator.astro # VLT shade preview (slider 50% → 5%)
      BookingWizard.astro # 5-step wizard → POST /api/book (fails open)
    pages/
      index.astro       # home
      services.astro    # detailing + paint/ceramic (+ tint/undercoat links)
      tinting.astro     # GEOShield films + simulator + legal limits
      undercoating.astro# Fluid Film vs Woolwax + pricing
      gallery.astro     # recent work (existing images + upload slots)
      locations.astro   # MI (mobile/shop) + TX
      about.astro       # TaSain's story
      book.astro        # booking wizard
      404.astro
  public/
    images/  fonts/     # copied from repo root (see note below)
    robots.txt  _redirects  _headers  favicon.ico
```

## Image upload slots (drop files into `public/images/`)

| Placeholder label | Filename to upload |
|---|---|
| Owner portrait (home + about) | `owner-ta-sain.webp` |
| Paint correction before/after (home) | a real pair → wire into `index.astro` `BeforeAfter` |
| Detailing before/after (services) | `detail-interior.webp` |
| Ceramic water beading (services) | `ceramic-beading.webp` |
| Tint base car (tinting simulator) | `tint-base-car.png` (clean side profile, clear glass) |
| Undercoating in progress | `undercoating-bay.webp` |
| Marysville / New Haven / Houston | `location-marysville.webp`, `location-newhaven.webp`, `location-houston.webp` |
| Tinting / undercoating / Texas jobs | `tint-job-1.webp`, `undercoat-job-1.webp`, `tx-job-1.webp` |

Every empty slot renders as a labeled dashed box with the exact filename + size,
so you can see at a glance what's missing.

## Booking wizard

`BookingWizard.astro` posts to `https://api.onwheelsdetailing.com/api/book`
(the existing CRM). It **fails open**: if the API is unreachable (local dev, or
before the CRM ships CORS), it falls back to a bundled service list and a
"call to book" message instead of erroring.

## Deploy (Cloudflare Pages, 2027)

- Build command: `npm run build`  ·  Output dir: `dist`
- Node 22.12+ required (Astro 7).
- `_headers` ships HSTS / frame / nosniff / permissions. **CSP is deferred** —
  needs testing with the inline island scripts + Cloudflare Turnstile before
  go-live (see `docs/security-plan.md` G4).

## Note on duplicated images

`public/images/` is currently a **copy** of the repo-root `images/` (legacy
site). Before 2027, pick one canonical location and delete the other to avoid
~40 MB of duplicated assets in git.
