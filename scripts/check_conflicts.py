#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Border Shared Infrastructure & Ruleset Conflict Checker
Scans Loon rulesets and plugins against shared_domains.yml to prevent:
  1. Domestic vs Overseas twin product collisions (Douyin vs TikTok, WeChat vs WeChat Int'l).
  2. Overseas-exclusive domains accidentally placed into domestic direct rulesets.
  3. DNS plugin misdirection for cross-border shared infrastructure.

Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
SPEC_PATH = os.path.join(BASE_DIR, "shared_domains.yml")
DNS_PLUGIN_PATH = os.path.join(BASE_DIR, "plugins", "Loon-China-DNS.lpx")

def load_ruleset_domains(dist_dir=DIST_DIR):
    """
    Parses all rulesets in dist_dir and maps ruleset_name -> list of (rule_type, domain).
    """
    rules_by_file = {}
    if not os.path.isdir(dist_dir):
        return rules_by_file

    for fname in sorted(os.listdir(dist_dir)):
        if not fname.endswith(".lsr"):
            continue
        fpath = os.path.join(dist_dir, fname)
        entries = []
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                l = line.strip()
                if not l or l.startswith(("#", ";")):
                    continue
                parts = l.split(",")
                rtype = parts[0].strip()
                if rtype in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD") and len(parts) >= 2:
                    domain = parts[1].strip().lower()
                    entries.append((rtype, domain))
        rules_by_file[fname] = entries
    return rules_by_file

def load_dns_plugin_hosts(plugin_path=DNS_PLUGIN_PATH, preserve_patterns=False):
    """
    Extracts all mapped host patterns from Loon DNS plugin.
    """
    hosts = []
    if not os.path.isfile(plugin_path):
        return hosts
    with open(plugin_path, "r", encoding="utf-8", errors="ignore") as f:
        in_host = False
        for line in f:
            l = line.strip()
            if l.startswith("[Host]"):
                in_host = True
                continue
            if l.startswith("[") and in_host:
                break
            if in_host and "=" in l:
                left = l.split("=")[0].strip().lower()
                if not preserve_patterns:
                    left = left.lstrip("*.")
                if left:
                    hosts.append(left)
    return hosts

def load_dns_plugin_entries(plugin_path=DNS_PLUGIN_PATH):
    """
    Parses all mapped host entries from Loon DNS plugin with line numbers and malformed line detection.
    Returns list of dicts:
      {"line_no": int, "left": str, "right": str, "raw": str, "error": Optional[str]}
    """
    entries = []
    if not os.path.isfile(plugin_path):
        return entries
    with open(plugin_path, "r", encoding="utf-8", errors="ignore") as f:
        in_host = False
        for line_no, raw_line in enumerate(f, 1):
            line = raw_line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[Host]"):
                in_host = True
                continue
            if line.startswith("[") and in_host:
                break
            if in_host:
                if "=" not in line:
                    entries.append({
                        "line_no": line_no,
                        "left": "",
                        "right": "",
                        "raw": line,
                        "error": f"Malformed line without '=' delimiter in [Host]: '{line}'"
                    })
                    continue
                parts = line.split("=", 1)
                left = parts[0].strip()
                right = parts[1].strip()
                if not left or not right:
                    entries.append({
                        "line_no": line_no,
                        "left": left,
                        "right": right,
                        "raw": line,
                        "error": f"Malformed line with empty host or target in [Host]: '{line}'"
                    })
                    continue
                entries.append({
                    "line_no": line_no,
                    "left": left,
                    "right": right,
                    "raw": line,
                    "error": None
                })
    return entries

def check_conflicts(spec_path=SPEC_PATH, dist_dir=DIST_DIR, dns_path=DNS_PLUGIN_PATH, strict=False):
    """
    Runs comprehensive conflict and shared domain boundary checks.
    Returns (bool success, list errors, list warnings).
    """
    if not os.path.isfile(spec_path):
        return False, [f"Specification file missing: {spec_path}"], []

    with open(spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    categories = spec.get("ruleset_categories", {})
    overseas_rulesets = set(categories.get("overseas_proxy", []))
    domestic_rulesets = set(categories.get("domestic_direct", []))
    ecosystems = spec.get("ecosystems", {})

    rules_by_file = load_ruleset_domains(dist_dir)
    dns_hosts = load_dns_plugin_hosts(dns_path, preserve_patterns=True)

    errors = []
    warnings = []

    print("[*] Starting Shared Infrastructure and Boundary Collision Check...")

    # Check 1: Verify overseas-exclusive domains are NOT in domestic rulesets
    for eco_name, eco in ecosystems.items():
        overseas_exclusive = eco.get("overseas_exclusive_domains", [])
        domestic_sets = eco.get("current_domestic_rulesets", [r for r in domestic_rulesets])

        for d_set in domestic_sets:
            if d_set not in rules_by_file:
                continue
            set_domains = [d for _, d in rules_by_file[d_set]]
            for o_dom in overseas_exclusive:
                for set_d in set_domains:
                    if set_d == o_dom or set_d.endswith("." + o_dom):
                        errors.append(
                            f"[{eco_name}] Overseas-exclusive domain '{o_dom}' leaked into domestic ruleset '{d_set}' (found '{set_d}')"
                        )

    # Check 2: Verify DNS plugin does not direct overseas-exclusive domains to domestic DNS
    for eco_name, eco in ecosystems.items():
        overseas_exclusive = eco.get("overseas_exclusive_domains", [])
        for o_dom in overseas_exclusive:
            for host in dns_hosts:
                if host == o_dom or host.endswith("." + o_dom):
                    errors.append(
                        f"[{eco_name}] Overseas-exclusive domain '{o_dom}' illegally routed to domestic DNS in {os.path.basename(dns_path)} (entry: '{host}')"
                    )

    # Check 2a: Verify DNS plugin does not route overseas proxy ruleset domains (e.g. google.com, twitter.com) to domestic DNS
    for o_set in sorted(overseas_rulesets):
        if o_set not in rules_by_file:
            continue
        for rtype, o_dom in rules_by_file[o_set]:
            is_shared = False
            for eco in ecosystems.values():
                if o_dom in eco.get("shared_infrastructure_domains", []) or any(o_dom.endswith("." + s) for s in eco.get("shared_infrastructure_domains", [])):
                    is_shared = True
                    break
            if is_shared:
                continue
            for host in dns_hosts:
                clean_h = host.lstrip("*.")
                if clean_h == o_dom or clean_h.endswith("." + o_dom):
                    errors.append(
                        f"[{o_set}] Overseas proxy domain '{o_dom}' illegally routed to domestic DNS in {os.path.basename(dns_path)} (entry: '{host}')"
                    )

    # Check 2b: Verify DNS plugin does not route forbidden infrastructure domains to domestic DNS
    for eco_name, eco in ecosystems.items():
        forbidden_dns = eco.get("forbidden_domestic_dns_domains", [])
        allowed_exact_dns = set(eco.get("allowed_exact_domestic_dns_hosts", []))
        for f_dom in forbidden_dns:
            for host in dns_hosts:
                clean_h = host.lstrip("*.")
                if host in allowed_exact_dns and "*" not in host and clean_h not in forbidden_dns:
                    continue
                if clean_h == f_dom or clean_h.endswith("." + f_dom) or (host.startswith("*.") and f_dom.endswith("." + clean_h)):
                    errors.append(
                        f"[{eco_name}] Red line violation: Forbidden domain '{f_dom}' illegally routed to domestic DNS in {os.path.basename(dns_path)} (entry: '{host}')"
                    )

    # Check 2c: Verify DNS plugin entries have valid transport, no plaintext/unapproved DoH, and no malformed syntax
    trusted_domestic_dns = set(spec.get("trusted_domestic_dns_endpoints", [
        "https://223.5.5.5/dns-query",
        "https://223.6.6.6/dns-query",
    ]))
    from urllib.parse import urlparse

    dns_entries = load_dns_plugin_entries(dns_path)
    for entry in dns_entries:
        l_no = entry["line_no"]
        if entry["error"]:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: {entry['error']}")
            continue
        right = entry["right"]

        if not right.startswith("server:"):
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Missing 'server:' prefix in target '{right}'")
            continue

        endpoint = right[len("server:"):].strip()

        if endpoint.startswith("http://"):
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Plaintext HTTP DNS forbidden in '{right}'")
            continue
        elif not endpoint.startswith("https://"):
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Plaintext UDP or unsupported DNS transport forbidden in '{right}'")
            continue

        try:
            parsed = urlparse(endpoint)
            explicit_port = parsed.port
        except ValueError as e:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Invalid URL structure '{endpoint}': {e}")
            continue

        if parsed.username or parsed.password:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Userinfo forbidden in DNS endpoint '{endpoint}'")
        elif explicit_port is not None:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Explicit port forbidden in DNS endpoint '{endpoint}'")
        elif parsed.fragment:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Fragment forbidden in DNS endpoint '{endpoint}'")
        elif parsed.query:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Query parameters forbidden in domestic DNS endpoint '{endpoint}'")
        elif endpoint not in trusted_domestic_dns:
            errors.append(f"[{os.path.basename(dns_path)}] Line {l_no}: Untrusted domestic DNS endpoint '{endpoint}' (allowed: {sorted(trusted_domestic_dns)})")

    # Check 3: Audit shared infrastructure domains placement across Proxy vs Direct
    for eco_name, eco in ecosystems.items():
        shared = eco.get("shared_infrastructure_domains", [])
        allowed_subdomains = set(eco.get("allowed_subdomain_delegations", []))

        for s_dom in shared:
            claimed_overseas = []
            claimed_domestic = []

            for rname, entries in rules_by_file.items():
                for _, dom in entries:
                    if dom == s_dom or dom.endswith("." + s_dom):
                        if dom in allowed_subdomains:
                            continue
                        if rname in overseas_rulesets:
                            claimed_overseas.append((rname, dom))
                        elif rname in domestic_rulesets:
                            claimed_domestic.append((rname, dom))

            if claimed_overseas and claimed_domestic:
                msg = (f"[{eco_name}] Shared domain '{s_dom}' collision: "
                       f"claimed by overseas {claimed_overseas} AND domestic {claimed_domestic}")
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # Check 4: China-Baseline guard validation (static layer security, hash lock, and boundary enforcement)
    guard_cfg = spec.get("china_baseline_guard", {})
    if guard_cfg.get("enabled", False):
        baseline_rel = guard_cfg.get("baseline_file", "rules/custom/China-Baseline.list")
        baseline_path = os.path.join(BASE_DIR, baseline_rel)
        if not os.path.isfile(baseline_path):
            errors.append(f"[China-Baseline] Required baseline file missing: {baseline_rel}")
        else:
            with open(baseline_path, "r", encoding="utf-8") as bf:
                raw_lines = bf.readlines()
            bl_rules = []
            syntax_errors = []
            for l_idx, line in enumerate(raw_lines, 1):
                clean_l = line.strip()
                if not clean_l or clean_l.startswith(("#", ";")):
                    continue
                parts = clean_l.split(",")
                if len(parts) != 2 or parts[0] not in ("DOMAIN", "DOMAIN-SUFFIX") or "*" in parts[1]:
                    syntax_errors.append(f"Line {l_idx}: invalid rule or non-neutral policy '{clean_l}'")
                else:
                    bl_rules.append((parts[0], parts[1].strip().lower()))

            if syntax_errors:
                errors.extend([f"[China-Baseline] Syntax/neutrality error: {se}" for se in syntax_errors])

            # Pinned body SHA256 check
            normalized_body = "\n".join([f"{rtype},{val}" for rtype, val in bl_rules]) + "\n"
            import hashlib
            body_sha = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
            pinned_sha = guard_cfg.get("pinned_body_sha256", "")
            if pinned_sha and body_sha != pinned_sha:
                errors.append(
                    f"[China-Baseline] Pinned body hash mismatch: expected {pinned_sha}, got {body_sha}. "
                    "Static baseline requires deliberate AI review before hash updates."
                )

            expected_cnt = guard_cfg.get("expected_rule_count")
            if expected_cnt and len(bl_rules) != expected_cnt:
                errors.append(
                    f"[China-Baseline] Rule count mismatch: expected {expected_cnt}, got {len(bl_rules)}"
                )

            # Forbidden boundary check
            forbidden_boundaries = set(guard_cfg.get("forbidden_boundary_domains", []))
            for rtype, val in bl_rules:
                for fb in forbidden_boundaries:
                    if val == fb or val.endswith("." + fb):
                        errors.append(
                            f"[China-Baseline] Forbidden boundary domain violation: '{val}' matches forbidden '{fb}'"
                        )

            # Ambiguous keywords check
            ambiguous_keywords = guard_cfg.get("ambiguous_keywords", [])
            for rtype, val in bl_rules:
                for kw in ambiguous_keywords:
                    if kw in val:
                        errors.append(
                            f"[China-Baseline] Ambiguous infrastructure keyword violation: '{val}' contains '{kw}'"
                        )

            # Bidirectional overlap check with overseas rulesets
            for o_set in overseas_rulesets:
                if o_set not in rules_by_file:
                    continue
                for o_type, o_dom in rules_by_file[o_set]:
                    for rtype, val in bl_rules:
                        if val == o_dom or (rtype == "DOMAIN-SUFFIX" and o_dom.endswith("." + val)) or (o_type == "DOMAIN-SUFFIX" and val.endswith("." + o_dom)):
                            errors.append(
                                f"[China-Baseline] Overseas collision with {o_set} ({o_type},{o_dom}): baseline rule ({rtype},{val})"
                            )

    # Print results
    if warnings:
        print(f"\n[!] Detected {len(warnings)} shared domain advisory warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[FAIL] Detected {len(errors)} critical conflict/leak error(s):")
        for e in errors:
            print(f"  - {e}")
        return False, errors, warnings

    print(f"[PASS] Zero unauthorized collisions or overseas leaks detected across {len(rules_by_file)} rulesets and DNS plugins.")
    return True, [], warnings

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check cross-ruleset shared domain conflicts.")
    parser.add_argument("--strict", action="store_true", help="Treat advisory warnings as fatal errors.")
    parser.add_argument("--spec", default=SPEC_PATH, help="Path to shared_domains.yml")
    args = parser.parse_args()

    success, errors, warnings = check_conflicts(spec_path=args.spec, strict=args.strict)
    if not success:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
