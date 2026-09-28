#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rule Hit Simulator (Strategy-Neutral, Zero-Egress)
Simulates top-to-bottom rule evaluation order in Loon for target domains.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")

# Standard Loon evaluation order for o-ocn rulesets (narrow/child before broad/parent)
RULE_EVALUATION_ORDER = [
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

def load_dist_rules():
    rules_by_file = []
    for fname in RULE_EVALUATION_ORDER:
        fpath = os.path.join(DIST_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        parsed_rules = []
        with open(fpath, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                clean = line.strip()
                if not clean or clean.startswith(("#", ";")):
                    continue
                parts = [p.strip() for p in clean.split(",")]
                rtype = parts[0].upper()
                rval = parts[1].strip() if len(parts) > 1 else ""
                parsed_rules.append((rtype, rval, clean, line_idx))
        rules_by_file.append((fname, parsed_rules))
    return rules_by_file

def match_domain(domain, rules_by_file):
    domain = domain.lower().strip()
    matches = []

    for fname, rule_list in rules_by_file:
        for rtype, rval, raw_line, line_idx in rule_list:
            rval_lower = rval.lower()
            hit = False
            if rtype == "DOMAIN":
                if domain == rval_lower:
                    hit = True
            elif rtype == "DOMAIN-SUFFIX":
                if domain == rval_lower or domain.endswith("." + rval_lower):
                    hit = True
            elif rtype == "DOMAIN-KEYWORD":
                if rval_lower in domain:
                    hit = True

            if hit:
                matches.append({
                    "ruleset": fname,
                    "rule": raw_line,
                    "type": rtype,
                    "value": rval_lower,
                    "line": line_idx
                })

    return matches

def simulate(domain, rules_by_file):
    matches = match_domain(domain, rules_by_file)
    print("=" * 60)
    print(f"输入测试域名: {domain}")
    if not matches:
        print("命中规则: [未命中任何自有规则]")
        print("所属规则集: FINAL (落入 Loon 兜底规则)")
        print("是否被更早规则覆盖: 否")
        print("是否存在跨分类冲突: 否")
        print("=" * 60)
        return

    first_hit = matches[0]
    print(f"命中规则: {first_hit['rule']} (第 {first_hit['line']} 行)")
    print(f"所属规则集: {first_hit['ruleset']}")

    if len(matches) == 1:
        print("是否被更早规则覆盖: 否 (独占首位生效)")
        print("是否存在跨分类冲突: 否 (全库唯一匹配)")
    else:
        # Check if other matches are in different rulesets
        other_sets = set(m['ruleset'] for m in matches[1:])
        other_matches = matches[1:]

        print(f"是否被更早规则覆盖: 否 (本规则优先命中生效，覆盖后续 {len(other_matches)} 条潜在匹配)")
        if other_sets:
            print(f"是否存在跨分类冲突: 是 (后续被覆盖规则集: {', '.join(sorted(other_sets))})")
            print("  [冲突明细]:")
            for m in other_matches:
                print(f"    - {m['ruleset']}: {m['rule']} (第 {m['line']} 行)")
        else:
            print("是否存在跨分类冲突: 否 (同规则集内部多重匹配)")
    print("=" * 60)

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/simulate_hit.py <domain1> [domain2 ...]")
        print("示例: python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com www.googleapis.com")
        sys.exit(1)

    rules_by_file = load_dist_rules()
    for d in sys.argv[1:]:
        simulate(d, rules_by_file)

if __name__ == "__main__":
    main()
