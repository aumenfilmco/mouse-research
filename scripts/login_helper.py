#!/usr/bin/env python3
"""Standalone login helper — run directly, not via Claude Code's ! prefix.

Uses the same persistent Chrome profile as the fetcher so Cloudflare
cf_clearance cookies stay bound to the same browser fingerprint.

Usage: .venv/bin/python3 scripts/login_helper.py newspapers.com
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

domain = sys.argv[1] if len(sys.argv) > 1 else "newspapers.com"

LOGIN_URLS = {
    "newspapers.com": "https://www.newspapers.com/signin/?next_url=/?",
}

login_url = LOGIN_URLS.get(domain, f"https://www.{domain}/")

# Same profile directory used by the fetcher
profile_dir = Path.home() / ".mouse-research" / "chrome-profile"
profile_dir.mkdir(parents=True, exist_ok=True)

print(f"Opening Chrome to {login_url}")
print(f"Profile: {profile_dir}")
print("Log in manually. You have 120 seconds.")
print("Cookies persist in the Chrome profile — shared with mouse-research archive.")

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        channel="chrome",
    )
    page = context.new_page()
    page.goto(login_url, wait_until="domcontentloaded", timeout=30000)

    try:
        for i in range(24):  # 120 seconds total
            time.sleep(5)
            current = page.url
            print(f"  [{(i+1)*5}s] Current URL: {current}")
            if "signin" not in current.lower() and "sign-in" not in current.lower():
                print("Login detected! Cookies are in the Chrome profile.")
                break
    except KeyboardInterrupt:
        print("\nClosing...")

    context.close()

print("Done! Cookies persist in Chrome profile for mouse-research archive.")
