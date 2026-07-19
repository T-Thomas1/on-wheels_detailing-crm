#!/usr/bin/env python3
"""On-Wheels Detailing CRM — SQLite-backed customer & appointment management."""

import sqlite3
import os
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(os.environ.get("ONWHEELS_DB", Path(__file__).parent / "onwheels.db"))


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
            duration_hours REAL
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
            payment_link TEXT,
            special_requests TEXT,
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
    return conn


# ── Customer Operations ──────────────────────────────────────────

def create_customer(full_name, phone=None, email=None, address=None,
                    city=None, state=None, zip_code=None, location=None,
                    source='Website', notes=None):
    conn = get_db()
    cust_id = conn.execute("""
        INSERT INTO customers (full_name, phone, email, address, city, state, zip, location, source, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (full_name, phone, email, address, city, state, zip_code, location, source, notes)).lastrowid
    conn.commit()
    # Get the real ID
    row = conn.execute("SELECT id FROM customers WHERE rowid=?", (cust_id,)).fetchone()
    conn.close()
    return row['id']


def find_customer(phone=None, email=None):
    """Find customer by phone or email. Returns list of matches."""
    conn = get_db()
    if phone:
        rows = conn.execute(
            "SELECT * FROM customers WHERE phone LIKE ? ORDER BY created_at DESC",
            (f'%{phone}%',)).fetchall()
    elif email:
        rows = conn.execute(
            "SELECT * FROM customers WHERE email=? ORDER BY created_at DESC",
            (email,)).fetchall()
    else:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def get_customers(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM customers ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Vehicle Operations ───────────────────────────────────────────

def add_vehicle(customer_id, vehicle_type, make=None, model=None,
                year=None, color=None, license_plate=None, notes=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO vehicles (customer_id, vehicle_type, make, model, year, color, license_plate, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (customer_id, vehicle_type, make, model, year, color, license_plate, notes))
    conn.commit()
    conn.close()


def get_customer_vehicles(customer_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM vehicles WHERE customer_id=? ORDER BY rowid DESC", (customer_id,)).fetchall()
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
        # Interior Detailing
        ("Interior Refresh", "Interior Detailing", "Interior Refresh",
         "Complete interior clean: vacuum, wipe-down, glass, and light stain treatment.",
         150, "Flat Rate", "Koch Chemie Pol Star, Carpro Perl", 2),
        ("Premium Interior Restoration", "Interior Detailing", "Premium Interior Restoration",
         "Deep clean with hot water extraction and steam. Carpet, upholstery, headliner — the works.",
         250, "Flat Rate", "Koch Chemie Pol Star, Carpro Perl, hot water extractor", 4),
        ("Steam & Hot Water Extraction", "Interior Detailing", "Steam & Hot Water Extraction",
         "Sanitizing steam treatment + hot water extraction for carpets and fabric seats.",
         180, "Flat Rate", "Steam cleaner, hot water extractor", 3),
        # Paint Correction
        ("Two-Step Paint Correction", "Paint Correction & Ceramic", "Two-Step Paint Correction",
         "Compound + polish to remove swirls, light scratches, and oxidation. Restores depth and clarity.",
         None, "Quote Only", "Compounds, polishes, dual-action polisher", 6),
        ("Ceramic Coating (Auto)", "Paint Correction & Ceramic", "Ceramic Coating",
         "Carpro CQ.UK 3.0 ceramic coating for cars/trucks. 2+ years of hydrophobic protection.",
         None, "Quote Only", "Carpro CQ.UK 3.0, surface prep", 8),
        ("Polish & Protect (Auto)", "Paint Correction & Ceramic", "Polish & Protect",
         "Single-stage polish with premium paint sealant. Perfect maintenance detail.",
         200, "Flat Rate", "Polish, sealant, dual-action polisher", 3),
        ("Signature Detail Package", "Paint Correction & Ceramic", "Signature Detail Package",
         "The full treatment: interior refresh + exterior polish & protect. Your car, transformed.",
         350, "Flat Rate", "Pol Star, Carpro Perl, polish, sealant", 5),
    ]
    conn = get_db()
    conn.executemany("""
        INSERT OR IGNORE INTO services (name, category, sub_service, description, starting_price, pricing_model, products_used, duration_hours)
        VALUES (?,?,?,?,?,?,?,?)
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


# ── Appointment Operations ───────────────────────────────────────

def create_appointment(customer_id, appointment_date, appointment_time=None,
                       vehicle_id=None, service_id=None, job_address=None,
                       special_requests=None, status='New Lead', payment_link=None):
    conn = get_db()
    conn.execute("""
        INSERT INTO appointments (customer_id, vehicle_id, service_id, appointment_date, appointment_time, job_address, status, special_requests, payment_link)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (customer_id, vehicle_id, service_id, appointment_date, appointment_time, job_address, status, special_requests, payment_link))
    conn.commit()
    appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    row = conn.execute("SELECT id FROM appointments WHERE rowid=?", (appt_id,)).fetchone()
    conn.close()
    return row['id']


def get_appointments(status=None, date_from=None, date_to=None, limit=50):
    conn = get_db()
    query = """
        SELECT a.*, c.full_name, c.phone, c.email,
               v.make||' '||v.model as vehicle_desc,
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
    today = datetime.now().strftime('%Y-%m-%d')
    end = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    rows = conn.execute("""
        SELECT a.*, c.full_name, c.phone, c.email,
               v.make||' '||v.model as vehicle_desc,
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
        VALUES (?,?,?,?,?,datetime('now'),?)
    """, (appointment_id, payment_type, amount, method, status, notes))
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

def create_follow_up(appointment_id, follow_type, scheduled_date, channel='SMS'):
    conn = get_db()
    conn.execute("""
        INSERT INTO follow_ups (appointment_id, follow_type, channel, scheduled_date)
        VALUES (?,?,?,?)
    """, (appointment_id, follow_type, channel, scheduled_date))
    conn.commit()
    conn.close()


def get_pending_follow_ups():
    """Get follow-ups scheduled for today or earlier, not yet sent."""
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
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
    stats = {}
    stats['total_customers'] = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    stats['pending_appointments'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status IN ('New Lead','Quote Sent','Awaiting Deposit','Confirmed')").fetchone()[0]
    stats['completed_today'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE status='Completed' AND appointment_date=date('now')").fetchone()[0]
    stats['upcoming_week'] = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appointment_date BETWEEN date('now') AND date('now','+7 days') AND status IN ('Confirmed','Awaiting Deposit')").fetchone()[0]
    deposits = get_deposit_balance()
    stats['deposits_pending'] = deposits['pending']
    stats['deposits_paid'] = deposits['paid']
    stats['pending_follow_ups'] = conn.execute(
        "SELECT COUNT(*) FROM follow_ups WHERE status='Pending'").fetchone()[0]
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
