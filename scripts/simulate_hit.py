#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rule Hit Simulator (Strategy-Neutral, Multi-Stage Evaluation)
Simulates top-to-bottom rule evaluation order in Loon:
  Stage 1: Local [Rule] (configuration file local rules, sanitized)
  Stage 2: Plugin [Rule] (active plugin injected rules)
  Stage 3: [Remote Rule] (remote subscription rulesets in declaration order)
  Stage 4: FINAL (fallback default rule)
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import re
import ipaddress

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")

DEFAULT_REMOTE_RULE_ORDER = [
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

def parse_rule_line(raw_line, line_idx=0):
    clean = raw_line.strip()
    if not clean or clean.startswith(("#", ";")):
        return None
    # Strip policy / actions if present (e.g. DOMAIN,foo.com,DIRECT -> DOMAIN,foo.com)
    parts = [p.strip() for p in clean.split(",")]
    if not parts:
        return None
    rtype = parts[0].upper()
    rval = parts[1].strip() if len(parts) > 1 else ""
    options = [p.strip() for p in parts[2:]]
    return {
        "type": rtype,
        "value": rval,
        "options": options,
        "raw": f"{rtype},{rval}" if rval else rtype,
        "line": line_idx
    }

def is_ip(val):
    try:
        ipaddress.ip_address(val.strip())
        return True
    except ValueError:
        return False

import functools

@functools.lru_cache(maxsize=32768)
def _get_ip_network(cidr_str):
    try:
        return ipaddress.ip_network(cidr_str.strip(), strict=False)
    except ValueError:
        return None

def check_ip_in_network(ip_str, cidr_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        net_obj = _get_ip_network(cidr_str)
        return ip_obj in net_obj if net_obj else False
    except ValueError:
        return False

def load_dist_rules(order=None):
    """Loads all dist/*.lsr remote rules in explicit top-to-bottom evaluation order."""
    eval_order = order if order is not None else DEFAULT_REMOTE_RULE_ORDER
    rules_by_file = []
    for fname in eval_order:
        fpath = os.path.join(DIST_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        parsed_rules = []
        with open(fpath, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                p = parse_rule_line(line, line_idx)
                if p:
                    parsed_rules.append((p["type"], p["value"], p["raw"], line_idx))
        rules_by_file.append((fname, parsed_rules))
    return rules_by_file

def load_lcf_pipeline(lcf_path):
    """
    Parses an actual .lcf configuration file to extract:
    1. Local [Rule] (skipping disabled rules, discarding private comments)
    2. Remote [Remote Rule] declaration order (skipping disabled rules)
    3. FINAL rule
    """
    local_rules = []
    remote_rulesets = []
    remote_entries = []
    final_policy = "DIRECT"
    has_final = False
    final_count = 0
    final_line = None
    final_is_last = True
    final_wrong_section = []
    active_plugins = []

    if not os.path.isfile(lcf_path):
        return None

    current_section = None
    with open(lcf_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_idx, line in enumerate(f, 1):
            clean = line.strip()
            if not clean or clean.startswith(("#", ";")):
                continue
            if clean.startswith("[") and clean.endswith("]"):
                current_section = clean[1:-1].strip()
                continue

            # Check if entry is explicitly disabled (e.g. enabled=false or enable=false)
            clean_lower = clean.lower()
            is_disabled = bool(re.search(r'\benabled?\s*=\s*false\b', clean_lower))

            # Check if this line is a FINAL rule
            clean_upper = clean.upper()
            is_final_rule = clean_upper.startswith("FINAL,") or clean_upper == "FINAL"

            if current_section == "Rule":
                p = parse_rule_line(clean, line_idx)
                if p:
                    if p["type"] == "FINAL":
                        final_count += 1
                        if not is_disabled:
                            has_final = True
                            final_line = line_idx
                            final_policy = p["value"] or "DIRECT"
                    else:
                        if final_count > 0:
                            final_is_last = False
                        if not is_disabled:
                            local_rules.append({
                                "type": p["type"],
                                "value": p["value"],
                                "raw": f"{p['type']},{p['value']}",
                                "line": line_idx
                            })
            elif current_section == "Remote Rule":
                if is_final_rule:
                    final_wrong_section.append(("Remote Rule", line_idx))
                    continue
                # Extract URL token and .lsr filename
                url_token = clean.split(",")[0].strip()
                m = re.search(r'([a-zA-Z0-9_\-]+\.lsr)', url_token)
                rname = m.group(1) if m else None
                remote_entries.append({
                    "name": rname,
                    "url": url_token,
                    "enabled": not is_disabled,
                    "line": line_idx,
                    "raw": clean
                })
                if rname and not is_disabled:
                    remote_rulesets.append(rname)
            elif current_section == "Plugin":
                if is_final_rule:
                    final_wrong_section.append(("Plugin", line_idx))
                    continue
                if not is_disabled:
                    active_plugins.append(clean)
            else:
                if is_final_rule:
                    final_wrong_section.append((current_section or "Unknown", line_idx))

    return {
        "local_rules": local_rules,
        "remote_order": remote_rulesets,  # Strictly parsed from file; NO silent fallback to default
        "remote_entries": remote_entries,
        "final_policy": final_policy,
        "has_final": has_final,
        "final_count": final_count,
        "final_line": final_line,
        "final_is_last": final_is_last and (final_count == 1),
        "final_wrong_section": final_wrong_section,
        "active_plugins": active_plugins,
        "active_plugin_count": len(active_plugins)
    }

def match_target(target, rules_by_file, local_rules=None, plugin_rules=None):
    """
    Simulates complete multi-stage evaluation for domain or IP:
      Stage 1: Local [Rule]
      Stage 2: Plugin [Rule]
      Stage 3: [Remote Rule] (ordered .lsr files)
      Stage 4: FINAL
    """
    clean_target = target.strip()
    target_is_ip = is_ip(clean_target)
    domain_lower = clean_target.lower() if not target_is_ip else ""
    matches = []

    def check_hit(rtype, rval):
        if target_is_ip:
            if rtype in ("IP-CIDR", "IP-CIDR6"):
                return check_ip_in_network(clean_target, rval)
            return False
        else:
            rval_lower = rval.lower()
            if rtype == "DOMAIN":
                return domain_lower == rval_lower
            elif rtype == "DOMAIN-SUFFIX":
                return domain_lower == rval_lower or domain_lower.endswith("." + rval_lower)
            elif rtype == "DOMAIN-KEYWORD":
                return rval_lower in domain_lower
            return False

    # Stage 1: Local [Rule]
    if local_rules:
        for r in local_rules:
            if check_hit(r["type"], r["value"]):
                matches.append({
                    "stage": "Stage 1 (Local [Rule])",
                    "ruleset": "Local [Rule]",
                    "rule": r.get("raw", f"{r['type']},{r['value']}"),
                    "type": r["type"],
                    "value": r["value"].lower(),
                    "line": r.get("line", 0)
                })

    # Stage 2: Plugin [Rule]
    if plugin_rules:
        for r in plugin_rules:
            if check_hit(r["type"], r["value"]):
                matches.append({
                    "stage": "Stage 2 (Plugin [Rule])",
                    "ruleset": "Plugin [Rule]",
                    "rule": r.get("raw", f"{r['type']},{r['value']}"),
                    "type": r["type"],
                    "value": r["value"].lower(),
                    "line": r.get("line", 0)
                })

    # Stage 3: Remote Rules
    for fname, rule_list in rules_by_file:
        for rtype, rval, raw_line, line_idx in rule_list:
            if check_hit(rtype, rval):
                matches.append({
                    "stage": f"Stage 3 ([Remote Rule]: {fname})",
                    "ruleset": fname,
                    "rule": raw_line,
                    "type": rtype,
                    "value": rval.lower(),
                    "line": line_idx
                })

    return matches

def match_domain(domain, rules_by_file, local_rules=None, plugin_rules=None):
    """Backward compatibility alias for match_target."""
    return match_target(domain, rules_by_file, local_rules, plugin_rules)

def simulate(target, rules_by_file, local_rules=None, plugin_rules=None, lcf_meta=None):
    matches = match_target(target, rules_by_file, local_rules, plugin_rules)
    print("=" * 64)
    print(f"输入测试目标: {target} ({'IP地址' if is_ip(target) else '域名'})")

    if plugin_rules is None:
        print("[状态: 插件注入规则未加载 - 第三方插件规则无法脱机静态推演，实际生效以真机 TUN 抓包为准]")

    if not matches:
        if lcf_meta:
            is_valid_final = lcf_meta.get("has_final", "final_policy" in lcf_meta)

            if is_valid_final:
                raw_final = lcf_meta.get("final_policy", "DIRECT")
                final_upper = raw_final.upper().strip()
                if final_upper in ("DIRECT", "REJECT", "REJECT-DROP", "REJECT-TINYGIF"):
                    sanitized_final = final_upper
                else:
                    sanitized_final = "PROXY"
                print("命中层级: Stage 4 (FINAL 兜底规则)")
                print(f"命中规则: FINAL,{sanitized_final}")
                print("判定结论: 正常命中默认兜底规则 (非故障，标准 Fallback 行为)")
            else:
                print("命中层级: Stage 4 (FINAL 兜底规则)")
                print("命中规则: FINAL,未知/未验证")
                print("判定结论: 配置已提供但缺已确认FINAL，兜底动作未知。")
        else:
            print("命中层级: Stage 4 (FINAL 兜底规则)")
            print("命中规则: FINAL,未知/未验证")
            print("判定结论: 未提供 --lcf 配置，兜底动作未知。请提供实际配置以验证。")
        print("跨规则集冲突: 否")
        print("=" * 64)
        return

    first_hit = matches[0]
    print(f"生效层级: {first_hit['stage']}")
    print(f"首命中规则: {first_hit['rule']} (行号: {first_hit['line']})")
    print(f"所属规则集: {first_hit['ruleset']}")

    if len(matches) == 1:
        print("生效判定: 首位独占命中生效 (全库无其它冲突规则)")
    else:
        other_sets = set(m['ruleset'] for m in matches[1:])
        other_matches = matches[1:]
        print(f"生效判定: 首位优先命中生效，阻断并覆盖后续 {len(other_matches)} 条潜在匹配规则")
        if other_sets:
            print(f"跨规则集被覆盖列表: {', '.join(sorted(other_sets))}")
            for m in other_matches:
                print(f"  - [{m['ruleset']}] {m['rule']} ({m['stage']})")
        else:
            print("跨规则集冲突: 否 (仅同一规则集内部不同粒度重合)")

    print("=" * 64)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Simulate complete Loon multi-stage rule evaluation.")
    parser.add_argument("targets", nargs="*", help="Domain names or IP addresses to simulate")
    parser.add_argument("--lcf", dest="lcf_file", default=None, help="Path to actual .lcf configuration file")
    args = parser.parse_args()

    if not args.targets:
        print("用法: python scripts/simulate_hit.py <domain_or_ip_1> [target2 ...] [--lcf <path.lcf>]")
        print("示例: python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com 17.249.1.5")
        sys.exit(1)

    lcf_meta = load_lcf_pipeline(args.lcf_file) if args.lcf_file else None
    local_rules = lcf_meta["local_rules"] if lcf_meta else None
    remote_order = lcf_meta["remote_order"] if lcf_meta else DEFAULT_REMOTE_RULE_ORDER

    rules_by_file = load_dist_rules(remote_order)
    for t in args.targets:
        simulate(t, rules_by_file, local_rules=local_rules, lcf_meta=lcf_meta)

if __name__ == "__main__":
    main()
