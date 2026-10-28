#!/usr/bin/env python3
"""End-to-end registration using waghost as a library."""
import time

from waghost import BadToken, RateLimited, load_state, register, request_code

CC, PHONE = "1", "5551234567"

state = load_state("wa_state.json")

try:
    res = request_code(CC, PHONE, state)
except RateLimited as exc:
    print(f"throttled, sleeping {exc.retry_after}s")
    time.sleep(exc.retry_after)
    res = request_code(CC, PHONE, state)

print(f"status={res['status']} method={res.get('method')}")

code = input("enter the 6-digit code: ").strip()

try:
    res = register(CC, PHONE, state, code)
except BadToken:
    print("identity rejected — delete wa_state.json and retry")
    raise SystemExit(1)

print(f"registered: {res.get('login')}")