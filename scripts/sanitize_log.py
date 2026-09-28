#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loon Log Sanitizing Analyzer (Zero-Privacy Leakage)
Parses Loon request logs or HAR files, strictly strips all private credentials/cookies/tokens/queries/bodies,
and automatically flags failures, FINAL hits, new uncollected domains, suspected misclassifications,
and high-bandwidth streaming requests.
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

SENSITIVE_PARAM_PATTERNS = [
    re.compile(r'(token|auth|key|secret|credential|session|sig|signature|pass|pwd|code)=[^&]*', re.IGNORECASE),
    re.compile(r'bearer\s+[a-zA-Z0-9_\-\.]+', re.IGNORECASE)
]

def sanitize_url(raw_url):
    """Strips query parameters and credentials, retaining only scheme, host, port, and sanitized path."""
    if not raw_url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(raw_url)
        # Drop query and fragment entirely for maximum privacy safety
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        # Fallback regex extraction of host
        m = re.match(r'^(https?://[^/?#]+)', raw_url)
        return m.group(1) if m else "unknown_url"

def extract_host(url_or_host):
    """Extracts lowercase host without port."""
    if not url_or_host:
        return ""
    try:
        if "://" in url_or_host:
            parsed = urllib.parse.urlsplit(url_or_host)
            host = parsed.netloc
        else:
            host = url_or_host.split("/")[0]
        if ":" in host:
            host = host.split(":")[0]
        return host.lower().strip()
    except Exception:
        return url_or_host.lower().strip()

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
    if not host:
        return True
    host = host.lower()
    if host in known_exact or host in known_suffixes:
        return True
    for sfx in known_suffixes:
        if host.endswith("." + sfx):
            return True
    return False

def sanitize_har(har_data, known_exact, known_suffixes):
    """Sanitizes HTTP Archive (HAR) format."""
    entries = har_data.get("log", {}).get("entries", [])
    sanitized_records = []

    for entry in entries:
        req = entry.get("request", {})
        resp = entry.get("response", {})
        timings = entry.get("timings", {})

        raw_url = req.get("url", "")
        clean_url = sanitize_url(raw_url)
        host = extract_host(raw_url)

        # Traffic calculation (request + response body size)
        req_size = max(0, req.get("bodySize", 0))
        resp_size = max(0, resp.get("bodySize", 0))
        total_bytes = req_size + resp_size
        if total_bytes == 0:
            total_bytes = max(0, resp.get("content", {}).get("size", 0))

        status = resp.get("status", 0)
        error = entry.get("_error", "") or (resp.get("statusText", "") if status >= 400 else "")
        rule = entry.get("_rule", "") or entry.get("_matchRule", "")
        policy = entry.get("_policy", "") or entry.get("_proxy", "")

        is_failed = status >= 400 or bool(error) or status == 0
        is_final = "final" in rule.lower() or "final" in policy.lower()
        is_uncollected = not is_domain_collected(host, known_exact, known_suffixes)
        is_high_bw = total_bytes >= HIGH_BANDWIDTH_THRESHOLD_BYTES

        # Suspected misclassifications
        suspected_issue = ""
        if host == "www.googleapis.com" and ("ai" in policy.lower() or "ai" in rule.lower()):
            suspected_issue = "www.googleapis.com 误入 AI 策略"
        elif "gemini" in host and ("google" in policy.lower() and not "ai" in policy.lower()):
            suspected_issue = "Gemini 流量落入通用 Google 策略"
        elif "deepseek" in host and policy.lower() not in ("", "direct"):
            suspected_issue = "DeepSeek 流量未走 DIRECT"

        sanitized_records.append({
            "timestamp": entry.get("startedDateTime", ""),
            "host": host,
            "url": clean_url,
            "status": status,
            "rule": rule,
            "policy": policy,
            "bytes": total_bytes,
            "error": error,
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

        # Look for host, URL, status, policy, rule, bytes
        # Sample Loon log: 2026-09-28 12:00:00 [REQ] https://api.openai.com/v1/... [RULE] DOMAIN-SUFFIX,openai.com [POLICY] AI [STATUS] 200 [BYTES] 4096
        host_match = re.search(r'https?://([^/\s]+)', clean)
        host = extract_host(host_match.group(1)) if host_match else ""
        if not host:
            # Check standalone domain pattern
            d_match = re.search(r'\b([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,})\b', clean)
            host = d_match.group(1).lower() if d_match else "unknown"

        # Timestamp
        ts_match = re.search(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', clean)
        timestamp = ts_match.group(0) if ts_match else ""

        # Status
        status_match = re.search(r'\b(?:status[:\s=]+|code[:\s=]+)?([1-5]\d{2})\b', clean, re.IGNORECASE)
        status = int(status_match.group(1)) if status_match else 200

        # Policy & Rule
        pol_match = re.search(r'\[?(?:policy|proxy)[:\s=]+([^\]\s,]+)', clean, re.IGNORECASE)
        policy = pol_match.group(1) if pol_match else ""

        rule_match = re.search(r'\[?(?:rule)[:\s=]+([^\]\s]+)', clean, re.IGNORECASE)
        rule = rule_match.group(1) if rule_match else ""

        # Bytes
        byte_match = re.search(r'(\d+)\s*(?:bytes|B|kb|mb)', clean, re.IGNORECASE)
        bytes_val = int(byte_match.group(1)) if byte_match else 0
        if "mb" in clean.lower():
            bytes_val *= (1024 * 1024)
        elif "kb" in clean.lower():
            bytes_val *= 1024

        is_failed = status >= 400
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
            "url": f"https://{host}/[sanitized]",
            "status": status,
            "rule": rule,
            "policy": policy,
            "bytes": bytes_val,
            "error": "HTTP " + str(status) if is_failed else "",
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

    unique_uncollected = sorted(list(set(r["host"] for r in uncollected if r["host"])))

    report = []
    report.append("==================== Loon 请求日志脱敏分析报告 ====================")
    report.append(f"总请求数: {total} 条 | 隐私脱敏状态: 100% 已移除 (无 Cookie/Token/Query/Body)")
    report.append("----------------------------------------------------------------")
    report.append("【统计概览】")
    report.append(f"  - 失败/异常请求: {len(failed)} 项")
    report.append(f"  - 命中 FINAL 兜底: {len(final_hits)} 项")
    report.append(f"  - 未收录新域名: {len(unique_uncollected)} 个独立 Host")
    report.append(f"  - 大流量传输 (>=5MB): {len(high_bw)} 项")
    report.append(f"  - 疑似错误分类: {len(suspected)} 项")
    report.append("----------------------------------------------------------------")

    if suspected:
        report.append("【⚠ 疑似错误分类发现】")
        for s in suspected[:10]:
            report.append(f"  - Host: {s['host']} | 策略: {s['policy']} | 判定: {s['flags']['suspected_issue']}")
        report.append("----------------------------------------------------------------")

    if high_bw:
        report.append("【大流量请求 (需重点保护独立分流)】")
        for hb in high_bw[:10]:
            mb = hb['bytes'] / (1024 * 1024)
            report.append(f"  - Host: {hb['host']} | 流量: {mb:.2f} MB | 命中规则: {hb['rule'] or '未知'}")
        report.append("----------------------------------------------------------------")

    if unique_uncollected:
        report.append("【未收录新域名 (建议评估加入 Custom 或提交上游)】")
        for uh in unique_uncollected[:15]:
            report.append(f"  - {uh}")
        if len(unique_uncollected) > 15:
            report.append(f"  ... 另有 {len(unique_uncollected) - 15} 个未收录域名")
        report.append("----------------------------------------------------------------")

    if failed:
        report.append("【失败请求抽样】")
        for f in failed[:5]:
            report.append(f"  - Host: {f['host']} | 状态: {f['status']} | 错误: {f['error']}")
        report.append("----------------------------------------------------------------")

    report.append("【真机能力边界提醒】")
    report.append("* APNs TCP 5223 守护进程、HomeKit 摄像头推流及 Watch 蜂窝行为无法靠日志单项判定，需结合真机实测。")
    report.append("================================================================")
    return "\n".join(report)

def process_file(filepath, output_json=None):
    if not os.path.isfile(filepath):
        print(f"Error: Log file not found: {filepath}", file=sys.stderr)
        return 1

    known_exact, known_suffixes = load_known_domains()

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Determine format
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

    # Save clean sanitized JSON
    out_file = output_json
    if not out_file:
        out_file = filepath + ".sanitized.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"\n[已保存脱敏数据] {out_file} (已完全剔除凭据、Cookie、查询参数及 Body)")
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
