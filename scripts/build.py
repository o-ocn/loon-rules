#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rules Generator and Validator
Maintains clean, policy-segregated .lsr files with conflict detection and deduplication.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import re
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone

try:
    import yaml
    def parse_yaml_file(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
except ImportError:
    # Standard library fallback parser for sources.yml
    def parse_yaml_file(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        cfg = {"rulesets": {}}
        current_ruleset = None
        current_list = None
        current_dict_item = None
        in_rulesets = False
        
        for line in lines:
            raw = line.rstrip()
            if not raw or raw.strip().startswith("#"):
                continue
            
            indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()

            if indent == 0 and stripped == "rulesets:":
                in_rulesets = True
                continue
            elif indent == 0 and stripped != "rulesets:":
                in_rulesets = False
                continue

            if not in_rulesets:
                continue
            
            if indent == 2 and stripped.endswith(":"):
                current_ruleset = stripped[:-1].strip()
                cfg["rulesets"][current_ruleset] = {"sources": []}
                current_list = None
                current_dict_item = None

            elif indent == 4 and current_ruleset:
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k == "sources":
                        current_list = "sources"
                    else:
                        cfg["rulesets"][current_ruleset][k] = v if v else True
                        current_list = None
            elif indent >= 6 and current_ruleset:
                if stripped.startswith("- "):
                    item_str = stripped[2:].strip()
                    if current_list == "sources":
                        if ":" in item_str:
                            k, v = item_str.split(":", 1)
                            current_dict_item = {k.strip(): v.strip().strip('"\'')}
                            cfg["rulesets"][current_ruleset]["sources"].append(current_dict_item)
                        else:
                            current_dict_item = {"name": item_str}
                            cfg["rulesets"][current_ruleset]["sources"].append(current_dict_item)
                    elif current_list == "filter_excluded" and current_dict_item is not None:
                        current_dict_item.setdefault("filter_excluded", []).append(item_str.strip('"\''))
                elif ":" in stripped and current_dict_item is not None:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k == "filter_excluded":
                        current_list = "filter_excluded"
                        current_dict_item["filter_excluded"] = []
                    else:
                        current_dict_item[k] = v
        return cfg


SUPPORTED_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "IP-CIDR",
    "IP-CIDR6",
    "USER-AGENT",
    "IP-ASN",
    "URL-REGEX"
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.yml")
RULES_CUSTOM_DIR = os.path.join(BASE_DIR, "rules", "custom")
DIST_DIR = os.path.join(BASE_DIR, "dist")

def load_sources():
    if not os.path.isfile(SOURCES_FILE):
        raise FileNotFoundError(f"Sources config not found: {SOURCES_FILE}")
    return parse_yaml_file(SOURCES_FILE)


def clean_rule_line(line):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith(";"):
        return None
    # Strip any trailing Loon policy if present (e.g. DOMAIN-SUFFIX,example.com,DIRECT -> DOMAIN-SUFFIX,example.com)
    # Remote rules in .lsr files should NOT contain target policy inline when bound by [Remote Rule] policy=...
    parts = [p.strip() for p in line.split(",")]
    if not parts:
        return None
    
    rule_type = parts[0].upper()
    if rule_type not in SUPPORTED_TYPES:
        return f"INVALID_SYNTAX: Unknown rule type '{rule_type}' in line: {line}"
    
    # Check parameters (e.g. no-resolve)
    has_no_resolve = any(p.lower() == "no-resolve" for p in parts[1:])
    value = parts[1] if len(parts) > 1 else ""
    if not value:
        return f"INVALID_SYNTAX: Missing rule target value in line: {line}"

    if has_no_resolve:
        return f"{rule_type},{value},no-resolve"
    else:
        return f"{rule_type},{value}"

def fetch_upstream(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Loon-Rules-Builder/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [WARN] Failed to fetch upstream {url}: {e}")
        return None

def build():
    print(f"[*] Starting Loon Rules Build at {datetime.now(timezone.utc).isoformat()}...")
    cfg = load_sources()
    rulesets = cfg.get("rulesets", {})
    
    all_rules_by_set = {}
    domain_to_set_map = {}
    has_critical_error = False

    for name, rcfg in rulesets.items():
        print(f"\n[*] Processing ruleset: {name} (Policy: {rcfg.get('bound_policy', 'UNBOUND')})")
        custom_file = os.path.join(BASE_DIR, rcfg.get("local_custom", ""))
        collected_rules = []
        seen = set()

        # 1. Custom rules first (Highest priority)
        if os.path.isfile(custom_file):
            print(f"  [+] Loading custom rules from {rcfg.get('local_custom')}")
            with open(custom_file, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    cleaned = clean_rule_line(line)
                    if cleaned:
                        if cleaned.startswith("INVALID_SYNTAX:"):
                            print(f"  [ERROR] {custom_file}:{line_idx} - {cleaned}")
                            has_critical_error = True
                        elif cleaned not in seen:
                            seen.add(cleaned)
                            collected_rules.append(cleaned)

        # 2. Upstream sources (optional, filtered)
        upstream_sources = rcfg.get("sources", [])
        for src in upstream_sources:
            sname = src.get("name")
            surl = src.get("url")
            excluded = set(src.get("filter_excluded", []))
            print(f"  [+] Ingesting upstream: {sname}")
            raw_text = fetch_upstream(surl)
            if raw_text:
                for line in raw_text.splitlines():
                    cleaned = clean_rule_line(line)
                    if cleaned and not cleaned.startswith("INVALID_SYNTAX:"):
                        if cleaned in excluded:
                            continue
                        if cleaned not in seen:
                            seen.add(cleaned)
                            collected_rules.append(cleaned)
            else:
                print(f"  [NOTE] Using local/cached definitions for {sname} due to fetch limit.")

        all_rules_by_set[name] = collected_rules
        print(f"  [=] Total rules for {name}: {len(collected_rules)}")

        # Check collision map
        for r in collected_rules:
            parts = r.split(",")
            rtype = parts[0]
            rval = parts[1]
            if rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
                if rval in domain_to_set_map and domain_to_set_map[rval] != name:
                    prev_set = domain_to_set_map[rval]
                    # Check if policies differ
                    p1 = rulesets[prev_set].get("bound_policy")
                    p2 = rcfg.get("bound_policy")
                    if p1 != p2:
                        print(f"  [CONFLICT DETECTED] Domain '{rval}' is in both '{prev_set}' ({p1}) and '{name}' ({p2})!")
                        # If AI-Overseas vs Google, verify precision
                        if (name == "AI-Overseas" and prev_set == "Google") or (prev_set == "AI-Overseas" and name == "Google"):
                            print(f"    -> Cross-hit between AI and Google! Review precision domain allocation.")
                domain_to_set_map[rval] = name

    # 3. Specific validation for user requirements
    ai_rules = all_rules_by_set.get("AI-Overseas", [])
    forbidden_in_ai = ["DOMAIN-SUFFIX,googleapis.com", "DOMAIN-SUFFIX,google.com", "DOMAIN-SUFFIX,x.com", "DOMAIN-SUFFIX,twitter.com", "DOMAIN-SUFFIX,facebook.com", "DOMAIN-SUFFIX,instagram.com", "DOMAIN-SUFFIX,meta.com"]
    for fb in forbidden_in_ai:
        if fb in ai_rules:
            print(f"  [CRITICAL ERROR] '{fb}' detected in AI-Overseas! Must not blanket include parent domains in AI.")
            has_critical_error = True

    if has_critical_error:
        print("\n[FAILED] Build aborted due to critical validation errors. Existing dist/ kept intact.")
        sys.exit(1)

    # 4. Write dist files
    os.makedirs(DIST_DIR, exist_ok=True)
    for name, rlist in all_rules_by_set.items():
        out_file = os.path.join(DIST_DIR, f"{name}.lsr")
        policy = rulesets[name].get("bound_policy", "DIRECT")
        desc = rulesets[name].get("description", "")
        with open(out_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"# NAME: {name}\n")
            f.write(f"# DESCRIPTION: {desc}\n")
            f.write(f"# RECOMMENDED POLICY: {policy}\n")
            f.write(f"# AUTHOR: o-ocn\n")
            f.write(f"# UPDATED: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"# TOTAL: {len(rlist)}\n")
            f.write("# ==============================================================================\n")
            for r in rlist:
                f.write(f"{r}\n")
        print(f"[OK] Generated {out_file} ({len(rlist)} rules)")

    print("\n[SUCCESS] All Loon rulesets built successfully.")

if __name__ == "__main__":
    build()
