#!/usr/bin/env python3
"""Serve the digital merch desk on loopback. No print, pitch, or spend."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from secrets import token_hex
import sys
from wsgiref.simple_server import make_server


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from digital_merch.app import create_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Digital merch desk binds to loopback only.")

    secret = os.environ.get("RAD_DAD_MERCH_SECRET") or token_hex(32)
    admin_token = os.environ.get("RAD_DAD_MERCH_ADMIN_TOKEN", "")
    app = create_app(secret=secret.encode("utf-8"), admin_token=admin_token)
    httpd = make_server(args.host, args.port, app)
    print(f"Digital merch desk: http://{args.host}:{args.port}/catalog")
    if admin_token:
        print("Admin is enabled for this process only.")
    else:
        print("Admin sign-in is disabled until RAD_DAD_MERCH_ADMIN_TOKEN is set.")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
