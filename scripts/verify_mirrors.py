#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Mirror & Artifact Verification Tool for Loon Rules
Strictly validates accessibility, byte-integrity, policy-neutrality, and SHA256 matching
across local artifacts (pre-release gate) and remote mirrors (post-release gate).
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import json
import ssl
import hashlib
import argparse
import subprocess
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
MANIFEST_PATH = os.path.join(DIST_DIR, "diagnostics", "manifest.json")
EXPECTED_RULESET_COUNT = 19
DIAGNOSTIC_FILES = [
    "diagnostics/manifest.json",
    "diagnostics/LoonRules-Diagnostic.lpx",
    "diagnostics/loon-rules-diagnostic.js"
]

FORBIDDEN_POLICY_TOKENS = [
    ",PROXY", ",DIRECT", ",REJECT", ",US", ",HK", ",JP", ",Final", ",All"
]

def compute_rule_body_sha256(content_bytes):
    """Computes SHA256 of rule body excluding comments and blank lines."""
    lines = [
        l.strip()
        for l in content_bytes.decode("utf-8", errors="ignore").splitlines()
        if l.strip() and not l.startswith("#") and not l.startswith(";")
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

def get_current_git_branch():
    """Detects current git branch or falls back to main."""
    try:
        res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        branch = res.stdout.strip()
        if branch and branch != "HEAD":
            return branch
    except Exception:
        pass
    return os.getenv("TARGET_BRANCH", "main")

def verify_local_pre_release(dist_dir=DIST_DIR, manifest_path=MANIFEST_PATH, exit_on_failure=True):
    """
    Pre-Release Local Integrity Gate:
    Runs BEFORE git commit/push to guarantee dist/ integrity.
    If ANY check fails, halts pipeline immediately to protect release stability.
    """
    print("[*] Starting Pre-Release Local Integrity Verification...")
    errors = []

    if not os.path.isfile(manifest_path):
        errors.append(f"Manifest missing: {manifest_path}")
        print(f"[FAIL] {errors[-1]}")
        if exit_on_failure:
            sys.exit(1)
        return False

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        errors.append(f"Manifest JSON parse error: {e}")
        print(f"[FAIL] {errors[-1]}")
        if exit_on_failure:
            sys.exit(1)
        return False

    rulesets = manifest.get("rulesets", {})
    if len(rulesets) != EXPECTED_RULESET_COUNT:
        errors.append(f"Expected {EXPECTED_RULESET_COUNT} rulesets in manifest, found {len(rulesets)}")

    # 1. Verify each ruleset file in dist/
    for rname, meta in rulesets.items():
        fpath = os.path.join(dist_dir, rname)
        if not os.path.isfile(fpath):
            errors.append(f"Ruleset file missing: {rname}")
            continue

        size = os.path.getsize(fpath)
        if size == 0:
            errors.append(f"Ruleset file empty (0 bytes): {rname}")
            continue

        with open(fpath, "rb") as f:
            content_bytes = f.read()

        # Policy neutrality check
        content_text = content_bytes.decode("utf-8", errors="ignore")
        for token in FORBIDDEN_POLICY_TOKENS:
            if token in content_text:
                errors.append(f"Forbidden policy token '{token}' in {rname}")

        # Rule count check
        valid_lines = [
            l.strip()
            for l in content_text.splitlines()
            if l.strip() and not l.strip().startswith(("#", ";"))
        ]
        expected_cnt = meta.get("total_rules", 0)
        if len(valid_lines) != expected_cnt:
            errors.append(f"{rname} rule count mismatch: expected {expected_cnt}, got {len(valid_lines)}")

        # SHA-256 check
        expected_sha = meta.get("sha256", "")
        computed_sha = compute_rule_body_sha256(content_bytes)
        if computed_sha != expected_sha:
            errors.append(f"{rname} SHA256 mismatch: expected {expected_sha[:12]}, got {computed_sha[:12]}")

    # 2. Verify diagnostic plugin artifacts in dist/diagnostics/
    lpx_path = os.path.join(dist_dir, "diagnostics", "LoonRules-Diagnostic.lpx")
    js_path = os.path.join(dist_dir, "diagnostics", "loon-rules-diagnostic.js")

    if not os.path.isfile(lpx_path) or os.path.getsize(lpx_path) < 50:
        errors.append("Diagnostic plugin LoonRules-Diagnostic.lpx missing or too small")
    if not os.path.isfile(js_path) or os.path.getsize(js_path) < 1000:
        errors.append("Diagnostic script loon-rules-diagnostic.js missing or too small")

    if errors:
        print(f"\n[FAIL] Pre-release integrity check failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        if exit_on_failure:
            sys.exit(1)
        return False

    print(f"[PASS] Pre-release integrity verified: {len(rulesets)} rulesets and diagnostic artifacts valid.")
    return True

def verify_mirrors(branch=None, manifest_path=MANIFEST_PATH,
                   mirrors=None, exit_on_failure=True, urlopen_fn=None):
    """
    Post-Release Live Mirror Verification:
    Validates accessibility, byte-integrity, and SHA256 matching
    across GitHub Raw and jsDelivr CDN mirrors for rulesets AND diagnostic artifacts.
    """
    if branch is None:
        branch = get_current_git_branch()

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
        remote_manifest = None
        for attempt in range(2):
            try:
                req = urllib.request.Request(man_url, headers=headers)
                with opener(req, context=ctx, timeout=12) if urlopen_fn is None else opener(req) as resp:
                    status = getattr(resp, "status", 200)
                    if status != 200:
                        m_errors.append(f"Remote manifest HTTP {status}")
                        break
                    remote_manifest_bytes = resp.read()
                    remote_manifest = json.loads(remote_manifest_bytes.decode("utf-8"))
                    break
            except Exception as e:
                if attempt == 1:
                    m_errors.append(f"Could not fetch manifest: {e}")

        if not remote_manifest:
            print(f"  [FAIL] Remote manifest inaccessible on {m_name}: {m_errors[-1] if m_errors else 'unknown'}")
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

        # 2. Check diagnostic files (.lpx and .js)
        for diag_rel in ["diagnostics/LoonRules-Diagnostic.lpx", "diagnostics/loon-rules-diagnostic.js"]:
            diag_url = f"{base_url}/{diag_rel}"
            diag_fetched = False
            for attempt in range(2):
                try:
                    d_req = urllib.request.Request(diag_url, headers=headers)
                    with opener(d_req, context=ctx, timeout=12) if urlopen_fn is None else opener(d_req) as d_resp:
                        d_status = getattr(d_resp, "status", 200)
                        if d_status != 200:
                            m_errors.append(f"{diag_rel}: HTTP {d_status}")
                            diag_fetched = True
                            break
                        d_bytes = d_resp.read()
                        if len(d_bytes) < 50:
                            m_errors.append(f"{diag_rel}: File too small ({len(d_bytes)} bytes)")
                        diag_fetched = True
                        break
                except Exception as e:
                    if attempt == 1:
                        m_errors.append(f"{diag_rel}: Fetch failed: {e}")
            if not diag_fetched and len(m_errors) == 0:
                m_errors.append(f"{diag_rel}: Fetch failed after retries")

        # 3. Check each ruleset
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
            print(f"  [PASS] Verified 19/19 rulesets and diagnostic artifacts on {m_name}.")

    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All mirrors verified completely with zero errors.")
        return True
    else:
        print("[FAILURE] Mirror verification failed on one or more mirrors.")
        if exit_on_failure:
            sys.exit(1)
        return False

def main():
    parser = argparse.ArgumentParser(description="Verify Loon rules artifacts locally or across mirrors.")
    parser.add_argument("--pre-release", "--local-only", dest="pre_release", action="store_true",
                        help="Run pre-release local integrity gate on dist/ directory.")
    parser.add_argument("--post-release", dest="post_release", action="store_true",
                        help="Run post-release remote mirror and CDN verification.")
    parser.add_argument("--branch", dest="branch", default=None,
                        help="Target git branch to verify on remote mirrors.")
    args = parser.parse_args()

    if args.pre_release:
        verify_local_pre_release(exit_on_failure=True)
    else:
        verify_mirrors(branch=args.branch, exit_on_failure=True)

if __name__ == "__main__":
    main()
