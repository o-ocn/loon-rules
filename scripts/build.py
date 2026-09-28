#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Rules Generator, Validator, and Diagnostic Manifest Builder
Fail-stop upstream fetching, atomic staging, idempotence, cross-service conflict detection,
and 100% strategy-neutral rule generation.
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
import subprocess
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.yml")
RULES_CUSTOM_DIR = os.path.join(BASE_DIR, "rules", "custom")
DIST_DIR = os.path.join(BASE_DIR, "dist")
DIAGNOSTICS_DIR = os.path.join(BASE_DIR, "diagnostics")
DIST_DIAGNOSTICS_DIR = os.path.join(DIST_DIR, "diagnostics")
SERVICES_FILE = os.path.join(DIAGNOSTICS_DIR, "services.yml")
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

# Explicitly verified and whitelisted parent-subdomain service delegations.
# (child_ruleset, parent_ruleset): Subdomain in child is legitimately carved out from parent suffix.
KNOWN_SAFE_DELEGATIONS = {
    # Gemini / AI Studio (AI-Overseas) carved out from Google
    "gemini.google.com": ("AI-Overseas", "Google"),
    "bard.google.com": ("AI-Overseas", "Google"),
    "aistudio.google.com": ("AI-Overseas", "Google"),
    "makersuite.google.com": ("AI-Overseas", "Google"),
    "ai.google.dev": ("AI-Overseas", "Google"),
    "deepmind.com": ("AI-Overseas", "Google"),
    "apis.google.com": ("AI-Overseas", "Google"),
    "generativelanguage.googleapis.com": ("AI-Overseas", "Google"),
    "alkalimakersuite-pa.clients6.google.com": ("AI-Overseas", "Google"),
    "proactivebackend-pa.googleapis.com": ("AI-Overseas", "Google"),
    "webchannel-robinfrontend-pa.googleapis.com": ("AI-Overseas", "Google"),
    "robinfrontend-pa.googleapis.com": ("AI-Overseas", "Google"),
    "geminiweb-pa.googleapis.com": ("AI-Overseas", "Google"),
    "gemini.gstatic.com": ("AI-Overseas", "Google"),
    "cloudcode-pa.googleapis.com": ("AI-Overseas", "Google"),

    # Google Drive (GoogleDrive) carved out from Google
    "drive.google.com": ("GoogleDrive", "Google"),
    "docs.google.com": ("GoogleDrive", "Google"),
    "googledrive.com": ("GoogleDrive", "Google"),
    "drive-thirdparty.google.com": ("GoogleDrive", "Google"),
    "filepickup.google.com": ("GoogleDrive", "Google"),

    # YouTube carved out from Google
    "video.google.com": ("YouTube", "Google"),
    "wide-youtube.l.google.com": ("YouTube", "Google"),
    "youtube-ui.l.google.com": ("YouTube", "Google"),
    "youtube.googleapis.com": ("YouTube", "Google"),
    "youtubeembeddedplayer.googleapis.com": ("YouTube", "Google"),
    "youtubei.googleapis.com": ("YouTube", "Google"),

    # Google GVT services under YouTube GVT suffix
    "beacons.gvt2.com": ("Google", "YouTube"),
    "beacons2.gvt2.com": ("Google", "YouTube"),
    "beacons3.gvt2.com": ("Google", "YouTube"),
    "gcp.gvt2.com": ("Google", "YouTube"),
    "redirector.gcpcdn.gvt1.com": ("Google", "YouTube"),
    "redirector.gvt1.com": ("Google", "YouTube"),
    "redirector.offline-maps.gvt1.com": ("Google", "YouTube"),
    "redirector.snap.gvt1.com": ("Google", "YouTube"),

    # Discord Dynamic Links (Discord) carved out from Google Firebase / Storage
    "discord-attachments-uploads-prd.storage.googleapis.com": ("Discord", "Google"),
    "discordapp.page.link": ("Discord", "Google"),

    # Apple Media (Apple-Media) carved out from Apple-Direct
    "tv.apple.com": ("Apple-Media", "Apple-Direct"),
    "tv.applemusic.com": ("Apple-Media", "Apple-Direct"),
    "linear.tv.apple.com": ("Apple-Media", "Apple-Direct"),
    "news-client.apple.com": ("Apple-Media", "Apple-Direct"),
    "news-client-search.apple.com": ("Apple-Media", "Apple-Direct"),
    "news-assets.apple.com": ("Apple-Media", "Apple-Direct"),
    "news-edge.apple.com": ("Apple-Media", "Apple-Direct"),
    "gspe1-ssl.ls.apple.com": ("Apple-Media", "Apple-Direct"),
    "apple.news": ("Apple-Media", "Apple-Direct"),
    "fitness.apple.com": ("Apple-Media", "Apple-Direct"),
    "amp-api.fitness.apple.com": ("Apple-Media", "Apple-Direct"),
    "play-edge.itunes.apple.com": ("Apple-Media", "Apple-Direct"),
    "np-edge.itunes.apple.com": ("Apple-Media", "Apple-Direct"),
    "uts-api.itunes.apple.com": ("Apple-Media", "Apple-Direct"),
    "hls.itunes.apple.com": ("Apple-Media", "Apple-Direct"),
    "hls-amt.itunes.apple.com": ("Apple-Media", "Apple-Direct"),

    # TestFlight carved out from Apple-Direct
    "testflight.apple.com": ("TestFlight", "Apple-Direct"),
    "beta.itunes.apple.com": ("TestFlight", "Apple-Direct"),

    # APNs (Apple-Push) carved out from Apple-Direct
    "push.apple.com": ("Apple-Push", "Apple-Direct"),
    "courier.push.apple.com": ("Apple-Push", "Apple-Direct"),
}

def count_lsr_rules(filepath):
    """Counts valid non-comment rule lines in an existing .lsr file."""
    if not os.path.isfile(filepath):
        return 0
    count = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if clean and not clean.startswith(("#", ";")):
                count += 1
    return count

def compute_file_sha256(filepath):
    """Computes hex sha256 checksum for a file."""
    if not os.path.isfile(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def get_git_revision():
    """Gets short git commit hash or timestamp fallback."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR,
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        if out:
            return out
    except Exception:
        pass
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

def load_upstream_lock(lock_file=UPSTREAM_LOCK_FILE, allow_missing=False):
    """Loads previously recorded valid upstream rule counts."""
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
    """Atomically saves recorded valid upstream rule counts to lock_file."""
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

def detect_upstream_overlaps(custom_rules, upstream_rules_by_source, ruleset_name=""):
    """
    Finds custom rules that are already officially covered by upstream sources.
    Returns list of overlap dicts: [{'ruleset': ..., 'rule': ..., 'upstream': ..., 'custom_file': ...}]
    """
    overlaps = []
    c_set = set(custom_rules) if isinstance(custom_rules, (list, tuple, set)) else set()
    for sname, up_rules in upstream_rules_by_source.items():
        for r in up_rules:
            if r in c_set:
                overlaps.append({
                    "ruleset": ruleset_name or "Custom",
                    "custom_file": f"rules/custom/{ruleset_name}.list" if ruleset_name else "rules/custom/*.list",
                    "rule": r,
                    "upstream": sname
                })
    return overlaps

def parse_yaml_fallback(filepath):
    """Robust stack-based indentation YAML parser for sources.yml and services.yml."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cfg = {"metadata": {}, "rulesets": {}, "services": [], "physical_verification_items": []}
    current_section = None
    current_ruleset = None
    current_source = None
    in_filter_excluded = False
    current_service = None
    in_expected_status = False

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
            current_service = None
            in_filter_excluded = False
            in_expected_status = False
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

        if current_section == "physical_verification_items":
            if stripped.startswith("- "):
                val = stripped[2:].strip().strip('"\'')
                cfg["physical_verification_items"].append(val)
            continue

        if current_section == "services":
            if indent == 2 and stripped.startswith("- "):
                current_service = {}
                cfg["services"].append(current_service)
                item = stripped[2:].strip()
                if ":" in item:
                    k, v = item.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    current_service[k] = v
                continue
            if indent == 4 and current_service is not None:
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"\'')
                    if k == "expected_status":
                        if v.startswith("[") and v.endswith("]"):
                            nums = [int(n.strip()) for n in v[1:-1].split(",") if n.strip()]
                            current_service[k] = nums
                        else:
                            current_service[k] = []
                            in_expected_status = True
                    elif k == "quick":
                        current_service[k] = v.lower() in ("true", "1", "yes")
                    else:
                        current_service[k] = v
                continue

        if current_section == "rulesets":
            if indent == 2 and stripped.endswith(":"):
                current_ruleset = stripped[:-1].strip()
                cfg["rulesets"][current_ruleset] = {"sources": []}
                current_source = None
                in_filter_excluded = False
                continue

            if not current_ruleset:
                continue

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

            if indent >= 10:
                if stripped.startswith("- ") and in_filter_excluded and current_source is not None:
                    ex_val = stripped[2:].strip().strip('"\'')
                    current_source["filter_excluded"].append(ex_val)
                continue

    return cfg

def load_yaml(filepath):
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"YAML config not found: {filepath}")
    try:
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        return parse_yaml_fallback(filepath)

def load_sources(filepath=SOURCES_FILE):
    return load_yaml(filepath)

def clean_rule_line(line):
    """
    Cleans and standardizes rule line syntax while enforcing policy-neutrality.
    Strips any trailing DIRECT, PROXY, REJECT or policy group names.
    Preserves valid 'no-resolve' parameters.
    """
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

    # Retain no-resolve parameter if present; strip all trailing policy actions
    has_no_resolve = any(p.lower() == "no-resolve" for p in parts[1:])
    if has_no_resolve:
        return f"{rule_type},{value},no-resolve"
    else:
        return f"{rule_type},{value}"

def prune_intra_set_redundancies(rules):
    """
    Prunes redundant subdomains in the SAME ruleset when covered by DOMAIN-SUFFIX.
    E.g. If DOMAIN-SUFFIX,push.apple.com is present, DOMAIN,courier.push.apple.com is pruned.
    """
    suffixes = set()
    for r in rules:
        parts = r.split(",")
        if parts[0].upper() == "DOMAIN-SUFFIX":
            suffixes.add(parts[1].strip().lower())

    pruned = []
    for r in rules:
        parts = r.split(",")
        rtype = parts[0].upper()
        rval = parts[1].strip().lower()
        if rtype == "DOMAIN":
            if rval in suffixes:
                continue
            is_sub = False
            subparts = rval.split(".")
            for i in range(1, len(subparts)):
                parent = ".".join(subparts[i:])
                if parent in suffixes:
                    is_sub = True
                    break
            if is_sub:
                continue
        pruned.append(r)
    return pruned

UPSTREAM_CACHE_DIR = os.path.join(BASE_DIR, "scripts", ".upstream_cache")

def get_upstream_cache_path(url):
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return os.path.join(UPSTREAM_CACHE_DIR, f"{url_hash}.list")

def fetch_upstream_strict(url, min_rules=2, timeout=15, max_retries=3, allow_offline_cache=False):
    """
    Fetches upstream rule list with strict retries, caching, and fail-stop guarantees.
    HTTP 404/500, abnormally few rules, and syntax errors fail immediately.
    Offline cache is ONLY used when allow_offline_cache=True is explicitly enabled.
    Returns: tuple (rule_text, used_offline_cache)
    """
    cache_path = get_upstream_cache_path(url)
    last_err = None
    network_failed = False
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Loon-Rules-Builder/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP status {response.status} when fetching {url}")
                body = response.read().decode("utf-8", errors="strict")
                lines = [l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith(("#", ";"))]
                if len(lines) < min_rules:
                    # Abnormally few rules is a fatal corruption from upstream; must NOT fall back to cache
                    raise RuntimeError(
                        f"Upstream returned abnormally few rules ({len(lines)} < min_rules {min_rules}) from {url}"
                    )
                try:
                    os.makedirs(UPSTREAM_CACHE_DIR, exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(body)
                except Exception:
                    pass
                return body, False
        except urllib.error.HTTPError as e:
            # Fatal upstream HTTP response (404, 500, etc.) must NEVER fall back to cache or disguise as synced
            raise RuntimeError(f"CRITICAL: Upstream returned HTTP {e.code} ({e.reason}) for {url}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            network_failed = True
            if attempt < max_retries:
                import time
                time.sleep(0.5)
                continue
        except Exception as e:
            # Fatal upstream response error (e.g. abnormally few rules, syntax error); fail immediately!
            raise

    # Fallback to local cache ONLY when network is genuinely unavailable/offline and allow_offline_cache is True
    if network_failed and allow_offline_cache and os.path.isfile(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_body = f.read()
            lines = [l.strip() for l in cached_body.splitlines() if l.strip() and not l.strip().startswith(("#", ";"))]
            if len(lines) >= min_rules:
                print(f"  [OFFLINE CACHE] Network unavailable, loaded {len(lines)} rules from cache for {url}")
                return cached_body, True
        except Exception:
            pass

    raise RuntimeError(f"CRITICAL: Failed to fetch upstream rule from {url} after {max_retries} attempts: {last_err}") from last_err

def recover_interrupted_dist(dist_dir: str = DIST_DIR) -> bool:
    """
    Checks for interrupted previous builds and recovers dist/ from .dist_old if needed.
    Returns True if recovery was performed, False otherwise.
    """
    dist_parent = os.path.dirname(os.path.abspath(dist_dir)) or BASE_DIR
    dist_old = os.path.join(dist_parent, ".dist_old")
    if not os.path.exists(dist_old):
        return False

    # Check if dist_dir is missing or broken (e.g., less than expected .lsr files)
    is_broken = False
    if not os.path.isdir(dist_dir):
        is_broken = True
    else:
        existing_lsrs = [f for f in os.listdir(dist_dir) if f.endswith(".lsr")]
        if len(existing_lsrs) < 10:  # Incomplete directory
            is_broken = True

    if is_broken:
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir, ignore_errors=True)
        os.rename(dist_old, dist_dir)
        print(f"[CRASH RECOVERY] Interrupted build detected! Successfully restored previous dist/ from {dist_old}.")
        return True
    else:
        # dist_dir is intact, safe to clean up stale .dist_old
        shutil.rmtree(dist_old, ignore_errors=True)
        return False

def switch_dist_directory(dist_new: str, dist_dir: str = DIST_DIR) -> None:
    """
    Two-stage staged directory switch with in-flight rollback protection and crash recovery.

    Design Note & Technical Guarantee:
    On Windows NTFS and standard POSIX filesystems without atomic directory symlinks,
    renaming an existing non-empty directory is a 2-stage operation:
    1. rename dist -> .dist_old
    2. rename dist_new -> dist
    Between step 1 and step 2, there is a sub-millisecond gap where dist does not exist.
    If a power failure or SIGKILL process termination occurs precisely inside this gap,
    automatic recovery is guaranteed on the next run via recover_interrupted_dist().
    If an exception occurs during step 2, instant in-flight rollback restores .dist_old -> dist.
    We honestly withdraw any unconditional claim that external readers never see an intermediate gap.
    """
    dist_parent = os.path.dirname(os.path.abspath(dist_dir)) or BASE_DIR
    dist_old = os.path.join(dist_parent, ".dist_old")

    recover_interrupted_dist(dist_dir)
    if os.path.exists(dist_old):
        shutil.rmtree(dist_old, ignore_errors=True)

    if os.path.exists(dist_dir):
        os.rename(dist_dir, dist_old)

    try:
        os.rename(dist_new, dist_dir)
        if os.path.exists(dist_old):
            shutil.rmtree(dist_old, ignore_errors=True)
        print(f"[STAGED SWITCH] Successfully replaced entire dist/ directory with crash-recovery protection.")
    except Exception as e:
        # In-flight rollback: restore .dist_old -> dist_dir
        if os.path.exists(dist_old) and not os.path.exists(dist_dir):
            try:
                os.rename(dist_old, dist_dir)
                print(f"[ROLLBACK] Restored previous dist/ directory following failed switch.")
            except Exception as rb_err:
                raise RuntimeError(f"Switch failed and rollback also encountered error: {rb_err}") from e
        raise RuntimeError(f"Directory switch failed, previous dist restored: {e}") from e

def build_rulesets(sources_file=SOURCES_FILE, dist_dir=DIST_DIR, lock_file=UPSTREAM_LOCK_FILE, allow_new_baseline=False, offline=False):
    recover_interrupted_dist(dist_dir)
    print(f"[*] Starting Loon Rules Build at {datetime.now(timezone.utc).isoformat()}...")
    cfg = load_sources(sources_file)
    rulesets = cfg.get("rulesets", {})
    if not rulesets:
        raise ValueError("No rulesets defined in sources.yml")

    env_allow = os.getenv("ALLOW_NEW_UPSTREAM_BASELINE", "").lower() in ("1", "true", "yes")
    allow_new_baseline = allow_new_baseline or env_allow

    offline_mode = offline or (os.getenv("LOON_BUILD_OFFLINE", "").lower() in ("1", "true", "yes")) or ("--offline" in sys.argv)
    any_offline_cache_used = False

    default_max_shrink = float(cfg.get("metadata", {}).get("max_shrink_ratio", 0.15))
    has_upstream_sources = any(rcfg.get("sources") for rcfg in rulesets.values())

    if has_upstream_sources:
        lock_data = load_upstream_lock(lock_file, allow_missing=allow_new_baseline)
    else:
        lock_data = {}

    new_lock_data = {}

    staged_rules_by_set = {}
    rule_to_set_map = {}       # (rule_type, rule_val) -> ruleset_name
    parent_domains = {}        # domain_suffix -> ruleset_name
    upstream_overlaps = []     # List of overlapping custom rules covered by upstream

    for name, rcfg in rulesets.items():
        custom_file_rel = rcfg.get("local_custom", "")
        custom_file = os.path.join(BASE_DIR, custom_file_rel) if custom_file_rel else ""
        collected_rules = []
        custom_rules_for_set = set()
        seen = set()

        # 1. Load custom rules first (highest author priority)
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
                            custom_rules_for_set.add(cleaned)

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
                raw_text, used_cache = fetch_upstream_strict(surl, min_rules=min_r, allow_offline_cache=offline_mode)
                if used_cache:
                    any_offline_cache_used = True

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
                        if cleaned in custom_rules_for_set:
                            upstream_overlaps.append({
                                "ruleset": name,
                                "custom_file": custom_file_rel,
                                "rule": cleaned,
                                "upstream": sname
                            })
                        if cleaned not in seen:
                            seen.add(cleaned)
                            collected_rules.append(cleaned)

        # Intra-ruleset deduplication and parent domain pruning
        pruned_rules = prune_intra_set_redundancies(collected_rules)
        staged_rules_by_set[name] = pruned_rules
        print(f"  [=] Ruleset '{name}': {len(pruned_rules)} rules loaded (pruned {len(collected_rules) - len(pruned_rules)} redundant subdomains).")

        # Record rule mapping for ALL rule types for cross-ruleset duplicate check
        for r in pruned_rules:
            parts = r.split(",")
            rtype = parts[0].upper()
            rval = parts[1].strip()
            if rtype in ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"):
                rval = rval.lower()

            rule_key = (rtype, rval)
            if rule_key in rule_to_set_map:
                prev_set = rule_to_set_map[rule_key]
                if prev_set != name:
                    raise ValueError(
                        f"FATAL CONFLICT: Exact rule '{rtype},{rval}' is mapped to both '{prev_set}' "
                        f"and '{name}'! Ambiguous service assignment is forbidden."
                    )
            rule_to_set_map[rule_key] = name

            if rtype == "DOMAIN-SUFFIX":
                parent_domains[rval] = name

    # 3. Check for illegal parent-domain shadowing across different rulesets
    for (rtype, rval), c_set in rule_to_set_map.items():
        if rtype in ("DOMAIN", "DOMAIN-SUFFIX"):
            domain = rval
            parts = domain.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[i:])
                if parent in parent_domains:
                    p_set = parent_domains[parent]
                    if p_set != c_set:
                        if domain in KNOWN_SAFE_DELEGATIONS:
                            expected_child, expected_parent = KNOWN_SAFE_DELEGATIONS[domain]
                            if c_set == expected_child and p_set == expected_parent:
                                continue  # Safe, intentional service delegation
                        raise ValueError(
                            f"FATAL SHADOWING: Subdomain '{domain}' in '{c_set}' is shadowed by parent "
                            f"suffix '{parent}' in '{p_set}' without verified delegation! Build halted."
                        )

    # 4. Strict assertions for service isolation and policy neutrality
    ai_rules = staged_rules_by_set.get("AI-Overseas", [])
    forbidden_in_ai = [
        "DOMAIN-SUFFIX,googleapis.com", "DOMAIN-SUFFIX,google.com",
        "DOMAIN-SUFFIX,googleusercontent.com",
        "DOMAIN-SUFFIX,x.com", "DOMAIN-SUFFIX,twitter.com",
        "DOMAIN-SUFFIX,facebook.com", "DOMAIN-SUFFIX,instagram.com", "DOMAIN-SUFFIX,meta.com",
        "DOMAIN-SUFFIX,whatsapp.com",
        "DOMAIN-SUFFIX,stripe.com", "DOMAIN-SUFFIX,auth0.com", "DOMAIN-SUFFIX,sentry.io",
        "DOMAIN-SUFFIX,intercom.io", "DOMAIN-SUFFIX,launchdarkly.com", "IP-ASN,20473,no-resolve",
        "DOMAIN-KEYWORD,openai",
        "DOMAIN-SUFFIX,client-api.arkoselabs.com", "DOMAIN,client-api.arkoselabs.com",
        "DOMAIN-SUFFIX,host.livekit.cloud", "DOMAIN,host.livekit.cloud",
        "DOMAIN-SUFFIX,turn.livekit.cloud", "DOMAIN,turn.livekit.cloud",
        "DOMAIN,www.googleapis.com"
    ]
    for fb in forbidden_in_ai:
        if fb in ai_rules:
            raise ValueError(f"CRITICAL: Prohibited broad/shared rule '{fb}' found in AI-Overseas.lsr! Halting build.")

    for r in ai_rules:
        if r.startswith("DOMAIN-KEYWORD,"):
            kw = r.split(",")[1].lower()
            if kw in ("google", "twitter", "x", "meta", "facebook", "apple"):
                raise ValueError(f"CRITICAL: Prohibited broad keyword rule '{r}' found in AI-Overseas.lsr! Halting build.")

    # Shared Google API and Drive assertions
    drive_rules = staged_rules_by_set.get("GoogleDrive", [])
    if "DOMAIN,www.googleapis.com" in drive_rules:
        raise ValueError("CRITICAL: Shared API 'www.googleapis.com' must not be placed in GoogleDrive.lsr!")
    if "DOMAIN-SUFFIX,googleusercontent.com" in drive_rules:
        raise ValueError("CRITICAL: Broad 'googleusercontent.com' must not be placed in GoogleDrive.lsr!")

    # APNs minimal assertion
    push_rules = staged_rules_by_set.get("Apple-Push", [])
    for pr in push_rules:
        if "17.0.0.0/8" in pr or "apple.com" in pr and not "push.apple.com" in pr:
            raise ValueError(f"CRITICAL: Apple-Push contains broad rule '{pr}', violating minimal APNs scope!")

    # 5. Relative shrinkage check for all auto-synced rulesets against previous valid dist version
    default_max_shrink = float(cfg.get("metadata", {}).get("max_shrink_ratio", 0.15))
    for name, rcfg in rulesets.items():
        upstream_sources = rcfg.get("sources", [])
        if not upstream_sources:
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

    # 6. Atomic write to temporary staging directory on E: drive first
    staging_dir = tempfile.mkdtemp(prefix="loon_dist_staging_", dir=BASE_DIR)
    staging_diag_dir = os.path.join(staging_dir, "diagnostics")
    os.makedirs(staging_diag_dir, exist_ok=True)

    try:
        generated_files = {}
        ruleset_metadata = {}

        for name, rlist in staged_rules_by_set.items():
            staging_file = os.path.join(staging_dir, f"{name}.lsr")
            desc = rulesets[name].get("description", "")
            rule_body = "\n".join(rlist)
            content_hash = hashlib.sha256(rule_body.encode("utf-8")).hexdigest()[:12]
            full_sha256 = hashlib.sha256(rule_body.encode("utf-8")).hexdigest()

            # Strategy Neutral Header: NO recommended policy, NO region, NO proxy group
            with open(staging_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(f"# NAME: {name}\n")
                f.write(f"# DESCRIPTION: {desc}\n")
                f.write(f"# AUTHOR: o-ocn\n")
                f.write(f"# REVISION: {content_hash}\n")
                f.write(f"# TOTAL: {len(rlist)}\n")
                f.write("# ==============================================================================\n")
                if rlist:
                    f.write(rule_body + "\n")

            generated_files[name] = staging_file
            ruleset_metadata[f"{name}.lsr"] = {
                "total_rules": len(rlist),
                "revision": content_hash,
                "sha256": full_sha256,
                "description": desc
            }

        # 7. Check for changes against existing dist/
        os.makedirs(dist_dir, exist_ok=True)
        os.makedirs(DIST_DIAGNOSTICS_DIR, exist_ok=True)

        files_to_update = {}
        for name, s_file in generated_files.items():
            target_file = os.path.join(dist_dir, f"{name}.lsr")
            with open(s_file, "r", encoding="utf-8") as f:
                new_data = f.read()
            if os.path.isfile(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    old_data = f.read()
                if old_data != new_data:
                    files_to_update[name] = new_data
            else:
                files_to_update[name] = new_data

        lpx_src = os.path.join(DIAGNOSTICS_DIR, "LoonRules-Diagnostic.lpx")
        js_src = os.path.join(DIAGNOSTICS_DIR, "loon-rules-diagnostic.js")
        lpx_dst = os.path.join(DIST_DIAGNOSTICS_DIR, "LoonRules-Diagnostic.lpx")
        js_dst = os.path.join(DIST_DIAGNOSTICS_DIR, "loon-rules-diagnostic.js")
        manifest_dst = os.path.join(DIST_DIAGNOSTICS_DIR, "manifest.json")

        diag_scripts_changed = False
        for s_p, d_p in [(lpx_src, lpx_dst), (js_src, js_dst)]:
            if os.path.isfile(s_p):
                with open(s_p, "rb") as f:
                    s_b = f.read()
                d_b = b""
                if os.path.isfile(d_p):
                    with open(d_p, "rb") as f:
                        d_b = f.read()
                if s_b != d_b:
                    diag_scripts_changed = True

        has_manifest = os.path.isfile(manifest_dst)

        # Compute deterministic package signature across all sorted rulesets
        pkg_h = hashlib.sha256()
        for rname in sorted(ruleset_metadata.keys()):
            m = ruleset_metadata[rname]
            pkg_h.update(f"{rname}:{m['sha256']}:{m['revision']}:{m['total_rules']}\n".encode("utf-8"))
        package_sha256 = pkg_h.hexdigest()
        content_rev = package_sha256[:12]

        existing_manifest_content_rev = None
        if os.path.isfile(manifest_dst):
            try:
                with open(manifest_dst, "r", encoding="utf-8") as f:
                    old_m = json.load(f)
                    existing_manifest_content_rev = old_m.get("content_revision")
            except Exception:
                existing_manifest_content_rev = None

        # Requirement 16: Zero-change build idempotence
        # If no ruleset changed and diagnostic scripts didn't change and manifest exists with matching content hash,
        # preserve previous release artifacts and manifest.json without modifying timestamps!
        is_zero_change = (len(files_to_update) == 0 and not diag_scripts_changed and has_manifest and (existing_manifest_content_rev == content_rev))

        services_cfg = load_yaml(SERVICES_FILE) if os.path.isfile(SERVICES_FILE) else {}
        git_rev = get_git_revision()
        build_time = datetime.now(timezone.utc).isoformat()

        change_summary_lines = []
        change_summary_lines.append("\n==================== 规则构建与诊断更新摘要 ====================")
        change_summary_lines.append(f"构建时间: {build_time} | Content Revision: {content_rev} | Git Source: {git_rev}")
        change_summary_lines.append(f"维护规则集: 共 {len(generated_files)} 个独立服务分类 (策略中立)")

        if is_zero_change:
            for name in generated_files:
                target_file = os.path.join(dist_dir, f"{name}.lsr")
                cnt = count_lsr_rules(target_file)
                change_summary_lines.append(f"  [UNCHANGED]  {name}.lsr: {cnt} 条规则 (内容一致)")
            change_summary_lines.append(f"  [PRESERVED]  diagnostics/manifest.json: 规则无变化，保留上一版时间戳与构建成品 (满足第16条)")
            updated_count = 0
        else:
            # Transactional deployment: Stage entire dist structure first, then swap with rollback protection
            dist_backup = os.path.join(BASE_DIR, ".dist_backup")
            dist_new = os.path.join(staging_dir, "dist_new")
            dist_new_diag = os.path.join(dist_new, "diagnostics")
            os.makedirs(dist_new_diag, exist_ok=True)

            # Copy all generated .lsr files to dist_new
            for name, s_file in generated_files.items():
                shutil.copy2(s_file, os.path.join(dist_new, f"{name}.lsr"))

            # Copy diagnostic scripts to dist_new
            for s_p, d_fname in [(lpx_src, "LoonRules-Diagnostic.lpx"), (js_src, "loon-rules-diagnostic.js")]:
                if os.path.isfile(s_p):
                    shutil.copy2(s_p, os.path.join(dist_new_diag, d_fname))

            # Generate and write new manifest.json atomically to dist_new
            manifest_data = {
                "schema_version": "1.0",
                "build_timestamp": build_time,
                "content_revision": content_rev,
                "package_sha256": package_sha256,
                "repository": "https://github.com/o-ocn/loon-rules",
                "primary_base": "https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist",
                "backup_base": "https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist",
                "rulesets": ruleset_metadata,
                "upstream_sync_status": "offline_cached (离线缓存构建，非实时同步)" if any_offline_cache_used else "synced",
                "services": services_cfg.get("services", []),
                "physical_verification_items": services_cfg.get("physical_verification_items", [
                    "APNs TCP 5223 系统级长连接与锁屏即时通知 (apsd)",
                    "Telegram 锁屏/蜂窝网络下的后台消息唤醒与推送延迟",
                    "HomeKit 室内摄像头即时视频画面流推流与门铃",
                    "Apple Watch 独立 Wi-Fi/蜂窝联网与天气表盘刷新",
                    "第三方依赖 CloudKit 的 App (爱乐记、猿音) 真实多端双向同步"
                ])
            }
            with open(os.path.join(dist_new_diag, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            # Count updated files summary before atomic switch
            updated_count = 0
            for name, s_file in generated_files.items():
                target_file = os.path.join(dist_dir, f"{name}.lsr")
                new_cnt = len(staged_rules_by_set.get(name, []))
                if name in files_to_update:
                    prev_cnt = count_lsr_rules(target_file) if os.path.isfile(target_file) else 0
                    delta = new_cnt - prev_cnt
                    delta_str = f"({'+' if delta > 0 else ''}{delta})" if delta != 0 else "(修改)"
                    change_summary_lines.append(f"  [UPDATED]    {name}.lsr: {new_cnt} 条规则 {delta_str}")
                    updated_count += 1
                else:
                    change_summary_lines.append(f"  [UNCHANGED]  {name}.lsr: {new_cnt} 条规则 (内容一致)")

            # Directory-level staged switch with rollback and crash recovery
            switch_dist_directory(dist_new, dist_dir)
            print(f"[UPDATED] diagnostics/manifest.json (build_timestamp: {build_time}, content_revision: {content_rev})")

            # Update lock baseline when dist genuinely updated
            if has_upstream_sources:
                save_upstream_lock(new_lock_data, lock_file)
                print(f"[LOCKED] Upstream rule baselines saved to {lock_file}")

        # Requirement 9: Prompt user if upstream officially covers custom rules
        if upstream_overlaps:
            change_summary_lines.append("\n-------------------- [UPSTREAM OVERLAP NOTICE] --------------------")
            change_summary_lines.append(f"提示: 检测到 {len(upstream_overlaps)} 条自定义规则已被成熟上游正式收录。")
            change_summary_lines.append("根据规则三层结构准则 (上游覆盖主体，Custom 仅补例外)，建议核对后从 rules/custom/*.list 中清理：")
            for ov in upstream_overlaps:
                change_summary_lines.append(f"  - [{ov['ruleset']}] '{ov['rule']}' 已被上游 '{ov['upstream']}' 收录 (文件: {ov['custom_file']})")
            change_summary_lines.append("-------------------------------------------------------------------")

        change_summary_lines.append("----------------------------------------------------------------")
        change_summary_lines.append("策略中立声明: 所有 .lsr 均未写入策略组名称、节点或动作，用户在 Loon 中自由绑定。")
        change_summary_lines.append("================================================================")
        print("\n".join(change_summary_lines))
        print(f"\n[SUCCESS] Build complete. {updated_count} ruleset files updated in {dist_dir}.")
        return {"updated_count": updated_count, "overlaps": upstream_overlaps, "rulesets": ruleset_metadata, "is_zero_change": is_zero_change}

    except Exception as e:
        failure_log = os.path.join(dist_dir, ".build_failure.log") if os.path.isdir(dist_dir) else os.path.join(BASE_DIR, ".build_failure.log")
        try:
            with open(failure_log, "w", encoding="utf-8") as f:
                f.write("Loon Rules Build Failure Report\n")
                f.write(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Error: {e}\n")
        except Exception:
            pass
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build and validate Loon rulesets and diagnostic artifacts.")
    parser.add_argument(
        "--init-baseline",
        "--allow-new-baseline",
        dest="allow_new_baseline",
        action="store_true",
        help="Explicitly establish baselines for newly added upstreams or initialize missing lock file."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Explicitly allow offline cache fallback (marks manifest as offline_cached)."
    )
    args = parser.parse_args()
    build_rulesets(allow_new_baseline=args.allow_new_baseline, offline=args.offline)

if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"\n[BUILD ABORTED] Error: {err}", file=sys.stderr)
        sys.exit(1)
