#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Live Mirror Verification Tool for Loon Rules
Strictly validates accessibility, byte-integrity, and SHA256 matching
across GitHub Raw and jsDelivr CDN mirrors for all 19 rulesets.
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
EXPECTED_RULESET_COUNT = 19

def compute_rule_body_sha256(content_bytes):
    """Computes SHA256 of rule body excluding comments and blank lines."""
    lines = [
        l.strip()
        for l in content_bytes.decode("utf-8", errors="ignore").splitlines()
        if l.strip() and not l.startswith("#") and not l.startswith(";")
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

def verify_mirrors(branch="feature/expand-rulesets-v2", manifest_path=MANIFEST_PATH,
                   mirrors=None, exit_on_failure=True, urlopen_fn=None):
    """
    Verifies primary and backup mirrors against manifest.
    Returns True if all mirrors pass completely, False otherwise.
    If exit_on_failure is True, terminates with sys.exit(1) on any failure.
    """
    print(f"[*] Starting Live Mirror Verification on branch '{branch}'...")

    if not os.path.isfile(manifest_path):
        print(f"[FAIL] Local manifest not found: {manifest_path}")
        if exit_on_failure:
            sys.exit(1)
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        local_manifest = json.load(f)

    rulesets = local_manifest.get("rulesets", {})
    print(f"[*] Local manifest declares {len(rulesets)} rulesets.")
    if len(rulesets) != EXPECTED_RULESET_COUNT:
        print(f"[FAIL] Expected {EXPECTED_RULESET_COUNT} rulesets in manifest, found {len(rulesets)}")
        if exit_on_failure:
            sys.exit(1)
        return False

    local_rev = local_manifest.get("content_revision") or local_manifest.get("release_commit", "")

    # Mirrors to test
    if mirrors is None:
        mirrors = {
            "GitHub Raw": f"https://raw.githubusercontent.com/o-ocn/loon-rules/{branch}/dist",
            "jsDelivr CDN": f"https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@{branch}/dist"
        }

    ctx = ssl.create_default_context()
    headers = {"User-Agent": "Mozilla/5.0 LoonMirrorVerifier/2.0"}
    opener = urlopen_fn or urllib.request.urlopen

    all_passed = True
    mirror_reports = {}

    for m_name, base_url in mirrors.items():
        print(f"\n--- Checking Mirror: {m_name} ({base_url}) ---")
        m_errors = []

        # 1. Fetch remote manifest
        man_url = f"{base_url}/diagnostics/manifest.json"
        try:
            req = urllib.request.Request(man_url, headers=headers)
            with opener(req, context=ctx, timeout=12) if urlopen_fn is None else opener(req) as resp:
                status = getattr(resp, "status", 200)
                if status != 200:
                    m_errors.append(f"Remote manifest HTTP {status}")
                else:
                    remote_manifest_bytes = resp.read()
                    remote_manifest = json.loads(remote_manifest_bytes.decode("utf-8"))
        except Exception as e:
            m_errors.append(f"Could not fetch manifest: {e}")
            remote_manifest = None

        if not remote_manifest:
            print(f"  [FAIL] Remote manifest inaccessible on {m_name}: {m_errors[-1]}")
            all_passed = False
            mirror_reports[m_name] = {"passed": False, "errors": m_errors}
            continue

        remote_rulesets = remote_manifest.get("rulesets", {})
        if len(remote_rulesets) != EXPECTED_RULESET_COUNT:
            m_errors.append(f"Manifest ruleset count mismatch: expected {EXPECTED_RULESET_COUNT}, got {len(remote_rulesets)}")

        remote_rev = remote_manifest.get("content_revision") or remote_manifest.get("release_commit", "")
        if local_rev and remote_rev and local_rev != remote_rev:
            m_errors.append(f"Revision mismatch: local {local_rev}, remote {remote_rev}")

        print(f"  [OK] Remote manifest accessible. Declares {len(remote_rulesets)} rulesets (revision: {remote_rev}).")

        # 2. Check each ruleset
        match_count = 0
        for rname, meta in rulesets.items():
            expected_sha = meta["sha256"]
            rule_url = f"{base_url}/{rname}"
            fetched = False
            last_err = None
            for attempt in range(2):
                try:
                    r_req = urllib.request.Request(rule_url, headers=headers)
                    with opener(r_req, context=ctx, timeout=12) if urlopen_fn is None else opener(r_req) as r_resp:
                        r_status = getattr(r_resp, "status", 200)
                        if r_status != 200:
                            m_errors.append(f"{rname}: HTTP {r_status}")
                            fetched = True
                            break
                        body_bytes = r_resp.read()
                        if not body_bytes:
                            m_errors.append(f"{rname}: Empty file (0 bytes)")
                            fetched = True
                            break
                        computed_sha = compute_rule_body_sha256(body_bytes)
                        if computed_sha == expected_sha:
                            match_count += 1
                        else:
                            m_errors.append(f"{rname}: SHA256 mismatch (expected {expected_sha[:12]}, got {computed_sha[:12]})")
                        fetched = True
                        break
                except Exception as e:
                    last_err = f"{rname}: Fetch failed: {e}"
            if not fetched and last_err:
                m_errors.append(last_err)

        if m_errors:
            all_passed = False
            mirror_reports[m_name] = {"passed": False, "errors": m_errors, "matched": match_count}
            print(f"  [FAIL] {m_name} encountered {len(m_errors)} errors:")
            for err in m_errors[:5]:
                print(f"    - {err}")
            if len(m_errors) > 5:
                print(f"    - ... and {len(m_errors) - 5} more errors")
        else:
            mirror_reports[m_name] = {"passed": True, "errors": [], "matched": match_count}
            print(f"  [PASS] Verified {match_count}/{len(rulesets)} rulesets with matching SHA256 on {m_name}.")

    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All mirrors verified completely with zero errors.")
        return True
    else:
        print("[FAILURE] Mirror verification failed on one or more mirrors.")
        if exit_on_failure:
            sys.exit(1)
        return False

if __name__ == "__main__":
    target_branch = sys.argv[1] if len(sys.argv) > 1 else "feature/expand-rulesets-v2"
    verify_mirrors(target_branch)
