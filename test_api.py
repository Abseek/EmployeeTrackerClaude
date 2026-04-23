"""
Quick smoke test for all Lambda API endpoints defined in lambda/lambda_function.py.
Run with: venv/Scripts/python.exe test_api.py
"""

import json
import sys
import requests
from config import API_ENDPOINT, API_KEY
BASE = API_ENDPOINT
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

results = []


def req(method, path, *, json_body=None, params=None, expect=200, label=None):
    url = BASE + path
    tag = label or f"{method} {path}"
    try:
        resp = requests.request(
            method, url, headers=HEADERS,
            json=json_body, params=params, timeout=(5, 15)
        )
        ok = resp.status_code == expect
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:200]
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {tag}")
        print(f"         HTTP {resp.status_code}  ->  {json.dumps(body)[:120]}")
        results.append((ok, tag))
        return resp, body
    except Exception as e:
        print(f"  [FAIL] {tag}")
        print(f"         ERROR: {e}")
        results.append((False, tag))
        return None, None


print("\n=== Claude Tracker API Smoke Test ===")
print(f"Base URL : {BASE}\n")

# --- Health ---
print("--- Health / misc ---")
req("GET", "/tracker/is_first_run", label="GET /tracker/is_first_run")

# --- Accounts ---
print("\n--- Accounts ---")
resp, body = req("GET", "/tracker/accounts", label="GET /tracker/accounts (all)")

existing_id = None
existing_username = None
if body and isinstance(body.get("accounts"), list) and body["accounts"]:
    existing_id = body["accounts"][0]["id"]
    existing_username = body["accounts"][0]["username"]
    print(f"         (found account id={existing_id}, username={existing_username})")

if existing_id:
    req("GET", f"/tracker/accounts/{existing_id}", label="GET /tracker/accounts/{id}")
else:
    req("GET", "/tracker/accounts/nonexistent_id", label="GET /tracker/accounts/{id} (no-op id)", expect=200)

if existing_username:
    req("GET", "/tracker/accounts", params={"username": existing_username},
        label="GET /tracker/accounts?username=...")

req("GET", "/tracker/accounts/check-username",
    params={"username": "test_nonexistent_zz99", "exclude_id": ""},
    label="GET /tracker/accounts/check-username")

# --- Settings ---
print("\n--- Settings ---")
req("GET", "/tracker/settings", label="GET /tracker/settings")

# --- Authenticate ---
print("\n--- Authenticate (bad creds -> expect 401) ---")
req("POST", "/tracker/authenticate",
    json_body={"username": "nobody", "password": "wrongpass"},
    expect=401,
    label="POST /tracker/authenticate (bad creds)")

if existing_username:
    print(f"\n--- Auth probe: real user '{existing_username}', wrong pass -> expect 401 ---")
    req("POST", "/tracker/authenticate",
        json_body={"username": existing_username, "password": "wrongpassword999"},
        expect=401,
        label="POST /tracker/authenticate (real user, wrong pass)")

# --- Activity read endpoints ---
print("\n--- Activity read endpoints ---")
dummy_emp = existing_id or "emp_test000"
dummy_date = "2026-04-22"

req("GET", "/tracker/activity/today",
    params={"employee_id": dummy_emp},
    label="GET /tracker/activity/today")

req("GET", "/tracker/activity/hourly",
    params={"employee_id": dummy_emp, "date_str": dummy_date},
    label="GET /tracker/activity/hourly")

req("GET", "/tracker/activity",
    params={"employee_id": dummy_emp, "date_str": dummy_date},
    label="GET /tracker/activity")

req("GET", "/tracker/activity/screenshots",
    params={"employee_id": dummy_emp, "date_str": dummy_date},
    label="GET /tracker/activity/screenshots")

req("GET", "/tracker/activity/dates",
    params={"employee_id": dummy_emp},
    label="GET /tracker/activity/dates")

# --- 404 sanity check ---
print("\n--- Route-not-found sanity check (expect 404) ---")
req("GET", "/tracker/nonexistent_route", expect=404,
    label="GET /tracker/nonexistent_route")

# --- Summary ---
passed = sum(1 for ok, _ in results if ok)
failed = sum(1 for ok, _ in results if not ok)
print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed out of {len(results)} tests")
if failed:
    print("\nFailed tests:")
    for ok, tag in results:
        if not ok:
            print(f"  - {tag}")
    sys.exit(1)
else:
    print("All tests passed.")
