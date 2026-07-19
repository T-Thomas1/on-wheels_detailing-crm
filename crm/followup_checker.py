#!/usr/bin/env python3
"""On-Wheels Detailing — Daily CRM check script for Hermes cron jobs.

Outputs pending actions as structured text for the cron agent to process.
Run this as a cron script (no_agent=True) for a watchdog, or with no_agent=False
for an LLM-driven morning briefing.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from crm import (
    get_db,
    get_pending_follow_ups,
    get_upcoming_appointments,
    get_appointments,
    get_deposit_balance,
    get_dashboard,
)


def check_pending_follow_ups():
    """Find follow-ups that need action today."""
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')

    rows = conn.execute("""
        SELECT f.*, a.appointment_date, a.status as appt_status,
               c.full_name, c.phone, c.email,
               s.name as service_name, s.category as service_category,
               a.payment_link
        FROM follow_ups f
        JOIN appointments a ON f.appointment_id = a.id
        JOIN customers c ON a.customer_id = c.id
        LEFT JOIN services s ON a.service_id = s.id
        WHERE f.scheduled_date <= ?
          AND f.status = 'Pending'
        ORDER BY f.follow_type, f.scheduled_date ASC
    """, (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def format_phone(phone):
    """Strip non-digits for display."""
    if not phone:
        return 'N/A'
    return phone


def generate_message(follow_up):
    """Generate a natural-sounding message based on follow-up type."""
    name = follow_up['full_name']
    service = follow_up.get('service_name') or 'detailing service'
    payment_link = follow_up.get('payment_link') or '[Stripe link here]'
    appt_date = follow_up['appointment_date']

    templates = {
        'Booking Confirmation': [
            f"Hey {name}! TaSain here from On-Wheels Detailing. Got your booking for {service}. I've got you on the schedule. To lock it in, here's your deposit link: {payment_link}. Once that's done you're confirmed. Talk soon!",
        ],
        '24hr Reminder': [
            f"  Tomorrow's the day, {name}! Reminder: I'll be out for your {service} tomorrow. Balance is due when I arrive (cash or card). Make sure the vehicle's accessible. Any changes, just text. — TaSain, On-Wheels Detailing",
        ],
        'Post-Service Check-in': [
            f"Hey {name}! Been a couple days since your {service} — how's everything looking? If anything needs a touch-up, don't hesitate to let me know. I stand behind my work. — TaSain, On-Wheels",
            f"Checking in, {name}! How's the {service} holding up? If you're happy, I'd love a review on Google or Facebook — it really helps a small operation like mine. Thanks again for your business! — TaSain",
        ],
        'Re-engagement': [
            f"Hey {name}! Been a while since your last detail with On-Wheels. If it's time for a refresh, I'm booking for the coming weeks. Text back and let's set something up! — TaSain",
        ],
        'Review Request': [
            f"Hey {name}! Hope you're still loving the {service} results. If you've got a minute, a quick Google or Facebook review would mean the world to this small business. Thanks a ton! — TaSain, On-Wheels Detailing",
        ],
        'Thank You': [
            f"Thanks again for choosing On-Wheels Detailing, {name}! It was a pleasure working on your vehicle. Keep me in mind for next time — I'll take care of you. — TaSain",
        ],
    }

    options = templates.get(follow_up['follow_type'], [
        f"Follow-up for {name}: {follow_up['follow_type']} — {service}"
    ])
    import random
    return random.choice(options)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'full'

    if mode == 'brief':
        # Quick check: only print if there's something actionable
        follow_ups = check_pending_follow_ups()
        if not follow_ups:
            return  # Silent — nothing to report
        print(f"[ACTION NEEDED] {len(follow_ups)} pending follow-ups today.")
        for fu in follow_ups:
            print(f"  - {fu['follow_type']}: {fu['full_name']} — {fu.get('service_name', 'N/A')}")
        return

    # Full morning briefing
    print("=" * 60)
    print("  ON-WHEELS DETAILLING — DAILY BRIEFING")
    print(f"  {datetime.now().strftime('%A, %B %d, %Y')}")
    print("=" * 60)

    # Stats
    stats = get_dashboard()
    print(f"\n  AT A GLANCE")
    print(f"  Total Customers:     {stats['total_customers']}")
    print(f"  Pending Appointments: {stats['pending_appointments']}")
    print(f"  This Week:           {stats['upcoming_week']} scheduled")
    print(f"  Deposits Pending:    ${stats['deposits_pending']:,.0f}")
    print(f"  Deposits Collected:  ${stats['deposits_paid']:,.0f}")

    # Upcoming appointments
    upcoming = get_upcoming_appointments(days=14)
    if upcoming:
        print(f"\n  UPCOMING APPOINTMENTS (Next 14 Days)")
        print(f"  {'─' * 54}")
        for a in upcoming:
            vehicle = a.get('vehicle_desc') or ''
            svc = a.get('service_name') or 'Unspecified'
            addr = a.get('job_address') or a.get('city') or ''
            price = f"${a['quoted_price']:,.0f}" if a['quoted_price'] else 'TBD'
            print(f"  {a['appointment_date']} | {a.get('appointment_time','--'):20s} | {a['full_name']:20s}")
            print(f"  {'':11s}| {svc:20s} | {vehicle} | {price}")
            print()

    # New leads (last 24h)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    new_leads = get_appointments(status='New Lead', date_from=yesterday)
    if new_leads:
        print(f"\n  NEW LEADS (Last 24 Hours)")
        print(f"  {'─' * 54}")
        for a in new_leads:
            print(f"    {a['full_name']} | {a['phone']} | {a.get('service_name','Unspecified')}")
            print(f"    From: {a.get('city','')} {a.get('state','')} | {a.get('vehicle_desc','')}")

    # Pending follow-ups that need action NOW
    follow_ups = check_pending_follow_ups()
    if follow_ups:
        print(f"\n  FOLLOW-UPS DUE TODAY ({len(follow_ups)})")
        print(f"  {'─' * 54}")
        for fu in follow_ups:
            msg = generate_message(fu)
            print(f"\n  Type: {fu['follow_type']}")
            print(f"  To:   {fu['full_name']} — {format_phone(fu['phone'])}")
            print(f"  Re:   {fu.get('service_name', 'N/A')} on {fu['appointment_date']}")
            print(f"  Message:")
            print(f"  ┌{'─' * 52}")
            for line in msg.split('\n'):
                print(f"  │ {line}")
            print(f"  └{'─' * 52}")

    if not upcoming and not new_leads and not follow_ups:
        print(f"\n  All quiet today. Time to prospect or post on social!")
        print(f"  IG: @on_wheelsdetailing")
        print(f"  FB: facebook.com/share/16tKSTuW4C/")

    print(f"\n{'=' * 60}")
    print(f"  End of briefing. Go make some vehicles shine.\n")


if __name__ == '__main__':
    main()
