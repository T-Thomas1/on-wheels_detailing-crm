# On-Wheels Detailing — SEO Plan (Astro rebuild)

> How search visibility is preserved and expanded through the redesign.
> Last updated 2026-09-03.

---

## 1. Current SEO state (what already works)

| Asset | Status |
|-------|--------|
| `sitemap.xml` | 5 URLs: `/`, `/about`, `/services`, `/gallery`, `/contact` |
| `robots.txt` | sitemap declared; `Disallow: /admin/`, `/includes/` |
| IndexNow | `indexnow-submit.py` + key file `f9533a2a0b4141c79c3448531f13f5fb.txt` → Bing/Yandex instant index |
| Google Search Console | active (HTTPS property) |
| Bing Webmaster Tools | active (via IndexNow) |
| Schema.org | `AutoDetailing` + `OfferCatalog` on services page |

**The rebuild must not break any of this.** That's the #1 SEO rule of a redesign.

---

## 2. Non-negotiables (do first, or lose rankings)

1. **URL continuity + 301 map.** Every existing URL either keeps its path or
   gets a 301 to its new home. Cloudflare Pages `_redirects` handles this
   trivially. Provisional map:

   | Old | New | Status |
   |-----|-----|--------|
   | `/` | `/` | keep |
   | `/about` | `/about` | keep |
   | `/services` | `/services` | keep |
   | `/gallery` | `/gallery` | keep |
   | `/contact` | `/contact` | keep |
   | `/book` | booking wizard (on-site) | 301 → new flow |
   | `/book.html` | booking wizard | 301 |

   *(New pages — `/tinting`, `/undercoating`, `/locations`, service detail pages
   — are additive and don't need redirects.)*

2. **Keep `robots.txt` + `sitemap.xml` live.** Astro generates both via
   `@astrojs/sitemap`; the sitemap auto-grows as pages are added.

3. **Keep IndexNow wired.** Update `indexnow-submit.py` `ALL_URLS` to the new
   sitemap, and run it as a post-deploy step (GitHub Action).

4. **No `www` vs `api` dilution.** The booking form must live on `www` (the new
   wizard), not `api`. One canonical origin. `api` becomes JSON-only, `X-Robots-Tag:
   noindex, nofollow` on all `/api/*` responses.

---

## 3. Astro's SEO advantages (why this stack helps)

- **SSG** → full static HTML at build, best possible crawl/render for Googlebot.
- **`@astrojs/sitemap`** → auto-generated sitemap with lastmod.
- **Image pipeline** → auto WebP/AVIF + responsive `srcset` + width/height (no
  CLS) → better Core Web Vitals.
- **Zero-JS pages** → fastest LCP/INP; JS only on interactive islands.
- **`<meta>` per route** → title/description/canonical/OG/Twitter in frontmatter.

---

## 4. Structured data plan (Schema.org)

| Page | Schema type |
|------|-------------|
| Home + Locations | `AutoDetailing` (LocalBusiness) — one per location: Marysville shop, New Haven shop, mobile (Metro Detroit / St. Clair), TX (Houston) |
| Services | `Service` + `OfferCatalog` + `Offer` with price |
| Tinting | `Service` + `FAQPage` (legal limits, film tiers) |
| Undercoating | `Service` + `FAQPage` (Fluid Film vs Woolwax) |
| Gallery | `ImageObject` list + `VideoObject` for before/after |
| Reviews | `AggregateRating` (from GBP) |

NAP consistency (Name / Address / Phone) must match Google Business Profile
**exactly** on every location block, or local ranking is diluted.

---

## 5. Local SEO — Michigan + Texas

- **Geo pages** (one per market, unique content, no doorway pages):
  - `Mobile Auto Detailing Detroit MI` / Port Huron / St. Clair / Macomb Co
  - `Ceramic Coating` + `Window Tinting` + `Undercoating` pages targeting each
    metro (Marysville / New Haven / Metro Detroit) + `Houston TX`.
- **Reviews name the town** (per the market-entry playbook): reviews that say
  "mobile detailing in Marysville" rank for Marysville.
- **GBP alignment**: Marysville storefront (single GBP, lists undercoating),
  New Haven (undercoating fixed location), mobile service area. New Tinting
  service should be added to GBP offerings.

---

## 6. Content & keyword strategy

- **Service landing pages** (one keyword each): window tinting (GEOShield),
  ceramic coating, paint correction, interior detailing, undercoating, RV.
- **Blog** (education = top-of-funnel + featured snippets):
  - "How long does ceramic coating last?"
  - "Michigan window tint laws (2026)"
  - "Wax vs sealant vs ceramic — what's the difference?"
  - "Fluid Film vs Woolwax for Michigan winters"
- **Before/after gallery** with descriptive filenames + alt text + captions
  (currently the gallery page is thin — 595 chars; the rebuild fixes this).

---

## 7. Technical SEO checklist

- [ ] Canonical tags on every page (no duplicate content).
- [ ] OG + Twitter card meta on every page.
- [ ] `X-Robots-Tag: noindex` on `/api/*`.
- [ ] 301 map in `_redirects` (old → new).
- [ ] `@astrojs/sitemap` + regenerate on every build.
- [ ] IndexNow `ALL_URLS` updated + post-deploy submit.
- [ ] Core Web Vitals: LCP <2s, CLS <0.1 (Astro static = near-free).
- [ ] Alt text on all gallery images; descriptive filenames.
- [ ] Breadcrumb schema on service pages.
- [ ] Hreflang not needed (US-only, single locale).

---

## 8. Post-launch submission workflow

1. Build deploys to Cloudflare Pages.
2. GitHub Action runs `indexnow-submit.py` (new URLs → Bing/Yandex instantly).
3. Re-submit sitemap in Google Search Console + Bing Webmaster Tools.
4. Request index of new pages (tinting, undercoating, locations) in GSC.
5. Monitor GSC coverage report for 404s / redirect errors in week 1.
