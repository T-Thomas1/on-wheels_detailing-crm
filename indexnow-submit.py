#!/usr/bin/env python3
"""
IndexNow submission script for On-Wheels Detailing.
Run after Cloudflare Pages deploys to notify search engines of changes.

Usage:
    python3 indexnow-submit.py                           # submit all known URLs
    python3 indexnow-submit.py /about /services          # submit specific URLs
    python3 indexnow-submit.py --dry-run                 # preview without sending
"""

import json
import sys
import urllib.request
import urllib.error

INDEXNOW_KEY = "f9533a2a0b4141c79c3448531f13f5fb"
HOST = "www.onwheelsdetailing.com"
KEY_LOCATION = f"https://{HOST}/{INDEXNOW_KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"

# All known site URLs — keep in sync with sitemap.xml
ALL_URLS = [
    f"https://{HOST}/",
    f"https://{HOST}/about",
    f"https://{HOST}/services",
    f"https://{HOST}/gallery",
    f"https://{HOST}/contact",
]


def submit(urls: list[str], dry_run: bool = False) -> bool:
    """Submit URLs to IndexNow. Returns True on success."""
    payload = json.dumps({
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }).encode("utf-8")

    if dry_run:
        print(f"[DRY RUN] Would submit {len(urls)} URLs to {ENDPOINT}:")
        for u in urls:
            print(f"  {u}")
        return True

    req = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode()
            print(f"IndexNow: HTTP {status} — {body}")
            return 200 <= status < 300
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"IndexNow: HTTP {e.code} — {body}")
        # 202 Accepted, 200 OK, 403 (key not yet verified — will retry)
        return e.code in (200, 202)
    except urllib.error.URLError as e:
        print(f"IndexNow: connection error — {e.reason}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        # User provided specific paths — normalize to full URLs
        urls = []
        for a in args:
            if a.startswith("https://"):
                urls.append(a)
            else:
                path = a if a.startswith("/") else f"/{a}"
                urls.append(f"https://{HOST}{path}")
    else:
        urls = ALL_URLS

    ok = submit(urls, dry_run=dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
