#!/usr/bin/env python3
"""On-Wheels Detailing CRM — SQLite-backed customer & appointment management."""

import sqlite3
import os
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Business Timezone ─────────────────────────────────────────────
# All times hardcoded to Eastern Standard (UTC-5) and Central Standard (UTC-6).
# No DST auto-switch — displays show EST/CST year-round for consistency.
# Set TZ env var to override the default offset (e.g., TZ_OFFSET=-6).

_DEFAULT_OFFSET = int(os.environ.get("TZ_OFFSET", "-5"))  # -5 = EST

def _fixed_tz(offset_hours):
    """Return a fixed-offset timezone (no DST)."""
    return timezone(timedelta(hours=offset_hours), 
                   f"UTC{offset_hours:+d}")

BUSINESS_TZ = _fixed_tz(_DEFAULT_OFFSET)  # EST (UTC-5)

# ── Location → Timezone mapping ───────────────────────────────────
# Each area maps to (IANA_name, display_label, display_abbrev, offset).
# IANA stored in DB for correctness; labels always show standard time.
LOCATION_TIMEZONES = {
    'Texas - Harris County':         ('America/Chicago', 'Central', 'CST', -6),
    'Michigan - St. Clair':          ('America/Detroit', 'Eastern', 'EST', -5),
    'Michigan - Metro Detroit':      ('America/Detroit', 'Eastern', 'EST', -5),
    'Michigan - Marysville (Shop)':  ('America/Detroit', 'Eastern', 'EST', -5),
    'Michigan - New Haven (Shop)':   ('America/Detroit', 'Eastern', 'EST', -5),
}

def get_tz_for(location):
    """Return fixed-offset timezone for a service area. Falls back to EST."""
    info = LOCATION_TIMEZONES.get(location)
    offset = info[3] if info else -5
    return _fixed_tz(offset)

def get_tz_info(location):
    """Return (iana_name, display_label, display_abbrev) or defaults."""
    info = LOCATION_TIMEZONES.get(location)
    if info:
        return info[0], info[1], info[2]
    return 'America/Detroit', 'Eastern', 'EST'

def tz_display_label(tz):
    """Return display label ('Eastern', 'Central') — always standard time."""
    if tz is None:
        return 'Eastern'
    offset = tz.utcoffset(datetime.now())
    if offset is None:
        return 'Eastern'
    hours = offset.total_seconds() / 3600
    if hours == -5:
        return 'Eastern'
    if hours == -6:
        return 'Central'
    if hours == -7:
        return 'Mountain'
    if hours == -8:
        return 'Pacific'
    return tz.tzname(None) or 'Local'

def tz_offset_label(tz):
    """Return abbreviation ('EST', 'CST') — always standard time."""
    if tz is None:
        return 'EST'
    offset = tz.utcoffset(datetime.now())
    if offset is None:
        return 'EST'
    hours = offset.total_seconds() / 3600
    labels = {-5: 'EST', -6: 'CST', -7: 'MST', -8: 'PST'}
    return labels.get(int(hours), f'UTC{int(hours):+d}')

def now_in_tz(tz):
    """Return current datetime in a specific timezone."""
    return datetime.now(tz) if tz else datetime.now()

def now():
    """Return current datetime in business timezone (EST/UTC-5)."""
    return datetime.now(BUSINESS_TZ)

def today_str():
    """Return today's date in EST as YYYY-MM-DD."""
    return now().strftime('%Y-%m-%d')

def now_str():
    """Return current datetime in EST as ISO timestamp."""
    return now().strftime('%Y-%m-%d %H:%M:%S')

def now_display():
    """Return human-readable current time (always shows EST)."""
    t = now()
    return f"{t.strftime('%A, %B %d, %Y at %I:%M %p')} EST"

DB_PATH = Path(os.environ.get("ONWHEELS_DB", Path(__file__).parent / "onwheels.db"))

# Stripe payment links
STRIPE_STANDARD = "https://buy.stripe.com/eVq4gBcqY6kvbhBdqT9ws00"   # $50 deposit
STRIPE_PREMIUM  = "https://buy.stripe.com/dRm6oJOIgfV5adx5Yr9ws01"   # $100 deposit


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA mmap_size=33554432")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            full_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            location TEXT CHECK(location IN ('Texas - Harris County','Michigan - Metro Detroit')),
            source TEXT CHECK(source IN ('Website','Facebook','Instagram','Referral','Repeat','Other')),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            customer_id TEXT NOT NULL REFERENCES customers(id),
            vehicle_type TEXT CHECK(vehicle_type IN ('Car','Truck','SUV','Van','Boat','RV','Motorcycle','Other')),
            make TEXT,
            model TEXT,
            year INTEGER,
            color TEXT,
            license_plate TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            name TEXT NOT NULL,
            category TEXT CHECK(category IN ('Marine Gel-coat','Interior Detailing','Paint Correction & Ceramic')),
            sub_service TEXT,
            description TEXT,
            starting_price REAL,
            pricing_model TEXT CHECK(pricing_model IN ('Flat Rate','Per Foot','Hourly','Quote Only')),
            products_used TEXT,
            duration_hours REAL,
            deposit_amount REAL
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            customer_id TEXT NOT NULL REFERENCES customers(id),
            vehicle_id TEXT REFERENCES vehicles(id),
            service_id TEXT REFERENCES services(id),
            appointment_date TEXT NOT NULL,
            appointment_time TEXT,
            job_address TEXT,
            status TEXT DEFAULT 'New Lead'
                CHECK(status IN ('New Lead','Quote Sent','Awaiting Deposit','Confirmed','In Progress','Completed','Cancelled','No Show')),
            quoted_price REAL,
            special_requests TEXT,
            payment_link TEXT,
            deposit_agreed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            appointment_id TEXT NOT NULL REFERENCES appointments(id),
            payment_type TEXT CHECK(payment_type IN ('Deposit','Full Payment','Balance','Tip','Refund')),
            amount REAL NOT NULL,
            method TEXT CHECK(method IN ('Cash','Zelle','Venmo','Cash App','Credit Card','Check')),
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Paid','Refunded','Failed')),
            payment_date TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS follow_ups (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            appointment_id TEXT NOT NULL REFERENCES appointments(id),
            follow_type TEXT CHECK(follow_type IN ('Booking Confirmation','24hr Reminder','Post-Service Check-in','Re-engagement','Review Request','Thank You')),
            channel TEXT CHECK(channel IN ('SMS','Email','Phone Call')),
            scheduled_date TEXT,
            status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Sent','Failed','Skipped')),
            message TEXT,
            response TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_appts_customer ON appointments(customer_id);
        CREATE INDEX IF NOT EXISTS idx_appts_date ON appointments(appointment_date);
        CREATE INDEX IF NOT EXISTS idx_appts_status ON appointments(status);
        CREATE INDEX IF NOT EXISTS idx_payments_appt ON payments(appointment_id);
        CREATE INDEX IF NOT EXISTS idx_followups_date ON follow_ups(scheduled_date);
        CREATE INDEX IF NOT EXISTS idx_followups_status ON follow_ups(status);
    """)
    conn.commit()

    # ── Schema migrations (safe for existing DBs) ──
    migrations = [
        "ALTER TABLE services ADD COLUMN deposit_amount REAL",
        "ALTER TABLE appointments ADD COLUMN payment_link TEXT",
        "ALTER TABLE appointments ADD COLUMN deposit_agreed_at TEXT",
        "ALTER TABLE appointments ADD COLUMN appointment_tz TEXT",
    ]
    for m in migrations:
        try:
            conn.execute(m)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Update deposit amounts for existing services (safe to re-run)
    deposit_updates = [
        (50, 'Polish & Protect (Auto)'),
        (100, 'Two-Step Paint Correction'),
        (100, 'Ceramic Coating (Auto)'),
        (100, 'Signature Detail Package'),
    ]
    for amount, name in deposit_updates:
        conn.execute(
            "UPDATE services SET deposit_amount=? WHERE name=? AND deposit_amount IS NULL",
            (amount, name))
    conn.commit()

    # Normalize existing phone numbers to digits-only (dedup migration)
    all_customers = conn.execute("SELECT id, phone FROM customers WHERE phone IS NOT NULL").fetchall()
    for row in all_customers:
        clean = ''.join(c for c in row['phone'] if c.isdigit())
        if clean and clean != row['phone']:
            conn.execute("UPDATE customers SET phone=? WHERE id=?", (clean, row['id']))
    conn.commit()
    conn.close()
    return


# ── Customer Operations ──────────────────────────────────────────

def create_customer(full_name, phone=None, email=None, address=None,
                    city=None, state=None, zip_code=None, location=None,
                    source='Website', notes=None, conn=None):
    _close = conn is None
    if _close:
        conn = get_db()
    cust_id = conn.execute("""
        INSERT INTO customers (full_name, phone, email, address, city, state, zip, location, source, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (full_name, phone, email, address, city, state, zip_code, location, source, notes)).lastrowid
    # Get the real ID
    row = conn.execute("SELECT id FROM customers WHERE rowid=?", (cust_id,)).fetchone()
    if _close:
        conn.commit()
        conn.close()
    return row['id']


def normalize_phone(phone):
    """Strip to digits only for dedup. Returns empty string if no digits."""
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit())


def find_customer(phone=None, email=None, conn=None):
    """Find customer by phone or email. Phone is normalized to digits-only."""
    _close = conn is None
    if _close:
        conn = get_db()
    if phone:
        clean = normalize_phone(phone)
        if not clean:
            if _close:
                conn.close()
            return []
        # Try exact digits-only match first, fall back to LIKE for legacy records
        rows = conn.execute(
            "SELECT * FROM customers WHERE phone=? ORDER BY created_at DESC",
            (clean,)).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT * FROM customers WHERE phone LIKE ? ORDER BY created_at DESC",
                (f'%{clean}%',)).fetchall()
    elif email:
        rows = conn.execute(
            "SELECT * FROM customers WHERE email=? ORDER BY created_at DESC",
            (email,)).fetchall()
    else:
        rows = []
    if _close:
        conn.close()
    return [dict(r) for r in rows]


def get_customers(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM customers ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Vehicle Size Classification ─────────────────────────────────

# Maps booking-form vehicle_type → pricing tier
VEHICLE_SIZE_MAP = {
    'Car':        'Sedan',
    'SUV':        'SUV/Hatchback',
    'Truck':      'Large SUV/Truck',
    'Van':        'Large SUV/Truck',
    'RV':         'Other',       # CHECK constraint only allows Sedan/SUV-H/Lg/Other
    'Motorcycle': 'Other',
    'Boat':       'Other',
    'Other':      'Other',
}

# Service pricing tiers by vehicle size
# Prices: [Sedan, SUV/Hatchback, Large SUV/Truck]
SERVICE_PRICE_TIERS = {
    'Interior Refresh':               [150,  180,  210],
    'Premium Interior Restoration':   [200,  240,  280],
    'Polish & Protect':               [375,  425,  475],
    'Signature Detail Package':       [1150, 1350, 1600],
    'Two-Step Paint Correction':      [525,  625,  725],
    'Ceramic Coating (Auto)':         [1500, 1750, 2000],
}

# Marine / RV services (per-foot pricing)
PER_FOOT_SERVICES = {'Marine Wash & Protect', 'RV Wash & Protect'}
PER_FOOT_RATE = 20  # dollars per foot


def classify_vehicle_size(vehicle_type):
    """Map vehicle_type from booking form to size tier for pricing."""
    if not vehicle_type:
        return 'Sedan'  # conservative default
    return VEHICLE_SIZE_MAP.get(vehicle_type, 'Sedan')


def get_vehicle_size_label(vehicle_size):
    """Return user-friendly size label."""
    if vehicle_size == 'SUV/Hatchback':
        return 'SUV'
    elif vehicle_size == 'Large SUV/Truck':
        return 'Large SUV/Truck'
    return vehicle_size or 'Sedan'


def get_service_tier_price(service_name, vehicle_size):
    """Return the price for a given service + vehicle size combination."""
    if not service_name or not vehicle_size:
        return None
    
    tiers = SERVICE_PRICE_TIERS.get(service_name)
    if not tiers:
        base = service_name.replace(' (Auto)', '')
        tiers = SERVICE_PRICE_TIERS.get(base)
    if not tiers:
        return None
    
    idx_map = {'Sedan': 0, 'SUV/Hatchback': 1, 'Large SUV/Truck': 2}
    idx = idx_map.get(vehicle_size, 0)
    return tiers[idx]


def get_vehicle_size_short(vehicle_size):
    """Short label for display: 'Sedan', 'SUV', 'Lg SUV', 'RV', 'Moto'."""
    if not vehicle_size:
        return '?'
    return {
        'Sedan': 'Sedan',
        'SUV/Hatchback': 'SUV',
        'Large SUV/Truck': 'Lg SUV',
        'Other': 'Other',
    }.get(vehicle_size, vehicle_size[:6])


# ── Vehicle Operations ───────────────────────────────────────────

def add_vehicle(customer_id, vehicle_type, make=None, model=None,
                year=None, color=None, license_plate=None, notes=None,
                vehicle_size=None, conn=None):
    _close = conn is None
    if _close:
        conn = get_db()
    if vehicle_size is None:
        vehicle_size = classify_vehicle_size(vehicle_type)
    conn.execute("""
        INSERT INTO vehicles (customer_id, vehicle_type, vehicle_size, make, model, year, color, license_plate, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (customer_id, vehicle_type, vehicle_size, make, model, year, color, license_plate, notes))
    if _close:
        conn.commit()
        conn.close()


def get_customer_vehicles(customer_id, conn=None):
    _close = conn is None
    if _close:
        conn = get_db()
    rows = conn.execute(
        "SELECT * FROM vehicles WHERE customer_id=? ORDER BY rowid DESC", (customer_id,)).fetchall()
    if _close:
        conn.close()
    return [dict(r) for r in rows]


# ── Service Catalog ──────────────────────────────────────────────

def seed_services():
    """Populate the services table with On-Wheels Detailing offerings."""
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
    if existing > 0:
        conn.close()
        return  # Already seeded

    services = [
        # RV Detailing (Per-Foot)
        ("RV Wash Only", "Marine Gel-coat", "Wash Only",
         "Hand wash, wheels, and windows. Per-foot pricing for RVs and campers.",
         8, "Per Foot", "pH-neutral soap", 2, 50),
        ("RV Wash & Protect", "Marine Gel-coat", "Wash & Protect",
         "Thorough wash with gelcoat-safe wax/sealant + UV protection. Per-foot.",
         25, "Per Foot", "pH-neutral soap, gelcoat sealant, UV protectant", 3, 100),
        ("RV Premium Detail", "Marine Gel-coat", "Premium Detail",
         "Wash & protect + roof treatment + awning cleaning. All-in-one per-foot.",
         35, "Per Foot", "pH-neutral soap, gelcoat sealant, roof protectant, awning cleaner", 5, 100),
        ("RV Oxidation Removal", "Marine Gel-coat", "Oxidation Removal",
         "Compound + polish + protect to restore chalked, oxidized gelcoat. Per-foot.",
         45, "Per Foot", "Marine compound, polish, gelcoat sealant, dual-action polisher", 8, 100),
        # Interior Detailing
        ("Interior Refresh", "Interior Detailing", "Interior Refresh",
         "Complete interior clean: vacuum, wipe-down, glass, and light stain treatment.",
         150, "Flat Rate", "Koch Chemie Pol Star, Carpro Perl", 2, None),
        ("Premium Interior Restoration", "Interior Detailing", "Premium Interior Restoration",
         "Deep clean with hot water extraction and steam. Carpet, upholstery, headliner — the works.",
         250, "Flat Rate", "Koch Chemie Pol Star, Carpro Perl, hot water extractor", 4, None),
        ("Steam & Hot Water Extraction", "Interior Detailing", "Steam & Hot Water Extraction",
         "Sanitizing steam treatment + hot water extraction for carpets and fabric seats.",
         180, "Flat Rate", "Steam cleaner, hot water extractor", 3, None),
        # Paint Correction
        ("Two-Step Paint Correction", "Paint Correction & Ceramic", "Two-Step Paint Correction",
         "Compound + polish to remove swirls, light scratches, and oxidation. Restores depth and clarity.",
         None, "Quote Only", "Compounds, polishes, dual-action polisher", 6, 100),
        ("Ceramic Coating (Auto)", "Paint Correction & Ceramic", "Ceramic Coating",
         "Carpro CQ.UK 3.0 ceramic coating for cars/trucks. 2+ years of hydrophobic protection.",
         None, "Quote Only", "Carpro CQ.UK 3.0, surface prep", 8, 100),
        ("Polish & Protect (Auto)", "Paint Correction & Ceramic", "Polish & Protect",
         "Single-stage polish with premium paint sealant. Perfect maintenance detail.",
         200, "Flat Rate", "Polish, sealant, dual-action polisher", 3, 50),
        ("Signature Detail Package", "Paint Correction & Ceramic", "Signature Detail Package",
         "The full treatment: interior refresh + exterior polish & protect. Your car, transformed.",
         350, "Flat Rate", "Pol Star, Carpro Perl, polish, sealant", 5, 100),
    ]
    conn = get_db()
    conn.executemany("""
        INSERT OR IGNORE INTO services (name, category, sub_service, description, starting_price, pricing_model, products_used, duration_hours, deposit_amount)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, services)
    conn.commit()
    conn.close()


def get_services(category=None):
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM services WHERE category=? ORDER BY category, name", (category,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM services ORDER BY category, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_service_deposit(service_id, conn=None):
    """Return (deposit_amount, stripe_link) for a service, or (None, None) if no deposit required."""
    _close = conn is None
    if _close:
        conn = get_db()
    row = conn.execute(
        "SELECT deposit_amount FROM services WHERE id=?", (service_id,)).fetchone()
    if _close:
        conn.close()
    if not row or not row['deposit_amount']:
        return None, None
    amount = row['deposit_amount']
    link = STRIPE_PREMIUM if amount >= 100 else STRIPE_STANDARD
    return amount, link


# ── Appointment Operations ───────────────────────────────────────

def create_appointment(customer_id, appointment_date, appointment_time=None,
                       vehicle_id=None, service_id=None, job_address=None,
                       special_requests=None, status='New Lead',
                       payment_link=None, deposit_agreed_at=None,
                       appointment_tz=None, conn=None):
    _close = conn is None
    if _close:
        conn = get_db()
    conn.execute("""
        INSERT INTO appointments (customer_id, vehicle_id, service_id, appointment_date, appointment_time, job_address, status, special_requests, payment_link, deposit_agreed_at, appointment_tz)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (customer_id, vehicle_id, service_id, appointment_date, appointment_time, job_address, status, special_requests, payment_link, deposit_agreed_at, appointment_tz))
    appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT id FROM appointments WHERE rowid=?", (appt_id,)).fetchone()
    if _close:
        conn.commit()
        conn.close()
    return row['id']


def get_appointments(status=None, date_from=None, date_to=None, limit=50):
    conn = get_db()
    query = """
        SELECT a.*, c.full_name, c.phone, c.email, c.location as customer_location,
               c.city, c.state,
               v.make||' '||v.model as vehicle_desc,
               v.vehicle_type, v.vehicle_size,
               s.name as service_name, s.category as service_category
        FROM appointments a
        LEFT JOIN customers c ON a.customer_id = c.id
        LEFT JOIN vehicles v ON a.vehicle_id = v.id
        LEFT JOIN services s ON a.service_id = s.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND a.status = ?"
        params.append(status)
    if date_from:
        query += " AND a.appointment_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND a.appointment_date <= ?"
        params.append(date_to)
    query += " ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_appointment_status(appointment_id, status):
    conn = get_db()
    conn.execute("UPDATE appointments SET status=? WHERE id=?", (status, appointment_id))
    conn.commit()
    conn.close()


def get_upcoming_appointments(days=7):
    """Get confirmed appointments in the next N days."""
    conn = get_db()
    today = today_str()
    end = (now() + timedelta(days=days)).strftime('%Y-%m-%d')
    rows = conn.execute("""
        SELECT a.*, c.full_name, c.phone, c.email,
               c.city, c.state,
               v.make||' '||v.model as vehicle_desc,
               v.vehicle_type, v.vehicle_size,
               s.name as service_name, s.category as service_category
        FROM appointments a
        JOIN customers c ON a.customer_id = c.id
        LEFT JOIN vehicles v ON a.vehicle_id = v.id
        LEFT JOIN services s ON a.service_id = s.id
        WHERE a.appointment_date BETWEEN ? AND ?
          AND a.status IN ('Confirmed','Awaiting Deposit')
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    """, (today, end)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Payment Operations ───────────────────────────────────────────

def add_payment(appointment_id, amount, payment_type='Deposit',
                method='Zelle', status='Pending', notes=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO payments (appointment_id, payment_type, amount, method, status, payment_date, notes)
        VALUES (?,?,?,?,?,?,?)
    """, (appointment_id, payment_type, amount, method, status, now_str(), notes))
    conn.commit()
    conn.close()


def get_appointment_payments(appointment_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM payments WHERE appointment_id=? ORDER BY payment_date DESC",
        (appointment_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_deposit_balance():
    """Total deposits pending vs paid."""
    conn = get_db()
    pending = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_type='Deposit' AND status='Pending'").fetchone()[0]
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_type='Deposit' AND status='Paid'").fetchone()[0]
    conn.close()
    return {'pending': pending, 'paid': paid, 'total': pending + paid}


# ── Follow-up Operations ─────────────────────────────────────────

def create_follow_up(appointment_id, follow_type, scheduled_date, channel='SMS', conn=None):
    _close = conn is None
    if _close:
        conn = get_db()
    conn.execute("""
        INSERT INTO follow_ups (appointment_id, follow_type, channel, scheduled_date)
        VALUES (?,?,?,?)
    """, (appointment_id, follow_type, channel, scheduled_date))
    if _close:
        conn.commit()
        conn.close()


def get_pending_follow_ups():
    """Get follow-ups scheduled for today or earlier, not yet sent."""
    conn = get_db()
    today = today_str()
    rows = conn.execute("""
        SELECT f.*, a.appointment_date, a.status as appt_status,
               c.full_name, c.phone, c.email,
               s.name as service_name
        FROM follow_ups f
        JOIN appointments a ON f.appointment_id = a.id
        JOIN customers c ON a.customer_id = c.id
        LEFT JOIN services s ON a.service_id = s.id
        WHERE f.scheduled_date <= ?
          AND f.status = 'Pending'
        ORDER BY f.scheduled_date ASC
    """, (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_follow_up(follow_up_id, status, message=None):
    conn = get_db()
    conn.execute(
        "UPDATE follow_ups SET status=?, message=? WHERE id=?",
        (status, message, follow_up_id))
    conn.commit()
    conn.close()


# ── Dashboard ────────────────────────────────────────────────────

def get_dashboard():
    """Quick stats for the business dashboard."""
    conn = get_db()
    t = now()
    biz_today = t.strftime('%Y-%m-%d')
    biz_week_end = (t + timedelta(days=7)).strftime('%Y-%m-%d')
    tz_label = "EST" if t.tzname() == "EST" else "EDT"

    stats = {}
    stats['total_customers'] = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    stats['pending_appointments'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status IN ('New Lead','Quote Sent','Awaiting Deposit','Confirmed')").fetchone()[0]
    stats['completed_today'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status='Completed' AND appointment_date=?",
        (biz_today,)).fetchone()[0]
    stats['upcoming_week'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appointment_date BETWEEN ? AND ? AND status IN ('Confirmed','Awaiting Deposit')",
        (biz_today, biz_week_end)).fetchone()[0]
    deposits = get_deposit_balance()
    stats['deposits_pending'] = deposits['pending']
    stats['deposits_paid'] = deposits['paid']
    stats['pending_follow_ups'] = conn.execute(
        "SELECT COUNT(*) FROM follow_ups WHERE status='Pending'").fetchone()[0]
    stats['as_of'] = now_display()
    conn.close()
    return stats


# ── CLI entry point ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    conn = init_db()
    seed_services()
    print("✅ CRM database initialized:", DB_PATH)
    print(f"   Tables: customers, vehicles, services, appointments, payments, follow_ups")

    if '--dashboard' in sys.argv:
        import json as j
        print(j.dumps(get_dashboard(), indent=2, default=str))
