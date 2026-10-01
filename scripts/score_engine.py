#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
置信度评分与三态裁决引擎 (Score / Confidence Engine)
实现三级门禁 (Type Filter -> Hard Block -> Hard Pass -> Confidence Scoring)
用于 Phase 0 旁路审计及后续自动化流水线。

设计原则：
1. Hard Pass 必须双重凭证：verified == True 且存在于 decisions.jsonl 中，严禁仅按企业归属放行。
2. Hard Block 一票否决：命中 decisions.jsonl 阻断记录或 overseas proxy 红线。
3. 规则类型感知：DOMAIN-SUFFIX (门槛85分) > DOMAIN (门槛75分) > IP-CIDR (当前阶段自动拦截)。
4. 输出标准三态：AUTO_PASS (模拟放行) / REVIEW (隔离待审) / BLOCK (彻底阻断)。
"""

import os
import sys
import json
import yaml
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class ScoreEngine:
    def __init__(self, base_dir=BASE_DIR):
        self.base_dir = base_dir
        self.risk_policy_path = os.path.join(base_dir, "config", "risk_policy.yml")
        self.upstream_sources_path = os.path.join(base_dir, "config", "upstream_sources.yml")
        self.decisions_path = os.path.join(base_dir, "history", "decisions.jsonl")
        self.shared_domains_path = os.path.join(base_dir, "shared_domains.yml")
        self.app_matrix_path = os.path.join(base_dir, "docs", "app-audit-matrix.md")

        self.policy = self._load_yaml(self.risk_policy_path)
        self.upstream_cfg = self._load_yaml(self.upstream_sources_path)
        self.decisions = self._load_decisions()
        self.redline_domains = self._load_redlines()
        self.matrix_domains = self._load_matrix_domains()

    def _load_yaml(self, path):
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_decisions(self):
        """加载历史永久决策记录"""
        decisions = []
        if not os.path.isfile(self.decisions_path):
            return decisions
        with open(self.decisions_path, "r", encoding="utf-8") as f:
            for line in f:
                l = line.strip()
                if not l:
                    continue
                try:
                    decisions.append(json.loads(l))
                except Exception:
                    continue
        return decisions

    def _load_redlines(self):
        """从 shared_domains.yml 提取海外代理及海外专属红线域名"""
        redlines = set([
            # 常见海外核心顶级主域
            "google.com", "google.com.hk", "googlevideo.com", "gstatic.com",
            "openai.com", "chatgpt.com", "oaistatic.com", "oaiusercontent.com",
            "telegram.org", "t.me", "telegram.dog",
            "twitter.com", "x.com", "twimg.com",
            "youtube.com", "ytimg.com",
            "discord.com", "discord.gg",
            "github.com", "githubusercontent.com",
            "netflix.com", "nflxvideo.net",
            "spotify.com", "scdn.co",
            "steampowered.com", "steamcommunity.com",
            # 出海独立孪生产品红线
            "tiktok.com", "byteoversea.com", "ibyteimg.com", "musical.ly",
            "temu.com", "kwai.com", "kwaicdn.com", "snackvideo.com",
            "keeta.com", "terabox.com",
            "cmbwinglungbank.com", "cignacmb.com",
            "netease.com", "bcebos.com"
        ])
        
        # 补充 shared_domains.yml 中的生态专属排除项
        spec = self._load_yaml(self.shared_domains_path)
        ecos = spec.get("ecosystems", {})
        for _, eco_data in ecos.items():
            for d in eco_data.get("overseas_exclusive_domains", []):
                redlines.add(d.lower())
        return redlines

    def _load_matrix_domains(self):
        """提取已知国内合规业务核心域名列表"""
        return set([
            "weixin.com", "qq.com", "tencent.com", "qpic.cn", "gtimg.com",
            "alipay.com", "alipayobjects.com", "taobao.com", "tmall.com",
            "1688.com", "idlefish.com", "alicdn.com",
            "jd.com", "jdpay.com", "360buyimg.com",
            "pinduoduo.com", "yangkeduo.com", "pddpic.com",
            "meituan.com", "dianping.com", "sankuai.com", "meituan.net",
            "ele.me", "elemecdn.com",
            "xiaohongshu.com", "xhscdn.com", "xhscdn.net",
            "douyin.com", "zijieapi.com", "bytedance.com", "bytetos.com", "byteimg.com",
            "kuaishou.com", "gifshow.com", "kuaishoupay.com", "yximgs.com",
            "bilibili.com", "bilivideo.com", "hdslb.com",
            "amap.com", "autonavi.com", "baidu.com", "baidupcs.com", "bdimg.com",
            "unionpay.com", "unionpaysecure.com", "95516.com",
            "cmbchina.com", "cmbimg.com"
        ])

    def _is_domain_match(self, domain, pattern):
        """检查域名是否与 pattern 匹配 (精确或子域)"""
        d = domain.lower().strip()
        p = pattern.lower().strip()
        if d == p:
            return True
        if d.endswith("." + p):
            return True
        return False

    def evaluate(self, rule_type, pattern, sources=None, dns_info=None):
        """
        三态裁决核心函数
        Returns:
            dict: {
                "decision": "AUTO_PASS" | "REVIEW" | "BLOCK",
                "confidence_score": int (0-100),
                "reason": str,
                "stage": "TYPE_FILTER" | "HARD_BLOCK" | "HARD_PASS" | "CONFIDENCE_SCORE",
                "score_details": dict
            }
        """
        sources = sources or []
        pattern = pattern.lower().strip()
        rule_type = rule_type.upper().strip()

        allowed_types = self.policy.get("allowed_auto_types", ["DOMAIN", "DOMAIN-SUFFIX"])
        weights = self.policy.get("scoring_weights", {})
        thresholds = self.policy.get("confidence_thresholds", {"domain_suffix": 85, "domain": 75, "quarantine_floor": 50})

        # =========================================================================
        # Stage 1: 规则类型门禁 (Type Filter)
        # =========================================================================
        if rule_type not in allowed_types:
            return {
                "decision": "BLOCK",
                "confidence_score": 0,
                "reason": f"forbidden_type: First phase strictly forbids auto-adding rule type '{rule_type}'",
                "stage": "TYPE_FILTER",
                "score_details": {}
            }

        # =========================================================================
        # Stage 2: Hard Block 一票否决门禁
        # =========================================================================
        # 1. 检查 history/decisions.jsonl 阻断记录
        for dec in self.decisions:
            if dec.get("decision") == "BLOCK":
                dec_rule = dec.get("rule", "")
                if "," in dec_rule:
                    _, dec_pat = dec_rule.split(",", 1)
                    dec_pat = dec_pat.strip().lower()
                    if self._is_domain_match(pattern, dec_pat) or self._is_domain_match(dec_pat, pattern):
                        return {
                            "decision": "BLOCK",
                            "confidence_score": 0,
                            "reason": f"Hard Block: Matched decision_history block record ({dec.get('reason')})",
                            "stage": "HARD_BLOCK",
                            "score_details": {"decision_record": dec}
                        }

        # 2. 检查 shared_domains.yml 与境外红线域名
        for red in self.redline_domains:
            if self._is_domain_match(pattern, red):
                return {
                    "decision": "BLOCK",
                    "confidence_score": 0,
                    "reason": f"Hard Block: Collision with overseas proxy / exclusive red-line domain '{red}'",
                    "stage": "HARD_BLOCK",
                    "score_details": {"matched_redline": red}
                }

        # =========================================================================
        # Stage 3: Hard Pass 免检放行门禁 (双重凭证：verified == True 且存在于决策账本)
        # =========================================================================
        for dec in self.decisions:
            if dec.get("decision") == "AUTO_PASS" and dec.get("verified") is True:
                dec_rule = dec.get("rule", "")
                if "," in dec_rule:
                    _, dec_pat = dec_rule.split(",", 1)
                    dec_pat = dec_pat.strip().lower()
                    scope = dec.get("scope", "EXACT_APP_SERVICE")
                    matched = False
                    if scope == "EXACT_APP_SERVICE":
                        matched = (pattern == dec_pat or pattern.endswith("." + dec_pat))
                    elif scope == "ENTIRE_DOMAIN_TREE":
                        matched = self._is_domain_match(pattern, dec_pat)

                    if matched:
                        return {
                            "decision": "AUTO_PASS",
                            "confidence_score": 100,
                            "reason": f"Hard Pass: Dual credentials satisfied (verified=true in decision_history: {dec.get('reason')})",
                            "stage": "HARD_PASS",
                            "score_details": {"decision_record": dec}
                        }

        # =========================================================================
        # Stage 4: 类型感知置信度评分 (Confidence Scoring)
        # =========================================================================
        consensus_score = 0
        conflict_safety_score = weights.get("zero_conflict_safety_bonus", 20)  # 已通过 Stage 2 零冲突检验
        matrix_score = 0
        dns_score = 0

        # A. 上游共识与加权得分
        providers = self.upstream_cfg.get("providers", {})
        high_tier_matches = 0
        for s in sources:
            p_info = providers.get(s, {})
            tier = p_info.get("tier", "secondary")
            if tier == "primary":
                high_tier_matches += 1

        if len(sources) >= 2 or high_tier_matches >= 2:
            consensus_score = weights.get("upstream_consensus", {}).get("multi_source_match", 35)
        elif high_tier_matches == 1:
            consensus_score = weights.get("upstream_consensus", {}).get("single_primary", 25)
        elif len(sources) == 1:
            consensus_score = weights.get("upstream_consensus", {}).get("single_secondary", 15)

        # B. 审计矩阵匹配得分
        is_matrix_matched = False
        if pattern.endswith(".cn"):
            is_matrix_matched = True
        else:
            for m_dom in self.matrix_domains:
                if self._is_domain_match(pattern, m_dom):
                    is_matrix_matched = True
                    break

        if is_matrix_matched:
            matrix_score = weights.get("matrix_verified_bonus", 30)

        # C. DNS 解析归属性质得分
        if dns_info and dns_info.get("is_china_ip") is True:
            dns_score = weights.get("dns_domestic_bonus", 15)
        elif dns_info and dns_info.get("is_overseas") is True:
            dns_score = 0
        else:
            # 默认中立分 (若命中 matrix 则假定国内 CDN)
            dns_score = 10 if is_matrix_matched else 0

        total_confidence = min(100, consensus_score + conflict_safety_score + matrix_score + dns_score)

        # 根据规则类型适用不同准入门槛
        if rule_type == "DOMAIN-SUFFIX":
            threshold = thresholds.get("domain_suffix", 85)
        else:
            threshold = thresholds.get("domain", 75)
        
        quarantine_floor = thresholds.get("quarantine_floor", 50)

        score_details = {
            "consensus_score": consensus_score,
            "conflict_safety_score": conflict_safety_score,
            "matrix_score": matrix_score,
            "dns_score": dns_score,
            "total_confidence": total_confidence,
            "required_threshold": threshold,
            "quarantine_floor": quarantine_floor
        }

        if total_confidence >= threshold:
            decision = "AUTO_PASS"
            reason = f"High confidence ({total_confidence} >= {threshold}), simulated auto-pass"
        elif total_confidence >= quarantine_floor:
            decision = "REVIEW"
            reason = f"Intermediate confidence ({total_confidence} in [{quarantine_floor}, {threshold})), routed to Quarantine"
        else:
            decision = "BLOCK"
            reason = f"Low confidence ({total_confidence} < {quarantine_floor}), dropped"

        return {
            "decision": decision,
            "confidence_score": total_confidence,
            "reason": reason,
            "stage": "CONFIDENCE_SCORE",
            "score_details": score_details
        }
