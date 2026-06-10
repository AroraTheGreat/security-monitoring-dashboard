"""
Security-Instrumented Flask Application
Exposes Prometheus metrics simulating a real security monitoring scenario:
- Failed login tracking (brute-force detection signal)
- Suspicious request detection (anomalous patterns)
- Active session count
- Request latency histogram
"""

import time
import random
import threading
from flask import Flask, jsonify, request
from prometheus_client import (
    Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

# ── Prometheus Metrics ──────────────────────────────────────────────────────

# Counts total HTTP requests by method, endpoint, and status
REQUEST_COUNT = Counter(
    'security_app_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Tracks failed login attempts (key signal for brute-force alerts)
FAILED_LOGINS = Counter(
    'security_app_failed_logins_total',
    'Total failed login attempts'
)

# Tracks requests flagged as suspicious (unexpected patterns)
SUSPICIOUS_REQUESTS = Counter(
    'security_app_suspicious_requests_total',
    'Total suspicious requests detected'
)

# Tracks currently active user sessions
ACTIVE_SESSIONS = Gauge(
    'security_app_active_sessions',
    'Number of currently active sessions'
)

# Measures request processing latency
REQUEST_LATENCY = Histogram(
    'security_app_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)

# ── Background Simulation ───────────────────────────────────────────────────

def simulate_security_events():
    """
    Simulates realistic security events in the background.
    In a real deployment, these would come from actual user activity.
    """
    while True:
        # Simulate normal traffic
        REQUEST_COUNT.labels(method='GET', endpoint='/dashboard', status='200').inc(random.randint(1, 5))

        # Simulate occasional failed logins (some bursts to trigger alerts)
        failed = random.choices([0, 1, 2, 5], weights=[60, 25, 10, 5])[0]
        if failed:
            FAILED_LOGINS.inc(failed)
            REQUEST_COUNT.labels(method='POST', endpoint='/login', status='401').inc(failed)

        # Simulate occasional suspicious requests
        if random.random() < 0.1:
            SUSPICIOUS_REQUESTS.inc(random.randint(1, 3))

        # Fluctuate active sessions realistically
        ACTIVE_SESSIONS.set(random.randint(10, 80))

        time.sleep(5)

# Start simulation in background thread
thread = threading.Thread(target=simulate_security_events, daemon=True)
thread.start()

# ── Routes ──────────────────────────────────────────────────────────────────

@app.route('/metrics')
def metrics():
    """Prometheus scrapes this endpoint every 15 seconds."""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health():
    """Health check endpoint — used by Prometheus 'up' metric."""
    return jsonify({"status": "healthy", "service": "security-app"}), 200

@app.route('/login', methods=['POST'])
def login():
    """Simulates a login endpoint with auth checking."""
    start = time.time()
    data = request.get_json(silent=True) or {}
    username = data.get('username', '')
    password = data.get('password', '')

    # Flag suspiciously short or malformed inputs
    if len(username) < 2 or len(password) < 4:
        SUSPICIOUS_REQUESTS.inc()
        REQUEST_COUNT.labels(method='POST', endpoint='/login', status='400').inc()
        REQUEST_LATENCY.labels(endpoint='/login').observe(time.time() - start)
        return jsonify({"error": "Invalid input"}), 400

    # Simulate auth (90% fail rate to demonstrate monitoring)
    if random.random() < 0.9:
        FAILED_LOGINS.inc()
        REQUEST_COUNT.labels(method='POST', endpoint='/login', status='401').inc()
        REQUEST_LATENCY.labels(endpoint='/login').observe(time.time() - start)
        return jsonify({"error": "Invalid credentials"}), 401

    ACTIVE_SESSIONS.inc()
    REQUEST_COUNT.labels(method='POST', endpoint='/login', status='200').inc()
    REQUEST_LATENCY.labels(endpoint='/login').observe(time.time() - start)
    return jsonify({"message": "Login successful"}), 200

@app.route('/dashboard')
def dashboard():
    """Protected dashboard endpoint."""
    start = time.time()
    time.sleep(random.uniform(0.01, 0.1))  # Simulate processing time
    REQUEST_COUNT.labels(method='GET', endpoint='/dashboard', status='200').inc()
    REQUEST_LATENCY.labels(endpoint='/dashboard').observe(time.time() - start)
    return jsonify({
        "active_sessions": int(ACTIVE_SESSIONS._value.get()),
        "message": "Dashboard data"
    }), 200

@app.route('/simulate/attack')
def simulate_attack():
    """
    Triggers a burst of failed logins to test alert pipeline.
    Visit http://localhost:5000/simulate/attack to fire the brute-force alert.
    """
    burst = 20
    FAILED_LOGINS.inc(burst)
    SUSPICIOUS_REQUESTS.inc(burst)
    REQUEST_COUNT.labels(method='GET', endpoint='/simulate/attack', status='200').inc()
    return jsonify({
        "message": f"Simulated {burst} failed logins and suspicious requests",
        "tip": "Check Prometheus alerts at http://localhost:9090/alerts"
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)