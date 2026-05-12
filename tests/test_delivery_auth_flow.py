import os
import re
import requests

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")


def _url(path: str) -> str:
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def _get_csrf_token(session: requests.Session, url: str) -> str:
    """Fetch a page and extract the CSRF token from its hidden form input.

    Required because Stage 3 Fix #14 introduced Flask-WTF CSRFProtect,
    which rejects any POST request without a server-issued token (HTTP 400).
    A realistic client (browser or otherwise) must GET the form first to
    obtain the token bound to its session, then submit it with the form.
    """
    resp = session.get(url, timeout=10)
    assert resp.status_code == 200, f"Failed to load {url}: {resp.status_code}"
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    assert match, "csrf_token input not found in form"
    return match.group(1)


def test_login_logout_flow():
    """
    Delivery-stage integration test.
    Verifies the authentication flow against a running deployment:
    1. Fetch login page to obtain a CSRF token
    2. Login with valid credentials and the token
    3. Access a protected page
    4. Logout
    5. Verify access is revoked
    """
    session = requests.Session()

    # ------------------------------------------------------------
    # Fetch CSRF token from the login form
    # ------------------------------------------------------------
    csrf_token = _get_csrf_token(session, _url("/login"))

    # ------------------------------------------------------------
    # Login
    # ------------------------------------------------------------
    login_resp = session.post(
        _url("/login"),
        data={
            "username": "alice",
            "password": "tth1mJj5?£58",
            "csrf_token": csrf_token,
        },
        allow_redirects=False,
        timeout=10,
    )
    assert login_resp.status_code in (302, 303), (
        f"Login failed unexpectedly: {login_resp.status_code}"
    )

    # ------------------------------------------------------------
    # Access protected page
    # ------------------------------------------------------------
    documents_resp = session.get(
        _url("/documents"),
        allow_redirects=False,
        timeout=10,
    )
    assert documents_resp.status_code == 200, (
        "Authenticated user cannot access /documents"
    )

    # ------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------
    logout_resp = session.get(
        _url("/logout"),
        allow_redirects=False,
        timeout=10,
    )
    assert logout_resp.status_code in (302, 303), (
        f"Logout failed unexpectedly: {logout_resp.status_code}"
    )

    # ------------------------------------------------------------
    # Verify session is invalidated
    # ------------------------------------------------------------
    after_logout = session.get(
        _url("/documents"),
        allow_redirects=False,
        timeout=10,
    )
    assert after_logout.status_code in (302, 303), (
        "Protected page still accessible after logout"
    )
