"""Command-line interface for waghost."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from . import __version__
from .core import (
    STATE_FILE,
    BadToken,
    RateLimited,
    WAError,
    is_registered,
    load_state,
    register,
    request_code,
    reset_state,
)

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
EXIT_RATE = 3
EXIT_BADTOKEN = 4
EXIT_TIMEOUT = 5


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="waghost",
        description="Request and verify WhatsApp registration OTPs over raw HTTP.",
        epilog="Docs: https://github.com/USER/waghost",
    )
    p.add_argument("--cc", default="1", help="country code, digits only (default: 1)")
    p.add_argument("--phone", required=True, help="subscriber number, digits only")
    p.add_argument("--method", default="sms", choices=["sms", "voice"],
                   help="OTP delivery channel (default: sms)")
    p.add_argument("--code", help="skip requesting, verify this code directly")
    p.add_argument("--check", action="store_true",
                   help="only run /v2/exist and exit")
    p.add_argument("--auto-otp", action="store_true",
                   help="harvest the OTP from a tethered phone via ADB")
    p.add_argument("--otp-timeout", type=int, default=180,
                   help="seconds to wait for an auto-harvested OTP (default: 180)")
    p.add_argument("--recaptcha", help="reCAPTCHA token if the server demands one")
    p.add_argument("--state", default=STATE_FILE,
                   help=f"device identity file (default: {STATE_FILE})")
    p.add_argument("--reset", action="store_true",
                   help="generate a fresh device identity first")
    p.add_argument("--json", action="store_true", help="emit raw JSON")
    p.add_argument("--quiet", action="store_true", help="suppress logging")
    p.add_argument("--version", action="version", version=f"waghost {__version__}")
    return p


def _emit(res: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        for key, value in res.items():
            print(f"{key}: {value}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def log(msg: str) -> None:
        if not args.quiet:
            print(msg, file=sys.stderr)

    if not args.phone.isdigit():
        print("error: --phone must be digits only", file=sys.stderr)
        return EXIT_USAGE
    if not args.cc.isdigit():
        print("error: --cc must be digits only", file=sys.stderr)
        return EXIT_USAGE

    try:
        state = reset_state(args.state) if args.reset else load_state(args.state)

        if args.check:
            res = is_registered(args.cc, args.phone, state)
            _emit(res, args.json)
            return EXIT_OK

        if args.code:
            log(f"[*] verifying code {args.code}")
            res = register(args.cc, args.phone, state, args.code, args.recaptcha)
            _emit(res, args.json)
            return EXIT_OK

        res = request_code(args.cc, args.phone, state, args.method, args.recaptcha)
        log(f"[+] {res.get('method', 'sms')} code sent "
            f"({res.get('length', 6)} digits)")

        if args.auto_otp:
            from .adb import wait_for_otp

            log("[*] waiting for OTP via ADB...")
            code = wait_for_otp(timeout=args.otp_timeout)
            if not code:
                log("[-] timed out waiting for OTP")
                return EXIT_TIMEOUT
            log(f"[+] harvested OTP {code}")
            res = register(args.cc, args.phone, state, code, args.recaptcha)

        _emit(res, args.json)
        return EXIT_OK

    except RateLimited as exc:
        print(f"rate limited: {exc}", file=sys.stderr)
        return EXIT_RATE
    except BadToken as exc:
        print(f"bad token: {exc} — try --reset or --recaptcha", file=sys.stderr)
        return EXIT_BADTOKEN
    except WAError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except KeyboardInterrupt:
        return EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())