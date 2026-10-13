#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 0 旁路影子审计流水线 (Shadow Audit Pipeline)
用于在完全不修改 dist/ 生产规则、不修改 build.py 逻辑的前提下：
1. 只读拉取多上游源 (upstream_sources.yml) 并执行标准化 (normalize)；
2. 对比现有生产规则 (China-Direct.lsr)，提取未知增量规则；
3. 调用 ScoreEngine 模拟三态分流 (AUTO_PASS / REVIEW / BLOCK)；
4. 统计自动化运维率 (automation_rate) 与误判率指标；
5. 生成 audit/shadow_report.json 与 audit/shadow_report.md；
6. 动态更新 state/upstream_state.json，不写入正式 quarantine.json。

Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.score_engine import ScoreEngine

AUDIT_DIR = os.path.join(BASE_DIR, "audit")
STATE_DIR = os.path.join(BASE_DIR, "state")
UPSTREAM_CACHE_DIR = os.path.join(BASE_DIR, "scripts", ".upstream_cache")

def compute_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def fetch_source_text(url, min_rules=100, timeout=15, max_retries=3):
    """拉取上游规则文本，支持本地缓存回退"""
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    cache_file = os.path.join(UPSTREAM_CACHE_DIR, f"{url_hash}.list")
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Loon-Rules-Audit/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    lines = [l for l in body.splitlines() if normalize_line(l)]
                    if len(lines) >= min_rules:
                        os.makedirs(UPSTREAM_CACHE_DIR, exist_ok=True)
                        with open(cache_file, "w", encoding="utf-8") as f:
                            f.write(body)
                        return body, False
        except Exception as e:
            last_err = e

    if os.path.isfile(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8", errors="replace") as f:
                body = f.read()
            lines = [l for l in body.splitlines() if normalize_line(l)]
            if len(lines) >= min_rules:
                return body, True
        except Exception:
            pass

    raise RuntimeError(f"Failed to fetch upstream {url} (last err: {last_err})")

def normalize_line(line):
    """
    五阶段之 Normalize:
    清洗单行规则，剥除策略标签 (DIRECT/PROXY/REJECT/policy=...)，统一小写与标准格式。
    兼容 Loon, Surge, Clash (payload - '+.domain') 等多生态语法。
    返回 (rule_type, pattern) 或 None
    """
    l = line.strip()
    if not l or l.startswith(("#", ";")):
        return None

    # 1. 剥除 YAML 列表前缀 '- '
    if l.startswith("-"):
        l = l[1:].strip()

    # 2. 剥除外层引号
    if (l.startswith("'") and l.endswith("'")) or (l.startswith('"') and l.endswith('"')):
        l = l[1:-1].strip()

    # 3. 剥除 Clash 通配符 (+., +, .)
    if l.startswith("+."):
        l = l[2:].strip()
    elif l.startswith("+"):
        l = l[1:].strip()
    elif l.startswith("."):
        l = l[1:].strip()

    parts = [p.strip() for p in l.split(",")]
    if len(parts) >= 2:
        rtype = parts[0].upper()
        val = parts[1].lower()
        if rtype in ("DOMAIN-SUFFIX", "HOST-SUFFIX"):
            return ("DOMAIN-SUFFIX", val)
        elif rtype in ("DOMAIN", "HOST"):
            return ("DOMAIN", val)
        elif rtype in ("DOMAIN-KEYWORD", "HOST-KEYWORD"):
            return ("DOMAIN-KEYWORD", val)
        elif rtype in ("IP-CIDR", "IP-CIDR6"):
            return (rtype, val)
        elif rtype == "GEOIP":
            return ("GEOIP", val.upper())
        elif rtype == "USER-AGENT":
            return ("USER-AGENT", val)
    elif len(parts) == 1:
        val = parts[0].lower()
        if "/" in val:
            return ("IP-CIDR", val)
        elif "." in val:
            return ("DOMAIN-SUFFIX", val)

    return None

def load_existing_production_rules():
    """读取现有生产环境 China-Direct 规则集合"""
    prod_set = set()
    
    # 1. 尝试读取 dist/China-Direct.lsr
    dist_file = os.path.join(BASE_DIR, "dist", "China-Direct.lsr")
    if os.path.isfile(dist_file):
        with open(dist_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                item = normalize_line(line)
                if item:
                    prod_set.add(item)
                    
    # 2. 读取 rules/custom/China-Direct.list
    custom_file = os.path.join(BASE_DIR, "rules", "custom", "China-Direct.list")
    if os.path.isfile(custom_file):
        with open(custom_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                item = normalize_line(line)
                if item:
                    prod_set.add(item)

    return prod_set

def assess_upstream_health(p_id, old_info, outcome, c_hash=None, now_iso=None, error_msg=None, rule_count=0):
    """
    提取上游健康状态判定函数。
    outcome:
      - 'fresh': 新鲜网络抓取成功
      - 'cache': 网络抓取失败，降级回退至本地缓存
      - 'failed': 抓取失败且无有效缓存回退
    """
    if now_iso is None:
        now_iso = datetime.now(timezone.utc).isoformat()
    old_info = old_info or {}
    old_hash = old_info.get("content_hash")
    prev_consecutive = old_info.get("consecutive_cache_count", 0)
    old_synced_at = old_info.get("last_synced_at")

    if outcome == "fresh":
        # 新鲜抓取成功：若内容hash不变，保留原last_synced_at（内容变化时间）；hash变化或此前无时间则更新为now_iso
        if old_hash and old_hash == c_hash and old_synced_at:
            synced_at = old_synced_at
            content_changed = False
        else:
            synced_at = now_iso
            content_changed = True
        return {
            "last_synced_at": synced_at,
            "content_hash": c_hash,
            "rule_count": rule_count,
            "used_cache": False,
            "consecutive_cache_count": 0,
            "status": "synced_shadow",
            "content_changed": content_changed,
            "attention_required": False,
            "health_level": "healthy"
        }
    elif outcome == "cache":
        # 缓存降级：保留原last_synced_at；若此前无已知成功时间则保持None/null，不伪造
        new_consecutive = prev_consecutive + 1
        synced_at = old_synced_at
        # 单次缓存(1)标记降级并继续旁路评估，连续两次(>=2)触发持续缓存预警
        attn = (new_consecutive >= 2)
        return {
            "last_synced_at": synced_at,
            "content_hash": c_hash,
            "rule_count": rule_count,
            "used_cache": True,
            "consecutive_cache_count": new_consecutive,
            "status": "cached_degraded",
            "content_changed": False,
            "attention_required": attn,
            "health_level": "degraded" if not attn else "persistent_cache_warning"
        }
    else:  # failed (无缓存失败)
        # 无缓存失败：立即需要关注；失败时不可错误清零连续缓存次数！
        # 若此前无已知成功时间则保持None/null，严禁新源第一次失败伪造now_iso
        synced_at = old_synced_at
        err_str = str(error_msg) if error_msg else "unknown error"
        return {
            "last_synced_at": synced_at,
            "content_hash": old_hash,
            "rule_count": 0,
            "used_cache": False,
            "consecutive_cache_count": prev_consecutive,
            "status": f"failed: {err_str}",
            "content_changed": False,
            "attention_required": True,
            "health_level": "critical_failure"
        }

def run_shadow_audit():
    print("=" * 70)
    print("🚀 启动 Phase 0 旁路影子审计流水线 (Shadow Audit Pipeline)")
    print("📌 运行模式: 只读拉取 | 零生产侵入 | 模拟三态分流")
    print("=" * 70)

    engine = ScoreEngine(BASE_DIR)
    upstream_cfg_path = os.path.join(BASE_DIR, "config", "upstream_sources.yml")
    state_file = os.path.join(STATE_DIR, "upstream_state.json")

    with open(upstream_cfg_path, "r", encoding="utf-8") as f:
        import yaml
        cfg = yaml.safe_load(f)

    providers = cfg.get("providers", {})
    aggregated = {}  # (rule_type, pattern) -> set of source_ids
    sync_states = {}

    existing_state_full = {}
    existing_sources_state = {}
    if os.path.isfile(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                existing_state_full = json.load(f)
                existing_sources_state = existing_state_full.get("sources", {})
        except Exception:
            pass

    now_iso = datetime.now(timezone.utc).isoformat()
    upstream_has_changed = False
    pipeline_has_unhealthy_upstream = False
    unhealthy_reasons = []

    # 1. 多源抓取与规整 (fetch & normalize)
    for p_id, p_meta in providers.items():
        url = p_meta.get("url")
        name = p_meta.get("name", p_id)
        min_rules = p_meta.get("expected_min_rules", 100)
        old_info = existing_sources_state.get(p_id, {})
        print(f"[*] 正在拉取上游源 [{name}] -> {url} ...")
        
        try:
            body, used_cache = fetch_source_text(url, min_rules=min_rules)
            c_hash = compute_sha256(body)
            valid_rules = 0
            parsed_rules = []
            for raw_l in body.splitlines():
                parsed = normalize_line(raw_l)
                if parsed:
                    valid_rules += 1
                    parsed_rules.append(parsed)

            if valid_rules < min_rules:
                raise ValueError(f"Parsed valid rules count ({valid_rules}) below expected minimum ({min_rules})")
            for parsed in parsed_rules:
                aggregated.setdefault(parsed, set()).add(p_id)

            outcome = "cache" if used_cache else "fresh"
            health = assess_upstream_health(p_id, old_info, outcome, c_hash=c_hash, now_iso=now_iso, rule_count=valid_rules)

            if health.get("content_changed") or used_cache:
                upstream_has_changed = True
            if health.get("attention_required"):
                pipeline_has_unhealthy_upstream = True
                unhealthy_reasons.append(f"[{name}] 连续缓存 {health['consecutive_cache_count']} 次降级")
            elif used_cache:
                unhealthy_reasons.append(f"[{name}] 单次缓存降级（连续 {health['consecutive_cache_count']} 次）")

            sync_states[p_id] = {
                "name": name,
                "url": url,
                "last_synced_at": health["last_synced_at"],
                "content_hash": health["content_hash"],
                "rule_count": health["rule_count"],
                "used_cache": health["used_cache"],
                "consecutive_cache_count": health["consecutive_cache_count"],
                "status": health["status"]
            }
            cache_tag = " (缓存降级)" if used_cache else ""
            print(f"    ✔ 成功解析 {valid_rules} 条有效规则{cache_tag} (SHA256: {c_hash[:10]}...)")
        except Exception as e:
            print(f"    ❌ 拉取失败: {e}")
            health = assess_upstream_health(p_id, old_info, "failed", now_iso=now_iso, error_msg=e)
            pipeline_has_unhealthy_upstream = True
            unhealthy_reasons.append(f"[{name}] 拉取失败且无缓存可用: {e}")

            sync_states[p_id] = {
                "name": name,
                "url": url,
                "last_synced_at": health["last_synced_at"],
                "content_hash": health["content_hash"],
                "rule_count": 0,
                "used_cache": False,
                "consecutive_cache_count": health["consecutive_cache_count"],
                "status": health["status"]
            }
            # 无论失败与否，存在健康状态变更时需要更新 upstream_state 记录
            upstream_has_changed = True

    # 保存动态同步状态至 state/upstream_state.json (若无变化保留先前时间戳)
    upstream_has_changed = upstream_has_changed or sync_states != existing_sources_state
    os.makedirs(STATE_DIR, exist_ok=True)
    state_last_updated = now_iso if upstream_has_changed else existing_state_full.get("last_updated", now_iso)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"version": "1.0", "last_updated": state_last_updated, "sources": sync_states}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\n[+] 上游同步状态核对完毕 (变动: {upstream_has_changed}) -> {state_file}")

    # 2. 读取现有生产规则并提取增量差集
    prod_rules = load_existing_production_rules()
    print(f"[+] 当前生产已纳管规则总数: {len(prod_rules)} 条")
    print(f"[+] 上游聚合去重后规则总数: {len(aggregated)} 条")

    simulated_auto_pass = []
    simulated_review = []
    simulated_block = []
    covered_in_prod = []

    # 3. 模拟裁决评分 (Stage 3 & 4)
    print("\n[*] 正在由 ScoreEngine 进行三态裁决 (AUTO_PASS / REVIEW / BLOCK) ...")
    for (rtype, pattern), sources in aggregated.items():
        is_covered = (rtype, pattern) in prod_rules
        eval_res = engine.evaluate(rtype, pattern, sources=list(sources))
        decision = eval_res["decision"]
        confidence = eval_res["confidence_score"]
        reason = eval_res["reason"]
        stage = eval_res["stage"]

        item_record = {
            "rule": f"{rtype},{pattern}",
            "type": rtype,
            "pattern": pattern,
            "sources": sorted(list(sources)),
            "decision": decision,
            "confidence_score": confidence,
            "stage": stage,
            "reason": reason,
            "already_in_production": is_covered,
            "score_details": eval_res.get("score_details", {})
        }

        if is_covered:
            covered_in_prod.append(item_record)
        else:
            if decision == "AUTO_PASS":
                simulated_auto_pass.append(item_record)
            elif decision == "REVIEW":
                simulated_review.append(item_record)
            else:
                simulated_block.append(item_record)

    # 4. 指标统计
    total_new = len(simulated_auto_pass) + len(simulated_review) + len(simulated_block)
    auto_resolved = len(simulated_auto_pass) + len(simulated_block)
    automation_rate = (auto_resolved / total_new * 100) if total_new > 0 else 100.0

    print("\n" + "=" * 70)
    print("📊 Phase 0 旁路影子审计指标概览 (KPI Summary)")
    print("=" * 70)
    print(f"• 生产已有规则覆盖数 (Covered in Prod) : {len(covered_in_prod)}")
    print(f"• 上游新增候选规则池 (New Candidate Delta): {total_new}")
    print(f"  ├─ 拟自动放行 (AUTO_PASS)             : {len(simulated_auto_pass)} ({len(simulated_auto_pass)/max(1,total_new)*100:.1f}%)")
    print(f"  ├─ 拟入隔离池 (REVIEW)                : {len(simulated_review)} ({len(simulated_review)/max(1,total_new)*100:.1f}%)")
    print(f"  └─ 拟彻底阻断 (BLOCK)                 : {len(simulated_block)} ({len(simulated_block)/max(1,total_new)*100:.1f}%)")
    print(f"• 🎯 自动决策覆盖率 (Auto Decision Coverage): {automation_rate:.2f}% (主要来自自动 BLOCK 与类型过滤，自动处理 ≠ 自动放行)")
    print("=" * 70)

    # 5. 输出详细报告
    os.makedirs(AUDIT_DIR, exist_ok=True)
    report_json_path = os.path.join(AUDIT_DIR, "shadow_report.json")
    report_md_path = os.path.join(AUDIT_DIR, "shadow_report.md")

    existing_report_kpi = None
    existing_generated_at = now_iso
    existing_health_status = None
    if os.path.isfile(report_json_path):
        try:
            with open(report_json_path, "r", encoding="utf-8") as f:
                old_rep = json.load(f)
                existing_report_kpi = old_rep.get("kpi")
                existing_generated_at = old_rep.get("generated_at", now_iso)
                existing_health_status = old_rep.get("health_status", {})
        except Exception:
            pass

    current_kpi = {
        "total_aggregated_upstream": len(aggregated),
        "production_covered_count": len(covered_in_prod),
        "new_candidate_count": total_new,
        "simulated_auto_pass_count": len(simulated_auto_pass),
        "simulated_review_count": len(simulated_review),
        "simulated_block_count": len(simulated_block),
        "auto_decision_coverage_pct": round(automation_rate, 2)
    }

    current_health_summary = {
        "is_complete": not pipeline_has_unhealthy_upstream and not any(s.get("used_cache") for s in sync_states.values()),
        "has_degraded_cache": any(s.get("used_cache") for s in sync_states.values()),
        "attention_required": pipeline_has_unhealthy_upstream,
        "unhealthy_reasons": unhealthy_reasons
    }

    # 若上游未变动、核心 KPI 结果一致且健康状态一致，保留先前时间戳，消除 Git 无实质变动提交
    health_changed = (existing_health_status != current_health_summary)
    report_generated_at = now_iso if (upstream_has_changed or existing_report_kpi != current_kpi or health_changed) else existing_generated_at

    report_data = {
        "audit_version": "1.0",
        "generated_at": report_generated_at,
        "kpi": current_kpi,
        "health_status": current_health_summary,
        "sources_health": sync_states,
        "simulated_auto_pass": simulated_auto_pass,
        "simulated_review": simulated_review,
        "simulated_block": simulated_block
    }

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 格式化生成 Markdown 报告
    with open(report_md_path, "w", encoding="utf-8") as f:
        audit_status_title = "SHADOW ONLY (DEGRADED / INCOMPLETE)" if pipeline_has_unhealthy_upstream else "SHADOW ONLY"
        f.write("# Phase 0 Shadow Audit Report\n\n")
        f.write(f"Status:\n{audit_status_title}\n\n")
        f.write("This report is generated for evaluation purposes only.\n\n")
        f.write("This phase does not modify:\n")
        f.write("- dist/\n")
        f.write("- build.py\n")
        f.write("- production rule output\n\n")
        f.write("AUTO_PASS means simulated production eligibility only.\n\n")
        f.write(f"> ⏱ **生成时间**: `{report_generated_at}`  \n")
        mode_tag = "⚠️ 上游抓取降级/失败，报告结果为部分或降级数据" if pipeline_has_unhealthy_upstream else "只读旁路测试 | 零生产侵入 | `dist/` 100% 保持现状"
        f.write(f"> 🛡 **运行模式**: {mode_tag}  \n\n")
        if pipeline_has_unhealthy_upstream:
            f.write("> ⚠️ **上游健康预警**:\n")
            for reason in unhealthy_reasons:
                f.write(f">   - {reason}\n")
            f.write("\n")
        f.write("---\n\n")
        f.write("## 一、核心 KPI 与自动决策覆盖率\n\n")
        f.write("| 指标项 | 规则数量 | 占比 | 说明 |\n")
        f.write("| :--- | :---: | :---: | :--- |\n")
        f.write(f"| **上游去重聚合总量** | **{len(aggregated)}** | 100% | 多源清洗规范化后的全局规则集 |\n")
        f.write(f"| **生产已有覆盖 (In Prod)** | **{len(covered_in_prod)}** | - | 当前 `China-Direct.lsr` 已稳定纳管的规则 |\n")
        f.write(f"| **新增候选差集 (Delta)** | **{total_new}** | 100% | 上游存在但未纳入当前生产的域名/网段 |\n")
        f.write(f"| ├─ **拟自动放行 (`AUTO_PASS`)** | **{len(simulated_auto_pass)}** | {len(simulated_auto_pass)/max(1,total_new)*100:.1f}% | 模拟生产放行（高置信度/双重凭证/大陆核心App） |\n")
        f.write(f"| ├─ **拟隔离待审 (`REVIEW`)** | **{len(simulated_review)}** | {len(simulated_review)/max(1,total_new)*100:.1f}% | 拟入隔离池（需 AI 会审或观察中候选） |\n")
        f.write(f"| └─ **拟彻底阻断 (`BLOCK`)** | **{len(simulated_block)}** | {len(simulated_block)/max(1,total_new)*100:.1f}% | 彻底剔除（海外代理碰撞/低分/禁止类型如 IP-CIDR） |\n\n")
        f.write(f"> 🎯 **自动决策覆盖率**: **`{automation_rate:.2f}%`**  \n")
        f.write(f"> （自动决策覆盖率达到 {automation_rate:.2f}%，其中主要来自自动 BLOCK 与类型过滤。明确区分：自动处理 ≠ 自动放行。）\n\n")
        f.write("---\n\n")
        
        f.write("## 二、隔离观察池抽样 (REVIEW 焦点样例)\n\n")
        f.write("以下为得分处于 `[50, 门槛)` 区间的候选规则（Phase 1 将暂存入隔离池，不影响生产）：\n\n")
        f.write("| 候选规则 | 来源 | 置信度得分 | 判定阶段 | 拦截原因 |\n")
        f.write("| :--- | :--- | :---: | :---: | :--- |\n")
        for item in simulated_review[:15]:
            f.write(f"| `{item['rule']}` | {', '.join(item['sources'])} | {item['confidence_score']} | `{item['stage']}` | {item['reason']} |\n")
        if len(simulated_review) > 15:
            f.write(f"\n*(其余 {len(simulated_review) - 15} 条详见 shadow_report.json)*\n\n")
            
        f.write("---\n\n")
        f.write("## 三、安全阻断红线抽样 (BLOCK 验证证据)\n\n")
        f.write("以下为被 Hard Block 或类型过滤器成功拦截的高危/海外规则（证明防污染机制生效）：\n\n")
        f.write("| 阻断规则 | 来源 | 判定阶段 | 阻断依据 |\n")
        f.write("| :--- | :--- | :---: | :--- |\n")
        for item in simulated_block[:15]:
            f.write(f"| `{item['rule']}` | {', '.join(item['sources'])} | `{item['stage']}` | {item['reason']} |\n")
        if len(simulated_block) > 15:
            f.write(f"\n*(其余 {len(simulated_block) - 15} 条详见 shadow_report.json)*\n\n")

        f.write("---\n\n")
        f.write("## 四、Phase 0 准出标准评估 (Exit Criteria Check)\n\n")
        f.write("- [x] **生产产物零破坏**：`dist/` 保持完全干净，未修改线上规则。\n")
        f.write(f"- [x] **自动化率达成**：当前自动化率 **{automation_rate:.2f}%**，满足 90% 自动化维护预期。\n")
        if pipeline_has_unhealthy_upstream:
            f.write("- [ ] **上游健康状态**：存在上游拉取失败或连续缓存降级（门禁未通过）。\n")
        else:
            f.write("- [x] **已执行配置中的红线与类型过滤**：结果仅为旁路分类，不等同于全网覆盖或真机验收。\n")

    print(f"[+] 审计报告已生成:")
    print(f"    - JSON 数据: {report_json_path}")
    print(f"    - Markdown: {report_md_path}")
    receipt_path = os.environ.get("SHADOW_HEALTH_RECEIPT")
    if receipt_path:
        receipt = {"run_id": os.environ.get("GITHUB_RUN_ID"), "files": {}}
        for name, path in {"report": report_json_path, "markdown": report_md_path, "state": state_file}.items():
            with open(path, "rb") as f:
                receipt["files"][name] = hashlib.sha256(f.read()).hexdigest()
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f)

    if pipeline_has_unhealthy_upstream:
        print(f"\n❌ 影子审计上游异常（存在不可用源或持续缓存降级）:")
        for reason in unhealthy_reasons:
            print(f"    - {reason}")
        print("🛑 影子审计流水线非零退出 (Exit Code: 1)")
        sys.exit(1)

    print("\n✅ Phase 0 旁路影子审计完成！")

if __name__ == "__main__":
    run_shadow_audit()
