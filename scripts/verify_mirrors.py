#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mirror and Release Gate Verifier for Loon Rulesets and Diagnostic Artifacts
Provides two essential verification gates:
  1. Pre-Release Local Integrity Gate (--pre-release):
     Strict local validation of dist/ rulesets, diagnostic artifacts, manifest metadata,
     and recomputed package signature before git commit/push.
  2. Post-Release Live Mirror Verifier (--post-release):
     Tests live mirrors (GitHub Raw, jsDelivr CDN) with finite retries for CDN propagation,
     strict manifest completeness, diagnostic artifact hashes, and package signature.

Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import json
import time
import ssl
import hashlib
import urllib.request
import subprocess
import argparse

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

def compute_package_sha256(ruleset_metadata, diagnostic_metadata):
    """
    Computes deterministic SHA256 package signature across sorted rulesets
    and diagnostic artifacts metadata.
    """
    pkg_h = hashlib.sha256()
    for rname in sorted(ruleset_metadata.keys()):
        m = ruleset_metadata[rname]
        pkg_h.update(f"{rname}:{m.get('sha256', '')}:{m.get('revision', '')}:{m.get('total_rules', 0)}\n".encode("utf-8"))
    for dname in sorted(diagnostic_metadata.keys()):
        dm = diagnostic_metadata[dname]
        pkg_h.update(f"{dname}:{dm.get('sha256', '')}:{dm.get('size', 0)}\n".encode("utf-8"))
    return pkg_h.hexdigest()

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

    # Check required top-level manifest fields
    for req_field in ["rulesets", "diagnostic_artifacts", "package_sha256", "content_revision"]:
        if req_field not in manifest:
            errors.append(f"Manifest missing required '{req_field}' field")

    rulesets = manifest.get("rulesets", {})
    if not isinstance(rulesets, dict) or len(rulesets) != EXPECTED_RULESET_COUNT:
        errors.append(f"Expected {EXPECTED_RULESET_COUNT} rulesets in manifest, found {len(rulesets) if isinstance(rulesets, dict) else 0}")

    # Check diagnostic_artifacts structure in manifest
    diag_meta = manifest.get("diagnostic_artifacts")
    if not isinstance(diag_meta, dict):
        errors.append("Manifest 'diagnostic_artifacts' must be a JSON object")
        diag_meta = {}

    for d_fname in ["LoonRules-Diagnostic.lpx", "loon-rules-diagnostic.js"]:
        if d_fname not in diag_meta:
            errors.append(f"Manifest missing diagnostic artifact metadata: {d_fname}")
        else:
            dm = diag_meta[d_fname]
            if not isinstance(dm, dict):
                errors.append(f"Manifest diagnostic artifact {d_fname} must be a dictionary")
            else:
                if "sha256" not in dm or not isinstance(dm["sha256"], str) or len(dm["sha256"]) != 64:
                    errors.append(f"Manifest diagnostic artifact {d_fname} has missing or invalid sha256")
                if "size" not in dm or not isinstance(dm["size"], int) or dm["size"] <= 50:
                    errors.append(f"Manifest diagnostic artifact {d_fname} has missing or invalid size")

    # 1. Verify each ruleset file in dist/
    if isinstance(rulesets, dict):
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

    # 2. Verify diagnostic plugin artifacts in dist/diagnostics/ with SHA256 integrity
    for d_fname in ["LoonRules-Diagnostic.lpx", "loon-rules-diagnostic.js"]:
        fpath = os.path.join(dist_dir, "diagnostics", d_fname)
        if not os.path.isfile(fpath):
            errors.append(f"Diagnostic artifact missing: {d_fname}")
            continue
        size = os.path.getsize(fpath)
        if size < 50:
            errors.append(f"Diagnostic artifact too small ({size} bytes): {d_fname}")
            continue
        with open(fpath, "rb") as df:
            raw_bytes = df.read()
            computed_d_sha = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
        if d_fname in diag_meta and isinstance(diag_meta[d_fname], dict):
            expected_d_sha = diag_meta[d_fname].get("sha256", "")
            if computed_d_sha != expected_d_sha:
                errors.append(f"Diagnostic artifact {d_fname} SHA256 mismatch: expected {expected_d_sha[:12]}, got {computed_d_sha[:12]}")
        # Also verify against source file in diagnostics/
        src_fpath = os.path.join(BASE_DIR, "diagnostics", d_fname)
        if os.path.isfile(src_fpath):
            with open(src_fpath, "rb") as sf:
                src_sha = hashlib.sha256(sf.read().replace(b"\r\n", b"\n")).hexdigest()
            if computed_d_sha != src_sha:
                errors.append(f"Diagnostic artifact {d_fname} does not match source file in diagnostics/ (SHA mismatch)")

    # 3. Verify package signature and content revision self-check
    declared_pkg_sha = manifest.get("package_sha256", "")
    if not declared_pkg_sha or not isinstance(declared_pkg_sha, str) or len(declared_pkg_sha) != 64:
        errors.append("Manifest 'package_sha256' missing or invalid 64-character hex format")
    else:
        computed_pkg_sha = compute_package_sha256(rulesets, diag_meta)
        if declared_pkg_sha != computed_pkg_sha:
            errors.append(f"Manifest package_sha256 self-check failed: expected {computed_pkg_sha[:12]}, declared {declared_pkg_sha[:12]}")

    declared_rev = manifest.get("content_revision", "")
    if declared_pkg_sha and declared_rev != declared_pkg_sha[:12]:
        errors.append(f"Manifest content_revision mismatch: expected {declared_pkg_sha[:12]}, declared {declared_rev}")

    if errors:
        print(f"\n[FAIL] Pre-release integrity check failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        if exit_on_failure:
            sys.exit(1)
        return False

    print(f"[PASS] Pre-release integrity verified: {len(rulesets)} rulesets, diagnostic artifacts, and package signature valid.")
    return True

def purge_jsdelivr_artifacts(branch, items, opener=None):
    """
    Sends explicit purge requests to jsDelivr Purge API for specified artifacts.
    """
    op = opener or urllib.request.urlopen
    purged = 0
    for item in items:
        # Standardize item relative path
        rel_item = item.replace("\\", "/").lstrip("/")
        if not rel_item.startswith("dist/"):
            rel_item = f"dist/{rel_item}"
        p_url = f"https://purge.jsdelivr.net/gh/o-ocn/loon-rules@{branch}/{rel_item}"
        try:
            req = urllib.request.Request(p_url, headers={"User-Agent": "Mozilla/5.0 LoonPurge/2.0"})
            with op(req, timeout=5) as resp:
                if getattr(resp, "status", 200) in (200, 204):
                    purged += 1
        except Exception:
            pass
    return purged

def verify_mirrors(branch=None, manifest_path=MANIFEST_PATH,
                   mirrors=None, exit_on_failure=True, urlopen_fn=None,
                   max_retries=3, retry_delay_sec=6.0, soft_cdn=False):
    """
    Post-Release Live Mirror Verification:
    Validates accessibility, byte-integrity, and SHA256 matching
    across GitHub Raw and jsDelivr CDN mirrors for rulesets AND diagnostic artifacts.
    Includes finite retries for CDN propagation delay with explicit timeout / desync reporting.
    When soft_cdn=True, CDN propagation desync emits a warning instead of failing the release
    provided GitHub Raw passes 100%.
    """
    if branch is None:
        branch = get_current_git_branch()

    print(f"[*] Starting Live Mirror Verification on branch '{branch}' (soft_cdn={soft_cdn})...")

    if not os.path.isfile(manifest_path):
        print(f"[FAIL] Local manifest not found: {manifest_path}")
        if exit_on_failure:
            sys.exit(1)
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        local_manifest = json.load(f)

    # Local manifest self-validation
    for req_field in ["rulesets", "diagnostic_artifacts", "package_sha256", "content_revision"]:
        if req_field not in local_manifest:
            print(f"[FAIL] Local manifest missing required '{req_field}' field")
            if exit_on_failure:
                sys.exit(1)
            return False

    rulesets = local_manifest.get("rulesets", {})
    print(f"[*] Local manifest declares {len(rulesets)} rulesets.")
    if len(rulesets) != EXPECTED_RULESET_COUNT:
        print(f"[FAIL] Expected {EXPECTED_RULESET_COUNT} rulesets in manifest, found {len(rulesets)}")
        if exit_on_failure:
            sys.exit(1)
        return False

    local_diag_meta = local_manifest.get("diagnostic_artifacts")
    if not isinstance(local_diag_meta, dict):
        print("[FAIL] Local manifest 'diagnostic_artifacts' must be a dictionary")
        if exit_on_failure:
            sys.exit(1)
        return False

    for d_fname in ["LoonRules-Diagnostic.lpx", "loon-rules-diagnostic.js"]:
        if d_fname not in local_diag_meta:
            print(f"[FAIL] Local manifest missing diagnostic artifact metadata: {d_fname}")
            if exit_on_failure:
                sys.exit(1)
            return False

    local_pkg_sha = local_manifest.get("package_sha256", "")
    computed_local_pkg_sha = compute_package_sha256(rulesets, local_diag_meta)
    if local_pkg_sha != computed_local_pkg_sha:
        print(f"[FAIL] Local manifest package_sha256 self-check failed: expected {computed_local_pkg_sha[:12]}, declared {local_pkg_sha[:12]}")
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
        mirror_success = False
        is_cdn = "jsdelivr" in base_url.lower()

        # If checking jsDelivr live mirror and not a mock unit test, trigger a proactive purge
        if is_cdn and urlopen_fn is None:
            purge_items = list(rulesets.keys()) + DIAGNOSTIC_FILES
            purge_jsdelivr_artifacts(branch, purge_items, opener=opener)

        for attempt in range(max_retries):
            m_errors = []
            man_url = f"{base_url}/diagnostics/manifest.json"
            remote_manifest = None

            # Attempt to fetch remote manifest
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

            if not remote_manifest:
                if attempt < max_retries - 1 and urlopen_fn is None:
                    print(f"  [-] {m_name} manifest fetch attempt {attempt + 1}/{max_retries} failed. Retrying in {retry_delay_sec}s...")
                    time.sleep(retry_delay_sec)
                    continue
                break

            # 1. Validate remote manifest required fields
            for req_field in ["rulesets", "diagnostic_artifacts", "package_sha256", "content_revision"]:
                if req_field not in remote_manifest:
                    m_errors.append(f"Remote manifest missing required '{req_field}' field")

            remote_rulesets = remote_manifest.get("rulesets", {})
            if not isinstance(remote_rulesets, dict) or len(remote_rulesets) != EXPECTED_RULESET_COUNT:
                m_errors.append(f"Manifest ruleset count mismatch: expected {EXPECTED_RULESET_COUNT}, got {len(remote_rulesets) if isinstance(remote_rulesets, dict) else 0}")

            remote_rev = remote_manifest.get("content_revision") or remote_manifest.get("release_commit", "")
            if local_rev and remote_rev and local_rev != remote_rev:
                m_errors.append(f"Revision mismatch: local {local_rev}, remote {remote_rev}")

            remote_diag_meta = remote_manifest.get("diagnostic_artifacts")
            if not isinstance(remote_diag_meta, dict):
                m_errors.append("Remote manifest 'diagnostic_artifacts' is missing or not a dictionary")
                remote_diag_meta = {}

            for d_name in ["LoonRules-Diagnostic.lpx", "loon-rules-diagnostic.js"]:
                if d_name not in remote_diag_meta:
                    m_errors.append(f"Remote manifest missing diagnostic artifact entry: {d_name}")
                else:
                    r_d_info = remote_diag_meta[d_name]
                    exp_d_info = local_diag_meta.get(d_name, {})
                    if not isinstance(r_d_info, dict):
                        m_errors.append(f"Remote manifest diagnostic artifact {d_name} must be a dictionary")
                    else:
                        if r_d_info.get("sha256") != exp_d_info.get("sha256"):
                            m_errors.append(f"Remote manifest diagnostic artifact {d_name} SHA256 mismatch (expected {exp_d_info.get('sha256', '')[:12]}, got {r_d_info.get('sha256', '')[:12]})")
                        if r_d_info.get("size") != exp_d_info.get("size"):
                            m_errors.append(f"Remote manifest diagnostic artifact {d_name} size mismatch (expected {exp_d_info.get('size')}, got {r_d_info.get('size')})")

            remote_pkg_sha = remote_manifest.get("package_sha256", "")
            if not remote_pkg_sha or not isinstance(remote_pkg_sha, str) or len(remote_pkg_sha) != 64:
                m_errors.append("Remote manifest 'package_sha256' missing or invalid 64-character format")
            else:
                computed_remote_pkg_sha = compute_package_sha256(remote_rulesets, remote_diag_meta)
                if remote_pkg_sha != computed_remote_pkg_sha:
                    m_errors.append(f"Remote manifest package signature self-check failed: computed {computed_remote_pkg_sha[:12]}, declared {remote_pkg_sha[:12]}")
                if local_pkg_sha != remote_pkg_sha:
                    m_errors.append(f"Package signature mismatch: local {local_pkg_sha[:12]}, remote {remote_pkg_sha[:12]}")

            # Check that remote manifest ruleset metadata has NOT been tampered
            if isinstance(remote_rulesets, dict):
                for rname, meta in rulesets.items():
                    if rname not in remote_rulesets:
                        m_errors.append(f"Remote manifest missing ruleset entry: {rname}")
                        continue
                    r_meta = remote_rulesets[rname]
                    if not isinstance(r_meta, dict):
                        m_errors.append(f"Remote manifest entry {rname} is not a dictionary")
                        continue
                    if r_meta.get("sha256") != meta.get("sha256"):
                        m_errors.append(f"Remote manifest metadata tampered for {rname}: SHA256 mismatch (expected {meta['sha256'][:12]}, got {r_meta.get('sha256', '')[:12]})")
                    if r_meta.get("total_rules") != meta.get("total_rules"):
                        m_errors.append(f"Remote manifest metadata tampered for {rname}: rule count mismatch (expected {meta['total_rules']}, got {r_meta.get('total_rules')})")

            # If revision mismatch or manifest errors occur, attempt retry for CDN propagation
            if m_errors and any("Revision mismatch" in e or "Could not fetch" in e for e in m_errors):
                if attempt < max_retries - 1:
                    print(f"  [-] {m_name} synchronization pending ({m_errors[0]}). Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay_sec}s...")
                    if urlopen_fn is None and ("fastly.jsdelivr.net" in base_url or "jsdelivr.net" in base_url):
                        try:
                            p_req = urllib.request.Request(man_url, method="PURGE")
                            opener(p_req, timeout=5)
                        except Exception:
                            pass
                    time.sleep(retry_delay_sec)
                    continue

            # 2. Check diagnostic files (.lpx and .js) with full SHA256 verification
            for diag_rel in ["diagnostics/LoonRules-Diagnostic.lpx", "diagnostics/loon-rules-diagnostic.js"]:
                diag_fname = os.path.basename(diag_rel)
                diag_url = f"{base_url}/{diag_rel}"
                diag_fetched = False
                try:
                    d_req = urllib.request.Request(diag_url, headers=headers)
                    with opener(d_req, context=ctx, timeout=12) if urlopen_fn is None else opener(d_req) as d_resp:
                        d_status = getattr(d_resp, "status", 200)
                        if d_status != 200:
                            m_errors.append(f"{diag_rel}: HTTP {d_status}")
                        else:
                            d_bytes = d_resp.read()
                            if len(d_bytes) < 50:
                                m_errors.append(f"{diag_rel}: File too small ({len(d_bytes)} bytes)")
                            exp_sha = local_diag_meta.get(diag_fname, {}).get("sha256")
                            if exp_sha:
                                actual_sha = hashlib.sha256(d_bytes.replace(b"\r\n", b"\n")).hexdigest()
                                if actual_sha != exp_sha:
                                    m_errors.append(f"{diag_rel}: SHA256 mismatch (expected {exp_sha[:12]}, got {actual_sha[:12]})")
                            diag_fetched = True
                except Exception as e:
                    m_errors.append(f"{diag_rel}: Fetch failed: {e}")

            # 3. Check each ruleset file
            match_count = 0
            for rname, meta in rulesets.items():
                expected_sha = meta["sha256"]
                rule_url = f"{base_url}/{rname}"
                fetched = False
                try:
                    r_req = urllib.request.Request(rule_url, headers=headers)
                    with opener(r_req, context=ctx, timeout=12) if urlopen_fn is None else opener(r_req) as r_resp:
                        r_status = getattr(r_resp, "status", 200)
                        if r_status != 200:
                            m_errors.append(f"{rname}: HTTP {r_status}")
                        else:
                            body_bytes = r_resp.read()
                            computed_sha = compute_rule_body_sha256(body_bytes)
                            if computed_sha == expected_sha:
                                match_count += 1
                            else:
                                m_errors.append(f"{rname}: SHA256 mismatch (expected {expected_sha[:12]}, got {computed_sha[:12]})")
                            fetched = True
                except Exception as e:
                    m_errors.append(f"{rname}: Fetch failed: {e}")

            if not m_errors:
                mirror_success = True
                mirror_reports[m_name] = {"passed": True, "errors": [], "matched": match_count}
                print(f"  [OK] Remote manifest accessible. Declares {len(remote_rulesets)} rulesets (revision: {remote_rev}).")
                print(f"  [PASS] Verified 19/19 rulesets and diagnostic artifacts on {m_name}.")
                break
            else:
                if attempt < max_retries - 1:
                    print(f"  [-] {m_name} encountered {len(m_errors)} verification error(s). Attempt {attempt + 1}/{max_retries}. Retrying in {retry_delay_sec}s...")
                    time.sleep(retry_delay_sec)
                else:
                    break

        if not mirror_success:
            mirror_reports[m_name] = {"passed": False, "errors": m_errors}
            if is_cdn and soft_cdn:
                print(f"  [WARN/SOFT_GATE] {m_name} edge propagation in progress ({len(m_errors)} desync items after {max_retries} attempts).")
                print("  [WARN/SOFT_GATE] Treated as non-fatal warning per soft_cdn policy (GitHub Raw is primary source of truth).")
                for err in m_errors[:5]:
                    print(f"    - {err}")
            else:
                all_passed = False
                print(f"  [TIMEOUT/FAIL] {m_name} encountered {len(m_errors)} error(s) after {max_retries} attempt(s):")
                for err in m_errors[:5]:
                    print(f"    - {err}")
                if len(m_errors) > 5:
                    print(f"    - ... and {len(m_errors) - 5} more error(s)")

    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All mirrors verified completely with zero fatal errors.")
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
    parser.add_argument("--retries", dest="retries", type=int, default=3,
                        help="Maximum retry attempts for remote CDN verification.")
    parser.add_argument("--retry-delay", dest="retry_delay", type=float, default=6.0,
                        help="Seconds to wait between CDN retry attempts.")
    parser.add_argument("--soft-cdn", dest="soft_cdn", action="store_true",
                        help="Treat secondary CDN propagation latency as non-fatal warning if primary mirror passes.")
    args = parser.parse_args()

    if args.pre_release:
        verify_local_pre_release(exit_on_failure=True)
    else:
        verify_mirrors(branch=args.branch, exit_on_failure=True,
                       max_retries=args.retries, retry_delay_sec=args.retry_delay,
                       soft_cdn=args.soft_cdn)

if __name__ == "__main__":
    main()
