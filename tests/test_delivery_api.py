"""
Delivery-stage API tests.
"""

import os
import re
import requests

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

ALICE_CREDS = ("alice", "tth1mJj5?£58")
ADMIN_CREDS = ("admin", "L|fP1D%327mB")


def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def _get_csrf_token(session: requests.Session, url: str) -> str:
    """Fetch a page and extract the CSRF token from its hidden form input."""
    resp = session.get(url, timeout=10)
    assert resp.status_code == 200, f"Failed to load {url}: {resp.status_code}"
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    assert match, "csrf_token input not found in form"
    return match.group(1)


def _login(session: requests.Session, username: str, password: str) -> requests.Response:
    """Performs the GET -> POST login dance correctly (with CSRF token)."""
    csrf_token = _get_csrf_token(session, _url("/login"))
    return session.post(
        _url("/login"),
        data={
            "username": username,
            "password": password,
            "csrf_token": csrf_token,
        },
        allow_redirects=False,
        timeout=10,
    )


# ============================================================================
# Test 1 - Health endpoint contract
# ============================================================================

def test_health_endpoint_returns_ok():
    resp = requests.get(_url("/health"), timeout=10)
    assert resp.status_code == 200, (
        f"/health returned {resp.status_code}, expected 200"
    )
    body = resp.json()
    assert body == {"status": "ok"}, (
        f"/health body was {body}, expected {{'status': 'ok'}}"
    )


# ============================================================================
# Test 2 - Admin endpoint authorisation
# ============================================================================

def test_admin_endpoint_requires_admin_role():
    alice = requests.Session()
    assert _login(alice, *ALICE_CREDS).status_code in (302, 303), (
        "Alice failed to log in"
    )

    resp = alice.get(_url("/admin/users"), allow_redirects=False, timeout=10)
    assert resp.status_code == 403, (
        f"Non-admin GET /admin/users should be 403, got {resp.status_code}"
    )

    admin = requests.Session()
    assert _login(admin, *ADMIN_CREDS).status_code in (302, 303), (
        "Admin failed to log in"
    )

    resp = admin.get(_url("/admin/users"), timeout=10)
    assert resp.status_code == 200, (
        f"Admin GET /admin/users should be 200, got {resp.status_code}"
    )
    assert "Username" in resp.text or "admin" in resp.text, (
        "/admin/users page did not render the user listing"
    )

# ============================================================================
# Test 3 - Documents listing access for authenticated user
# ============================================================================

def test_documents_listing_for_authenticated_user():
    session = requests.Session()
    assert _login(session, *ALICE_CREDS).status_code in (302, 303), (
        "Alice failed to log in"
    )

    resp = session.get(_url("/documents"), timeout=10)
    assert resp.status_code == 200, (
        f"GET /documents returned {resp.status_code}, expected 200"
    )
    assert 'name="csrf_token"' in resp.text, (
        "/documents page is missing the CSRF token in the upload form"
    )
    assert 'name="document"' in resp.text, (
        "/documents page is missing the file input"
    )
