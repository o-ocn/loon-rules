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
import json
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
UPSTREAM_LOCK_FILE = os.path.join(BASE_DIR, "scripts", "upstream_lock.json")

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

def count_lsr_rules(filepath):
    """
    Counts valid non-comment rule lines in an existing .lsr file.
    """
    if not os.path.isfile(filepath):
        return 0
    count = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if clean and not clean.startswith(("#", ";")):
                count += 1
    return count

def load_upstream_lock(lock_file=UPSTREAM_LOCK_FILE, allow_missing=False):
    """
    Loads previously recorded valid upstream rule counts.
    Returns a dictionary mapping ruleset -> {source_name: rule_count}.

    Strict validation:
    - If lock_file is missing:
        - If allow_missing=False: raises RuntimeError (daily builds must have a valid lock file).
        - If allow_missing=True: returns empty dict {} to allow controlled baseline creation.
    - If lock_file is corrupted (invalid JSON syntax, empty file, wrong data structure):
        - Raises RuntimeError in all cases to prevent corrupted data from being silently accepted.
    """
    if not lock_file:
        raise ValueError("lock_file path must be provided.")

    if not os.path.isfile(lock_file):
        if allow_missing:
            print(f"  [BASELINE] Upstream lock file '{lock_file}' not found. Initializing empty baseline under controlled mode.")
            return {}
        raise RuntimeError(
            f"CRITICAL: Upstream lock file '{lock_file}' is missing! "
            f"In established daily build mode, missing lock file is forbidden to prevent silent baseline bypass. "
            f"Please run with '--init-baseline' to explicitly initialize baseline."
        )

    try:
        with open(lock_file, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            raise ValueError("Lock file is empty (0 bytes)")
        data = json.loads(content)
    except Exception as e:
        raise RuntimeError(
            f"CRITICAL: Upstream lock file '{lock_file}' is corrupt or invalid JSON: {e}! Build halted."
        ) from e

    if not isinstance(data, dict):
        raise RuntimeError(
            f"CRITICAL: Upstream lock file '{lock_file}' root structure must be a JSON dictionary, got {type(data).__name__}! Build halted."
        )

    for rset, sdict in data.items():
        if not isinstance(sdict, dict):
            raise RuntimeError(
                f"CRITICAL: Upstream lock file '{lock_file}' corrupted: entry for ruleset '{rset}' must be a dictionary! Build halted."
            )
        for sname, scnt in sdict.items():
            if not isinstance(scnt, int) or scnt < 0:
                raise RuntimeError(
                    f"CRITICAL: Upstream lock file '{lock_file}' corrupted: rule count for '{rset}.{sname}' must be a non-negative integer, got {scnt}! Build halted."
                )

    return data

def save_upstream_lock(lock_data, lock_file=UPSTREAM_LOCK_FILE):
    """
    Atomically saves recorded valid upstream rule counts to lock_file.
    """
    if not lock_file:
        return
    dir_name = os.path.dirname(lock_file)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    temp_lock = lock_file + ".tmp"
    with open(temp_lock, "w", encoding="utf-8", newline="\n") as f:
        json.dump(lock_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(temp_lock, lock_file)

def parse_yaml_fallback(filepath):
    """
    Robust stack-based indentation YAML parser for sources.yml.
    Accurately supports nested lists, dicts, and property values without PyYAML.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cfg = {"metadata": {}, "rulesets": {}}
    current_section = None
    current_ruleset = None
    current_source = None
    in_filter_excluded = False

    for line_num, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip())

        if indent == 0:
            if stripped.endswith(":"):
                current_section = stripped[:-1].strip()
            else:
                current_section = None
            current_ruleset = None
            current_source = None
            in_filter_excluded = False
            continue

        if current_section == "metadata":
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if v:
                    try:
                        cfg["metadata"][k] = float(v) if "." in v else int(v)
                    except ValueError:
                        cfg["metadata"][k] = v
            continue

        if current_section == "rulesets":
            # Ruleset level: indent 2
            if indent == 2 and stripped.endswith(":"):
                current_ruleset = stripped[:-1].strip()
                cfg["rulesets"][current_ruleset] = {"sources": []}
                current_source = None
                in_filter_excluded = False
                continue

            if not current_ruleset:
                continue

            # Ruleset properties: indent 4
            if indent == 4:
                in_filter_excluded = False
                current_source = None
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k != "sources":
                        try:
                            cfg["rulesets"][current_ruleset][k] = float(v) if "." in v else int(v)
                        except ValueError:
                            cfg["rulesets"][current_ruleset][k] = v if v else True
                continue

            # Source list items: indent 6
            if indent == 6:
                in_filter_excluded = False
                if stripped.startswith("- "):
                    item_content = stripped[2:].strip()
                    current_source = {}
                    cfg["rulesets"][current_ruleset]["sources"].append(current_source)
                    if ":" in item_content:
                        k, v = item_content.split(":", 1)
                        k = k.strip()
                        v = v.strip().strip('"\'')
                        current_source[k] = int(v) if k == "min_rules" else v
                elif ":" in stripped and current_source is not None:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k == "filter_excluded":
                        current_source["filter_excluded"] = []
                        in_filter_excluded = True
                    elif k == "min_rules":
                        current_source["min_rules"] = int(v)
                    else:
                        current_source[k] = v
                continue

            # Source properties: indent 8
            if indent == 8:
                if ":" in stripped and current_source is not None:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k == "filter_excluded":
                        current_source["filter_excluded"] = []
                        in_filter_excluded = True
                    elif k == "min_rules":
                        current_source["min_rules"] = int(v)
                        in_filter_excluded = False
                    else:
                        in_filter_excluded = False
                        current_source[k] = v
                elif stripped.startswith("- ") and in_filter_excluded and current_source is not None:
                    ex_val = stripped[2:].strip().strip('"\'')
                    current_source["filter_excluded"].append(ex_val)
                continue

            # Nested filter_excluded list items: indent >= 10
            if indent >= 10:
                if stripped.startswith("- ") and in_filter_excluded and current_source is not None:
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

def build_rulesets(sources_file=SOURCES_FILE, dist_dir=DIST_DIR, lock_file=UPSTREAM_LOCK_FILE, allow_new_baseline=False):
    print(f"[*] Starting Loon Rules Build at {datetime.now(timezone.utc).isoformat()}...")
    cfg = load_sources(sources_file)
    rulesets = cfg.get("rulesets", {})
    if not rulesets:
        raise ValueError("No rulesets defined in sources.yml")

    env_allow = os.getenv("ALLOW_NEW_UPSTREAM_BASELINE", "").lower() in ("1", "true", "yes")
    allow_new_baseline = allow_new_baseline or env_allow

    default_max_shrink = float(cfg.get("metadata", {}).get("max_shrink_ratio", 0.15))
    has_upstream_sources = any(rcfg.get("sources") for rcfg in rulesets.values())

    if has_upstream_sources:
        lock_data = load_upstream_lock(lock_file, allow_missing=allow_new_baseline)
    else:
        lock_data = {}

    new_lock_data = {}

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
        if upstream_sources:
            new_lock_data[name] = {}
        for src in upstream_sources:
            sname = src.get("name")
            surl = src.get("url")
            min_r = src.get("min_rules", 2)
            excluded = set(src.get("filter_excluded", []))
            print(f"  [+] Ingesting upstream: {sname} (min_rules={min_r}, url={surl})")
            raw_text = fetch_upstream_strict(surl, min_rules=min_r)

            # Count valid non-comment rule lines in upstream source
            valid_src_lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith(("#", ";"))]
            src_count = len(valid_src_lines)
            new_lock_data[name][sname] = src_count

            # Per-upstream shrinkage protection against previous valid lock baseline
            prev_src_count = lock_data.get(name, {}).get(sname)
            src_max_shrink = float(src.get("max_shrink_ratio", rcfg.get("max_shrink_ratio", default_max_shrink)))
            if prev_src_count is not None and prev_src_count > 0:
                if src_count < prev_src_count:
                    drop = prev_src_count - src_count
                    shrink_ratio = drop / float(prev_src_count)
                    if shrink_ratio > src_max_shrink:
                        raise RuntimeError(
                            f"CRITICAL: Upstream source '{sname}' in ruleset '{name}' shrank abnormally by "
                            f"{shrink_ratio:.1%} ({prev_src_count} -> {src_count} rules, dropped {drop} rules), "
                            f"exceeding allowed threshold of {src_max_shrink:.1%}. Build halted to protect dist."
                        )
            else:
                if not allow_new_baseline:
                    raise RuntimeError(
                        f"CRITICAL: Missing baseline lock record for upstream '{sname}' in ruleset '{name}'! "
                        f"In daily build mode, unbaselined upstreams are forbidden to prevent silent shrinkage bypass. "
                        f"Please run build with '--init-baseline' (or set allow_new_baseline=True) to establish baseline for new upstreams."
                    )
                print(f"  [BASELINE] Explicitly established initial valid count for new upstream '{sname}' in '{name}': {src_count} rules.")

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
        "DOMAIN-SUFFIX,intercom.io", "DOMAIN-SUFFIX,launchdarkly.com", "IP-ASN,20473,no-resolve",
        "DOMAIN-KEYWORD,openai",
        "DOMAIN-SUFFIX,client-api.arkoselabs.com", "DOMAIN,client-api.arkoselabs.com",
        "DOMAIN-SUFFIX,host.livekit.cloud", "DOMAIN,host.livekit.cloud",
        "DOMAIN-SUFFIX,turn.livekit.cloud", "DOMAIN,turn.livekit.cloud"
    ]
    for fb in forbidden_in_ai:
        if fb in ai_rules:
            raise ValueError(f"CRITICAL: Prohibited broad/shared rule '{fb}' found in AI-Overseas.lsr! Halting build.")

    for r in ai_rules:
        if r.startswith("DOMAIN-KEYWORD,"):
            raise ValueError(f"CRITICAL: Prohibited keyword rule '{r}' found in AI-Overseas.lsr! Halting build.")

    # 5. Dual protection: Relative shrinkage check for all auto-synced rulesets against previous valid dist version
    default_max_shrink = float(cfg.get("metadata", {}).get("max_shrink_ratio", 0.15))
    for name, rcfg in rulesets.items():
        upstream_sources = rcfg.get("sources", [])
        if not upstream_sources:
            # Custom-only rulesets (e.g. AI-China-Direct, Apple-Push-Experimental) are author-controlled
            continue

        target_file = os.path.join(dist_dir, f"{name}.lsr")
        prev_count = count_lsr_rules(target_file)
        new_count = len(staged_rules_by_set.get(name, []))
        max_shrink_ratio = float(rcfg.get("max_shrink_ratio", default_max_shrink))

        if prev_count > 0 and new_count < prev_count:
            drop_count = prev_count - new_count
            shrink_ratio = drop_count / float(prev_count)
            if shrink_ratio > max_shrink_ratio:
                raise RuntimeError(
                    f"CRITICAL: Ruleset '{name}' shrank abnormally by {shrink_ratio:.1%} "
                    f"({prev_count} -> {new_count} rules, dropped {drop_count} rules), "
                    f"exceeding maximum allowed shrinkage threshold of {max_shrink_ratio:.1%}. "
                    f"Build halted to protect dist."
                )

    # 6. Atomic write to temporary staging directory first
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

        # 7. Update upstream lock file only after all validations pass and dist is updated
        if has_upstream_sources:
            save_upstream_lock(new_lock_data, lock_file)
            print(f"[LOCKED] Upstream rule baselines saved to {lock_file}")

        print(f"\n[SUCCESS] Build complete. {updated_count} files updated in {dist_dir}.")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build and validate Loon rulesets.")
    parser.add_argument(
        "--init-baseline",
        "--allow-new-baseline",
        dest="allow_new_baseline",
        action="store_true",
        help="Explicitly establish baselines for newly added upstreams or initialize missing lock file."
    )
    args = parser.parse_args()
    build_rulesets(allow_new_baseline=args.allow_new_baseline)

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"\n[BUILD ABORTED] Error: {err}", file=sys.stderr)
        sys.exit(1)
