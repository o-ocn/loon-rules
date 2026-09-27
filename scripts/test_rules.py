#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Test Suite for Loon Rules
Validates syntax, isolation, fail-stop on single-rule upstream, real-engine conflict detection,
build idempotence, APNs default disabled, and credential leak security.
"""

import os
import sys
import unittest
import tempfile
import shutil
import io
from unittest.mock import patch, MagicMock

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

    def test_02_ai_overseas_narrowed_and_clean(self):
        """Ensure AI-Overseas contains only verified AI domains and strips all shared SaaS/APM/payment/ASN rules."""
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        self.assertTrue(os.path.isfile(ai_path), "AI-Overseas.lsr missing")
        with open(ai_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must contain verified AI domains
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

        # STRICT PROHIBITIONS: Broad parent domains & shared SaaS/APM/Payment/ASN
        forbidden_rules = [
            "DOMAIN-SUFFIX,google.com",
            "DOMAIN-SUFFIX,googleapis.com",
            "DOMAIN-SUFFIX,twitter.com",
            "DOMAIN-SUFFIX,x.com",
            "DOMAIN-SUFFIX,meta.com",
            "DOMAIN-SUFFIX,facebook.com",
            "DOMAIN-SUFFIX,instagram.com",
            "DOMAIN-SUFFIX,whatsapp.com",
            "DOMAIN-SUFFIX,stripe.com",
            "DOMAIN-SUFFIX,auth0.com",
            "DOMAIN-SUFFIX,sentry.io",
            "DOMAIN-SUFFIX,intercom.io",
            "DOMAIN-SUFFIX,launchdarkly.com",
            "DOMAIN-SUFFIX,segment.io",
            "IP-ASN,20473",
        ]
        for fb in forbidden_rules:
            self.assertNotIn(fb, content, f"Violation: '{fb}' found in AI-Overseas.lsr! Must be scoped.")

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

    def test_04_upstream_fail_stop_on_single_rule_200_response(self):
        """
        Verify that an upstream returning an HTTP 200 response with only 1 valid rule
        triggers fail-stop (RuntimeError) via real build engine, leaving dist/ 100% untouched.
        """
        # Capture current dist hashes before simulated failure
        hashes_before = {}
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hashes_before[fname] = f.read()

        # Mock an HTTP 200 response containing only a single valid rule line
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"# Single rule test\nDOMAIN,only-one-rule.example.com\n"
        mock_response.__enter__.return_value = mock_response

        # Execute real build_rulesets with mocked upstream for Google (which requires min_rules=100)
        with patch("urllib.request.urlopen", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                build.build_rulesets()
            self.assertIn("abnormally few rules", str(ctx.exception))

        # Assert dist/ files remain completely unchanged
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hash_after = f.read()
            self.assertEqual(
                hashes_before[fname], hash_after,
                f"Dist protection failed: {fname} was modified during failed build!"
            )

    def test_05_cross_policy_conflict_detection_real_engine(self):
        """
        Invoke the real build engine with a test configuration containing an unhandled cross-policy duplicate
        (e.g. USER-AGENT or DOMAIN in two different policies) and verify it raises ValueError.
        """
        tmp_dir = tempfile.mkdtemp(prefix="test_loon_conflict_")
        try:
            test_sources_file = os.path.join(tmp_dir, "sources.yml")
            test_dist_dir = os.path.join(tmp_dir, "dist")
            test_custom_a = os.path.join(tmp_dir, "CustomA.list")
            test_custom_b = os.path.join(tmp_dir, "CustomB.list")

            # Write conflicting rule in two different policy custom lists
            with open(test_custom_a, "w", encoding="utf-8") as f:
                f.write("USER-AGENT,*ConflictApp*\nDOMAIN,conflict.example.com\n")
            with open(test_custom_b, "w", encoding="utf-8") as f:
                f.write("USER-AGENT,*ConflictApp*\n")

            # Write test sources.yml
            test_yaml = f"""
rulesets:
  ServiceA:
    bound_policy: "PolicyA"
    local_custom: "{test_custom_a.replace(chr(92), '/')}"
  ServiceB:
    bound_policy: "PolicyB"
    local_custom: "{test_custom_b.replace(chr(92), '/')}"
"""
            with open(test_sources_file, "w", encoding="utf-8") as f:
                f.write(test_yaml)

            # Invoke real build_rulesets
            with self.assertRaises(ValueError) as ctx:
                build.build_rulesets(sources_file=test_sources_file, dist_dir=test_dist_dir)
            self.assertIn("FATAL CONFLICT: Exact rule 'USER-AGENT,*ConflictApp*'", str(ctx.exception))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_06_illegal_parent_domain_shadowing_real_engine(self):
        """
        Invoke the real build engine with an illegal parent-domain shadowing scenario
        (subdomain in PolicyA shadowed by parent suffix in PolicyB without delegation) and verify it raises ValueError.
        """
        tmp_dir = tempfile.mkdtemp(prefix="test_loon_shadowing_")
        try:
            test_sources_file = os.path.join(tmp_dir, "sources.yml")
            test_dist_dir = os.path.join(tmp_dir, "dist")
            test_custom_child = os.path.join(tmp_dir, "Child.list")
            test_custom_parent = os.path.join(tmp_dir, "Parent.list")

            with open(test_custom_child, "w", encoding="utf-8") as f:
                f.write("DOMAIN,secret.unauthorized.com\n")
            with open(test_custom_parent, "w", encoding="utf-8") as f:
                f.write("DOMAIN-SUFFIX,unauthorized.com\n")

            test_yaml = f"""
rulesets:
  ChildSet:
    bound_policy: "ProxyPolicy"
    local_custom: "{test_custom_child.replace(chr(92), '/')}"
  ParentSet:
    bound_policy: "DirectPolicy"
    local_custom: "{test_custom_parent.replace(chr(92), '/')}"
"""
            with open(test_sources_file, "w", encoding="utf-8") as f:
                f.write(test_yaml)

            with self.assertRaises(ValueError) as ctx:
                build.build_rulesets(sources_file=test_sources_file, dist_dir=test_dist_dir)
            self.assertIn("FATAL SHADOWING", str(ctx.exception))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_07_claude_source_ingestion_and_fallback_parser(self):
        """Verify fallback YAML parser correctly parses Claude under AI-Overseas."""
        parsed = build.parse_yaml_fallback(SOURCES_FILE)
        ai_sources = parsed.get("rulesets", {}).get("AI-Overseas", {}).get("sources", [])
        source_names = [s.get("name") for s in ai_sources]
        self.assertIn("Claude", source_names, "Fallback YAML parser failed to ingest Claude source!")
        self.assertIn("OpenAI", source_names, "Fallback YAML parser failed to ingest OpenAI source!")

    def test_08_idempotent_build_no_diff(self):
        """Verify repeated build on unchanged sources results in 0 file modifications."""
        hashes_before = {}
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hashes_before[fname] = f.read()

        build.build_rulesets()

        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "rb") as f:
                hash_after = f.read()
            self.assertEqual(
                hashes_before[fname], hash_after,
                f"Idempotence violation: {fname} changed on repeated build!"
            )

    def test_09_apns_default_disabled(self):
        """Verify APNs rule is configured with enabled=false in all doc examples and tables."""
        doc_files = [
            os.path.join(BASE_DIR, "README.md"),
            os.path.join(BASE_DIR, "docs", "policy_mapping.md"),
            os.path.join(BASE_DIR, "docs", "migration_and_rollback.md"),
        ]
        for dpath in doc_files:
            with open(dpath, "r", encoding="utf-8") as f:
                text = f.read()
            if "Apple-Push-Experimental.lsr" in text and "tag=Apple-Push-Experimental" in text:
                self.assertIn(
                    "Apple-Push-Experimental.lsr, policy=Apple Push, tag=Apple-Push-Experimental, enabled=false",
                    text,
                    f"APNs remote rule snippet is not set to enabled=false in {dpath}"
                )

    def test_10_security_scan_no_secrets(self):
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
                if os.path.abspath(fpath) == os.path.abspath(__file__):
                    continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for pat, desc in forbidden_patterns:
                    if re.search(pat, content):
                        self.fail(f"Security leak detected ({desc}) in {fpath}")

if __name__ == "__main__":
    unittest.main()
