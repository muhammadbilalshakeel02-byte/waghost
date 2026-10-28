"""Harvest WhatsApp OTPs from a USB-connected Android device via ADB."""
from __future__ import annotations

import re
import subprocess
import time
from typing import List, Optional

# WhatsApp sends the code formatted as 123-456
CODE_RE = re.compile(r"\b(\d{3})[- ](\d{3})\b")


def adb_available() -> bool:
    try:
        return subprocess.run(
            ["adb", "version"], capture_output=True, timeout=5
        ).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _inbox_lines() -> List[str]:
    """Dump recent SMS bodies. Needs READ_SMS for the shell user."""
    out = subprocess.run(
        ["adb", "shell", "content", "query",
         "--uri", "content://sms/inbox",
         "--projection", "body", "--sort", "date DESC"],
        capture_output=True, text=True, timeout=15,
    ).stdout
    return out.splitlines()


def _logcat_lines() -> List[str]:
    """Fallback: recent WhatsApp notification traffic."""
    out = subprocess.run(
        ["adb", "logcat", "-d", "-t", "400", "-v", "brief"],
        capture_output=True, text=True, timeout=15,
    ).stdout
    return [ln for ln in out.splitlines() if "whatsapp" in ln.lower()]


def extract_code(lines: List[str], require_whatsapp: bool = True) -> Optional[str]:
    """Pull the first `123-456` style code out of a list of lines."""
    for line in lines:
        if require_whatsapp and "whatsapp" not in line.lower():
            continue
        match = CODE_RE.search(line)
        if match:
            return match.group(1) + match.group(2)
    return None


def wait_for_otp(timeout: int = 180, poll: float = 2.0) -> Optional[str]:
    """Block until an OTP appears, or return None on timeout.

    Tries the SMS inbox first, then falls back to logcat, then to an
    unfiltered scan in case the sender string is localised.
    """
    if not adb_available():
        raise RuntimeError("adb not found on PATH")

    seen: set[str] = set()
    deadline = time.time() + timeout

    while time.time() < deadline:
        for lines in (_inbox_lines(), _logcat_lines()):
            code = extract_code(lines)
            if code and code not in seen:
                return code
            if code:
                seen.add(code)

        # last resort: any 6-digit XXX-XXX in the inbox
        code = extract_code(_inbox_lines(), require_whatsapp=False)
        if code:
            return code

        time.sleep(poll)

    return None