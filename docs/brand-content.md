# On-Wheels Detailing — Brand, Content & Voice

> Single source for content direction during the rebuild.
> Last updated 2026-09-03.

---

## 1. Owner-centric direction (primary theme)

The site is the story of **TaSain** — not a faceless shop. "On-Wheels Detailing"
is the name; the person is the brand.

- About page = TaSain's story front-and-center: founded May 2024, the craft,
  the standard, the growth (mobile → Marysville shop → New Haven undercoating
  bay → window tinting → Texas).
- "Meet your detailer" — one person treats your car like his own. No stock
  photos of people; real photos of TaSain working.
- First-person, confident voice in copy. A personal guarantee: "if it's not
  right, I'll make it right."
- The "doing big things" effect: growth timeline, certifications, reviews,
  the full service stack (detailing + tinting + undercoating) under one roof.

---

## 2. Navigation decision (locked)

**Tinting is nested under Services** — not a top-level nav item. Most customers
know the business for detailing; the name is On-Wheels *Detailing*.

Proposed nav (7 items):
`Home · Services (▾ Detailing / Paint & Ceramic / Tinting / Undercoating) ·
Gallery · Locations · About · [Book Now]`

---

## 3. Products — display strategy

### The product list (as provided)
- **Interior:** P&S Carpet Bomb · P&S Interior Cleaner · Koch Chemie Pol Star ·
  CarPro Perl · StarryBot Hot Water Extraction · Steam Cleaning
- **Paint correction:** Oberk Supreme Cut · Oberk Supreme Polish ·
  Oberk Sole (One-Step Medium Polish)
- **Ceramic:** CarPro CQuartz 3.0

### How we show it
- **Curated "Products We Trust" element** (brand-name badges + one-line "why"):
  CarPro · Koch Chemie · P&S · Oberk. Signals pro-grade, not parts-store.
- **Feature the crown jewels** on their service pages: **CarPro CQuartz 3.0**
  (ceramic) and the **Oberk** polish line (paint correction).
- **No per-service chemical spec dump.** Customers buy outcomes; the raw
  `products_used` field stays in the DB for internal use only (already returned
  by `/api/services`, but the public site never renders it).
- **Undercoating** is the one place we DO compare products: Fluid Film vs
  Woolwax (real customer choice — yearly vs 2-yr reapply).

---

## 4. Process constraint (locked)

**Build everything, then it sits.** Work goes to `development` and stays there.
No push-to-master, no deployment — the site doesn't roll out until **2027**.
Testing is limited until Cloudflare actually hosts it; we build + test locally
(`astro dev` / `astro build`) in the meantime.
