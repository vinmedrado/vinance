from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest


BASE_URL = os.getenv("VINANCE_LIVE_BASE_URL")
pytestmark = pytest.mark.skipif(not BASE_URL, reason="requires an isolated live production-like backend")


def test_refresh_rotation_origin_logout_and_password_revocation() -> None:
    email = f"phase-e-{uuid4().hex}@example.com"
    password = "Phase-E-Initial-Password-38"
    replacement = "Phase-E-Replaced-Password-39"
    headers = {"Host": "phase-e.local", "Origin": "https://phase-e.local"}

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=20) as client:
        registered = client.post("/register", json={"email": email, "password": password, "full_name": "Phase E"})
        assert registered.status_code == 201, registered.text
        first_access = registered.json()["access_token"]
        cookie = registered.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
        assert "path=/api/v1" in cookie
        refresh_cookie = registered.cookies.get("vinance_refresh")
        assert refresh_cookie

        without_origin = httpx.Client(base_url=BASE_URL, headers={"Host": "phase-e.local"}, timeout=20)
        try:
            assert without_origin.post("/login", json={"email": email, "password": password}).status_code == 403
        finally:
            without_origin.close()

        me = client.get("/me", headers={"Authorization": f"Bearer {first_access}"})
        assert me.status_code == 200

        missing_origin = httpx.Client(
            base_url=BASE_URL,
            headers={"Host": "phase-e.local", "Cookie": f"vinance_refresh={refresh_cookie}"},
            timeout=20,
        )
        try:
            assert missing_origin.post("/refresh").status_code == 403
        finally:
            missing_origin.close()

        refreshed = client.post("/refresh", headers={"Cookie": f"vinance_refresh={refresh_cookie}"})
        assert refreshed.status_code == 200, refreshed.text
        second_access = refreshed.json()["access_token"]
        assert second_access != first_access
        replacement_cookie = refreshed.cookies.get("vinance_refresh")
        assert replacement_cookie and replacement_cookie != refresh_cookie

        logout = client.post("/logout", headers={"Cookie": f"vinance_refresh={replacement_cookie}"})
        assert logout.status_code == 204
        assert client.get("/me", headers={"Authorization": f"Bearer {second_access}"}).status_code == 401
        assert client.post("/refresh", headers={"Cookie": f"vinance_refresh={replacement_cookie}"}).status_code == 401

        relogin = client.post("/login", json={"email": email, "password": password})
        assert relogin.status_code == 200, relogin.text
        access = relogin.json()["access_token"]
        changed = client.post(
            "/password/change",
            headers={"Authorization": f"Bearer {access}"},
            json={"current_password": password, "new_password": replacement},
        )
        assert changed.status_code == 204, changed.text
        assert client.get("/me", headers={"Authorization": f"Bearer {access}"}).status_code == 401
        assert client.post("/login", json={"email": email, "password": password}).status_code == 401
        assert client.post("/login", json={"email": email, "password": replacement}).status_code == 200


def test_login_rate_limit_is_coordinated_by_redis() -> None:
    headers = {"Host": "phase-e.local", "Origin": "https://phase-e.local"}
    email = f"rate-limit-phase-e-{uuid4().hex}@example.com"
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=20) as client:
        statuses = [
            client.post(
                "/login",
                json={"email": email, "password": "invalid-password"},
            ).status_code
            for _ in range(11)
        ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
