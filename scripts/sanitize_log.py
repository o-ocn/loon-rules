#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Log Sanitizing Analyzer (Strict Privacy Protection)
Parses Loon request logs or HAR files, strictly extracts only verified hostnames,
timestamps, HTTP status codes, safe rule/policy labels, traffic volumes, and fixed
error categories. Completely discards URL paths, query strings, headers, bodies,
user credentials, and raw exception messages.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import re
import json
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")

HIGH_BANDWIDTH_THRESHOLD_BYTES = 5 * 1024 * 1024  # 5 MB

# Hostname validation regex (RFC 1123 compliant label characters)
HOSTNAME_REGEX = re.compile(r'^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*$')

# Strict ISO8601 timestamp validation regex
SAFE_TIMESTAMP_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$')

# Safe built-in policy labels in Loon
SAFE_BUILTIN_POLICIES = {"DIRECT", "PROXY", "REJECT", "REJECT-TINYGIF", "REJECT-DROP", "FINAL"}

# Safe rule prefixes
SAFE_RULE_PREFIXES = (
    "DOMAIN,", "DOMAIN-SUFFIX,", "DOMAIN-KEYWORD,",
    "IP-CIDR,", "IP-CIDR6,", "IP-ASN,",
    "GEOIP,", "USER-AGENT,", "URL-REGEX,", "RULE-SET,"
)

# Fixed safe error categories (Enum)
class ErrorCategory:
    NONE = "NONE"
    TIMEOUT = "TIMEOUT"
    DNS_FAILURE = "DNS_FAILURE"
    TLS_ERROR = "TLS_ERROR"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    HTTP_4XX = "HTTP_4XX"
    HTTP_5XX = "HTTP_5XX"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

def extract_safe_host(url_or_host):
    """
    Extracts strictly validated lowercase hostname without userinfo, password, port, or path.
    Guarantees zero leakage of credentials in URLs (e.g. user:pass@host:port).
    """
    if not url_or_host:
        return ""
    raw = str(url_or_host).strip()

    # Prepend scheme if missing so urlsplit handles userinfo/port properly
    if "://" not in raw:
        target = "http://" + raw
    else:
        target = raw

    try:
        parsed = urllib.parse.urlsplit(target)
        hostname = parsed.hostname
        if not hostname:
            return ""
        hostname = hostname.lower().strip()
        # Verify characters against strict hostname regex
        if HOSTNAME_REGEX.match(hostname):
            return hostname
        return "invalid_host"
    except Exception:
        return "invalid_host"

def validate_safe_timestamp(raw_ts):
    """
    Validates that a timestamp strictly conforms to standard date/time format.
    Rejects and strips arbitrary text, usernames, or leaked tokens in timestamp fields.
    """
    if not raw_ts:
        return ""
    clean = str(raw_ts).strip()
    if SAFE_TIMESTAMP_REGEX.match(clean):
        return clean
    return ""

def sanitize_safe_rule_label(raw_rule):
    """
    Sanitizes rule label. Strictly admits only standard rule types or ruleset names.
    Rejects and discards sensitive tokens, HTTP headers (e.g. 'Authorization: Bearer'),
    passwords, cookies, or arbitrary user strings.
    """
    if not raw_rule:
        return ""
    clean = str(raw_rule).strip()
    lower = clean.lower()

    # Strict rejection of sensitive tokens, auth headers, and user info
    for bad in ("bearer", "authorization", "token", "secret", "password", "cookie", "session", "user@", "pass=", "api_key", "apikey"):
        if bad in lower:
            return ""

    if ":" in clean:
        return ""

    upper = clean.upper()
    if upper == "FINAL":
        return "FINAL"

    # If it is a standard rule prefix like DOMAIN,foo.com or IP-CIDR,1.2.3.4/24
    if any(upper.startswith(p) for p in SAFE_RULE_PREFIXES):
        parts = [p.strip() for p in clean.split(",")]
        rtype = parts[0].upper()
        rval = parts[1].strip() if len(parts) > 1 else ""
        if re.match(r'^[a-zA-Z0-9_\-\.:/]+$', rval) and len(rval) <= 80:
            return f"{rtype},{rval}"
        return rtype

    # If it is a clean ruleset filename or identifier, e.g. AI-Overseas.lsr, GoogleDrive
    if re.match(r'^[a-zA-Z0-9_\-\.]{1,40}$', clean):
        return clean

    return ""

def sanitize_safe_policy_label(raw_policy):
    """
    Sanitizes policy label.
    Preserves standard built-in actions (DIRECT, PROXY, REJECT, FINAL) or clean group category names.
    Strips and sanitizes private node names, device identifiers, host:ports, or tokens.
    """
    if not raw_policy:
        return ""
    clean = str(raw_policy).strip()
    upper = clean.upper()
    if upper in SAFE_BUILTIN_POLICIES:
        return upper

    lower = clean.lower()
    for bad in ("device-id", "device_", "node", "server", "bearer", "secret", "token", "password", "session", "@", ":", "/", "=", "?", "&"):
        if bad in lower:
            return "PROXY"

    # Allow safe category/group names like 'AI', 'Apple Push', 'Global', 'Google', 'China'
    if re.match(r'^[a-zA-Z0-9_\- ]{1,30}$', clean):
        return clean

    return "PROXY"

def sanitize_safe_label(label):
    """Fallback helper for backward compatibility."""
    return sanitize_safe_rule_label(label) or sanitize_safe_policy_label(label)

def classify_error_category(status, error_str=None):
    """
    Maps status and optional error hint to a fixed enum category.
    Guarantees no raw error string or credential is leaked into output records.
    """
    if error_str:
        low = str(error_str).lower()
        if any(k in low for k in ("timeout", "timed out", "etimeout")):
            return ErrorCategory.TIMEOUT
        if any(k in low for k in ("dns", "resolve", "enotfound", "getaddrinfo", "nodename")):
            return ErrorCategory.DNS_FAILURE
        if any(k in low for k in ("tls", "ssl", "cert", "handshake", "proto")):
            return ErrorCategory.TLS_ERROR
        if any(k in low for k in ("refused", "reset", "econnrefused", "abort")):
            return ErrorCategory.CONNECTION_REFUSED

    if 400 <= status < 500:
        return ErrorCategory.HTTP_4XX
    elif status >= 500:
        return ErrorCategory.HTTP_5XX
    elif status == 0 and error_str:
        return ErrorCategory.UNKNOWN_ERROR

    return ErrorCategory.NONE

def load_known_domains():
    """Loads all known domains and suffixes from dist/*.lsr to identify uncollected new domains."""
    known_exact = set()
    known_suffixes = set()
    if not os.path.isdir(DIST_DIR):
        return known_exact, known_suffixes

    for fname in os.listdir(DIST_DIR):
        if not fname.endswith(".lsr"):
            continue
        with open(os.path.join(DIST_DIR, fname), "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                clean = line.strip()
                if not clean or clean.startswith(("#", ";")):
                    continue
                parts = [p.strip() for p in clean.split(",")]
                if len(parts) >= 2:
                    rtype = parts[0].upper()
                    rval = parts[1].lower()
                    if rtype == "DOMAIN":
                        known_exact.add(rval)
                    elif rtype == "DOMAIN-SUFFIX":
                        known_suffixes.add(rval)
    return known_exact, known_suffixes

def is_domain_collected(host, known_exact, known_suffixes):
    if not host or host == "invalid_host":
        return True
    host = host.lower()
    if host in known_exact or host in known_suffixes:
        return True
    for sfx in known_suffixes:
        if host.endswith("." + sfx):
            return True
    return False

def sanitize_har(har_data, known_exact, known_suffixes):
    """
    Sanitizes HTTP Archive (HAR) format.
    Extracts strictly: host, timestamp, status, rule, policy, bytes, error_category.
    Completely ignores request/response headers, cookies, POST bodies, and URL paths/queries.
    """
    entries = har_data.get("log", {}).get("entries", [])
    sanitized_records = []

    for entry in entries:
        req = entry.get("request", {})
        resp = entry.get("response", {})

        raw_url = req.get("url", "")
        host = extract_safe_host(raw_url)
        if not host:
            continue

        req_size = max(0, req.get("bodySize", 0))
        resp_size = max(0, resp.get("bodySize", 0))
        total_bytes = req_size + resp_size
        if total_bytes == 0:
            total_bytes = max(0, resp.get("content", {}).get("size", 0))

        status = resp.get("status", 0)
        error_hint = entry.get("_error", "") or (resp.get("statusText", "") if status >= 400 else "")
        error_cat = classify_error_category(status, error_hint)

        raw_rule = entry.get("_rule", "") or entry.get("_matchRule", "")
        raw_pol = entry.get("_policy", "") or entry.get("_proxy", "")

        rule = sanitize_safe_rule_label(raw_rule)
        policy = sanitize_safe_policy_label(raw_pol)
        timestamp = validate_safe_timestamp(entry.get("startedDateTime", ""))

        is_failed = error_cat != ErrorCategory.NONE
        is_final = "final" in rule.lower() or "final" in policy.lower()
        is_uncollected = not is_domain_collected(host, known_exact, known_suffixes)
        is_high_bw = total_bytes >= HIGH_BANDWIDTH_THRESHOLD_BYTES

        # Suspected cross-service misclassification check
        suspected_issue = ""
        if host == "www.googleapis.com" and ("ai" in policy.lower() or "ai" in rule.lower()):
            suspected_issue = "www.googleapis.com 误入 AI 策略"
        elif "gemini" in host and ("google" in policy.lower() and "ai" not in policy.lower()):
            suspected_issue = "Gemini 流量落入通用 Google 策略"

        sanitized_records.append({
            "timestamp": timestamp,
            "host": host,
            "status": status,
            "rule": rule,
            "policy": policy,
            "bytes": total_bytes,
            "error_category": error_cat,
            "flags": {
                "failed": is_failed,
                "final": is_final,
                "uncollected": is_uncollected,
                "high_bandwidth": is_high_bw,
                "suspected_issue": suspected_issue
            }
        })

    return sanitized_records

def sanitize_text_log(text_content, known_exact, known_suffixes):
    """Sanitizes Loon request text log export."""
    lines = text_content.splitlines()
    sanitized_records = []

    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        host_match = re.search(r'https?://([^\s/\?#]+)', clean)
        raw_host = host_match.group(0) if host_match else ""
        if not raw_host:
            d_match = re.search(r'\b([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,})\b', clean)
            raw_host = d_match.group(1) if d_match else ""

        host = extract_safe_host(raw_host)
        if not host:
            continue

        ts_match = re.search(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?', clean)
        timestamp = validate_safe_timestamp(ts_match.group(0) if ts_match else "")

        status_match = re.search(r'\b(?:status[:\s=]+|code[:\s=]+)?([1-5]\d{2})\b', clean, re.IGNORECASE)
        status = int(status_match.group(1)) if status_match else 200

        pol_match = re.search(r'\[?(?:policy|proxy)[:\s=]+([^\]\s,]+)', clean, re.IGNORECASE)
        policy = sanitize_safe_policy_label(pol_match.group(1) if pol_match else "")

        rule_match = re.search(r'\[?(?:rule)[:\s=]+([^\]\s]+)', clean, re.IGNORECASE)
        rule = sanitize_safe_rule_label(rule_match.group(1) if rule_match else "")

        byte_match = re.search(r'(\d+)\s*(?:bytes|b|kb|mb)', clean, re.IGNORECASE)
        bytes_val = int(byte_match.group(1)) if byte_match else 0
        if "mb" in clean.lower():
            bytes_val *= (1024 * 1024)
        elif "kb" in clean.lower():
            bytes_val *= 1024

        error_cat = classify_error_category(status, clean if status >= 400 or status == 0 else None)

        is_failed = error_cat != ErrorCategory.NONE
        is_final = "final" in rule.lower() or "final" in policy.lower()
        is_uncollected = not is_domain_collected(host, known_exact, known_suffixes)
        is_high_bw = bytes_val >= HIGH_BANDWIDTH_THRESHOLD_BYTES

        suspected_issue = ""
        if host == "www.googleapis.com" and "ai" in policy.lower():
            suspected_issue = "www.googleapis.com 误入 AI 策略"
        elif "gemini" in host and "google" in policy.lower() and "ai" not in policy.lower():
            suspected_issue = "Gemini 流量落入通用 Google 策略"

        sanitized_records.append({
            "timestamp": timestamp,
            "host": host,
            "status": status,
            "rule": rule,
            "policy": policy,
            "bytes": bytes_val,
            "error_category": error_cat,
            "flags": {
                "failed": is_failed,
                "final": is_final,
                "uncollected": is_uncollected,
                "high_bandwidth": is_high_bw,
                "suspected_issue": suspected_issue
            }
        })

    return sanitized_records

def analyze_and_report(records):
    """Generates structured, zero-leak Chinese markdown diagnostic report."""
    total = len(records)
    failed = [r for r in records if r["flags"]["failed"]]
    final_hits = [r for r in records if r["flags"]["final"]]
    uncollected = [r for r in records if r["flags"]["uncollected"]]
    high_bw = [r for r in records if r["flags"]["high_bandwidth"]]
    suspected = [r for r in records if r["flags"]["suspected_issue"]]

    unique_uncollected = sorted(list(set(r["host"] for r in uncollected if r["host"] and r["host"] != "invalid_host")))

    report = []
    report.append("==================== Loon 请求日志脱敏分析报告 ====================")
    report.append(f"总请求数: {total} 条 | 隐私脱敏状态: 已完成严格主机与字段脱敏 (仅输出 Host/状态/流量/错误分类)")
    report.append("----------------------------------------------------------------")
    report.append("【统计概览】")
    report.append(f"  - 失败/异常请求: {len(failed)} 项")
    report.append(f"  - 命中 FINAL 兜底: {len(final_hits)} 项 (正常兜底，非故障判定)")
    report.append(f"  - 未收录新域名: {len(unique_uncollected)} 个独立 Host")
    report.append(f"  - 大流量传输 (>=5MB): {len(high_bw)} 项")
    report.append(f"  - 疑似跨分类冲突: {len(suspected)} 项")
    report.append("----------------------------------------------------------------")

    if suspected:
        report.append("【⚠ 疑似边界分类冲突】")
        for s in suspected[:10]:
            report.append(f"  - Host: {s['host']} | 策略: {s['policy']} | 判定: {s['flags']['suspected_issue']}")
        report.append("----------------------------------------------------------------")

    if high_bw:
        report.append("【大流量请求 (建议关注分流节点带宽)】")
        for hb in high_bw[:10]:
            mb = hb['bytes'] / (1024 * 1024)
            report.append(f"  - Host: {hb['host']} | 流量: {mb:.2f} MB | 命中规则: {hb['rule'] or '未知'}")
        report.append("----------------------------------------------------------------")

    if unique_uncollected:
        report.append("【未收录新域名列表 (供评估是否为新遗漏)】")
        for uh in unique_uncollected[:15]:
            report.append(f"  - {uh}")
        if len(unique_uncollected) > 15:
            report.append(f"  ... 另有 {len(unique_uncollected) - 15} 个未收录域名")
        report.append("----------------------------------------------------------------")

    if failed:
        report.append("【失败请求抽样 (固定脱敏分类)】")
        for f in failed[:5]:
            report.append(f"  - Host: {f['host']} | 状态: {f['status']} | 类别: {f['error_category']}")
        report.append("----------------------------------------------------------------")

    report.append("【真机能力边界提醒】")
    report.append("* APNs TCP 5223、Telegram 锁屏长连接、HomeKit 摄像头及 Watch 蜂窝行为需结合真机实测。")
    report.append("================================================================")
    return "\n".join(report)

def process_file(filepath, output_json=None):
    if not os.path.isfile(filepath):
        print(f"Error: Log file not found: {filepath}", file=sys.stderr)
        return 1

    known_exact, known_suffixes = load_known_domains()

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    is_har = False
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "log" in data:
            is_har = True
    except Exception:
        is_har = False

    if is_har:
        records = sanitize_har(data, known_exact, known_suffixes)
    else:
        records = sanitize_text_log(content, known_exact, known_suffixes)

    report_text = analyze_and_report(records)
    print(report_text)

    out_file = output_json
    if not out_file:
        out_file = filepath + ".sanitized.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\n[已保存脱敏数据] {out_file} (已完全剔除 URL 路径、查询参数、凭据、Cookie 及 Body)")
    return 0

def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/sanitize_log.py <path_to_log_or_har> [output.json]")
        print("说明: 本机执行脱敏并分析，严禁提交未脱敏原始日志。")
        sys.exit(1)

    log_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(process_file(log_path, out_path))

if __name__ == "__main__":
    main()
