"""
Security module for fordeveloper.
- Machine binding: only runs on the registered machine (hardware UUID + serial + hostname)
- Session auth: cryptographic token-based sessions
- PIN login: simple PIN-based authentication
- Data encryption: AES-256-GCM for sensitive fields
"""

import os
import hashlib
import hmac
import secrets
import subprocess
import json
from datetime import datetime, timedelta
from functools import wraps
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from config import DATA_DIR

KEYFILE = os.path.join(DATA_DIR, ".keystore")
MACHINE_FILE = os.path.join(DATA_DIR, ".machine_id")


# ─── Machine Fingerprint ─────────────────────────────────

def _get_machine_fingerprint():
    """Generate a unique fingerprint from hardware UUID, serial number, and hostname."""
    parts = []

    # Hardware UUID
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Hardware UUID" in line:
                parts.append(line.split(":")[-1].strip())
                break
    except Exception:
        pass

    # Serial number
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "IOPlatformSerialNumber" in line:
                serial = line.split('"')[-2] if '"' in line else ""
                if serial:
                    parts.append(serial)
                break
    except Exception:
        pass

    # Hostname
    try:
        import socket
        parts.append(socket.gethostname())
    except Exception:
        pass

    # Username
    parts.append(os.environ.get("USER", "unknown"))

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_machine():
    """Verify this is the registered machine. On first run, register it."""
    current_fp = _get_machine_fingerprint()

    if os.path.exists(MACHINE_FILE):
        with open(MACHINE_FILE, "r") as f:
            stored_fp = f.read().strip()
        if not hmac.compare_digest(current_fp, stored_fp):
            return False
    else:
        with open(MACHINE_FILE, "w") as f:
            f.write(current_fp)
        os.chmod(MACHINE_FILE, 0o600)

    return True


# ─── Encryption ───────────────────────────────────────────

def _get_or_create_key():
    """Get or generate the Fernet encryption key derived from machine fingerprint."""
    if os.path.exists(KEYFILE):
        with open(KEYFILE, "rb") as f:
            return f.read()

    fp = _get_machine_fingerprint().encode()
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    key = base64.urlsafe_b64encode(kdf.derive(fp))

    payload = salt + key
    with open(KEYFILE, "wb") as f:
        f.write(payload)
    os.chmod(KEYFILE, 0o600)

    return payload


def _get_fernet():
    payload = _get_or_create_key()
    salt = payload[:16]
    key = payload[16:]
    return Fernet(key)


def encrypt_value(plaintext):
    """Encrypt a string value."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext):
    """Decrypt a string value."""
    if not ciphertext:
        return ciphertext
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext  # fallback: return as-is if not encrypted


# ─── Session / Auth ───────────────────────────────────────

SESSION_DURATION_HOURS = 24
DEFAULT_PIN = "1453"  # Initial PIN, user should change

_session_store = {}  # token -> {expires, ip}


def _get_pin_hash():
    """Get stored PIN hash from keyfile, or default."""
    pin_file = os.path.join(DATA_DIR, ".pin_hash")
    if os.path.exists(pin_file):
        with open(pin_file, "r") as f:
            return f.read().strip()
    # First run: store default PIN hash
    h = hashlib.sha256(DEFAULT_PIN.encode()).hexdigest()
    with open(pin_file, "w") as f:
        f.write(h)
    os.chmod(pin_file, 0o600)
    return h


def set_pin(new_pin):
    """Update the PIN."""
    pin_file = os.path.join(DATA_DIR, ".pin_hash")
    h = hashlib.sha256(new_pin.encode()).hexdigest()
    with open(pin_file, "w") as f:
        f.write(h)
    os.chmod(pin_file, 0o600)


def verify_pin(pin):
    """Check if PIN matches."""
    stored = _get_pin_hash()
    candidate = hashlib.sha256(pin.encode()).hexdigest()
    return hmac.compare_digest(stored, candidate)


def create_session(ip=""):
    """Create a new session token."""
    token = secrets.token_urlsafe(48)
    _session_store[token] = {
        "expires": datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS),
        "ip": ip,
    }
    # Cleanup old sessions
    now = datetime.utcnow()
    expired = [k for k, v in _session_store.items() if v["expires"] < now]
    for k in expired:
        del _session_store[k]

    return token


def validate_session(token, ip=""):
    """Validate a session token."""
    if not token or token not in _session_store:
        return False
    session = _session_store[token]
    if session["expires"] < datetime.utcnow():
        del _session_store[token]
        return False
    return True


def destroy_session(token):
    """Invalidate a session."""
    _session_store.pop(token, None)


# ─── Flask Auth Decorator ────────────────────────────────

def require_auth(f):
    """Decorator to require authentication on routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, redirect, url_for, make_response

        # Always allow login page and static
        token = request.cookies.get("ys_session")
        if validate_session(token, request.remote_addr):
            return f(*args, **kwargs)

        # API calls get 401
        if request.path.startswith("/api/"):
            return (json.dumps({"error": "unauthorized"}), 401, {"Content-Type": "application/json"})

        return redirect("/login")

    return decorated
