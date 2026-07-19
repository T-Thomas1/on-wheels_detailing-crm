#!/usr/bin/env python3
"""On-Wheels Detailing CRM — Zero-dependency HTTP server with API + booking form."""

import os
import sys
import json
import io
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))
from crm import (
    init_db, seed_services,
    create_customer, find_customer, get_customers,
    add_vehicle, get_customer_vehicles,
    get_services,
    create_appointment, get_appointments, update_appointment_status, get_upcoming_appointments,
    add_payment, get_appointment_payments, get_deposit_balance,
    create_follow_up, get_pending_follow_ups, mark_follow_up,
    get_dashboard
)

PORT = int(os.environ.get('PORT', 5050))
STATIC_DIR = Path(__file__).parent / 'static'
TEMPLATES_DIR = Path(__file__).parent / 'templates'
SITE_ROOT = Path(__file__).parent.parent  # repo root — serves index.html, about.html, etc.

# Init DB on startup
init_db()
seed_services()


def json_response(handler, data, status=200):
    """Send JSON response."""
    body = json.dumps(data, default=str).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', len(body))
    handler.end_headers()
    handler.wfile.write(body)


def render_template(name, **context):
    """Render an HTML template with simple {{ var }} substitution."""
    path = TEMPLATES_DIR / name
    if not path.exists():
        return f"<h1>Template not found: {name}</h1>"
    html = path.read_text()

    # Simple template: {{ var }} and {% if %}..{% endif %} and {% for %}..{% endfor %}
    import re

    # {% for item in list %}...{% endfor %}
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

    # {% if var %}...{% endif %}
    def replace_if(match):
        cond = match.group(1).strip()
        block = match.group(2)
        if context.get(cond):
            return block
        return ''

    html = re.sub(r'\{% if (\w+) %\}(.*?)\{% endif %\}', replace_if, html, flags=re.DOTALL)

    # {{ var }} and {{ var.key }}
    def replace_var(match):
        expr = match.group(1).strip()
        if '.' in expr:
            obj, key = expr.split('.', 1)
            val = context.get(obj, {})
            if isinstance(val, dict):
                return str(val.get(key, ''))
            return str(val or '')
        return str(context.get(expr, ''))

    html = re.sub(r'\{\{ ([\w.]+) \}\}', replace_var, html)

    # {{ "format"|filter(var) }} — handle simple format filter
    def replace_filtered(match):
        fmt = match.group(1)
        filter_name = match.group(2)
        var_expr = match.group(3).strip()
        val = context.get(var_expr, 0)
        if filter_name == 'format' and val is not None:
            return fmt % (float(val),)
        return str(val)

    html = re.sub(r'\{\{ "([^"]+)"\|(\w+)\((\w+)\) \}\}', replace_filtered, html)

    return html


class CRMHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the CRM."""

    def log_message(self, format, *args):
        """Suppress default logging noise."""
        pass

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            self.serve_site_file('/index.html')
        elif path == '/book':
            self.serve_html('booking.html')
        elif path == '/dashboard':
            stats = get_dashboard()
            appointments = get_upcoming_appointments(days=14)
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
                    'id': s['id'],
                    'name': s['name'],
                    'sub_service': s['sub_service'],
                    'description': s['description'],
                    'starting_price': s['starting_price'],
                    'pricing_model': s['pricing_model'],
                    'products_used': s['products_used'],
                    'duration_hours': s['duration_hours'],
                })
            json_response(self, {'services': categorized})
        elif path == '/api/dashboard':
            json_response(self, get_dashboard())
        elif path == '/api/appointments':
            qs = parse_qs(urlparse(self.path).query)
            status = qs.get('status', [None])[0]
            days = int(qs.get('days', ['7'])[0])
            date_from = qs.get('from', [datetime.now().strftime('%Y-%m-%d')])[0]
            date_to = qs.get('to', [(datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')])[0]
            appointments = get_appointments(status=status, date_from=date_from, date_to=date_to)
            json_response(self, {'appointments': appointments})
        elif path.startswith('/static/'):
            filename = path[len('/static/'):]
            filepath = STATIC_DIR / filename
            if filepath.exists():
                content_type = 'text/css' if filename.endswith('.css') else 'application/octet-stream'
                body = filepath.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        else:
            # Serve website static files (index.html, about.html, css/, js/, images/, fonts/)
            self.serve_site_file(path)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/book':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                json_response(self, {'error': 'Invalid JSON'}, 400)
                return

            name = (data.get('name') or '').strip()
            phone = (data.get('phone') or '').strip()
            email = (data.get('email') or '').strip()
            if not name or not phone:
                json_response(self, {'error': 'Name and phone are required.'}, 400)
                return

            existing = find_customer(phone=phone)
            if existing:
                customer_id = existing[0]['id']
            else:
                customer_id = create_customer(
                    full_name=name, phone=phone, email=email or None,
                    address=data.get('address') or None,
                    city=data.get('city') or None,
                    state=data.get('state') or None,
                    zip_code=data.get('zip') or None,
                    location=data.get('location') or None,
                    source=data.get('source', 'Website'),
                )

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

            appointment_id = create_appointment(
                customer_id=customer_id,
                appointment_date=data.get('preferred_date', datetime.now().strftime('%Y-%m-%d')),
                appointment_time=data.get('preferred_time') or None,
                vehicle_id=vehicle_id,
                service_id=data.get('service_id') or None,
                job_address=data.get('job_address') or None,
                special_requests=data.get('special_requests') or None,
                status='New Lead',
            )

            today = datetime.now().strftime('%Y-%m-%d')
            create_follow_up(appointment_id, 'Booking Confirmation', today, 'SMS')

            json_response(self, {
                'success': True,
                'message': "Thanks for reaching out! TaSain will text you shortly to confirm your appointment. You are in good hands.",
                'appointment_id': appointment_id,
            }, 201)

        elif path.startswith('/api/appointments/') and path.endswith('/status'):
            # PATCH /api/appointments/<id>/status
            appointment_id = path.split('/')[3]
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                json_response(self, {'error': 'Invalid JSON'}, 400)
                return

            new_status = data.get('status')
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

            json_response(self, {'success': True, 'status': new_status})

        else:
            self.send_error(404)

    def serve_site_file(self, path):
        """Serve a static file from the website root (index.html, css/, js/, etc.)."""
        # Strip leading slash and map to filesystem
        rel = path.lstrip('/')
        if not rel:
            rel = 'index.html'
        if rel.endswith('/'):
            rel += 'index.html'

        # Also try .html extension
        candidates = [SITE_ROOT / rel]
        if '.' not in rel.split('/')[-1]:
            candidates.append(SITE_ROOT / f'{rel}.html')

        for filepath in candidates:
            if filepath.exists() and filepath.is_file():
                # Security: only serve files within SITE_ROOT
                try:
                    filepath.resolve().relative_to(SITE_ROOT.resolve())
                except ValueError:
                    self.send_error(403)
                    return

                ext = filepath.suffix.lower()
                content_types = {
                    '.html': 'text/html; charset=utf-8',
                    '.css': 'text/css',
                    '.js': 'application/javascript',
                    '.json': 'application/json',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.svg': 'image/svg+xml',
                    '.ico': 'image/x-icon',
                    '.xml': 'application/xml',
                    '.txt': 'text/plain',
                    '.woff': 'font/woff',
                    '.woff2': 'font/woff2',
                    '.ttf': 'font/ttf',
                }
                content_type = content_types.get(ext, 'application/octet-stream')
                body = filepath.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
                return

        self.send_error(404)

    def serve_html(self, filename):
        """Serve an HTML template file."""
        html = render_template(filename)
        self.serve_html_string(html)

    def serve_html_string(self, html):
        """Serve HTML string."""
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), CRMHandler)
    print(f"\n  On-Wheels Detailing CRM — http://localhost:{PORT}")
    print(f"  Booking form:     http://localhost:{PORT}/")
    print(f"  Dashboard:        http://localhost:{PORT}/dashboard")
    print(f"  API:              http://localhost:{PORT}/api/dashboard\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
