"""
verify_scheme_codes.py
----------------------
Run this FIRST after placing files in your project to confirm all
scheme codes in mf_fetcher.py resolve to the correct fund names.

Usage:
    python verify_scheme_codes.py

Expected output: a table showing each fund key, scheme code,
and the actual fund name returned by mfapi.in.
"""

import sys
import requests

FUND_REGISTRY = {
    "HDFC_MIDCAP":       118989,
    "NIPPON_LARGECAP":   118632,
    "HDFC_FLEXICAP":     118955,
    "BANDHAN_SMALLCAP":  147946
}

BASE_URL = "https://api.mfapi.in"

print("\nVerifying mfapi.in scheme codes...\n")
print(f"{'FUND KEY':<22} {'CODE':<10} {'STATUS':<10} ACTUAL NAME FROM API")
print("-" * 100)

all_ok = True
for key, code in FUND_REGISTRY.items():
    try:
        resp = requests.get(f"{BASE_URL}/mf/{code}/latest", timeout=10)
        data = resp.json()
        if data.get("status") == "SUCCESS":
            name = data.get("meta", {}).get("scheme_name", "N/A")
            nav  = data.get("data", [{}])[0].get("nav", "?")
            print(f"{key:<22} {code:<10} {'OK':<10} {name}  [NAV: {nav}]")
        else:
            print(f"{key:<22} {code:<10} {'FAIL':<10} status={data.get('status')}")
            all_ok = False
    except Exception as e:
        print(f"{key:<22} {code:<10} {'ERROR':<10} {e}")
        all_ok = False

print("\n" + ("All scheme codes verified OK." if all_ok else
              "Some codes failed — update them in data/mf_fetcher.py"))
print(
    "\nTo find a correct code, search:"
    "\n  https://api.mfapi.in/mf/search?q=<fund+name>\n"
)
