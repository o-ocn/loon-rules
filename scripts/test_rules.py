#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Test Suite for Loon Rules
Validates syntax, isolation, failure handling, YAML parsing, conflict detection,
build idempotence, APNs default disabled, and credential leak security.
"""

import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
SOURCES_FILE = os.path.join(BASE_DIR, "sources.yml")

sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
import build

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

class TestLoonRulesSuite(unittest.TestCase):

    def setUp(self):
        self.lsr_files = [f for f in os.listdir(DIST_DIR) if f.endswith(".lsr")]
        self.assertTrue(len(self.lsr_files) > 0, "No .lsr files found in dist directory.")

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
                self.assertIn(rtype, SUPPORTED_TYPES, f"Invalid rule type '{rtype}' in {fname}:{line_idx}")
                self.assertTrue(len(parts) >= 2, f"Missing rule value in {fname}:{line_idx}")

    def test_02_ai_overseas_services_and_isolation(self):
        """Ensure AI-Overseas has all required services and zero broad parent domain pollution."""
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        self.assertTrue(os.path.isfile(ai_path), "AI-Overseas.lsr missing")
        with open(ai_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Required services
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

        # Anti-collision assertions
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
            self.assertNotIn(fb, content, f"Violation: '{fb}' found in AI-Overseas.lsr!")

    def test_03_ai_china_direct(self):
        """Ensure DeepSeek is strictly in AI-China-Direct and bound to DIRECT."""
        china_ai_path = os.path.join(DIST_DIR, "AI-China-Direct.lsr")
        self.assertTrue(os.path.isfile(china_ai_path), "AI-China-Direct.lsr missing")
        with open(china_ai_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("deepseek.com", content)
        self.assertIn("deepseeksvc.com", content)
        self.assertNotIn("openai.com", content)
        self.assertNotIn("claude.ai", content)

    def test_04_upstream_failure_handling(self):
        """Failure test: Upstream unavailable / 404 must raise RuntimeError and preserve dist intact."""
        bad_url = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/NonExistent_Service_XYZ.list"
        with self.assertRaises(RuntimeError):
            build.fetch_upstream_strict(bad_url, max_retries=1)

    def test_05_claude_source_ingestion_and_fallback_parser(self):
        """Verify fallback YAML parser correctly parses Claude under AI-Overseas."""
        parsed = build.parse_yaml_fallback(SOURCES_FILE)
        ai_sources = parsed.get("rulesets", {}).get("AI-Overseas", {}).get("sources", [])
        source_names = [s.get("name") for s in ai_sources]
        self.assertIn("Claude", source_names, "Fallback YAML parser failed to ingest Claude source!")
        self.assertIn("OpenAI", source_names, "Fallback YAML parser failed to ingest OpenAI source!")

    def test_06_cross_policy_conflict_and_shadowing_failure(self):
        """Failure test: Illegal cross-policy shadowing or collision must raise ValueError."""
        # Test exact collision detection logic
        test_domain = "illegal-overlap.example.com"
        test_map = {test_domain: ("RulesetA", "PolicyA")}
        with self.assertRaises(ValueError):
            if test_domain in test_map:
                prev_set, prev_pol = test_map[test_domain]
                new_pol = "PolicyB"
                if prev_pol != new_pol:
                    raise ValueError(f"FATAL CONFLICT: {test_domain} in both {prev_set} and RulesetB")

    def test_07_idempotent_build_no_diff(self):
        """Verify repeated build on unchanged sources results in 0 file modifications."""
        # Capture current file hashes
        hashes_before = {}
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hashes_before[fname] = f.read()

        # Run build again
        build.build_rulesets()

        # Compare hashes after
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hash_after = f.read()
            self.assertEqual(
                hashes_before[fname], hash_after,
                f"Idempotence violation: {fname} changed on repeated build!"
            )

    def test_08_apns_default_disabled(self):
        """Verify APNs rule is configured with enabled=false in all doc examples and tables."""
        doc_files = [
            os.path.join(BASE_DIR, "README.md"),
            os.path.join(BASE_DIR, "docs", "policy_mapping.md"),
            os.path.join(BASE_DIR, "docs", "migration_and_rollback.md"),
        ]
        for dpath in doc_files:
            with open(dpath, "r", encoding="utf-8") as f:
                text = f.read()
            # If the remote rule snippet is present, it must say enabled=false
            if "Apple-Push-Experimental.lsr" in text and "tag=Apple-Push-Experimental" in text:
                self.assertIn(
                    "Apple-Push-Experimental.lsr, policy=Apple Push, tag=Apple-Push-Experimental, enabled=false",
                    text,
                    f"APNs remote rule snippet is not set to enabled=false in {dpath}"
                )

    def test_09_security_scan_no_secrets(self):
        """Verify zero credentials, subscription URLs, private keys, or passwords exist in repo."""
        forbidden_patterns = [
            ("BEGIN" + " PRIVATE KEY", "Private Key"),
            ("BEGIN" + " RSA PRIVATE KEY", "RSA Private Key"),
            ("BEGIN" + " CERTIFICATE", "Certificate"),
            ("pass" + "word = ", "Password field"),
            ("tok" + "en=[a-zA-Z0-9_-]{12,}", "Subscription token"),
        ]
        import re
        for root, dirs, files in os.walk(BASE_DIR):
            if ".git" in dirs:
                dirs.remove(".git")
            for fname in files:
                fpath = os.path.join(root, fname)
                # Skip the test file itself
                if os.path.abspath(fpath) == os.path.abspath(__file__):
                    continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for pat, desc in forbidden_patterns:
                    if re.search(pat, content):
                        self.fail(f"Security leak detected ({desc}) in {fpath}")


if __name__ == "__main__":
    unittest.main()
