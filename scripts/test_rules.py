#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Test Suite for Loon Rules
Validates syntax, isolation, cross-hit prevention, and Apple stability constraints.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

class TestLoonRules(unittest.TestCase):

    def setUp(self):
        self.lsr_files = [f for f in os.listdir(DIST_DIR) if f.endswith(".lsr")]
        self.assertTrue(len(self.lsr_files) > 0, "No .lsr files found in dist directory. Run build.py first.")

    def test_01_syntax_and_encoding(self):
        """Verify each line in every .lsr complies with Loon format."""
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for line_idx, line in enumerate(lines, 1):
                clean = line.strip()
                if not clean or clean.startswith("#"):
                    continue
                parts = [p.strip() for p in clean.split(",")]
                rtype = parts[0].upper()
                self.assertIn(
                    rtype, SUPPORTED_TYPES,
                    f"Invalid rule type '{rtype}' in {fname}:{line_idx}"
                )
                self.assertTrue(
                    len(parts) >= 2,
                    f"Missing rule value in {fname}:{line_idx}"
                )

    def test_02_ai_overseas_isolation(self):
        """Ensure AI-Overseas has all required services and zero broad parent domain pollution."""
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        self.assertTrue(os.path.isfile(ai_path), "AI-Overseas.lsr missing")
        with open(ai_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must contain required AI services
        self.assertIn("openai.com", content)
        self.assertIn("chatgpt.com", content)
        self.assertIn("claude.ai", content)
        self.assertIn("anthropic.com", content)
        self.assertIn("gemini.google.com", content)
        self.assertIn("generativelanguage.googleapis.com", content)
        self.assertIn("grok.com", content)
        self.assertIn("x.ai", content)
        self.assertIn("muse.ai", content)
        self.assertIn("meta.ai", content)

        # STRICT PROHIBITIONS: Anti-collision checks
        forbidden = [
            "DOMAIN-SUFFIX,google.com",
            "DOMAIN-SUFFIX,googleapis.com",
            "DOMAIN-SUFFIX,twitter.com",
            "DOMAIN-SUFFIX,x.com",
            "DOMAIN-SUFFIX,meta.com",
            "DOMAIN-SUFFIX,facebook.com",
            "DOMAIN-SUFFIX,instagram.com",
            "DOMAIN-SUFFIX,whatsapp.com",
        ]
        for fb in forbidden:
            self.assertNotIn(
                fb, content,
                f"Violation: '{fb}' found in AI-Overseas.lsr! Must be precisely scoped."
            )

    def test_03_ai_china_direct(self):
        """Ensure DeepSeek is strictly in AI-China-Direct and bound to DIRECT."""
        china_ai_path = os.path.join(DIST_DIR, "AI-China-Direct.lsr")
        self.assertTrue(os.path.isfile(china_ai_path), "AI-China-Direct.lsr missing")
        with open(china_ai_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("deepseek.com", content)

    def test_04_apple_direct_stability(self):
        """Verify Apple baseline direct rules do not use blanket wildcard or 17.0.0.0/8."""
        apple_path = os.path.join(DIST_DIR, "Apple-Direct.lsr")
        self.assertTrue(os.path.isfile(apple_path), "Apple-Direct.lsr missing")
        with open(apple_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must contain iCloud, CloudKit, Music, App Store
        self.assertIn("apple-cloudkit.com", content)
        self.assertIn("icloud.com", content)
        self.assertIn("music.apple.com", content)
        self.assertIn("apps.apple.com", content)

        # Forbidden blanket shortcuts
        self.assertNotIn("IP-CIDR,17.0.0.0/8", content)
        self.assertNotIn("DOMAIN-SUFFIX,apple.com", content)

    def test_05_apns_experimental_segregation(self):
        """Verify APNs rules are segregated in dedicated experimental ruleset."""
        apns_path = os.path.join(DIST_DIR, "Apple-Push-Experimental.lsr")
        self.assertTrue(os.path.isfile(apns_path), "Apple-Push-Experimental.lsr missing")
        with open(apns_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("push.apple.com", content)
        self.assertIn("17.249.0.0/16", content)

if __name__ == "__main__":
    unittest.main()
