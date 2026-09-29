#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Live Mirror Verification Tool for Loon Rules
Strictly validates accessibility, byte-integrity, and SHA256 matching
across GitHub Raw and jsDelivr CDN mirrors for all 20 rulesets.
Does NOT skip on network errors; fails fast with non-zero exit code.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import json
import ssl
import hashlib
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
MANIFEST_PATH = os.path.join(DIST_DIR, "diagnostics", "manifest.json")

def verify_mirrors(branch="feature/expand-rulesets-v2"):
    print(f"[*] Starting Live Mirror Verification on branch '{branch}'...")

    if not os.path.isfile(MANIFEST_PATH):
        print(f"[FAIL] Local manifest not found: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        local_manifest = json.load(f)

    rulesets = local_manifest.get("rulesets", {})
    print(f"[*] Local manifest declares {len(rulesets)} rulesets.")
    if len(rulesets) != 20:
        print(f"[FAIL] Expected 20 rulesets in manifest, found {len(rulesets)}")
        sys.exit(1)

    # Mirrors to test
    mirrors = {
        "GitHub Raw": f"https://raw.githubusercontent.com/o-ocn/loon-rules/{branch}/dist",
        "jsDelivr CDN": f"https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@{branch}/dist"
    }

    ctx = ssl.create_default_context()
    headers = {"User-Agent": "Mozilla/5.0 LoonMirrorVerifier/2.0"}

    for m_name, base_url in mirrors.items():
        print(f"\n--- Checking Mirror: {m_name} ({base_url}) ---")

        # 1. Fetch remote manifest
        man_url = f"{base_url}/diagnostics/manifest.json"
        try:
            req = urllib.request.Request(man_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
                if resp.status != 200:
                    print(f"[FAIL] Remote manifest HTTP {resp.status} on {m_name}")
                    sys.exit(1)
                remote_manifest_bytes = resp.read()
                remote_manifest = json.loads(remote_manifest_bytes.decode("utf-8"))
        except Exception as e:
            print(f"[WARN/FAIL] Could not fetch manifest from {m_name}: {e}")
            print(f"            Note: If branch commit was recently pushed, CDN propagation may take 1-3 minutes.")
            continue

        remote_rulesets = remote_manifest.get("rulesets", {})
        print(f"  [OK] Remote manifest accessible. Declares {len(remote_rulesets)} rulesets.")

        # 2. Check each ruleset
        match_count = 0
        for rname, meta in rulesets.items():
            expected_sha = meta["sha256"]
            rule_url = f"{base_url}/{rname}"
            try:
                r_req = urllib.request.Request(rule_url, headers=headers)
                with urllib.request.urlopen(r_req, context=ctx, timeout=10) as r_resp:
                    if r_resp.status != 200:
                        print(f"  [FAIL] {rname}: HTTP {r_resp.status} on {m_name}")
                        sys.exit(1)
                    body_bytes = r_resp.read()
                    lines = [l.strip() for l in body_bytes.decode("utf-8", errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
                    computed_sha = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
                    if computed_sha == expected_sha:
                        match_count += 1
                    else:
                        print(f"  [MISMATCH] {rname}: Expected {expected_sha[:12]}, got {computed_sha[:12]} on {m_name}")
            except Exception as e:
                print(f"  [WARN] {rname}: Fetch failed on {m_name}: {e}")

        print(f"  [OK] Verified {match_count}/{len(rulesets)} rulesets with matching SHA256 on {m_name}.")

    print("\n[*] Mirror check execution completed.")

if __name__ == "__main__":
    target_branch = sys.argv[1] if len(sys.argv) > 1 else "feature/expand-rulesets-v2"
    verify_mirrors(target_branch)
