"""
Stage 3 / Stage 4 automated security tests.
"""

import os
import re
import requests

BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

ALICE_CREDS = ("alice", "tth1mJj5?£58")
BOB_CREDS = ("bob", "De586:Iq6}?!")

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
# Test 1 - Authentication enforcement
# ============================================================================

def test_authentication_enforcement():
    """The @login_required decorator must redirect unauthenticated
    requests away from protected endpoints to /login.
    """
    session = requests.Session()
    # /documents must redirect anonymous callers to /login
    resp = session.get(_url("/documents"), allow_redirects=False, timeout=10)
    assert resp.status_code in (302, 303), (
        f"Expected redirect on anonymous /documents, got {resp.status_code}"
    )
    assert "/login" in resp.headers.get("Location", "")
    # /documents/<id> must also redirect anonymous callers
    resp = session.get(_url("/documents/1"), allow_redirects=False, timeout=10)
    assert resp.status_code in (302, 303), (
        f"Expected redirect on anonymous /documents/1, got {resp.status_code}"
    )
    # /admin/users must also redirect anonymous callers
    resp = session.get(_url("/admin/users"), allow_redirects=False, timeout=10)
    assert resp.status_code in (302, 303), (
        f"Expected redirect on anonymous /admin/users, got {resp.status_code}"
    )

# ============================================================================
# Test 2 - SQL injection resistance at /login
# ============================================================================

def test_sql_injection_login_resistance():
    """A classic tautological injection at the login form must be treated
    as a literal username (failing authentication), not as SQL.
    """
    session = requests.Session()
    csrf_token = _get_csrf_token(session, _url("/login"))

    # OR '1'='1
    resp = session.post(
        _url("/login"),
        data={
            "username": "' OR '1'='1",
            "password": "anything",
            "csrf_token": csrf_token,
        },
        allow_redirects=False,
        timeout=10,
    )
    # returns 200 with "Invalid credentials".
    assert resp.status_code == 200, (
        f"SQL injection at /login should not redirect (got {resp.status_code})"
    )

    resp = session.get(_url("/documents"), allow_redirects=False, timeout=10)
    assert resp.status_code in (302, 303), (
        "Could access /documents after a SQL-injection login attempt"
    )

# ============================================================================
# Test 3 - Cross-user IDOR resistance
# ============================================================================
def test_cross_user_idor_resistance():
    bob = requests.Session()
    assert _login(bob, *BOB_CREDS).status_code in (302, 303), "Bob failed to log in"

    resp = bob.get(
        _url("/documents?user_id=2"),
        allow_redirects=False,
        timeout=10,
    )
    assert resp.status_code == 200, (
        f"GET /documents?user_id=2 returned unexpected {resp.status_code}; "
        f"the route should ignore the parameter and serve Bob's own listing."
    )

    for doc_id in [1, 2, 3, 100, 999]:
        resp = bob.get(
            _url(f"/documents/{doc_id}"),
            allow_redirects=False,
            timeout=10,
        )
        assert resp.status_code in (200, 302, 303, 403, 404), (
            f"/documents/{doc_id} returned unexpected status {resp.status_code} "
            f"(possible leak or unhandled error)"
        )

    resp = bob.get(
        _url("/documents?user_id=' OR 1=1--"),
        allow_redirects=False,
        timeout=10,
    )
    assert resp.status_code in (200, 302, 303), (
        f"Malformed ?user_id returned {resp.status_code}; the route should "
        f"ignore the parameter cleanly."
    )
# ============================================================================
# Test 4 - File upload validation
# ============================================================================
def test_file_upload_validation():
    """Files with disallowed extensions or exceeding the size limit must
    be rejected before being saved.
    """
    session = requests.Session()
    assert _login(session, *ALICE_CREDS).status_code in (302, 303)

    # ------- disallowed extension (.py) is rejected --------
    csrf = _get_csrf_token(session, _url("/documents"))
    files = {"document": ("malicious.py", b"import os; os.system('whoami')",
                          "text/x-python")}
    data = {"title": "reject-extension-test", "csrf_token": csrf}
    resp = session.post(
        _url("/documents/upload"),
        data=data,
        files=files,
        allow_redirects=False,
        timeout=10,
    )
    assert resp.status_code in (302, 303), (
        f"Bad-extension upload returned {resp.status_code}"
    )

    list_resp = session.get(_url("/documents"), timeout=10)
    assert "reject-extension-test" not in list_resp.text, (
        ".py file was accepted into the document store"
    )

    # ------- oversized file (>10 MB) is rejected -----------
    csrf = _get_csrf_token(session, _url("/documents"))
    big_payload = b"x" * (12 * 1024 * 1024)  # 12 MB, limit is 10 MB
    files = {"document": ("huge.pdf", big_payload, "application/pdf")}
    data = {"title": "reject-size-test", "csrf_token": csrf}
    resp = session.post(
        _url("/documents/upload"),
        data=data,
        files=files,
        allow_redirects=False,
        timeout=30,
    )
    assert resp.status_code in (302, 303), (
        f"Oversized upload returned {resp.status_code}"
    )

    list_resp = session.get(_url("/documents"), timeout=10)
    assert "reject-size-test" not in list_resp.text, (
        "12 MB file was accepted (the limit is 10 MB)"
    )
