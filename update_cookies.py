#!/usr/bin/env python3
"""
update_cookies.py — Railway pe cookies update karne ka script
─────────────────────────────────────────────────────────────
Usage:
  python update_cookies.py --url https://your-app.railway.app --token YOUR_ADMIN_TOKEN --cookies path/to/cookies.txt

Description:
  Yeh script local cookies.txt file ko Railway pe deploy ki hui app me
  /api/cookies endpoint ke zariye upload karta hai.
  Jab bhi YouTube ne block kare ya download fail ho, cookies refresh karo.
"""

import argparse
import sys
import requests


def upload_cookies(app_url: str, admin_token: str, cookies_file: str):
    app_url = app_url.rstrip('/')

    print(f"📂 Reading cookies from: {cookies_file}")
    try:
        with open(cookies_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {cookies_file}")
        sys.exit(1)

    if not content.strip():
        print("❌ cookies.txt khaali hai!")
        sys.exit(1)

    print(f"🚀 Uploading to: {app_url}/api/cookies")
    try:
        resp = requests.post(
            f"{app_url}/api/cookies",
            json={"cookies": content},
            headers={"X-Admin-Token": admin_token, "Content-Type": "application/json"},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("success"):
            print(f"✅ Cookies successfully uploaded!")
            print(f"   Path: {data.get('path')}")
            print(f"   Size: {data.get('size')} bytes")
        else:
            print(f"❌ Upload failed: {data.get('error', 'Unknown error')}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"❌ App se connect nahi ho saka: {app_url}")
        sys.exit(1)


def check_health(app_url: str):
    resp = requests.get(f"{app_url.rstrip('/')}/api/health", timeout=10)
    data = resp.json()
    print(f"\n📊 Health Check:")
    print(f"   Status:  {data.get('status')}")
    print(f"   Cookies: {data.get('cookies')}")
    print(f"   Path:    {data.get('cookies_path')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YTDown — Railway pe cookies update karo")
    parser.add_argument("--url", required=True, help="Railway app URL (e.g. https://ytdown.railway.app)")
    parser.add_argument("--token", default="", help="ADMIN_TOKEN env var ka value")
    parser.add_argument("--cookies", default="cookies.txt", help="Local cookies.txt path")
    parser.add_argument("--health", action="store_true", help="Sirf health check karo")

    args = parser.parse_args()

    if args.health:
        check_health(args.url)
    else:
        upload_cookies(args.url, args.token, args.cookies)
        check_health(args.url)