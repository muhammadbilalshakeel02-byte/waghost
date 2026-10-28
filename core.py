"""Wire-level WhatsApp registration client.

Talks to the unofficial v.whatsapp.net endpoints the Android client uses.
"""
from __future__ import annotations

import base64
import json
import os
import random
import struct
import time
from typing import Any, Dict, Optional

import requests

UA = "WhatsApp/2.26.35.75 Android/13 Device/samsung-SM-A325F"
BASE = "https://v.whatsapp.net/v2"
STATE_FILE = "wa_state.json"

RATE_REASONS = {"too_recent", "too_many"}


class WAError(RuntimeError):
    """Base class for waghost failures."""


class RateLimited(WAError):
    """Server is throttling us; retry after `retry_after` seconds."""

    def __init__(self, reason: str, retry_after: int = 0) -> None:
        super().__init__(f"{reason} (retry in {retry_after}s)")
        self.reason = reason
        self.retry_after = retry_after


class BadToken(WAError):
    """Device identity rejected, or a reCAPTCHA token is required."""


def _b64(data: bytes) -> str:
    """base64url, unpadded — WhatsApp's wire encoding for binary fields."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _rnd_hex(n: int) -> str:
    return "".join(random.choice("0123456789ABCDEF") for _ in range(n))


def _new_state() -> Dict[str, Any]:
    return {
        "id": _rnd_hex(16),                       # device id, 16 upper hex
        "fdid": _rnd_hex(16),                     # facebook device id
        "expid": _b64(os.urandom(16)),
        "authkey": _b64(os.urandom(32)),          # 43-char base64
        "e_regid": _b64(struct.pack(">I", random.getrandbits(32))),
        "e_skey_id": _b64(os.urandom(3)),
        "e_skey_val": _b64(os.urandom(32)),
        "e_skey_sig": _b64(os.urandom(64)),
        "backup_token": _b64(os.urandom(16)),
        "backup_token_ts": int(time.time() * 1000),
    }


def load_state(path: str = STATE_FILE) -> Dict[str, Any]:
    """Load the persisted device identity, creating one on first run.

    The `id` and `authkey` pair must stay identical across the /code and
    /register calls or the server answers `bad_token`.
    """
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    state = _new_state()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    return state


def reset_state(path: str = STATE_FILE) -> Dict[str, Any]:
    """Discard the current identity and generate a fresh one."""
    if os.path.exists(path):
        os.remove(path)
    return load_state(path)


def base_fields(state: Dict[str, Any], cc: str, phone: str) -> Dict[str, str]:
    """Fields common to every request."""
    return {
        "cc": cc,
        "in": phone,
        "id": state["id"],
        "fdid": state["fdid"],
        "expid": state["expid"],
        "authkey": state["authkey"],
        "e_keytype": "BQ",
        "e_ident": _b64(os.urandom(16)),
        "e_regid": state["e_regid"],
        "e_skey_id": state["e_skey_id"],
        "e_skey_val": state["e_skey_val"],
        "e_skey_sig": state["e_skey_sig"],
        "lg": "en",
        "lc": "US",
        "rc": cc,
        "fd": "false",
        "hasav": "1",
        "tos_version": "5",
        "device_ram": "4,00",
        "backup_token": state["backup_token"],
        "backup_token_ts": str(state["backup_token_ts"]),
    }


def _post(endpoint: str, payload: Dict[str, str],
          recaptcha: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
    if recaptcha:
        payload["recaptcha"] = recaptcha
    resp = requests.post(
        f"{BASE}/{endpoint}",
        data=payload,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _raise_for_failure(res: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a `fail` response into a typed exception."""
    if res.get("status") != "fail":
        return res

    reason = res.get("reason", "unknown")
    if reason in RATE_REASONS:
        raise RateLimited(reason, int(res.get("retry_after") or 0))
    if reason == "bad_token":
        raise BadToken(reason)
    raise WAError(reason)


def is_registered(cc: str, phone: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Check whether a number has a WhatsApp account.

    Also returns handset metadata (model, manufacturer) — handy for OSINT.
    """
    return _raise_for_failure(_post("exist", base_fields(state, cc, phone)))


def request_code(cc: str, phone: str, state: Dict[str, Any],
                 method: str = "sms",
                 recaptcha: Optional[str] = None) -> Dict[str, Any]:
    """Trigger an OTP over `sms` or a `voice` call."""
    if method not in ("sms", "voice"):
        raise ValueError(f"method must be 'sms' or 'voice', got {method!r}")

    payload = base_fields(state, cc, phone)
    payload.update({
        "method": method,
        "sim_mcc": "000",     # SIM-less / Wi-Fi only device
        "sim_mnc": "000",
        "sim_opt_in": "1",
        "mcc": "000",
        "mnc": "000",
    })
    return _raise_for_failure(_post("code", payload, recaptcha))


def register(cc: str, phone: str, state: Dict[str, Any], code: str,
             recaptcha: Optional[str] = None) -> Dict[str, Any]:
    """Submit the OTP and complete registration."""
    payload = base_fields(state, cc, phone)
    payload.update({
        "code": code.replace("-", "").replace(" ", ""),
        "entered": "1",              # 1 = typed manually, 2 = auto-filled
        "has_play_store": "false",
    })
    return _raise_for_failure(_post("register", payload, recaptcha))