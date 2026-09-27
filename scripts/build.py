#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rules Generator and Validator
Fail-stop upstream fetching, atomic staging, idempotence, and full-spectrum cross-policy conflict engine.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import re
import shutil
import tempfile
import urllib.request
import urllib.error
import hashlib
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.yml")
RULES_CUSTOM_DIR = os.path.join(BASE_DIR, "rules", "custom")
DIST_DIR = os.path.join(BASE_DIR, "dist")

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

# Explicitly verified and whitelisted parent-subdomain policy delegations.
# Any unlisted cross-policy shadowing will halt build immediately.
KNOWN_SAFE_DELEGATIONS = {
    # Gemini / AI Studio (AI) carved out from Google (US Test)
    "gemini.google.com": ("AI-Overseas", "Google"),
    "bard.google.com": ("AI-Overseas", "Google"),
    "aistudio.google.com": ("AI-Overseas", "Google"),
    "makersuite.google.com": ("AI-Overseas", "Google"),
    "generativelanguage.googleapis.com": ("AI-Overseas", "Google"),
    "alkalimakersuite-pa.clients6.google.com": ("AI-Overseas", "Google"),
    "proactivebackend-pa.googleapis.com": ("AI-Overseas", "Google"),

    # Google Drive (HK) carved out from Google (US Test)
    "drive.google.com": ("GoogleDrive", "Google"),
    "docs.google.com": ("GoogleDrive", "Google"),
    "googledrive.com": ("GoogleDrive", "Google"),
    "drive-thirdparty.google.com": ("GoogleDrive", "Google"),
    "filepickup.google.com": ("GoogleDrive", "Google"),

    # Discord Dynamic Links (US) carved out from Google Firebase (US Test)
    "discord-attachments-uploads-prd.storage.googleapis.com": ("Discord", "Google"),
    "discordapp.page.link": ("Discord", "Google"),

    # Apple Media (US Test) carved out from Apple-Direct (DIRECT)
    "tv.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "tv.applemusic.com": ("Apple-Media-US", "Apple-Direct"),
    "linear.tv.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "news-client.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "news-client-search.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "news-assets.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "news-edge.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "gspe1-ssl.ls.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "apple.news": ("Apple-Media-US", "Apple-Direct"),
    "fitness.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "amp-api.fitness.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "testflight.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "play-edge.itunes.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "np-edge.itunes.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "uts-api.itunes.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "hls.itunes.apple.com": ("Apple-Media-US", "Apple-Direct"),
    "hls-amt.itunes.apple.com": ("Apple-Media-US", "Apple-Direct"),

    # APNs Experimental (Apple Push) carved out from Apple-Direct (DIRECT)
    "push.apple.com": ("Apple-Push-Experimental", "Apple-Direct"),
    "courier.push.apple.com": ("Apple-Push-Experimental", "Apple-Direct"),
}

def parse_yaml_fallback(filepath):
    """
    Robust stack-based indentation YAML parser for sources.yml.
    Accurately supports nested lists and dicts without PyYAML.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cfg = {"rulesets": {}}
    current_ruleset = None
    current_source = None
    in_rulesets = False

    for line_num, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())

        if indent == 0:
            if stripped == "rulesets:":
                in_rulesets = True
            else:
                in_rulesets = False
            continue

        if not in_rulesets:
            continue

        # Ruleset level: indent 2
        if indent == 2 and stripped.endswith(":"):
            current_ruleset = stripped[:-1].strip()
            cfg["rulesets"][current_ruleset] = {"sources": []}
            current_source = None
            continue

        if not current_ruleset:
            continue

        # Ruleset properties: indent 4
        if indent == 4:
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k != "sources":
                    cfg["rulesets"][current_ruleset][k] = v if v else True
            continue

        # Source list items: indent 6
        if indent == 6:
            if stripped.startswith("- "):
                item_content = stripped[2:].strip()
                if ":" in item_content:
                    k, v = item_content.split(":", 1)
                    val = int(v.strip().strip('"\'')) if k.strip() == "min_rules" else v.strip().strip('"\'')
                    current_source = {k.strip(): val}
                    cfg["rulesets"][current_ruleset]["sources"].append(current_source)
                else:
                    current_source = {"name": item_content}
                    cfg["rulesets"][current_ruleset]["sources"].append(current_source)
            elif ":" in stripped and current_source is not None:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k == "filter_excluded":
                    current_source["filter_excluded"] = []
                elif k == "min_rules":
                    current_source["min_rules"] = int(v)
                else:
                    current_source[k] = v
            continue

        # Nested filter_excluded list items: indent 8 or 10
        if indent >= 8:
            if stripped.startswith("- ") and current_source is not None and "filter_excluded" in current_source:
                ex_val = stripped[2:].strip().strip('"\'')
                current_source["filter_excluded"].append(ex_val)
            continue

    return cfg

def load_sources(filepath=SOURCES_FILE):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Sources config not found: {filepath}")
    try:
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        return parse_yaml_fallback(filepath)

def clean_rule_line(line):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith(";"):
        return None
    parts = [p.strip() for p in line.split(",")]
    if not parts:
        return None
    rule_type = parts[0].upper()
    if rule_type not in SUPPORTED_TYPES:
        return f"INVALID_SYNTAX: Unknown rule type '{rule_type}' in line: {line}"
    value = parts[1] if len(parts) > 1 else ""
    if not value:
        return f"INVALID_SYNTAX: Missing rule target value in line: {line}"
    has_no_resolve = any(p.lower() == "no-resolve" for p in parts[1:])
    if has_no_resolve:
        return f"{rule_type},{value},no-resolve"
    else:
        return f"{rule_type},{value}"

def fetch_upstream_strict(url, min_rules=2, timeout=15, max_retries=3):
    """
    Fetches upstream rule list with strict error handling and retries.
    Raises RuntimeError on any failure or if rule count is less than min_rules.
    """
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Loon-Rules-Builder/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP status {response.status} when fetching {url}")
                body = response.read().decode("utf-8", errors="strict")
                lines = [l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith(("#", ";"))]
                if len(lines) < min_rules:
                    raise RuntimeError(
                        f"Upstream returned abnormally few rules ({len(lines)} < min_rules {min_rules}) from {url}"
                    )
                return body
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                import time
                time.sleep(1.0)
                continue
    raise RuntimeError(f"CRITICAL: Failed to fetch upstream rule from {url} after {max_retries} attempts: {last_err}") from last_err

def build_rulesets(sources_file=SOURCES_FILE, dist_dir=DIST_DIR):
    print(f"[*] Starting Loon Rules Build at {datetime.now(timezone.utc).isoformat()}...")
    cfg = load_sources(sources_file)
    rulesets = cfg.get("rulesets", {})
    if not rulesets:
        raise ValueError("No rulesets defined in sources.yml")

    staged_rules_by_set = {}
    rule_to_policy_map = {}   # (rule_type, rule_val) -> (ruleset_name, bound_policy)
    parent_domains = {}       # domain_suffix -> (ruleset, policy)

    for name, rcfg in rulesets.items():
        bound_policy = rcfg.get("bound_policy", "DIRECT")
        custom_file_rel = rcfg.get("local_custom", "")
        custom_file = os.path.join(BASE_DIR, custom_file_rel) if custom_file_rel else ""
        collected_rules = []
        seen = set()

        # 1. Load custom rules first
        if custom_file and os.path.isfile(custom_file):
            print(f"  [+] Ingesting custom rules: {custom_file_rel}")
            with open(custom_file, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    cleaned = clean_rule_line(line)
                    if cleaned:
                        if cleaned.startswith("INVALID_SYNTAX:"):
                            raise SyntaxError(f"Syntax error in {custom_file}:{line_idx} - {cleaned}")
                        if cleaned not in seen:
                            seen.add(cleaned)
                            collected_rules.append(cleaned)

        # 2. Ingest upstream sources strictly
        upstream_sources = rcfg.get("sources", [])
        for src in upstream_sources:
            sname = src.get("name")
            surl = src.get("url")
            min_r = src.get("min_rules", 2)
            excluded = set(src.get("filter_excluded", []))
            print(f"  [+] Ingesting upstream: {sname} (min_rules={min_r}, url={surl})")
            raw_text = fetch_upstream_strict(surl, min_rules=min_r)
            for line in raw_text.splitlines():
                cleaned = clean_rule_line(line)
                if cleaned:
                    if cleaned.startswith("INVALID_SYNTAX:"):
                        raise SyntaxError(f"Syntax error in upstream {sname} ({surl}): {cleaned}")
                    if cleaned in excluded:
                        continue
                    if cleaned not in seen:
                        seen.add(cleaned)
                        collected_rules.append(cleaned)

        staged_rules_by_set[name] = collected_rules
        print(f"  [=] Ruleset '{name}': {len(collected_rules)} rules loaded.")

        # Record rule mapping for ALL rule types for cross-policy duplicate check
        for r in collected_rules:
            parts = r.split(",")
            rtype = parts[0].upper()
            rval = parts[1].strip()
            # Normalize domain case
            if rtype in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
                rval = rval.lower()

            rule_key = (rtype, rval)
            if rule_key in rule_to_policy_map:
                prev_set, prev_pol = rule_to_policy_map[rule_key]
                if prev_pol != bound_policy:
                    raise ValueError(
                        f"FATAL CONFLICT: Exact rule '{rtype},{rval}' is mapped to both '{prev_set}' (Policy: {prev_pol}) "
                        f"and '{name}' (Policy: {bound_policy})! Ambiguous policy assignment is forbidden."
                    )
            rule_to_policy_map[rule_key] = (name, bound_policy)

            if rtype == "DOMAIN-SUFFIX":
                parent_domains[rval] = (name, bound_policy)

    # 3. Check for illegal parent-domain shadowing across different policies
    for (rtype, rval), (c_set, c_pol) in rule_to_policy_map.items():
        if rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
            domain = rval
            parts = domain.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[i:])
                if parent in parent_domains:
                    p_set, p_pol = parent_domains[parent]
                    if p_pol != c_pol:
                        # Check if this cross-policy delegation is explicitly whitelisted
                        if domain in KNOWN_SAFE_DELEGATIONS:
                            expected_child, expected_parent = KNOWN_SAFE_DELEGATIONS[domain]
                            if c_set == expected_child and p_set == expected_parent:
                                continue  # Safe, intentional delegation
                        raise ValueError(
                            f"FATAL SHADOWING: Subdomain '{domain}' in '{c_set}' ({c_pol}) is shadowed by parent "
                            f"suffix '{parent}' in '{p_set}' ({p_pol}) without verified delegation! Build halted."
                        )

    # 4. Strict assertions for user requirements
    ai_rules = staged_rules_by_set.get("AI-Overseas", [])
    forbidden_in_ai = [
        "DOMAIN-SUFFIX,googleapis.com", "DOMAIN-SUFFIX,google.com",
        "DOMAIN-SUFFIX,x.com", "DOMAIN-SUFFIX,twitter.com",
        "DOMAIN-SUFFIX,facebook.com", "DOMAIN-SUFFIX,instagram.com", "DOMAIN-SUFFIX,meta.com",
        "DOMAIN-SUFFIX,stripe.com", "DOMAIN-SUFFIX,auth0.com", "DOMAIN-SUFFIX,sentry.io",
        "DOMAIN-SUFFIX,intercom.io", "DOMAIN-SUFFIX,launchdarkly.com", "IP-ASN,20473,no-resolve"
    ]
    for fb in forbidden_in_ai:
        if fb in ai_rules:
            raise ValueError(f"CRITICAL: Prohibited broad/shared rule '{fb}' found in AI-Overseas.lsr! Halting build.")

    # 5. Atomic write to temporary staging directory first
    staging_dir = tempfile.mkdtemp(prefix="loon_dist_staging_")
    try:
        generated_files = {}
        for name, rlist in staged_rules_by_set.items():
            staging_file = os.path.join(staging_dir, f"{name}.lsr")
            policy = rulesets[name].get("bound_policy", "DIRECT")
            desc = rulesets[name].get("description", "")
            
            rule_body = "\n".join(rlist)
            content_hash = hashlib.sha256(rule_body.encode("utf-8")).hexdigest()[:12]
            
            with open(staging_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"# NAME: {name}\n")
                f.write(f"# DESCRIPTION: {desc}\n")
                f.write(f"# RECOMMENDED POLICY: {policy}\n")
                f.write(f"# AUTHOR: o-ocn\n")
                f.write(f"# REVISION: {content_hash}\n")
                f.write(f"# TOTAL: {len(rlist)}\n")
                f.write("# ==============================================================================\n")
                if rlist:
                    f.write(rule_body + "\n")
            generated_files[name] = staging_file

        # 6. Idempotent sync to dist/
        os.makedirs(dist_dir, exist_ok=True)
        updated_count = 0
        for name, s_file in generated_files.items():
            target_file = os.path.join(dist_dir, f"{name}.lsr")
            with open(s_file, "r", encoding="utf-8") as f:
                new_data = f.read()
            
            should_write = True
            if os.path.isfile(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    old_data = f.read()
                if old_data == new_data:
                    should_write = False
            
            if should_write:
                with open(target_file, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_data)
                updated_count += 1
                print(f"[UPDATED] {name}.lsr")
            else:
                print(f"[UNCHANGED] {name}.lsr (Identical hash)")

        print(f"\n[SUCCESS] Build complete. {updated_count} files updated in {dist_dir}.")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

if __name__ == "__main__":
    try:
        build_rulesets()
    except Exception as err:
        print(f"\n[BUILD ABORTED] Error: {err}", file=sys.stderr)
        sys.exit(1)
