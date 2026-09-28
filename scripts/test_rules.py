#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Test Suite for Loon Rules
Validates syntax, strategy neutrality, isolation, fail-stop on single-rule upstream,
real-engine cross-ruleset conflict detection, build idempotence, Gemini iOS precision,
Google Drive shared API protection, minimal APNs, and diagnostic manifest validity.
Author: o-ocn
License: GPL-2.0
"""

import os
import sys
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "dist")
SOURCES_FILE = os.path.join(BASE_DIR, "sources.yml")
DIAGNOSTICS_DIST_DIR = os.path.join(DIST_DIR, "diagnostics")

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

EXPECTED_RULESETS = {
    "AI-Overseas.lsr",
    "AI-China-Direct.lsr",
    "GoogleDrive.lsr",
    "Google.lsr",
    "YouTube.lsr",
    "OneDrive.lsr",
    "Telegram.lsr",
    "Twitter.lsr",
    "Discord.lsr",
    "Apple-Push.lsr",
    "Apple-Direct.lsr",
    "Apple-Media.lsr",
    "TestFlight.lsr",
    "China-Direct.lsr"
}

class TestLoonRulesSuite(unittest.TestCase):

    def setUp(self):
        self.lsr_files = [f for f in os.listdir(DIST_DIR) if f.endswith(".lsr")]
        self.assertTrue(len(self.lsr_files) >= 14, f"Expected at least 14 .lsr files, found {len(self.lsr_files)}")
        self.assertEqual(EXPECTED_RULESETS.issubset(set(self.lsr_files)), True, f"Missing rulesets: {EXPECTED_RULESETS - set(self.lsr_files)}")

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

    def test_02_policy_neutrality_across_all_lsr(self):
        """Verify all generated .lsr files are strictly policy-neutral."""
        forbidden_policies = [
            "DIRECT", "PROXY", "REJECT",
            "HK", "US", "JP", "VMISS", "FINAL", "Apple Push"
        ]
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Header check: must NOT have # RECOMMENDED POLICY:
            self.assertNotIn("# RECOMMENDED POLICY:", content, f"Policy recommendation found in {fname}")

            for line_idx, line in enumerate(content.splitlines(), 1):
                clean = line.strip()
                if not clean or clean.startswith("#"):
                    continue
                parts = [p.strip() for p in clean.split(",")]
                # Rule format must be TYPE,VALUE or TYPE,VALUE,no-resolve
                if len(parts) > 2:
                    for extra in parts[2:]:
                        self.assertEqual(extra.lower(), "no-resolve", f"Forbidden policy or action '{extra}' in {fname}:{line_idx}")

    def test_03_ai_overseas_sync_and_gemini_ios_precision(self):
        """Verify AI-Overseas has upstream sync + custom Gemini iOS and blocks broad parent domains."""
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        self.assertTrue(os.path.isfile(ai_path), "AI-Overseas.lsr missing")
        with open(ai_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must contain verified AI domains from upstream & custom
        self.assertIn("openai.com", content)
        self.assertIn("chatgpt.com", content)
        self.assertIn("claude.ai", content)
        self.assertIn("anthropic.com", content)
        self.assertIn("gemini.google.com", content)
        self.assertIn("grok.com", content)
        self.assertIn("x.ai", content)
        self.assertIn("muse.ai", content)
        self.assertIn("meta.ai", content)

        # Gemini iOS specific endpoints
        self.assertIn("webchannel-robinfrontend-pa.googleapis.com", content)
        self.assertIn("robinfrontend-pa.googleapis.com", content)
        self.assertIn("geminiweb-pa.googleapis.com", content)
        self.assertIn("gemini.gstatic.com", content)
        self.assertIn("cloudcode-pa.googleapis.com", content)
        self.assertIn("aistudio.google.com", content)

        # Strict prohibitions: broad domains & shared infrastructure
        forbidden_rules = [
            "DOMAIN-SUFFIX,google.com",
            "DOMAIN-SUFFIX,googleapis.com",
            "DOMAIN-SUFFIX,googleusercontent.com",
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
            "IP-ASN,20473",
            "DOMAIN,www.googleapis.com",
            "DOMAIN-KEYWORD,openai"
        ]
        for fb in forbidden_rules:
            self.assertNotIn(fb, content, f"Violation: '{fb}' found in AI-Overseas.lsr! Must be scoped.")

    def test_04_ai_china_direct_policy_neutral(self):
        """Ensure DeepSeek is in AI-China-Direct without hardcoded DIRECT action."""
        china_ai_path = os.path.join(DIST_DIR, "AI-China-Direct.lsr")
        self.assertTrue(os.path.isfile(china_ai_path), "AI-China-Direct.lsr missing")
        with open(china_ai_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("deepseek.com", content)
        self.assertNotIn("openai.com", content)
        self.assertNotIn("claude.ai", content)
        for line in content.splitlines():
            if line.strip() and not line.strip().startswith("#"):
                self.assertNotIn(",DIRECT", line, f"Policy action hardcoded in AI-China-Direct: {line}")

    def test_05_google_drive_shared_api_and_youtube_segregation(self):
        """Verify www.googleapis.com is strictly segregated from AI and Drive."""
        drive_path = os.path.join(DIST_DIR, "GoogleDrive.lsr")
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        yt_path = os.path.join(DIST_DIR, "YouTube.lsr")
        google_path = os.path.join(DIST_DIR, "Google.lsr")

        with open(drive_path, "r", encoding="utf-8") as f:
            drive_c = f.read()
        with open(ai_path, "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(yt_path, "r", encoding="utf-8") as f:
            yt_c = f.read()
        with open(google_path, "r", encoding="utf-8") as f:
            google_c = f.read()

        # www.googleapis.com must NOT be in AI or Drive
        self.assertNotIn("www.googleapis.com", ai_c)
        self.assertNotIn("www.googleapis.com", drive_c)
        self.assertNotIn("ws.audioscrobbler.com", drive_c)

        # Drive explicit domains in GoogleDrive
        self.assertIn("drive.google.com", drive_c)
        self.assertIn("googledrive.com", drive_c)

        # YouTube segregation
        self.assertIn("youtube.com", yt_c)
        self.assertIn("googlevideo.com", yt_c)
        self.assertNotIn("googledrive.com", google_c)

    def test_06_apple_push_minimal_and_testflight_isolation(self):
        """Verify Apple-Push is minimal official APNs and TestFlight is separate."""
        push_path = os.path.join(DIST_DIR, "Apple-Push.lsr")
        direct_path = os.path.join(DIST_DIR, "Apple-Direct.lsr")
        tf_path = os.path.join(DIST_DIR, "TestFlight.lsr")

        with open(push_path, "r", encoding="utf-8") as f:
            push_c = f.read()
        with open(direct_path, "r", encoding="utf-8") as f:
            direct_c = f.read()
        with open(tf_path, "r", encoding="utf-8") as f:
            tf_c = f.read()

        # Apple-Push must contain push.apple.com and official CIDRs
        self.assertIn("push.apple.com", push_c)
        self.assertIn("17.249.0.0/16", push_c)
        self.assertIn("2620:149:a40::/48", push_c)

        # Must NOT contain broad Apple network
        self.assertNotIn("17.0.0.0/8", push_c)
        self.assertNotIn("DOMAIN-SUFFIX,apple.com", push_c)
        self.assertNotIn("DOMAIN-SUFFIX,icloud.com", push_c)

        # TestFlight isolation
        self.assertIn("testflight.apple.com", tf_c)
        self.assertNotIn("testflight.apple.com", direct_c)

    def test_07_grok_and_muse_isolation(self):
        """Verify Grok is separate from Twitter, and Muse does not expand to Meta platforms."""
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        twitter_path = os.path.join(DIST_DIR, "Twitter.lsr")

        with open(ai_path, "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(twitter_path, "r", encoding="utf-8") as f:
            twitter_c = f.read()

        # Grok in AI, not Twitter
        self.assertIn("grok.com", ai_c)
        self.assertIn("x.ai", ai_c)
        self.assertNotIn("grok.com", twitter_c)
        self.assertNotIn("x.ai", twitter_c)

        # Twitter in Twitter, not AI
        self.assertIn("twitter.com", twitter_c)
        self.assertIn("x.com", twitter_c)
        self.assertNotIn("DOMAIN-SUFFIX,twitter.com", ai_c)
        self.assertNotIn("DOMAIN-SUFFIX,x.com", ai_c)

        # Muse in AI without Meta platforms
        self.assertIn("muse.ai", ai_c)
        self.assertIn("meta.ai", ai_c)
        self.assertNotIn("facebook.com", ai_c)
        self.assertNotIn("instagram.com", ai_c)
        self.assertNotIn("DOMAIN-SUFFIX,meta.com", ai_c)

    def test_08_upstream_fail_stop_on_single_rule(self):
        """Verify upstream returning abnormally few rules halts build without touching dist/."""
        hashes_before = {fname: open(os.path.join(DIST_DIR, fname), "rb").read() for fname in self.lsr_files}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"# Single rule\nDOMAIN,only-one.com\n"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(RuntimeError) as ctx:
                build.build_rulesets()
            self.assertIn("abnormally few rules", str(ctx.exception))

        # Verify dist untouched
        for fname in self.lsr_files:
            hash_after = open(os.path.join(DIST_DIR, fname), "rb").read()
            self.assertEqual(hashes_before[fname], hash_after)

    def test_09_cross_ruleset_conflict_detection_real_engine(self):
        """Verify real build engine catches exact duplicate rules across rulesets."""
        tmp_dir = tempfile.mkdtemp(prefix="test_conflict_")
        try:
            t_src = os.path.join(tmp_dir, "sources.yml")
            t_dist = os.path.join(tmp_dir, "dist")
            t_a = os.path.join(tmp_dir, "A.list")
            t_b = os.path.join(tmp_dir, "B.list")

            with open(t_a, "w", encoding="utf-8") as f:
                f.write("DOMAIN,dup.example.com\n")
            with open(t_b, "w", encoding="utf-8") as f:
                f.write("DOMAIN,dup.example.com\n")

            with open(t_src, "w", encoding="utf-8") as f:
                f.write(f"""
rulesets:
  ServiceA:
    local_custom: "{t_a.replace(chr(92), '/')}"
  ServiceB:
    local_custom: "{t_b.replace(chr(92), '/')}"
""")
            with self.assertRaises(ValueError) as ctx:
                build.build_rulesets(sources_file=t_src, dist_dir=t_dist)
            self.assertIn("FATAL CONFLICT: Exact rule 'DOMAIN,dup.example.com'", str(ctx.exception))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_10_illegal_parent_domain_shadowing_real_engine(self):
        """Verify build engine catches un-delegated parent domain shadowing."""
        tmp_dir = tempfile.mkdtemp(prefix="test_shadow_")
        try:
            t_src = os.path.join(tmp_dir, "sources.yml")
            t_dist = os.path.join(tmp_dir, "dist")
            t_child = os.path.join(tmp_dir, "Child.list")
            t_parent = os.path.join(tmp_dir, "Parent.list")

            with open(t_child, "w", encoding="utf-8") as f:
                f.write("DOMAIN,unauthorized.bad.com\n")
            with open(t_parent, "w", encoding="utf-8") as f:
                f.write("DOMAIN-SUFFIX,bad.com\n")

            with open(t_src, "w", encoding="utf-8") as f:
                f.write(f"""
rulesets:
  ChildSet:
    local_custom: "{t_child.replace(chr(92), '/')}"
  ParentSet:
    local_custom: "{t_parent.replace(chr(92), '/')}"
""")
            with self.assertRaises(ValueError) as ctx:
                build.build_rulesets(sources_file=t_src, dist_dir=t_dist)
            self.assertIn("FATAL SHADOWING", str(ctx.exception))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_11_idempotent_build_no_diff(self):
        """Verify repeated build on unchanged sources results in zero modifications."""
        hashes_before = {fname: open(os.path.join(DIST_DIR, fname), "rb").read() for fname in self.lsr_files}
        build.build_rulesets()
        for fname in self.lsr_files:
            hash_after = open(os.path.join(DIST_DIR, fname), "rb").read()
            self.assertEqual(hashes_before[fname], hash_after, f"Idempotence violation: {fname} changed!")

    def test_12_diagnostics_manifest_and_plugin_validity(self):
        """Verify diagnostic manifest and plugin files are generated and valid."""
        manifest_path = os.path.join(DIAGNOSTICS_DIST_DIR, "manifest.json")
        lpx_path = os.path.join(DIAGNOSTICS_DIST_DIR, "LoonRules-Diagnostic.lpx")
        js_path = os.path.join(DIAGNOSTICS_DIST_DIR, "loon-rules-diagnostic.js")

        self.assertTrue(os.path.isfile(manifest_path), "manifest.json missing in dist/diagnostics/")
        self.assertTrue(os.path.isfile(lpx_path), "LoonRules-Diagnostic.lpx missing in dist/diagnostics/")
        self.assertTrue(os.path.isfile(js_path), "loon-rules-diagnostic.js missing in dist/diagnostics/")

        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)

        self.assertEqual(m.get("schema_version"), "1.0")
        self.assertTrue(len(m.get("rulesets", {})) >= 14)
        for rname in EXPECTED_RULESETS:
            self.assertIn(rname, m["rulesets"])
            self.assertGreater(m["rulesets"][rname]["total_rules"], 0)
            self.assertTrue(len(m["rulesets"][rname]["sha256"]) == 64)

        # Check physical verification items documented
        self.assertTrue(len(m.get("physical_verification_items", [])) >= 5)

    def test_13_security_scan_no_secrets(self):
        """Verify zero credentials, tokens, private keys, or passwords in repo."""
        forbidden_patterns = [
            ("BEGIN" + " PRIVATE KEY", "Private Key"),
            ("BEGIN" + " RSA PRIVATE KEY", "RSA Private Key"),
            ("BEGIN" + " CERTIFICATE", "Certificate"),
            ("pass" + "word = ", "Password field"),
            ("tok" + "en=[a-zA-Z0-9_-]{16,}", "Subscription token"),
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
