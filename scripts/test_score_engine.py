#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试：ScoreEngine 置信度与三态决策回归验证
运行方式: python -B -m unittest scripts.test_score_engine
"""

import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.score_engine import ScoreEngine

class TestScoreEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ScoreEngine(BASE_DIR)
        cls.fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "audit_cases.json")
        with open(cls.fixture_path, "r", encoding="utf-8") as f:
            cls.fixture_data = json.load(f)

    def test_fixture_cases(self):
        """逐项验证 audit_cases.json 中的固定回归样本"""
        for case in self.fixture_data.get("cases", []):
            case_id = case.get("id")
            rtype = case.get("type")
            domain = case.get("domain")
            sources = case.get("sources", [])
            dns_info = case.get("dns_info")
            expected_decision = case.get("expected_decision")
            expected_reason = case.get("expected_reason_contains", "")

            with self.subTest(case_id=case_id):
                result = self.engine.evaluate(rtype, domain, sources=sources, dns_info=dns_info)
                self.assertEqual(
                    result["decision"],
                    expected_decision,
                    f"[{case_id}] Decision mismatch for {rtype},{domain}: got {result['decision']}, expected {expected_decision}"
                )
                if expected_reason:
                    self.assertIn(
                        expected_reason.lower(),
                        result["reason"].lower(),
                        f"[{case_id}] Reason substring '{expected_reason}' not found in '{result['reason']}'"
                    )

    def test_hard_pass_verified_boundary(self):
        """验证 Hard Pass 必须 verified == True 且在 decisions.jsonl 中"""
        # music.163.com 是在 decisions.jsonl 中且 verified=true
        res = self.engine.evaluate("DOMAIN-SUFFIX", "music.163.com")
        self.assertEqual(res["decision"], "AUTO_PASS")
        self.assertEqual(res["stage"], "HARD_PASS")
        self.assertEqual(res["confidence_score"], 100)

        # 随机网易子域名 (如 fake.163.com) 不在 decisions.jsonl 中，虽然 163 属于已知矩阵，但不能走 Hard Pass
        res2 = self.engine.evaluate("DOMAIN-SUFFIX", "fake-unknown-edge-163.com")
        self.assertNotEqual(res2["stage"], "HARD_PASS", "未经验证的域名绝对不能触发 Hard Pass")

    def test_hard_block_overseas_boundary(self):
        """验证海外核心服务与出海孪生业务直接 Hard Block"""
        overseas_tests = [
            ("DOMAIN-SUFFIX", "google.com"),
            ("DOMAIN-SUFFIX", "chatgpt.com"),
            ("DOMAIN-SUFFIX", "tiktok.com"),
            ("DOMAIN-SUFFIX", "temu.com"),
            ("DOMAIN-SUFFIX", "netease.com"),
            ("DOMAIN-SUFFIX", "bcebos.com"),
            ("DOMAIN-SUFFIX", "cmbwinglungbank.com")
        ]
        for rtype, dom in overseas_tests:
            with self.subTest(domain=dom):
                res = self.engine.evaluate(rtype, dom)
                self.assertEqual(res["decision"], "BLOCK")
                self.assertEqual(res["stage"], "HARD_BLOCK")

    def test_forbidden_types_blocked(self):
        """验证第一阶段严格禁止 IP-CIDR 与 USER-AGENT 自动入库"""
        res_ip = self.engine.evaluate("IP-CIDR", "192.168.1.1/32")
        self.assertEqual(res_ip["decision"], "BLOCK")
        self.assertEqual(res_ip["stage"], "TYPE_FILTER")

        res_ua = self.engine.evaluate("USER-AGENT", "MicroMessenger*")
        self.assertEqual(res_ua["decision"], "BLOCK")
        self.assertEqual(res_ua["stage"], "TYPE_FILTER")

if __name__ == "__main__":
    unittest.main()
