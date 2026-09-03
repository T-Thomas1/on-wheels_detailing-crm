#!/usr/bin/env python3
"""On-Wheels Detailing CRM — Zero-dependency HTTP server with API + booking form.

Security: API-key gated (X-API-Key header), dual-tier (read/write), PII redaction,
          input sanitization, audit logging, rate-limit hints via Nginx.
"""
import os
import sys
import json
import re
import io
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))
from crm import (
    init_db, seed_services, seed_expansion_services, seed_rv_detailing,
    create_customer, find_customer, get_customers,
    add_vehicle, get_customer_vehicles,
    get_services, get_service_deposit,
    create_appointment, get_appointments, update_appointment_status, get_upcoming_appointments,
    add_payment, get_appointment_payments, get_deposit_balance,
    create_follow_up, get_pending_follow_ups, mark_follow_up,
    get_dashboard,
    now, today_str, now_str,
    get_tz_for, tz_display_label, tz_offset_label, LOCATION_TIMEZONES,
    classify_vehicle_size, get_service_tier_price, get_vehicle_size_short,
)

PORT = int(os.environ.get('PORT', 5050))
STATIC_DIR = Path(__file__).parent / 'static'
TEMPLATES_DIR = Path(__file__).parent / 'templates'

# ═══════════════════════════════════════════════════════════════
#  SECURITY CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# API keys (loaded from environment ONLY — no hardcoded defaults)
# Set via /opt/onwheels/crm/.env or systemd EnvironmentFile
API_KEY = os.environ.get('ONWHEELS_API_KEY', '')
ADMIN_KEY = os.environ.get('ONWHEELS_ADMIN_KEY', '')

# Validate on startup
if not API_KEY or not ADMIN_KEY:
    print("ERROR: ONWHEELS_API_KEY and ONWHEELS_ADMIN_KEY must be set in environment.")
    print("Create /opt/onwheels/crm/.env with:")
    print("  ONWHEELS_API_KEY=<your-read-key>")
    print("  ONWHEELS_ADMIN_KEY=<your-admin-key>")
    sys.exit(1)

# Rate limiting (simple in-memory — Nginx handles the heavy lifting)
_RATE_LIMITS = {}  # {ip: [timestamps]}
RATE_LIMIT_WINDOW = 60       # seconds
RATE_LIMIT_MAX = 30          # requests per window (generous for normal use)
BOOK_RATE_LIMIT_MAX = 5      # booking submissions per window

# CORS — allow the marketing site + dev origins only (never '*')
CORS_ALLOWED_ORIGINS = {
    'https://www.onwheelsdetailing.com',
    'https://onwheelsdetailing.com',
    'http://localhost:4321',
    'http://127.0.0.1:4321',
}

# Sensitive field names to strip from public API responses
PII_REDACT_FIELDS = {'email', 'payment_link'}
PHONE_REDACT_LENGTH = 4  # show last 4 digits only

# Audit log
AUDIT_LOG_PATH = Path(__file__).parent / 'audit.log'

# Public endpoints (no API key required)
PUBLIC_PATHS = {'/', '/book', '/api/book', '/api/services', '/static/'}

# Init DB on startup
_db = init_db()
seed_services()
seed_expansion_services()
seed_rv_detailing()

from crm import get_db
conn = get_db()
conn.execute("UPDATE services SET deposit_amount=50 WHERE name LIKE '%Polish & Protect%' AND deposit_amount IS NULL")
conn.commit()
conn.close()


# Location constants
MOBILE_LOCATIONS = {'Texas - Harris County', 'Michigan - St. Clair', 'Michigan - Metro Detroit'}

# Map booking form location values to DB constraint values
# The customers table CHECK constraint expects these specific values
LOCATION_DB_MAP = {
    'Michigan - Marysville (Shop)': 'Shop - Marysville, MI',
    'Michigan - New Haven (Shop)': 'Shop - New Haven, MI',
    'Michigan - St. Clair': 'Michigan - Metro Detroit',
}

VALID_BUSINESS_DAYS = {3, 5, 6}  # Python weekday(): 3=Thu, 5=Sat, 6=Sun


# ═══════════════════════════════════════════════════════════════
#  SECURITY UTILITIES
# ═══════════════════════════════════════════════════════════════

def constant_time_compare(a: str, b: str) -> bool:
    """Timing-attack-safe string comparison."""
    return hmac.compare_digest(a.encode(), b.encode())


def cors_origin(handler) -> str:
    """Return the request Origin if allowed, else '' (no CORS header sent)."""
    origin = handler.headers.get('Origin', '')
    if origin in CORS_ALLOWED_ORIGINS or origin.endswith('.pages.dev'):
        return origin
    return ''


def audit_log(event: str, ip: str, path: str = '', detail: str = ''):
    """Write to audit log with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {event:12s} | ip={ip:15s} | {path}"
    if detail:
        line += f" | {detail}"
    try:
        with open(AUDIT_LOG_PATH, 'a') as f:
            f.write(line + '\n')
    except Exception:
        pass  # Never crash on logging failure


def redact_pii(appointment: dict) -> dict:
    """Remove PII and redact sensitive fields for public API responses."""
    safe = {}
    for k, v in appointment.items():
        if k in PII_REDACT_FIELDS:
            continue
        if k == 'phone' and v:
            # Redact: show only last N digits
            clean = ''.join(c for c in str(v) if c.isdigit())
            if len(clean) > PHONE_REDACT_LENGTH:
                safe[k] = '*' * (len(clean) - PHONE_REDACT_LENGTH) + clean[-PHONE_REDACT_LENGTH:]
            else:
                safe[k] = v
        else:
            safe[k] = v
    return safe


def redact_pii_list(appointments: list) -> list:
    return [redact_pii(a) for a in appointments]


def sanitize_input(value: str, max_length: int = 200) -> str:
    """Strip, truncate, and remove control characters."""
    if not value:
        return ''
    return value.strip()[:max_length]


def check_rate_limit(ip: str, max_requests: int = RATE_LIMIT_MAX) -> bool:
    """Simple in-memory rate limiter. Returns True if allowed."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    if ip not in _RATE_LIMITS:
        _RATE_LIMITS[ip] = []
    # Clean old entries
    _RATE_LIMITS[ip] = [t for t in _RATE_LIMITS[ip] if t > window_start]
    if len(_RATE_LIMITS[ip]) >= max_requests:
        return False
    _RATE_LIMITS[ip].append(now)
    return True


def json_response(handler, data, status=200):
    """Send JSON response."""
    body = json.dumps(data, default=str).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', len(body))
    handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('X-XSS-Protection', '1; mode=block')
    handler.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
    origin = cors_origin(handler)
    if origin:
        handler.send_header('Access-Control-Allow-Origin', origin)
        handler.send_header('Vary', 'Origin')
    handler.end_headers()
    handler.wfile.write(body)


def render_template(name, **context):
    """Render an HTML template with simple {{ var }} substitution."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        return f"<h1>Template not found: {name}</h1>"
    html = path.read_text()

    def replace_for(match):
        var = match.group(1).strip()
        list_name = match.group(2).strip()
        block = match.group(3)
        items = context.get(list_name, [])
        result = []
        for item in items:
            item_html = block
            if isinstance(item, dict):
                for k, v in item.items():
                    item_html = item_html.replace('{{ ' + var + '.' + k + ' }}', str(v or ''))
            else:
                item_html = item_html.replace('{{ ' + var + ' }}', str(item or ''))
            result.append(item_html)
        return ''.join(result)

    html = re.sub(r'\{% for (\w+) in (\w+) %\}(.*?)\{% endfor %\}', replace_for, html, flags=re.DOTALL)

    def replace_if(match):
        cond = match.group(1).strip()
        block = match.group(2)
        return block if context.get(cond) else ''

    html = re.sub(r'\{% if (\w+) %\}(.*?)\{% endif %\}', replace_if, html, flags=re.DOTALL)

    def replace_var(match):
        expr = match.group(1).strip()
        if '.' in expr:
            obj, key = expr.split('.', 1)
            val = context.get(obj, {})
            return str(val.get(key, '')) if isinstance(val, dict) else str(val or '')
        return str(context.get(expr, ''))

    html = re.sub(r'\{\{ ([\w.]+) \}\}', replace_var, html)

    def replace_filtered(match):
        fmt = match.group(1)
        filter_name = match.group(2)
        var_expr = match.group(3).strip()
        val = context.get(var_expr, 0)
        return fmt % (float(val),) if filter_name == 'format' and val is not None else str(val)

    html = re.sub(r'\{\{ "([^"]+)"\|(\w+)\((\w+)\) \}\}', replace_filtered, html)
    return html


# ═══════════════════════════════════════════════════════════════
#  HTTP HANDLER
# ═══════════════════════════════════════════════════════════════

class CRMHandler(BaseHTTPRequestHandler):

    def _client_ip(self) -> str:
        """Extract client IP, respecting X-Forwarded-For from Nginx."""
        forwarded = self.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return self.client_address[0]

    def _is_public_path(self) -> bool:
        path = urlparse(self.path).path
        for pub in PUBLIC_PATHS:
            if path == pub:
                return True
            # Prefix match only for directory-style paths (e.g. /static/)
            if pub.endswith('/') and pub != '/' and path.startswith(pub):
                return True
        return False

    def _authenticate(self) -> str | None:
        """
        Validate API key from X-API-Key header.
        Returns 'read', 'admin', or None (failed).
        Public paths skip auth.
        """
        if self._is_public_path():
            return 'public'

        api_key = self.headers.get('X-API-Key', '').strip()
        if not api_key:
            return None

        if constant_time_compare(api_key, ADMIN_KEY):
            return 'admin'
        if constant_time_compare(api_key, API_KEY):
            return 'read'
        return None

    def _require_auth(self, min_level: str = 'read') -> bool:
        """Check auth and send 401 if insufficient. Returns True if authorized."""
        level = self._authenticate()
        if level is None:
            json_response(self, {'error': 'Unauthorized — valid X-API-Key header required'}, 401)
            audit_log('AUTH_FAIL', self._client_ip(), self.path, 'no key')
            return False

        if min_level == 'admin' and level != 'admin':
            json_response(self, {'error': 'Forbidden — admin key required for this operation'}, 403)
            audit_log('AUTH_DENIED', self._client_ip(), self.path, f'level={level}, need=admin')
            return False

        audit_log('AUTH_OK', self._client_ip(), self.path, f'level={level}')
        return True

    def _rate_limit_check(self, book_mode: bool = False) -> bool:
        """Check rate limits. Returns True if allowed."""
        ip = self._client_ip()
        max_req = BOOK_RATE_LIMIT_MAX if book_mode else RATE_LIMIT_MAX
        if not check_rate_limit(ip, max_req):
            json_response(self, {'error': 'Rate limit exceeded. Please slow down.'}, 429)
            audit_log('RATE_LIMIT', ip, self.path)
            return False
        return True

    def log_message(self, format, *args):
        """Suppress default logging — we use audit_log instead."""
        pass

    def do_HEAD(self):
        """Support HEAD requests (Google Search Console URL inspection)."""
        self.do_GET()

    def do_OPTIONS(self):
        """CORS preflight for cross-origin booking requests."""
        origin = cors_origin(self)
        if origin:
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-API-Key')
            self.send_header('Access-Control-Max-Age', '86400')
            self.send_header('Vary', 'Origin')
        else:
            self.send_response(403)
        self.end_headers()

    # ── GET ────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/' or path == '/book':
            self.serve_html('booking.html')

        elif path == '/dashboard':
            if not self._require_auth('read'):
                return
            stats = get_dashboard()
            appointments = get_upcoming_appointments(days=14)
            for a in appointments:
                if a.get('deposit_agreed_at'):
                    a['deposit_status'] = a['deposit_agreed_at'][:10]
                elif a.get('payment_link'):
                    a['deposit_status'] = 'Pending'
                else:
                    a['deposit_status'] = '--'
            html = render_template('dashboard.html', stats=stats, appointments=appointments)
            self.serve_html_string(html)

        elif path == '/api/services':
            services = get_services()
            categorized = {}
            for s in services:
                cat = s['category']
                if cat not in categorized:
                    categorized[cat] = []
                categorized[cat].append({
                    'id': s['id'], 'name': s['name'],
                    'sub_service': s['sub_service'],
                    'description': s['description'],
                    'starting_price': s['starting_price'],
                    'pricing_model': s['pricing_model'],
                    'duration_hours': s['duration_hours'],
                    'deposit_amount': s['deposit_amount'],
                })
            json_response(self, {'services': categorized})

        elif path == '/api/dashboard':
            if not self._require_auth('read'):
                return
            json_response(self, get_dashboard())

        elif path == '/api/appointments':
            if not self._require_auth('read'):
                return
            qs = parse_qs(urlparse(self.path).query)
            status = qs.get('status', [None])[0]
            days = int(qs.get('days', ['7'])[0])
            date_from = qs.get('from', [datetime.now().strftime('%Y-%m-%d')])[0]
            date_to = qs.get('to', [(datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')])[0]
            appointments = get_appointments(status=status, date_from=date_from, date_to=date_to)
            # Redact PII from API responses
            appointments = redact_pii_list(appointments)
            json_response(self, {'appointments': appointments})

        elif path.startswith('/static/'):
            filename = path[len('/static/'):]
            # Prevent path traversal
            if '..' in filename or filename.startswith('/'):
                self.send_error(403)
                return
            filepath = STATIC_DIR / filename
            if filepath.exists() and filepath.is_file():
                content_type = 'text/css' if filename.endswith('.css') else 'application/octet-stream'
                body = filepath.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', len(body))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    # ── POST ───────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/book':
            # Public endpoint — but rate-limited
            if not self._rate_limit_check(book_mode=True):
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 10_000:  # 10KB max
                json_response(self, {'error': 'Request too large'}, 413)
                return

            try:
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    json_response(self, {'error': 'Invalid JSON'}, 400)
                    audit_log('BOOK_FAIL', self._client_ip(), path, 'invalid JSON')
                    return
    
                # Sanitize inputs
                name = sanitize_input(data.get('name', ''), 100)
                phone = sanitize_input(data.get('phone', ''), 20)
                email = sanitize_input(data.get('email', ''), 100)
                special_requests = sanitize_input(data.get('special_requests', ''), 500)
    
                if not name or not phone:
                    json_response(self, {'error': 'Name and phone are required.'}, 400)
                    return
    
                # Validate phone contains mostly digits
                phone_digits = ''.join(c for c in phone if c.isdigit())
                if len(phone_digits) < 10:
                    json_response(self, {'error': 'Please provide a valid phone number.'}, 400)
                    return
    
                # Validate preferred date is Thu, Sat, or Sun
                preferred_date = data.get('preferred_date', '')
                if preferred_date:
                    try:
                        dt = datetime.strptime(preferred_date, '%Y-%m-%d')
                        if dt.weekday() not in VALID_BUSINESS_DAYS:
                            json_response(self, {'error': 'We are only open Thursday, Saturday, and Sunday. Please select one of those days.'}, 400)
                            audit_log('BOOK_FAIL', self._client_ip(), path, f'bad day: {preferred_date} (weekday={dt.weekday()})')
                            return
                    except ValueError:
                        json_response(self, {'error': 'Invalid date format.'}, 400)
                        return
    
                # Require a package (service) to be selected
                service_id = data.get('service_id')
                if not service_id:
                    json_response(self, {'error': 'Please select a package to continue.'}, 400)
                    audit_log('BOOK_FAIL', self._client_ip(), path, 'no service selected')
                    return

                location_raw = sanitize_input(data.get('location', ''), 100)
                location_db = LOCATION_DB_MAP.get(location_raw, location_raw)
    
                # ── Single-connection transaction boundary ──
                conn = get_db()
                conn.execute('BEGIN IMMEDIATE')
    
                existing = find_customer(phone=phone, conn=conn)
                if existing:
                    customer_id = existing[0]['id']
                else:
                    customer_id = create_customer(
                        full_name=name, phone=phone, email=email or None,
                        address=sanitize_input(data.get('address', ''), 200),
                        city=sanitize_input(data.get('city', ''), 100),
                        state=sanitize_input(data.get('state', ''), 50),
                        zip_code=sanitize_input(data.get('zip', ''), 20),
                        location=location_db,
                        source=sanitize_input(data.get('source', 'Website'), 50),
                        conn=conn,
                    )
    
                vehicle_id = None
                vehicle_size = None
                if data.get('vehicle_type'):
                    raw_type = sanitize_input(data.get('vehicle_type', ''), 50)
                    vehicle_size = classify_vehicle_size(raw_type)
                    add_vehicle(
                        customer_id=customer_id,
                        vehicle_type=raw_type,
                        make=sanitize_input(data.get('vehicle_make', ''), 50),
                        model=sanitize_input(data.get('vehicle_model', ''), 50),
                        year=data.get('vehicle_year'),
                        color=sanitize_input(data.get('vehicle_color', ''), 30),
                        license_plate=sanitize_input(data.get('license_plate', ''), 20),
                        vehicle_size=vehicle_size,
                        conn=conn,
                    )
                    vehicles = get_customer_vehicles(customer_id, conn=conn)
                    if vehicles:
                        vehicle_id = vehicles[0]['id']
    
                payment_link = None
                deposit_agreed_at = None
                deposit_agreed = data.get('deposit_agreed') in (True, 'true', 'on', '1')
    
                if service_id:
                    deposit_amount, link = get_service_deposit(service_id, conn=conn)
                    if deposit_amount and deposit_agreed:
                        payment_link = link
                        deposit_agreed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
                appointment_id = create_appointment(
                    customer_id=customer_id,
                    appointment_date=data.get('preferred_date', datetime.now().strftime('%Y-%m-%d')),
                    appointment_time=data.get('preferred_time') or None,
                    vehicle_id=vehicle_id,
                    service_id=service_id,
                    job_address=sanitize_input(data.get('job_address', ''), 200),
                    special_requests=special_requests or None,
                    status='New Lead',
                    payment_link=payment_link,
                    deposit_agreed_at=deposit_agreed_at,
                    conn=conn,
                )
    
                today = datetime.now().strftime('%Y-%m-%d')
                create_follow_up(appointment_id, 'Booking Confirmation', today, 'SMS', conn=conn)
    
                conn.commit()
                conn.close()
    
                # Build confirmation message with mobile fee note if applicable
                is_mobile = data.get('location', '') in MOBILE_LOCATIONS
                if is_mobile:
                    confirm_msg = "Thanks for reaching out! TaSain will text you shortly to confirm your appointment. \u26a0\ufe0f A $25 mobile service fee applies."
                else:
                    confirm_msg = "Thanks for reaching out! TaSain will text you shortly to confirm your appointment."
    
                audit_log('BOOK_OK', self._client_ip(), path, f'customer={name}, appt={appointment_id[:8]}')
                json_response(self, {
                    'success': True,
                    'message': confirm_msg,
                    'appointment_id': appointment_id,
                }, 201)
            except Exception as e:
                try:
                    conn.rollback()
                except:
                    pass
                try:
                    conn.close()
                except:
                    pass
                audit_log('BOOK_FAIL', self._client_ip(), path, 'DB error: ' + str(e))
                json_response(self, {
                    'success': False,
                    'error': 'Booking temporarily unavailable. Please try again or call (586) 873-0656.'
                }, 503)


        elif path.startswith('/api/appointments/') and path.endswith('/status'):
            # Requires ADMIN key
            if not self._require_auth('admin'):
                return

            appointment_id = path.split('/')[3]
            # Validate appointment_id is alphanumeric
            if not re.match(r'^[a-f0-9]{32}$', appointment_id):
                json_response(self, {'error': 'Invalid appointment ID'}, 400)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                json_response(self, {'error': 'Invalid JSON'}, 400)
                return

            new_status = sanitize_input(data.get('status', ''), 50)
            if not new_status:
                json_response(self, {'error': 'status is required'}, 400)
                return

            update_appointment_status(appointment_id, new_status)
            if new_status == 'Confirmed':
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                create_follow_up(appointment_id, '24hr Reminder', tomorrow, 'SMS')
            elif new_status == 'Completed':
                check_in = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
                create_follow_up(appointment_id, 'Post-Service Check-in', check_in, 'SMS')

            audit_log('STATUS_CHG', self._client_ip(), path,
                      f'appt={appointment_id[:8]}, status={new_status}')
            json_response(self, {'success': True, 'status': new_status})

        else:
            self.send_error(404)

    def serve_html(self, filename):
        html = render_template(filename)
        self.serve_html_string(html)

    def serve_html_string(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Cache-Control', 'no-cache, must-revalidate')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('0.0.0.0', PORT), CRMHandler)
    print(f"\n  On-Wheels Detailing CRM — http://localhost:{PORT}")
    print(f"  Booking form:     http://localhost:{PORT}/")
    print(f"  Dashboard:        http://localhost:{PORT}/dashboard")
    print(f"  API:              http://localhost:{PORT}/api/dashboard")
    print(f"  Security:         API-key gated (X-API-Key header)")
    print(f"  Audit log:        {AUDIT_LOG_PATH}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
