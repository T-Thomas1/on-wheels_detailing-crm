#!/bin/bash
# On-Wheels Detailing — Local Dev Server
# Starts the full stack: website + CRM booking + API on port 5050
# Usage: ./start.sh

cd "$(dirname "$0")/crm"
echo "Starting On-Wheels Detailing — Full Stack"
echo ""
echo "  Website:    http://localhost:5050"
echo "  Book Now:   http://localhost:5050/book"
echo "  Dashboard:  http://localhost:5050/dashboard"
echo "  API:        http://localhost:5050/api/dashboard"
echo ""
echo "  Press Ctrl+C to stop"
echo ""
python3 server.py
