#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Private .lcf Acceptance Tool (Desensitized & Multi-Stage)
Strictly validates private Loon configuration file for ruleset references,
local rule preemptions, active plugin injections, and First Match Wins precedence.

Failure Modes:
- Missing file / parse failure: exits code 1 with sanitized error code (no paths leaked)
- Local rule preemption (e.g. DOMAIN,drive.google.com,DIRECT): exits code 1
- Remote ruleset precedence violation (e.g. YouTube < Google = False): exits code 1
- Missing required rulesets (< 19 rulesets): exits code 1
- Missing FINAL fallback: exits code 1
- Active unverified plugins: marked UNVERIFIED, cannot grant full pass

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

BENCHMARK_PROBES = [
    {
        "probe": "www.youtube.com",
        "category": "YouTube",
        "expected_ruleset": "YouTube.lsr",
        "desc": "YouTube domain must hit YouTube.lsr before Google.lsr"
    },
    {
        "probe": "googlevideo.com",
        "category": "YouTube",
        "expected_ruleset": "YouTube.lsr",
        "desc": "YouTube CDN domain must hit YouTube.lsr before Google.lsr"
    },
    {
        "probe": "drive.google.com",
        "category": "GoogleDrive",
        "expected_ruleset": "GoogleDrive.lsr",
        "desc": "Google Drive domain must hit GoogleDrive.lsr before Google.lsr"
    },
    {
        "probe": "www.google.com",
        "category": "Google",
        "expected_ruleset": "Google.lsr",
        "desc": "Google general domain must hit Google.lsr"
    },
    {
        "probe": "192.168.1.1",
        "category": "Lan",
        "expected_ruleset": "Lan.lsr",
        "desc": "RFC1918 private IPv4 must hit Lan.lsr before China-GeoIP.lsr"
    },
    {
        "probe": "10.0.0.1",
        "category": "Lan",
        "expected_ruleset": "Lan.lsr",
        "desc": "RFC1918 private IPv4 must hit Lan.lsr before China-GeoIP.lsr"
    },
    {
        "probe": "119.147.195.212",
        "category": "China-GeoIP",
        "expected_ruleset": "China-GeoIP.lsr",
        "desc": "Douyin incident IP must hit China-GeoIP.lsr before FINAL"
    },
    {
        "probe": "240e:97c:2f:1::1",
        "category": "China-GeoIP",
        "expected_ruleset": "China-GeoIP.lsr",
        "desc": "China Telecom IPv6 must hit China-GeoIP.lsr before FINAL"
    },
    {
        "probe": "gateway.push.apple.com",
        "category": "Apple-Push",
        "expected_ruleset": "Apple-Push.lsr",
        "desc": "APNs gateway domain must hit Apple-Push.lsr before China-GeoIP.lsr"
    },
    {
        "probe": "courier.push.apple.com",
        "category": "Apple-Push",
        "expected_ruleset": "Apple-Push.lsr",
        "desc": "APNs courier domain must hit Apple-Push.lsr before China-GeoIP.lsr"
    },
    {
        "probe": "gsa.apple.com",
        "category": "Apple-Direct",
        "expected_ruleset": "Apple-Direct.lsr",
        "desc": "Apple ID auth domain must hit Apple-Direct.lsr"
    },
    {
        "probe": "weixin.qq.com",
        "category": "China-Direct",
        "expected_ruleset": "China-Direct.lsr",
        "desc": "WeChat domain must hit China-Direct.lsr"
    }
]

def verify_private_lcf(lcf_path: str, allow_unverified_plugins: bool = False) -> bool:
    """
    Validates a private .lcf file strictly and desensitized.
    Never prints full file paths, proxies, credentials, or private tokens.
    Returns True if 100% compliant, False otherwise.
    """
    if not lcf_path:
        print("[ERROR] [ERR_FILE_NOT_FOUND] No configuration path provided.")
        return False

    if not os.path.isfile(lcf_path):
        print("[ERROR] [ERR_FILE_NOT_FOUND] Specified configuration file does not exist.")
        return False

    print("============================================================")
    print("[*] Inspecting Configuration: [LOCAL_FILE]")
    print("    (Running in strict local desensitized mode - no credentials, paths, or proxies displayed)")
    print("============================================================")

    try:
        pipeline = simulate_hit.load_lcf_pipeline(lcf_path)
    except Exception:
        print("[ERROR] [ERR_PARSE_FAILED] Failed to parse configuration file syntax.")
        return False

    if not pipeline:
        print("[ERROR] [ERR_LOAD_FAILED] Failed to load rule pipeline from configuration file.")
        return False

    remote_order = pipeline.get("remote_order", [])
    local_rules = pipeline.get("local_rules", [])
    has_final = pipeline.get("has_final", False)
    final_is_last = pipeline.get("final_is_last", True)
    active_plugin_count = pipeline.get("active_plugin_count", 0)

    print(f"\n[+] Total Remote Rulesets Found: {len(remote_order)} (Expected: 19)")
    print("--- Remote Ruleset Sequence ---")
    for idx, rname in enumerate(remote_order):
        print(f"  [{idx:02d}] {rname}")

    errors = []

    # 1. Verify 19 rulesets are present
    missing_rulesets = [r for r in EXPECTED_19_RULESETS if r not in remote_order]
    if missing_rulesets:
        errors.append(f"[ERR_MISSING_RULESET] Missing required rulesets ({len(missing_rulesets)}): {', '.join(missing_rulesets)}")

    if len(remote_order) != 19:
        errors.append(f"[ERR_RULESET_COUNT] Expected exactly 19 remote rulesets, found {len(remote_order)}")

    # 2. Strict Precedence Checks (First Match Wins) between remote rules
    checks = {}

    # YouTube vs Google
    if "YouTube.lsr" in remote_order and "Google.lsr" in remote_order:
        yt_idx = remote_order.index("YouTube.lsr")
        g_idx = remote_order.index("Google.lsr")
        checks["YouTube < Google"] = (yt_idx < g_idx)
        if yt_idx >= g_idx:
            errors.append(f"[ERR_PRECEDENCE_VIOLATION] YouTube.lsr (idx {yt_idx}) is AFTER Google.lsr (idx {g_idx})")
    else:
        checks["YouTube < Google"] = False

    # GoogleDrive vs Google
    if "GoogleDrive.lsr" in remote_order and "Google.lsr" in remote_order:
        gd_idx = remote_order.index("GoogleDrive.lsr")
        g_idx = remote_order.index("Google.lsr")
        checks["GoogleDrive < Google"] = (gd_idx < g_idx)
        if gd_idx >= g_idx:
            errors.append(f"[ERR_PRECEDENCE_VIOLATION] GoogleDrive.lsr (idx {gd_idx}) is AFTER Google.lsr (idx {g_idx})")
    else:
        checks["GoogleDrive < Google"] = False

    # Lan vs China-GeoIP
    if "Lan.lsr" in remote_order and "China-GeoIP.lsr" in remote_order:
        lan_idx = remote_order.index("Lan.lsr")
        geoip_idx = remote_order.index("China-GeoIP.lsr")
        checks["Lan < China-GeoIP"] = (lan_idx < geoip_idx)
        if lan_idx >= geoip_idx:
            errors.append(f"[ERR_PRECEDENCE_VIOLATION] Lan.lsr (idx {lan_idx}) is AFTER China-GeoIP.lsr (idx {geoip_idx})")
    else:
        checks["Lan < China-GeoIP"] = False

    # Apple-Push vs China-GeoIP
    if "Apple-Push.lsr" in remote_order and "China-GeoIP.lsr" in remote_order:
        push_idx = remote_order.index("Apple-Push.lsr")
        geoip_idx = remote_order.index("China-GeoIP.lsr")
        checks["Apple-Push < China-GeoIP"] = (push_idx < geoip_idx)
        if push_idx >= geoip_idx:
            errors.append(f"[ERR_PRECEDENCE_VIOLATION] Apple-Push.lsr (idx {push_idx}) is AFTER China-GeoIP.lsr (idx {geoip_idx})")
    else:
        checks["Apple-Push < China-GeoIP"] = False

    checks["All 19 Rulesets Present"] = (len(missing_rulesets) == 0 and len(remote_order) == 19)

    print("\n--- Desensitized Precedence Check Results ---")
    for check_name, res in checks.items():
        status_tag = "[PASS]" if res else "[FAIL]"
        print(f"  {status_tag:6s} {check_name} = {res}")

    # 3. Multi-Stage First Hit Simulation Check (Local [Rule] vs [Remote Rule])
    print(f"\n--- Multi-Stage Pipeline Evaluation (Local Rules: {len(local_rules)}, Remote Rulesets: {len(remote_order)}) ---")
    rules_by_file = simulate_hit.load_dist_rules(remote_order)
    preemption_errors = []

    for b in BENCHMARK_PROBES:
        probe = b["probe"]
        exp_rs = b["expected_ruleset"]
        matches = simulate_hit.match_target(probe, rules_by_file, local_rules=local_rules)
        if not matches:
            preemption_errors.append(f"[ERR_PROBE_MISS] Probe '{probe}' did not match any rule (expected {exp_rs})")
            continue
        first_hit = matches[0]
        if first_hit["ruleset"] == "Local [Rule]":
            preemption_errors.append(
                f"[ERR_LOCAL_PREEMPTION] Probe '{probe}' ({b['category']}) was preempted by Local [Rule] (line {first_hit['line']}) instead of expected '{exp_rs}'"
            )
        elif first_hit["ruleset"] != exp_rs:
            preemption_errors.append(
                f"[ERR_PRECEDENCE_VIOLATION] Probe '{probe}' ({b['category']}) first hit '{first_hit['ruleset']}' instead of expected '{exp_rs}'"
            )

    if preemption_errors:
        errors.extend(preemption_errors)
        for pe in preemption_errors:
            print(f"  [FAIL] {pe}")
    else:
        print(f"  [PASS] All {len(BENCHMARK_PROBES)} benchmark probes achieved expected first-hit ruleset.")

    # 4. FINAL Rule Check
    print("\n--- Fallback FINAL Rule Check ---")
    if not has_final:
        errors.append("[ERR_FINAL_MISSING] Missing FINAL fallback rule in [Rule] section")
        print("  [FAIL] FINAL rule: MISSING")
    else:
        if not final_is_last:
            errors.append("[ERR_FINAL_NOT_LAST] FINAL rule is not at the end of [Rule] section")
            print("  [FAIL] FINAL rule: Present but not at end of [Rule] section")
        else:
            print("  [PASS] FINAL rule: Present and positioned at end of [Rule] section")

    # 5. Plugin Rule Verification Status
    print("\n--- Plugin Injected Rules Status ---")
    if active_plugin_count > 0:
        print(f"  [-] Plugin Injected Rules: UNVERIFIED")
        print(f"      (Detected {active_plugin_count} active plugin(s); third-party plugin injected rules cannot be verified offline)")
    else:
        print("  [PASS] Plugin Injected Rules: NONE (0 active plugins)")

    # 6. Overall Acceptance Determination
    if errors:
        print("\n[!] Acceptance Failures Detected:")
        for err in errors:
            print(f"  - {err}")
        print("\n============================================================")
        print("[FAIL] Configuration acceptance FAILED: Precedence, rulesets, or local conflicts detected.")
        print("============================================================")
        return False

    if active_plugin_count > 0:
        print("\n============================================================")
        print(f"[PARTIAL_PASS] Precedence, local rules, and FINAL verified.")
        print(f"               Configuration contains {active_plugin_count} unverified active plugin(s).")
        print(f"               Overall Status: UNVERIFIED_PLUGINS")
        print(f"               (Cannot grant FULL PASS without on-device TUN confirmation)")
        print("============================================================")
        if not allow_unverified_plugins:
            return False
        return True

    print("\n============================================================")
    print("[SUCCESS] Configuration acceptance PASSED: 19 rulesets and multi-stage precedence verified.")
    print("============================================================")
    return True

def main():
    parser = argparse.ArgumentParser(description="Desensitized acceptance validator for Loon .lcf files")
    parser.add_argument("lcf_path", nargs="?", default="", help="Path to the .lcf file")
    parser.add_argument("--lcf-path", dest="flag_lcf_path", default="", help="Path to the .lcf file")
    parser.add_argument("--allow-unverified-plugins", action="store_true", default=False,
                        help="Allow conditional pass when plugins are present but unverified")

    args = parser.parse_args()
    target_path = args.flag_lcf_path or args.lcf_path

    if not target_path:
        print("[ERROR] [ERR_FILE_NOT_FOUND] Missing required .lcf file path argument.")
        print("Usage: python scripts/verify_private_lcf.py --lcf-path <PATH_TO_LCF>")
        sys.exit(1)

    ok = verify_private_lcf(target_path, allow_unverified_plugins=args.allow_unverified_plugins)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
