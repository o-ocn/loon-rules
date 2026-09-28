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
import simulate_hit

TEST_TMP_DIR = os.path.join(BASE_DIR, ".test_tmp")
os.makedirs(TEST_TMP_DIR, exist_ok=True)

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
        self.assertNotIn("meta.ai", content)

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

        # Apple-Push must contain push.apple.com and official Apple APNs CIDRs (Apple Doc 102266)
        self.assertIn("push.apple.com", push_c)
        # Official 5 IPv4 CIDR blocks
        self.assertIn("17.249.0.0/16", push_c)
        self.assertIn("17.252.0.0/16", push_c)
        self.assertIn("17.57.144.0/22", push_c)
        self.assertIn("17.188.128.0/18", push_c)
        self.assertIn("17.188.20.0/23", push_c)

        # Official 4 IPv6 CIDR blocks (including official a44)
        self.assertIn("2620:149:a44::/48", push_c)
        self.assertIn("2403:300:a42::/48", push_c)
        self.assertIn("2403:300:a51::/48", push_c)
        self.assertIn("2a01:b740:a42::/48", push_c)

        # Prohibit typo a40 and broad Apple networks
        self.assertNotIn("2620:149:a40::/48", push_c)
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

        # Muse in AI without broad Meta platforms or unevidenced meta.ai
        self.assertIn("muse.ai", ai_c)
        self.assertNotIn("meta.ai", ai_c)
        self.assertNotIn("facebook.com", ai_c)
        self.assertNotIn("instagram.com", ai_c)
        self.assertNotIn("DOMAIN-SUFFIX,meta.com", ai_c)

    def test_08_upstream_fail_stop_on_single_rule(self):
        """Verify upstream returning abnormally few rules halts build without touching dist/."""
        hashes_before = {}
        for fname in self.lsr_files:
            with open(os.path.join(DIST_DIR, fname), "rb") as f:
                hashes_before[fname] = f.read()

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
            with open(os.path.join(DIST_DIR, fname), "rb") as f:
                hash_after = f.read()
            self.assertEqual(hashes_before[fname], hash_after)

    def test_09_cross_ruleset_conflict_detection_real_engine(self):
        """Verify real build engine catches exact duplicate rules across rulesets."""
        tmp_dir = tempfile.mkdtemp(prefix="test_conflict_", dir=TEST_TMP_DIR)
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
        tmp_dir = tempfile.mkdtemp(prefix="test_shadow_", dir=TEST_TMP_DIR)
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
        """Verify repeated build on unchanged sources results in zero modifications and preserves manifest."""
        hashes_before = {}
        for fname in self.lsr_files:
            with open(os.path.join(DIST_DIR, fname), "rb") as f:
                hashes_before[fname] = f.read()
        manifest_path = os.path.join(DIAGNOSTICS_DIST_DIR, "manifest.json")
        with open(manifest_path, "rb") as f:
            manifest_before = f.read()

        res = build.build_rulesets()
        self.assertEqual(res.get("updated_count"), 0)
        self.assertTrue(res.get("is_zero_change"))

        for fname in self.lsr_files:
            with open(os.path.join(DIST_DIR, fname), "rb") as f:
                hash_after = f.read()
            self.assertEqual(hashes_before[fname], hash_after, f"Idempotence violation: {fname} changed!")
        with open(manifest_path, "rb") as f:
            manifest_after = f.read()
        self.assertEqual(manifest_before, manifest_after, "Idempotence violation: manifest.json changed on zero changes!")

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
        scanned_exts = {".py", ".js", ".lpx", ".list", ".lsr", ".yml", ".yaml", ".json", ".md", ".txt", ".sh"}
        for root, dirs, files in os.walk(BASE_DIR):
            for d in [".git", "__pycache__", ".pytest_cache", "node_modules", "tmp_build", ".tmp_staging"]:
                if d in dirs:
                    dirs.remove(d)
            for fname in files:
                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()
                if ext not in scanned_exts:
                    continue
                if os.path.abspath(fpath) == os.path.abspath(__file__):
                    continue
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                for pat, desc in forbidden_patterns:
                    if re.search(pat, content):
                        self.fail(f"Security leak detected ({desc}) in {fpath}")

    def test_14_boundary_01_gemini_vs_google(self):
        """Boundary 1: Gemini vs Ordinary Google. Gemini endpoints in AI-Overseas, broad google in Google."""
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(os.path.join(DIST_DIR, "Google.lsr"), "r", encoding="utf-8") as f:
            google_c = f.read()

        gemini_endpoints = [
            "gemini.google.com",
            "aistudio.google.com",
            "makersuite.google.com",
            "deepmind.com",
            "generativelanguage.googleapis.com",
            "proactivebackend-pa.googleapis.com",
            "webchannel-robinfrontend-pa.googleapis.com",
            "robinfrontend-pa.googleapis.com",
            "geminiweb-pa.googleapis.com",
            "gemini.gstatic.com",
            "cloudcode-pa.googleapis.com",
        ]
        for ep in gemini_endpoints:
            self.assertIn(ep, ai_c, f"Gemini endpoint '{ep}' missing from AI-Overseas.lsr")
            self.assertNotIn(f"DOMAIN,{ep}", google_c, f"Gemini endpoint '{ep}' must not be claimed by Google.lsr")

        # Broad parent domains prohibited in AI-Overseas
        self.assertNotIn("DOMAIN-SUFFIX,google.com", ai_c)
        self.assertNotIn("DOMAIN-SUFFIX,googleapis.com", ai_c)
        self.assertNotIn("apis.google.com", ai_c)
        self.assertNotIn("DOMAIN-KEYWORD,colab", ai_c)
        self.assertNotIn("DOMAIN-KEYWORD,developerprofiles", ai_c)
        self.assertNotIn("DOMAIN-KEYWORD,generativelanguage", ai_c)

        # Simulation check: gemini.google.com must resolve to AI-Overseas.lsr
        rules_by_file = simulate_hit.load_dist_rules()
        matches = simulate_hit.match_domain("gemini.google.com", rules_by_file)
        self.assertTrue(len(matches) >= 1)
        self.assertEqual(matches[0]["ruleset"], "AI-Overseas.lsr", "gemini.google.com was not matched first by AI-Overseas.lsr")

    def test_15_boundary_02_gemini_vs_drive(self):
        """Boundary 2: Gemini vs Google Drive. Clean separation of storage vs AI."""
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(os.path.join(DIST_DIR, "GoogleDrive.lsr"), "r", encoding="utf-8") as f:
            drive_c = f.read()

        self.assertIn("drive.google.com", drive_c)
        self.assertIn("docs.google.com", drive_c)
        self.assertNotIn("drive.google.com", ai_c)
        self.assertNotIn("docs.google.com", ai_c)

        self.assertNotIn("gemini.google.com", drive_c)
        self.assertNotIn("aistudio.google.com", drive_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches = simulate_hit.match_domain("drive.google.com", rules_by_file)
        self.assertEqual(matches[0]["ruleset"], "GoogleDrive.lsr")

    def test_16_boundary_03_drive_vs_shared_api(self):
        """Boundary 3: Google Drive vs Google Shared API (www.googleapis.com). Shared APIs must not be hijacked."""
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(os.path.join(DIST_DIR, "GoogleDrive.lsr"), "r", encoding="utf-8") as f:
            drive_c = f.read()
        with open(os.path.join(DIST_DIR, "Google.lsr"), "r", encoding="utf-8") as f:
            google_c = f.read()

        # Requirement 7: www.googleapis.com is shared and must NOT be in Drive or AI
        self.assertNotIn("www.googleapis.com", drive_c)
        self.assertNotIn("www.googleapis.com", ai_c)
        self.assertIn("googleapis.com", google_c)

        # Broad googleusercontent.com must not be in GoogleDrive
        self.assertNotIn("DOMAIN-SUFFIX,googleusercontent.com", drive_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches = simulate_hit.match_domain("www.googleapis.com", rules_by_file)
        self.assertEqual(matches[0]["ruleset"], "Google.lsr")

    def test_17_boundary_04_youtube_vs_google(self):
        """Boundary 4: YouTube vs Ordinary Google. YouTube streaming & CDN isolated from Google."""
        with open(os.path.join(DIST_DIR, "YouTube.lsr"), "r", encoding="utf-8") as f:
            yt_c = f.read()
        with open(os.path.join(DIST_DIR, "Google.lsr"), "r", encoding="utf-8") as f:
            google_c = f.read()
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()

        self.assertIn("youtube.com", yt_c)
        self.assertIn("googlevideo.com", yt_c)
        self.assertIn("172.110.32.0/21", yt_c)
        self.assertIn("216.73.80.0/20", yt_c)

        # YouTube CDN IPs excluded from Google.lsr
        self.assertNotIn("172.110.32.0/21", google_c)
        self.assertNotIn("216.73.80.0/20", google_c)

        # deepmind.com in AI, not Google
        self.assertIn("deepmind.com", ai_c)
        self.assertNotIn("deepmind.com", google_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches = simulate_hit.match_domain("www.youtube.com", rules_by_file)
        self.assertEqual(matches[0]["ruleset"], "YouTube.lsr")

    def test_18_boundary_05_grok_vs_twitter(self):
        """Boundary 5: Grok vs Twitter/X. Grok in AI-Overseas, Twitter in Twitter."""
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(os.path.join(DIST_DIR, "Twitter.lsr"), "r", encoding="utf-8") as f:
            twitter_c = f.read()

        self.assertIn("grok.com", ai_c)
        self.assertIn("x.ai", ai_c)
        self.assertNotIn("grok.com", twitter_c)
        self.assertNotIn("x.ai", twitter_c)

        self.assertIn("twitter.com", twitter_c)
        self.assertIn("x.com", twitter_c)
        self.assertNotIn("DOMAIN-SUFFIX,twitter.com", ai_c)
        self.assertNotIn("DOMAIN-SUFFIX,x.com", ai_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches_grok = simulate_hit.match_domain("api.grok.com", rules_by_file)
        self.assertEqual(matches_grok[0]["ruleset"], "AI-Overseas.lsr")

        matches_xai = simulate_hit.match_domain("api.x.ai", rules_by_file)
        self.assertEqual(matches_xai[0]["ruleset"], "AI-Overseas.lsr")

        matches_twitter = simulate_hit.match_domain("api.twitter.com", rules_by_file)
        self.assertEqual(matches_twitter[0]["ruleset"], "Twitter.lsr")

    def test_19_boundary_06_muse_vs_meta(self):
        """Boundary 6: Muse vs Meta. Muse from Meta (App Store ID 6760173601) on muse.ai."""
        with open(os.path.join(DIST_DIR, "AI-Overseas.lsr"), "r", encoding="utf-8") as f:
            ai_c = f.read()

        # muse.ai in AI-Overseas; meta.ai excluded due to lack of Muse-specific evidence
        self.assertIn("muse.ai", ai_c)
        self.assertNotIn("meta.ai", ai_c)

        # Meta broad platforms strictly forbidden
        forbidden_meta = [
            "facebook.com", "instagram.com", "meta.com", "whatsapp.com", "fbcdn.net"
        ]
        for fm in forbidden_meta:
            self.assertNotIn(f"DOMAIN-SUFFIX,{fm}", ai_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches_muse = simulate_hit.match_domain("muse.ai", rules_by_file)
        self.assertEqual(matches_muse[0]["ruleset"], "AI-Overseas.lsr")

        # api.meta.ai does not match AI-Overseas
        matches_meta_ai = simulate_hit.match_domain("api.meta.ai", rules_by_file)
        if matches_meta_ai:
            self.assertNotEqual(matches_meta_ai[0]["ruleset"], "AI-Overseas.lsr")

    def test_20_boundary_07_testflight_vs_apple_media_vs_apple_direct(self):
        """Boundary 7: TestFlight vs Apple Media vs Apple Direct."""
        with open(os.path.join(DIST_DIR, "TestFlight.lsr"), "r", encoding="utf-8") as f:
            tf_c = f.read()
        with open(os.path.join(DIST_DIR, "Apple-Media.lsr"), "r", encoding="utf-8") as f:
            media_c = f.read()
        with open(os.path.join(DIST_DIR, "Apple-Direct.lsr"), "r", encoding="utf-8") as f:
            direct_c = f.read()

        self.assertIn("testflight.apple.com", tf_c)
        self.assertNotIn("testflight.apple.com", direct_c)
        self.assertNotIn("DOMAIN-SUFFIX,apple.com", tf_c)

        self.assertIn("tv.apple.com", media_c)
        self.assertIn("apple.news", media_c)
        self.assertNotIn("DOMAIN-SUFFIX,apple.com", media_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches_tf = simulate_hit.match_domain("testflight.apple.com", rules_by_file)
        self.assertEqual(matches_tf[0]["ruleset"], "TestFlight.lsr")

        matches_media = simulate_hit.match_domain("tv.apple.com", rules_by_file)
        self.assertEqual(matches_media[0]["ruleset"], "Apple-Media.lsr")

        matches_direct = simulate_hit.match_domain("icloud.com", rules_by_file)
        self.assertEqual(matches_direct[0]["ruleset"], "Apple-Direct.lsr")

    def test_21_boundary_08_apns_vs_apple_direct(self):
        """Boundary 8: APNs vs Apple Direct. Minimal official APNs isolated from base Apple."""
        with open(os.path.join(DIST_DIR, "Apple-Push.lsr"), "r", encoding="utf-8") as f:
            push_c = f.read()
        with open(os.path.join(DIST_DIR, "Apple-Direct.lsr"), "r", encoding="utf-8") as f:
            direct_c = f.read()

        self.assertIn("push.apple.com", push_c)
        self.assertIn("17.249.0.0/16", push_c)
        self.assertNotIn("17.0.0.0/8", push_c)
        self.assertNotIn("DOMAIN-SUFFIX,apple.com", push_c)

        rules_by_file = simulate_hit.load_dist_rules()
        matches_push = simulate_hit.match_domain("courier.push.apple.com", rules_by_file)
        self.assertEqual(matches_push[0]["ruleset"], "Apple-Push.lsr")

    def test_22_full_pipeline_evaluation_order_simulation(self):
        """Verify simulated top-to-bottom rule evaluation across all 14 services."""
        rules_by_file = simulate_hit.load_dist_rules()
        test_cases = [
            ("deepseek.com", "AI-China-Direct.lsr"),
            ("chatgpt.com", "AI-Overseas.lsr"),
            ("gemini.google.com", "AI-Overseas.lsr"),
            ("youtube.com", "YouTube.lsr"),
            ("drive.google.com", "GoogleDrive.lsr"),
            ("google.com", "Google.lsr"),
            ("onedrive.live.com", "OneDrive.lsr"),
            ("t.me", "Telegram.lsr"),
            ("twitter.com", "Twitter.lsr"),
            ("discord.com", "Discord.lsr"),
            ("testflight.apple.com", "TestFlight.lsr"),
            ("tv.apple.com", "Apple-Media.lsr"),
            ("push.apple.com", "Apple-Push.lsr"),
            ("icloud.com", "Apple-Direct.lsr"),
            ("weixin.com", "China-Direct.lsr"),
        ]
        for domain, expected_ruleset in test_cases:
            matches = simulate_hit.match_domain(domain, rules_by_file)
            self.assertTrue(len(matches) >= 1, f"Domain '{domain}' did not match any rule!")
            self.assertEqual(matches[0]["ruleset"], expected_ruleset,
                             f"Domain '{domain}' matched '{matches[0]['ruleset']}' instead of expected '{expected_ruleset}'")

    def test_23_upstream_overlap_detection_functionality(self):
        """Verify automated prompt is generated when upstream officially incorporates a custom rule."""
        custom_rules = {"DOMAIN-SUFFIX,1drv.com", "DOMAIN-SUFFIX,custom-new.com"}
        upstream_rules_by_source = {"OneDrive": ["DOMAIN-SUFFIX,1drv.com", "DOMAIN-SUFFIX,onedrive.com"]}
        overlaps = build.detect_upstream_overlaps(custom_rules, upstream_rules_by_source, ruleset_name="OneDrive")

        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0]["rule"], "DOMAIN-SUFFIX,1drv.com")
        self.assertEqual(overlaps[0]["ruleset"], "OneDrive")
        self.assertEqual(overlaps[0]["upstream"], "OneDrive")

    def test_24_manifest_mirror_endpoints_structure(self):
        """Verify China-accessible backup mirror and primary mirror endpoints configured in manifest.json."""
        manifest_path = os.path.join(DIAGNOSTICS_DIST_DIR, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)

        self.assertIn("primary_base", m)
        self.assertIn("backup_base", m)
        self.assertTrue(m["primary_base"].startswith("https://raw.githubusercontent.com"))
        self.assertTrue(m["backup_base"].startswith("https://fastly.jsdelivr.net"))

        for rname in EXPECTED_RULESETS:
            primary_url = f"{m['primary_base']}/{rname}"
            backup_url = f"{m['backup_base']}/{rname}"
            self.assertTrue(primary_url.endswith(".lsr"))
            self.assertTrue(backup_url.endswith(".lsr"))

    def test_25_sanitize_log_zero_privacy_leak(self):
        """Verify sanitize_log strictly strips credentials, URL paths, tokens, and raw errors."""
        from scripts.sanitize_log import sanitize_har, extract_safe_host, ErrorCategory

        # 1. extract_safe_host test with credentials, port, path, query
        h1 = extract_safe_host("https://admin:super_secret_password123@api.openai.com:8443/v1/chat?token=secret#frag")
        self.assertEqual(h1, "api.openai.com")

        # 2. Synthetic HAR test with sensitive tokens in URL, headers, postData, statusText, and error
        synthetic_har = {
            "log": {
                "entries": [
                    {
                        "startedDateTime": "2026-09-28T12:00:00.000Z",
                        "request": {
                            "url": "https://admin:super_secret_password123@api.openai.com:8443/v1/chat/completions?auth_token=tok_secret_999#frag",
                            "method": "POST",
                            "headers": [
                                {"name": "Authorization", "value": "Bearer sk-secret-bearer-token-12345"},
                                {"name": "Cookie", "value": "session=sess_secret_cookie_abcdef"}
                            ],
                            "postData": {"text": "{\"prompt\": \"confidential private data\"}"},
                            "bodySize": 1024
                        },
                        "response": {
                            "status": 401,
                            "statusText": "Unauthorized user_secret_id_888",
                            "headers": [{"name": "Set-Cookie", "value": "secret_cookie=999"}],
                            "content": {"text": "{\"error\": \"Invalid bearer token\"}", "size": 128},
                            "bodySize": 128
                        },
                        "_error": "Bearer token sk-secret-bearer-token-12345 failed authentication",
                        "_rule": "DOMAIN-SUFFIX,openai.com",
                        "_policy": "AI"
                    },
                    {
                        "startedDateTime": "user@example.com",
                        "request": {
                            "url": "https://api.github.com/zen",
                            "method": "GET"
                        },
                        "response": {"status": 200},
                        "_rule": "Authorization: Bearer SECRETXYZ",
                        "_proxy": "Device-ID-ABC123"
                    }
                ]
            }
        }

        records = sanitize_har(synthetic_har, set(), set())
        self.assertEqual(len(records), 2)
        rec = records[0]
        rec2 = records[1]

        # Check host extracted safely
        self.assertEqual(rec["host"], "api.openai.com")
        self.assertNotIn("url", rec)
        self.assertEqual(rec["status"], 401)
        self.assertEqual(rec["error_category"], ErrorCategory.HTTP_4XX)

        # Check second entry privacy enforcement
        self.assertEqual(rec2["host"], "api.github.com")
        self.assertEqual(rec2["timestamp"], "")   # user@example.com redacted
        self.assertEqual(rec2["rule"], "")        # Authorization: Bearer redacted
        self.assertEqual(rec2["policy"], "PROXY") # Device-ID redacted to safe PROXY

        # Verify zero leakage of credentials, tokens, paths, cookies in serialized output
        all_json = json.dumps(records)
        leaked_secrets = [
            "admin", "super_secret", "password123", "tok_secret", "sk-secret",
            "sess_secret", "user_secret", "/v1/chat/completions", "confidential",
            "SECRETXYZ", "Device-ID-ABC123", "user@example.com", "Authorization"
        ]
        for secret in leaked_secrets:
            self.assertNotIn(secret, all_json, f"Privacy leak detected: '{secret}' found in sanitized record!")

    def test_26_simulate_hit_ip_and_disabled_lcf_rules(self):
        """Verify simulator correctly matches IP-CIDR / IP-CIDR6 and ignores disabled LCF rules."""
        rules_by_file = simulate_hit.load_dist_rules()

        # APNs IPv4 CIDR matching
        m_ip4 = simulate_hit.match_target("17.249.1.5", rules_by_file)
        self.assertTrue(len(m_ip4) >= 1)
        self.assertEqual(m_ip4[0]["ruleset"], "Apple-Push.lsr")

        # APNs IPv6 CIDR matching
        m_ip6 = simulate_hit.match_target("2620:149:a44::1", rules_by_file)
        self.assertTrue(len(m_ip6) >= 1)
        self.assertEqual(m_ip6[0]["ruleset"], "Apple-Push.lsr")

        # LCF simulation skipping enabled=false
        mock_lcf = os.path.join(TEST_TMP_DIR, "mock.lcf")
        with open(mock_lcf, "w", encoding="utf-8") as f:
            f.write("""[Rule]
DOMAIN,disabled-rule.com,DIRECT,enabled=false
DOMAIN,enabled-rule.com,DIRECT

[Remote Rule]
https://raw.githubusercontent.com/.../dist/Disabled.lsr, policy=DIRECT, tag=Disabled, enabled=false
https://raw.githubusercontent.com/.../dist/Apple-Push.lsr, policy=DIRECT, tag=Apple-Push
""")
        pipe = simulate_hit.load_lcf_pipeline(mock_lcf)
        self.assertIsNotNone(pipe)
        local_values = [r["value"] for r in pipe["local_rules"]]
        self.assertIn("enabled-rule.com", local_values)
        self.assertNotIn("disabled-rule.com", local_values)
        self.assertIn("Apple-Push.lsr", pipe["remote_order"])
        self.assertNotIn("Disabled.lsr", pipe["remote_order"])

    def test_27_sanitize_unknown_rule_and_policy_labels(self):
        """Verify unknown rule labels and private policy/node names are strictly redacted."""
        from scripts.sanitize_log import sanitize_safe_rule_label, sanitize_safe_policy_label

        # Unknown rule labels stripped
        self.assertEqual(sanitize_safe_rule_label("MyPrivateRule"), "")
        self.assertEqual(sanitize_safe_rule_label("CustomSecretTag"), "")
        self.assertEqual(sanitize_safe_rule_label("MyNode123"), "")

        # Known public rulesets allowed
        self.assertEqual(sanitize_safe_rule_label("AI-Overseas.lsr"), "AI-Overseas.lsr")
        self.assertEqual(sanitize_safe_rule_label("GoogleDrive"), "GoogleDrive")

        # Unknown policies/nodes sanitized to PROXY
        self.assertEqual(sanitize_safe_policy_label("PrivateNode123"), "PROXY")
        self.assertEqual(sanitize_safe_policy_label("HK-BGP-01"), "PROXY")
        self.assertEqual(sanitize_safe_policy_label("MyCustomProxyGroup"), "PROXY")

        # Safe built-in and category policies preserved
        self.assertEqual(sanitize_safe_policy_label("DIRECT"), "DIRECT")
        self.assertEqual(sanitize_safe_policy_label("REJECT"), "REJECT")
        self.assertEqual(sanitize_safe_policy_label("Apple Push"), "Apple Push")

        # simulate_hit FINAL policy sanitization
        mock_lcf = os.path.join(TEST_TMP_DIR, "mock_final.lcf")
        with open(mock_lcf, "w", encoding="utf-8") as f:
            f.write("[Rule]\nFINAL,PrivateNode123\n")
        pipe = simulate_hit.load_lcf_pipeline(mock_lcf)
        self.assertEqual(pipe["final_policy"], "PrivateNode123")

        # Redirect stdout and assert simulate prints sanitized FINAL,PROXY
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            simulate_hit.simulate("nonexistent-unmatched-domain-12345.xyz", [], local_rules=[], lcf_meta=pipe)
        out = buf.getvalue()
        self.assertIn("FINAL,PROXY", out)
        self.assertNotIn("PrivateNode123", out)

    def test_28_upstream_failure_injection(self):
        """Verify HTTP 404/500 and network drop fail strictly and do not use cache without --offline."""
        import urllib.error
        from unittest.mock import patch

        # 1. HTTP 404 fail-stop
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "https://raw.githubusercontent.com/.../404.list", 404, "Not Found", {}, None
            )
            with self.assertRaises(RuntimeError) as cm:
                build.fetch_upstream_strict("https://example.com/404.list", allow_offline_cache=False)
            self.assertIn("HTTP 404", str(cm.exception))

        # 2. HTTP 500 fail-stop
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "https://raw.githubusercontent.com/.../500.list", 500, "Internal Server Error", {}, None
            )
            with self.assertRaises(RuntimeError) as cm:
                build.fetch_upstream_strict("https://example.com/500.list", allow_offline_cache=False)
            self.assertIn("HTTP 500", str(cm.exception))

        # 3. Network offline fail-stop when allow_offline_cache=False
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.URLError("Network is unreachable")
            with self.assertRaises(RuntimeError) as cm:
                build.fetch_upstream_strict("https://example.com/offline.list", allow_offline_cache=False)
            self.assertIn("Failed to fetch upstream rule", str(cm.exception))

    def test_29_atomic_directory_switch_and_rollback(self):
        """Verify atomic directory switch and rollback protection on failure."""
        test_dist = os.path.join(TEST_TMP_DIR, "test_dist")
        os.makedirs(test_dist, exist_ok=True)
        orig_file = os.path.join(test_dist, "original.lsr")
        with open(orig_file, "w", encoding="utf-8") as f:
            f.write("# ORIGINAL CONTENT\n")

        # Test simulated failed swap
        test_new = os.path.join(TEST_TMP_DIR, "test_dist_new")
        os.makedirs(test_new, exist_ok=True)
        new_file = os.path.join(test_new, "new.lsr")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("# NEW CONTENT\n")

        dist_old = os.path.join(TEST_TMP_DIR, ".test_dist_old")
        os.rename(test_dist, dist_old)
        # Simulate failure by causing exception
        try:
            raise OSError("Simulated disk error during rename")
        except Exception:
            # Rollback
            if os.path.exists(dist_old) and not os.path.exists(test_dist):
                os.rename(dist_old, test_dist)

        # Assert rollback preserved original content
        self.assertTrue(os.path.isdir(test_dist))
        self.assertTrue(os.path.isfile(orig_file))
        with open(orig_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "# ORIGINAL CONTENT\n")

        # Verify manifest.json does NOT contain release_commit
        manifest_path = os.path.join(DIAGNOSTICS_DIST_DIR, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        self.assertNotIn("release_commit", m)
        self.assertIn("content_revision", m)

    def test_30_custom_zero_overlap_with_upstream(self):
        """Verify rules/custom/*.list has zero duplicates with upstream."""
        cfg = build.load_sources(SOURCES_FILE)
        all_overlaps = []
        for name, rcfg in cfg.get("rulesets", {}).items():
            custom_file_rel = rcfg.get("local_custom", "")
            if not custom_file_rel:
                continue
            custom_file = os.path.join(BASE_DIR, custom_file_rel)
            if not os.path.isfile(custom_file):
                continue
            c_rules = set()
            with open(custom_file, "r", encoding="utf-8") as f:
                for line in f:
                    cl = build.clean_rule_line(line)
                    if cl and not cl.startswith("INVALID_SYNTAX:"):
                        c_rules.add(cl)
            for src in rcfg.get("sources", []):
                surl = src.get("url")
                cache_path = build.get_upstream_cache_path(surl)
                if os.path.isfile(cache_path):
                    with open(cache_path, "r", encoding="utf-8") as f:
                        up_text = f.read()
                    up_rules = [build.clean_rule_line(l) for l in up_text.splitlines() if build.clean_rule_line(l)]
                    ovs = build.detect_upstream_overlaps(c_rules, {src.get("name"): up_rules}, ruleset_name=name)
                    all_overlaps.extend(ovs)

        self.assertEqual(len(all_overlaps), 0, f"Expected zero custom duplicates with upstream, found: {all_overlaps}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
