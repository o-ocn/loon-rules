#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rule Hit Simulator (Strategy-Neutral, Multi-Stage Evaluation)
Simulates complete top-to-bottom rule evaluation order in Loon:
  Stage 1: Local [Rule] (configuration file local rules)
  Stage 2: Plugin [Rule] (active plugin injected rules)
  Stage 3: [Remote Rule] (remote subscription rulesets in declaration order)
  Stage 4: FINAL (fallback default rule)
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")

# Standard Loon evaluation order for o-ocn rulesets (narrow/child before broad/parent)
DEFAULT_REMOTE_RULE_ORDER = [
    "AI-China-Direct.lsr",
    "AI-Overseas.lsr",
    "YouTube.lsr",
    "GoogleDrive.lsr",
    "Google.lsr",
    "OneDrive.lsr",
    "Telegram.lsr",
    "Twitter.lsr",
    "Discord.lsr",
    "TestFlight.lsr",
    "Apple-Media.lsr",
    "Apple-Push.lsr",
    "Apple-Direct.lsr",
    "China-Direct.lsr"
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
    # Extract options like no-resolve
    options = [p.strip() for p in parts[2:]]
    return {
        "type": rtype,
        "value": rval,
        "options": options,
        "raw": clean,
        "line": line_idx
    }

def load_dist_rules(order=None):
    """Loads all dist/*.lsr remote rules in explicit top-to-bottom evaluation order."""
    eval_order = order or DEFAULT_REMOTE_RULE_ORDER
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
    1. Local [Rule]
    2. Remote [Remote Rule] declaration order
    3. FINAL rule
    """
    local_rules = []
    remote_rulesets = []
    final_policy = "DIRECT"

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

            if current_section == "Rule":
                p = parse_rule_line(clean, line_idx)
                if p:
                    if p["type"] == "FINAL":
                        final_policy = p["value"] or "DIRECT"
                    else:
                        local_rules.append(p)
            elif current_section == "Remote Rule":
                # e.g.: https://raw.githubusercontent.com/.../dist/AI-Overseas.lsr, policy=..., tag=AI-Overseas
                # Extract filename or tag
                m = re.search(r'([a-zA-Z0-9_\-]+\.lsr)', clean)
                if m:
                    rname = m.group(1)
                    if rname not in remote_rulesets:
                        remote_rulesets.append(rname)

    return {
        "local_rules": local_rules,
        "remote_order": remote_rulesets or DEFAULT_REMOTE_RULE_ORDER,
        "final_policy": final_policy
    }

def match_domain(domain, rules_by_file, local_rules=None, plugin_rules=None):
    """
    Simulates complete multi-stage evaluation:
      Stage 1: Local [Rule]
      Stage 2: Plugin [Rule]
      Stage 3: [Remote Rule] (ordered .lsr files)
      Stage 4: FINAL
    """
    domain = domain.lower().strip()
    matches = []

    def check_rule_hit(rtype, rval):
        rval_lower = rval.lower()
        if rtype == "DOMAIN":
            return domain == rval_lower
        elif rtype == "DOMAIN-SUFFIX":
            return domain == rval_lower or domain.endswith("." + rval_lower)
        elif rtype == "DOMAIN-KEYWORD":
            return rval_lower in domain
        return False

    # Stage 1: Local [Rule]
    if local_rules:
        for r in local_rules:
            if check_rule_hit(r["type"], r["value"]):
                matches.append({
                    "stage": "Stage 1 (Local [Rule])",
                    "ruleset": "Local [Rule]",
                    "rule": r["raw"],
                    "type": r["type"],
                    "value": r["value"].lower(),
                    "line": r.get("line", 0)
                })

    # Stage 2: Plugin [Rule]
    if plugin_rules:
        for r in plugin_rules:
            if check_rule_hit(r["type"], r["value"]):
                matches.append({
                    "stage": "Stage 2 (Plugin [Rule])",
                    "ruleset": "Plugin [Rule]",
                    "rule": r["raw"],
                    "type": r["type"],
                    "value": r["value"].lower(),
                    "line": r.get("line", 0)
                })

    # Stage 3: Remote Rules
    for fname, rule_list in rules_by_file:
        for rtype, rval, raw_line, line_idx in rule_list:
            if check_rule_hit(rtype, rval):
                matches.append({
                    "stage": f"Stage 3 ([Remote Rule]: {fname})",
                    "ruleset": fname,
                    "rule": raw_line,
                    "type": rtype,
                    "value": rval.lower(),
                    "line": line_idx
                })

    return matches

def simulate(domain, rules_by_file, local_rules=None, plugin_rules=None, lcf_meta=None):
    matches = match_domain(domain, rules_by_file, local_rules, plugin_rules)
    print("=" * 64)
    print(f"输入测试域名: {domain}")

    if not matches:
        final_pol = lcf_meta.get("final_policy", "DIRECT") if lcf_meta else "FINAL"
        print("命中层级: Stage 4 (FINAL 兜底规则)")
        print(f"命中规则: FINAL,{final_pol}")
        print("判定结论: 正常命中默认兜底规则 (非故障，标准 Fallback 行为)")
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

    print("[提示]: 第三方未审查插件注入规则无法脱机静态推演，实际生效以真机 TUN 抓包为准。")
    print("=" * 64)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Simulate complete Loon multi-stage rule evaluation.")
    parser.add_argument("domains", nargs="*", help="Domain names to simulate")
    parser.add_argument("--lcf", dest="lcf_file", default=None, help="Path to actual .lcf configuration file")
    args = parser.parse_args()

    if not args.domains:
        print("用法: python scripts/simulate_hit.py <domain1> [domain2 ...] [--lcf <path.lcf>]")
        print("示例: python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com www.googleapis.com")
        sys.exit(1)

    lcf_meta = load_lcf_pipeline(args.lcf_file) if args.lcf_file else None
    local_rules = lcf_meta["local_rules"] if lcf_meta else None
    remote_order = lcf_meta["remote_order"] if lcf_meta else DEFAULT_REMOTE_RULE_ORDER

    rules_by_file = load_dist_rules(remote_order)
    for d in args.domains:
        simulate(d, rules_by_file, local_rules=local_rules, lcf_meta=lcf_meta)

if __name__ == "__main__":
    main()
