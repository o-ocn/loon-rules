#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Private .lcf Acceptance Tool (Desensitized)
Strictly validates private Loon configuration file for ruleset references and precedence order.
Fails immediately if file is missing, incomplete, or violates First Match Wins precedence.
Outputs desensitized boolean results only - never leaks proxies, credentials, or private tokens.

Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
import simulate_hit

EXPECTED_19_RULESETS = [
    "Apple-Push.lsr",
    "AI-Overseas.lsr",
    "YouTube.lsr",
    "GoogleDrive.lsr",
    "Google.lsr",
    "OneDrive.lsr",
    "Telegram.lsr",
    "Twitter.lsr",
    "Discord.lsr",
    "PayPal.lsr",
    "Gaming.lsr",
    "GitHub.lsr",
    "TestFlight.lsr",
    "Apple-Media.lsr",
    "AI-China-Direct.lsr",
    "Apple-Direct.lsr",
    "China-Direct.lsr",
    "Lan.lsr",
    "China-GeoIP.lsr"
]

def verify_private_lcf(lcf_path: str) -> bool:
    """
    Validates a private .lcf file strictly and desensitized.
    Returns True if 100% compliant, False otherwise.
    """
    if not lcf_path:
        print("[ERROR] No .lcf path provided. Usage: python scripts/verify_private_lcf.py --lcf-path <PATH>")
        return False

    if not os.path.isfile(lcf_path):
        print(f"[ERROR] Private .lcf file not found: {lcf_path}")
        return False

    print("============================================================")
    print(f"[*] Inspecting Private Configuration: {os.path.basename(lcf_path)}")
    print("    (Running in strict local desensitized mode - no credentials or proxies displayed)")
    print("============================================================")

    try:
        pipeline = simulate_hit.load_lcf_pipeline(lcf_path)
    except Exception as e:
        print(f"[FAIL] Error parsing .lcf pipeline: {e}")
        return False

    if not pipeline:
        print("[FAIL] Failed to load rule pipeline from .lcf file.")
        return False

    remote_order = pipeline.get("remote_order", [])
    print(f"\n[+] Total Remote Rulesets Found: {len(remote_order)} (Expected: 19)")
    print("--- Remote Ruleset Sequence ---")
    for idx, rname in enumerate(remote_order):
        print(f"  [{idx:02d}] {rname}")

    errors = []

    # 1. Verify 19 rulesets are present
    missing_rulesets = [r for r in EXPECTED_19_RULESETS if r not in remote_order]
    if missing_rulesets:
        errors.append(f"Missing required rulesets ({len(missing_rulesets)}): {', '.join(missing_rulesets)}")

    if len(remote_order) != 19:
        errors.append(f"Expected exactly 19 remote rulesets, found {len(remote_order)}")

    # 2. Strict Precedence Checks (First Match Wins)
    checks = {}

    # YouTube vs Google
    if "YouTube.lsr" in remote_order and "Google.lsr" in remote_order:
        yt_idx = remote_order.index("YouTube.lsr")
        g_idx = remote_order.index("Google.lsr")
        checks["YouTube < Google"] = (yt_idx < g_idx)
        if yt_idx >= g_idx:
            errors.append(f"Precedence violation: YouTube.lsr (idx {yt_idx}) is AFTER Google.lsr (idx {g_idx})")
    else:
        checks["YouTube < Google"] = False

    # GoogleDrive vs Google
    if "GoogleDrive.lsr" in remote_order and "Google.lsr" in remote_order:
        gd_idx = remote_order.index("GoogleDrive.lsr")
        g_idx = remote_order.index("Google.lsr")
        checks["GoogleDrive < Google"] = (gd_idx < g_idx)
        if gd_idx >= g_idx:
            errors.append(f"Precedence violation: GoogleDrive.lsr (idx {gd_idx}) is AFTER Google.lsr (idx {g_idx})")
    else:
        checks["GoogleDrive < Google"] = False

    # Lan vs China-GeoIP
    if "Lan.lsr" in remote_order and "China-GeoIP.lsr" in remote_order:
        lan_idx = remote_order.index("Lan.lsr")
        geoip_idx = remote_order.index("China-GeoIP.lsr")
        checks["Lan < China-GeoIP"] = (lan_idx < geoip_idx)
        if lan_idx >= geoip_idx:
            errors.append(f"Precedence violation: Lan.lsr (idx {lan_idx}) is AFTER China-GeoIP.lsr (idx {geoip_idx})")
    else:
        checks["Lan < China-GeoIP"] = False

    # Apple-Push vs China-GeoIP
    if "Apple-Push.lsr" in remote_order and "China-GeoIP.lsr" in remote_order:
        push_idx = remote_order.index("Apple-Push.lsr")
        geoip_idx = remote_order.index("China-GeoIP.lsr")
        checks["Apple-Push < China-GeoIP"] = (push_idx < geoip_idx)
        if push_idx >= geoip_idx:
            errors.append(f"Precedence violation: Apple-Push.lsr (idx {push_idx}) is AFTER China-GeoIP.lsr (idx {geoip_idx})")
    else:
        checks["Apple-Push < China-GeoIP"] = False

    checks["All 19 Rulesets Present"] = (len(missing_rulesets) == 0 and len(remote_order) == 19)

    print("\n--- Desensitized Precedence Check Results ---")
    for check_name, res in checks.items():
        status_tag = "[PASS]" if res else "[FAIL]"
        print(f"  {status_tag:6s} {check_name} = {res}")

    if errors:
        print("\n[!] Acceptance Failures Detected:")
        for err in errors:
            print(f"  - {err}")
        print("\n============================================================")
        print("[FAIL] Private .lcf acceptance FAILED. Precedence or rulesets not compliant.")
        print("============================================================")
        return False

    print("\n============================================================")
    print("[SUCCESS] Private .lcf acceptance PASSED: 19 rulesets and precedence verified.")
    print("============================================================")
    return True

def main():
    parser = argparse.ArgumentParser(description="Desensitized acceptance validator for private Loon .lcf files")
    parser.add_argument("lcf_path", nargs="?", default="", help="Path to the private .lcf file")
    parser.add_argument("--lcf-path", dest="flag_lcf_path", default="", help="Path to the private .lcf file")

    args = parser.parse_args()
    target_path = args.flag_lcf_path or args.lcf_path

    if not target_path:
        print("[ERROR] Missing required .lcf file path argument.")
        print("Usage: python scripts/verify_private_lcf.py <PATH_TO_LCF>")
        sys.exit(1)

    ok = verify_private_lcf(target_path)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
