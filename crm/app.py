#!/usr/bin/env python3
"""On-Wheels Detailing — Flask API backend & booking form server."""

import os
import sys
import json
from datetime import timedelta
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory

# Add parent to path so we can import crm
sys.path.insert(0, str(Path(__file__).parent))
from crm import (
    init_db, seed_services,
    create_customer, find_customer, get_customers,
    add_vehicle, get_customer_vehicles,
    get_services, get_service_deposit,
    create_appointment, get_appointments, update_appointment_status, get_upcoming_appointments,
    add_payment, get_appointment_payments, get_deposit_balance,
    create_follow_up, get_pending_follow_ups, mark_follow_up,
    get_dashboard,
    now, today_str, now_str,
)

app = Flask(__name__)

# ── Initialize DB on startup ─────────────────────────────────────
with app.app_context():
    init_db()
    seed_services()

# ── API: Service Catalog ─────────────────────────────────────────

@app.route('/api/services')
def api_services():
    """Return full service catalog with 'starting at' pricing."""
    services = get_services()
    # Group by category for the frontend
    categorized = {}
    for s in services:
        cat = s['category']
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append({
            'id': s['id'],
            'name': s['name'],
            'sub_service': s['sub_service'],
            'description': s['description'],
            'starting_price': s['starting_price'],
            'pricing_model': s['pricing_model'],
            'products_used': s['products_used'],
            'duration_hours': s['duration_hours'],
        })
    return jsonify({'services': categorized})


# ── API: Book Appointment ────────────────────────────────────────

@app.route('/api/book', methods=['POST'])
def api_book():
    """Customer books an appointment through the intake form."""
    data = request.get_json() or {}

    # Validate required fields
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').strip()
    if not name or not phone:
        return jsonify({'error': 'Name and phone are required.'}), 400

    # ── Customer: find existing or create ─────────────────────
    existing = find_customer(phone=phone)
    if existing:
        customer_id = existing[0]['id']
    else:
        customer_id = create_customer(
            full_name=name,
            phone=phone,
            email=email or None,
            address=data.get('address') or None,
            city=data.get('city') or None,
            state=data.get('state') or None,
            zip_code=data.get('zip') or None,
            location=data.get('location') or None,
            source=data.get('source', 'Website'),
        )

    # ── Vehicle ───────────────────────────────────────────────
    vehicle_id = None
    if data.get('vehicle_type'):
        add_vehicle(
            customer_id=customer_id,
            vehicle_type=data.get('vehicle_type'),
            make=data.get('vehicle_make') or None,
            model=data.get('vehicle_model') or None,
            year=data.get('vehicle_year') or None,
            color=data.get('vehicle_color') or None,
            license_plate=data.get('license_plate') or None,
        )
        vehicles = get_customer_vehicles(customer_id)
        if vehicles:
            vehicle_id = vehicles[0]['id']

    # ── Deposit logic ──
    payment_link = None
    deposit_agreed_at = None
    service_id = data.get('service_id')
    deposit_agreed = data.get('deposit_agreed') in (True, 'true', 'on', '1')

    if service_id:
        deposit_amount, link = get_service_deposit(service_id)
        if deposit_amount and deposit_agreed:
            payment_link = link
            deposit_agreed_at = now_str()

    # ── Appointment ───────────────────────────────────────────
    appointment_id = create_appointment(
        customer_id=customer_id,
        appointment_date=data.get('preferred_date', today_str()),
        appointment_time=data.get('preferred_time') or None,
        vehicle_id=vehicle_id,
        service_id=service_id,
        job_address=data.get('job_address') or None,
        special_requests=data.get('special_requests') or None,
        status='New Lead',
        payment_link=payment_link,
        deposit_agreed_at=deposit_agreed_at,
    )

    # ── Auto-schedule follow-ups ──────────────────────────────
    today = today_str()
    # Booking confirmation - same day
    create_follow_up(appointment_id, 'Booking Confirmation', today, 'SMS')

    return jsonify({
        'success': True,
        'message': "Thanks for reaching out! TaSain will text you shortly to confirm your appointment. You're in good hands.",
        'appointment_id': appointment_id,
        'customer_id': customer_id,
    }), 201


# ── API: Dashboard (internal) ────────────────────────────────────

@app.route('/api/dashboard')
def api_dashboard():
    """Dashboard stats for the business owner."""
    return jsonify(get_dashboard())


@app.route('/api/appointments')
def api_appointments():
    """List upcoming appointments."""
    status = request.args.get('status')
    days = int(request.args.get('days', 7))
    date_from = request.args.get('from', today_str())
    date_to = request.args.get('to', (now() + timedelta(days=days)).strftime('%Y-%m-%d'))
    appointments = get_appointments(status=status, date_from=date_from, date_to=date_to)
    return jsonify({'appointments': appointments})


@app.route('/api/appointments/<appointment_id>/status', methods=['PATCH'])
def api_update_status(appointment_id):
    """Update appointment status and auto-schedule follow-ups."""
    data = request.get_json() or {}
    new_status = data.get('status')
    if not new_status:
        return jsonify({'error': 'status is required'}), 400

    update_appointment_status(appointment_id, new_status)

    # Auto-schedule follow-ups based on status change
    if new_status == 'Confirmed':
        # Schedule 24hr reminder
        tomorrow = (now() + timedelta(days=1)).strftime('%Y-%m-%d')
        create_follow_up(appointment_id, '24hr Reminder', tomorrow, 'SMS')
    elif new_status == 'Completed':
        # Schedule post-service check-in (2 days after)
        check_in = (now() + timedelta(days=2)).strftime('%Y-%m-%d')
        create_follow_up(appointment_id, 'Post-Service Check-in', check_in, 'SMS')

    return jsonify({'success': True, 'status': new_status})


# ── Booking Form (customer-facing) ───────────────────────────────

@app.route('/')
def booking_form():
    """The customer-facing booking intake form."""
    return render_template('booking.html')


@app.route('/dashboard')
def dashboard_page():
    """Simple business dashboard."""
    stats = get_dashboard()
    appointments = get_upcoming_appointments(days=14)
    return render_template('dashboard.html', stats=stats, appointments=appointments)


# ── Static files ─────────────────────────────────────────────────

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# ── Run ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f"\n  On-Wheels Detailing CRM — http://localhost:{port}")
    print(f"  Booking form:     http://localhost:{port}/")
    print(f"  Dashboard:        http://localhost:{port}/dashboard\n")
    app.run(host='0.0.0.0', port=port, debug=True)
