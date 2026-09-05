# Stripe Checkout at Booking — Card + Cash

Customers can now pay their deposit at booking time (Stripe Checkout) or choose
to pay cash at the appointment. This doc covers where the secret key lives, how
to turn it on, and how to test.

## Architecture (why the key is NOT in the website)

The secret key must never ship to the browser. The Astro site (Cloudflare Pages)
is 100% static and contains zero secrets. The Stripe secret key lives on the
CRM droplet, which is already the secret holder (`ONWHEELS_API_KEY`,
`ONWHEELS_ADMIN_KEY`) and already owns the booking record.

Flow:

```
customer → www (Astro wizard) → POST /api/book {payment_method: "card"|"cash"}
  → api.onwheelsdetailing.com (Python) creates a Stripe Checkout Session
  → returns {checkout_url} → browser redirects to Stripe-hosted checkout
  → Stripe redirects back to /book/success (or /book/cancel)
  → Stripe POSTs /api/stripe-webhook → CRM marks deposit paid
```

The wizard never sees the secret key; it only ever receives a checkout URL.

## Environment variables (droplet: /opt/onwheels/crm/.env)

Add these to the same `.env` that already holds the API keys:

```
STRIPE_SECRET_KEY=sk_live_...        # or sk_test_... in test mode
STRIPE_WEBHOOK_SECRET=whsec_...      # signing secret for the webhook
SITE_BASE_URL=https://www.onwheelsdetailing.com   # optional; defaults to this
```

Then restart the service: `systemctl restart onwheels`.

- `STRIPE_SECRET_KEY` — from Stripe Dashboard → Developers → API keys.
- `STRIPE_WEBHOOK_SECRET` — from the webhook endpoint's "Signing secret".
- `SITE_BASE_URL` — set to a `.pages.dev` preview URL (or `http://localhost:4321`)
  while testing so the success/cancel redirects land back on your dev site.

## Register the webhook (Stripe Dashboard)

1. Stripe Dashboard → Developers → Webhooks → Add endpoint.
2. URL: `https://api.onwheelsdetailing.com/api/stripe-webhook`
3. Events: `checkout.session.completed` (add `checkout.session.expired` too if
   you want to track abandoned checkouts).
4. Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.

The webhook is the thing that flips the deposit to "paid": it writes a
`payments` row (Credit Card / Paid) and stamps `deposit_agreed_at` on the
appointment, which the dashboard already surfaces as the deposit date.

## How the booking flow behaves now

- Service has no deposit (Interior Refresh / Premium): no payment step, "pay on
  the day", unchanged.
- Service has a deposit and the customer picks **card**: status becomes
  `Awaiting Deposit`, a Checkout Session is created, the browser redirects to
  Stripe. On completion the webhook marks it paid.
- Service has a deposit and the customer picks **cash**: status stays `New
  Lead`, no Stripe link, nothing charged. Owner confirms manually.
- **Key not configured yet**: the card path degrades gracefully to the legacy
  behavior (owner texts the existing `buy.stripe.com` link) instead of failing.

The legacy `booking.html` form (api.onwheelsdetailing.com/book) still sends only
`deposit_agreed` (no `payment_method`), and is handled by the same backward-
compatible branch, so nothing breaks there.

## Test in Stripe test mode

1. Put an `sk_test_...` key + a `whsec_...` secret in the droplet `.env`.
2. Set `SITE_BASE_URL` to your dev URL (or leave localhost).
3. Book a service with a deposit, pick "Pay the deposit now by card".
4. On the Stripe test checkout use card `4242 4242 4242 4242`, any future expiry,
   any CVC, any ZIP.
5. Confirm the dashboard shows the deposit date (paid) for that appointment.

## What was verified locally (no live key required)

- `python3 -m py_compile server.py` — clean.
- Unit-tested `verify_stripe_signature` (valid / bad / empty) and
  `create_checkout_session` payload construction (amount, client_reference_id,
  email, Basic-auth header) with a mocked HTTP layer.
- `npm run build` + `npm run check` — site builds, 0 type errors, new routes
  `/book/success` and `/book/cancel` emitted, payment UI present in the output.
