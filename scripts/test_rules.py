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
import re
import unittest
import tempfile
import shutil
import json
import hashlib
import ipaddress
import urllib.request
import urllib.error
import yaml
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
    "URL-REGEX",
    "GEOIP"
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
    "China-Direct.lsr",
    "China-GeoIP.lsr",
    "Lan.lsr",
    "PayPal.lsr",
    "Gaming.lsr",
    "GitHub.lsr"
}

class TestLoonRulesSuite(unittest.TestCase):

    def setUp(self):
        self.lsr_files = [f for f in os.listdir(DIST_DIR) if f.endswith(".lsr")]
        self.assertEqual(len(self.lsr_files), 19, f"Expected exactly 19 .lsr files, found {len(self.lsr_files)}")
        self.assertEqual(EXPECTED_RULESETS, set(self.lsr_files), f"Ruleset mismatch: diff={EXPECTED_RULESETS ^ set(self.lsr_files)}")

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

        def controlled_urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            cache_file = build.get_upstream_cache_path(url)
            if os.path.isfile(cache_file):
                with open(cache_file, "rb") as f:
                    content = f.read()
                mock_resp = MagicMock()
                mock_resp.status = 200
                mock_resp.read.return_value = content
                mock_resp.__enter__.return_value = mock_resp
                return mock_resp
            # Robust fallback: synthesize response from locked baseline to prevent failure in stripped runners
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.read.return_value = b"# Controlled Offline Fixture\nDOMAIN,fallback.example.com\n" * 50
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=controlled_urlopen):
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
        self.assertEqual(len(m.get("rulesets", {})), 19)
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
        """Verify simulated top-to-bottom rule evaluation across all 20 services."""
        rules_by_file = simulate_hit.load_dist_rules()
        test_cases = [
            ("push.apple.com", "Apple-Push.lsr"),
            ("chatgpt.com", "AI-Overseas.lsr"),
            ("gemini.google.com", "AI-Overseas.lsr"),
            ("youtube.com", "YouTube.lsr"),
            ("drive.google.com", "GoogleDrive.lsr"),
            ("google.com", "Google.lsr"),
            ("onedrive.live.com", "OneDrive.lsr"),
            ("t.me", "Telegram.lsr"),
            ("twitter.com", "Twitter.lsr"),
            ("discord.com", "Discord.lsr"),
            ("paypal.com", "PayPal.lsr"),
            ("steampowered.com", "Gaming.lsr"),
            ("epicgames.com", "Gaming.lsr"),
            ("github.com", "GitHub.lsr"),
            ("testflight.apple.com", "TestFlight.lsr"),
            ("tv.apple.com", "Apple-Media.lsr"),
            ("deepseek.com", "AI-China-Direct.lsr"),
            ("icloud.com", "Apple-Direct.lsr"),
            ("weixin.com", "China-Direct.lsr"),
            ("douyin.com", "China-Direct.lsr"),
            ("p3-sign.douyinpic.com", "China-Direct.lsr"),
            ("bilibili.com", "China-Direct.lsr"),
        ]
        for domain, expected_ruleset in test_cases:
            matches = simulate_hit.match_domain(domain, rules_by_file)
            self.assertTrue(len(matches) >= 1, f"Domain '{domain}' did not match any rule!")
            self.assertEqual(matches[0]["ruleset"], expected_ruleset,
                             f"Domain '{domain}' matched '{matches[0]['ruleset']}' instead of expected '{expected_ruleset}'")

        # Verify LAN private subnets hit Lan.lsr
        lan_test_cases = [
            ("192.168.1.1", "Lan.lsr"),
            ("10.0.0.1", "Lan.lsr"),
            ("172.16.0.1", "Lan.lsr"),
            ("100.64.0.1", "Lan.lsr"),
        ]
        for ip_addr, expected_ruleset in lan_test_cases:
            matches = simulate_hit.match_target(ip_addr, rules_by_file)
            self.assertTrue(len(matches) >= 1, f"IP '{ip_addr}' did not match any rule!")
            self.assertEqual(matches[0]["ruleset"], expected_ruleset)

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
        """Verify switch_dist_directory in-flight rollback and recover_interrupted_dist crash recovery."""
        test_dist = os.path.join(TEST_TMP_DIR, "test_dist_actual")
        os.makedirs(test_dist, exist_ok=True)
        orig_file = os.path.join(test_dist, "original.lsr")
        with open(orig_file, "w", encoding="utf-8") as f:
            f.write("# ORIGINAL CONTENT\n")

        test_new = os.path.join(TEST_TMP_DIR, "test_dist_new_actual")
        os.makedirs(test_new, exist_ok=True)
        new_file = os.path.join(test_new, "new.lsr")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("# NEW CONTENT\n")

        # 1. Test in-flight rollback in switch_dist_directory when second rename fails
        real_rename = os.rename
        rename_call_count = [0]
        def faulty_rename(src, dst):
            rename_call_count[0] += 1
            if rename_call_count[0] == 2:  # Step 2: dist_new -> dist
                raise OSError("Injected disk I/O error during second rename")
            return real_rename(src, dst)

        with patch("os.rename", side_effect=faulty_rename):
            with self.assertRaises(RuntimeError) as cm:
                build.switch_dist_directory(test_new, test_dist)
            self.assertIn("Directory switch failed, previous dist restored", str(cm.exception))

        # Assert rollback preserved original content
        self.assertTrue(os.path.isdir(test_dist))
        self.assertTrue(os.path.isfile(orig_file))
        with open(orig_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "# ORIGINAL CONTENT\n")

        # 2. Test crash recovery: simulate process terminated mid-switch (dist missing, .dist_old exists)
        dist_parent = os.path.dirname(os.path.abspath(test_dist))
        dist_old = os.path.join(dist_parent, ".dist_old")
        if os.path.exists(dist_old):
            shutil.rmtree(dist_old, ignore_errors=True)
        os.rename(test_dist, dist_old)
        self.assertFalse(os.path.exists(test_dist))
        self.assertTrue(os.path.exists(dist_old))

        # Call recover_interrupted_dist
        recovered = build.recover_interrupted_dist(test_dist)
        self.assertTrue(recovered)
        self.assertTrue(os.path.isdir(test_dist))
        self.assertTrue(os.path.isfile(orig_file))
        self.assertFalse(os.path.exists(dist_old))

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

    def test_31_googleusercontent_placement_boundary(self):
        """Verify DOMAIN-SUFFIX,googleusercontent.com is in Google.lsr and absent in AI and Drive."""
        google_path = os.path.join(DIST_DIR, "Google.lsr")
        ai_path = os.path.join(DIST_DIR, "AI-Overseas.lsr")
        drive_path = os.path.join(DIST_DIR, "GoogleDrive.lsr")

        with open(google_path, "r", encoding="utf-8") as f:
            g_c = f.read()
        with open(ai_path, "r", encoding="utf-8") as f:
            ai_c = f.read()
        with open(drive_path, "r", encoding="utf-8") as f:
            dr_c = f.read()

        self.assertIn("DOMAIN-SUFFIX,googleusercontent.com", g_c, "googleusercontent.com missing in Google.lsr!")
        self.assertNotIn("googleusercontent.com", ai_c, "googleusercontent.com leaked into AI-Overseas.lsr!")
        self.assertNotIn("googleusercontent.com", dr_c, "googleusercontent.com leaked into GoogleDrive.lsr!")

        # Verify total rules across all 19 .lsr files is exactly 21098
        total_rules = 0
        for fname in self.lsr_files:
            total_rules += build.count_lsr_rules(os.path.join(DIST_DIR, fname))
        self.assertEqual(total_rules, 21098, f"Expected 21098 rules, got {total_rules}")

    def test_32_public_19_order_fixture_and_four_stage_pipeline(self):
        """Verify complete 4-stage pipeline against public 19-class order fixture."""
        fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "sample_order_19.fixture")
        if not os.path.isfile(fixture_path):
            fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "sample_order_20.fixture")
        self.assertTrue(os.path.isfile(fixture_path), "sample_order_19.fixture missing!")

        pipeline = simulate_hit.load_lcf_pipeline(fixture_path)
        self.assertIsNotNone(pipeline)
        self.assertEqual(len(pipeline["remote_order"]), 19, "Expected 19 rulesets in remote_order")

        rules_by_file = simulate_hit.load_dist_rules(pipeline["remote_order"])
        local_rules = pipeline["local_rules"]
        simulated_plugin_rules = [
            {"type": "DOMAIN", "value": "plugin-injected.example.com", "raw": "DOMAIN,plugin-injected.example.com"}
        ]

        # Stage 1: Local [Rule] outranks everything
        m_s1 = simulate_hit.match_target("local-override.example.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_s1[0]["stage"], "Stage 1 (Local [Rule])")

        # Stage 2: Plugin [Rule] outranks Stage 3
        m_s2 = simulate_hit.match_target("plugin-injected.example.com", rules_by_file, local_rules=local_rules, plugin_rules=simulated_plugin_rules)
        self.assertEqual(m_s2[0]["stage"], "Stage 2 (Plugin [Rule])")

        # Stage 3: Specific before broad evaluations (First Match Wins)
        # CRITICAL: YouTube specific Google subdomain must hit YouTube.lsr, NOT Google.lsr
        m_yt_sub = simulate_hit.match_target("youtube-ui.l.google.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_yt_sub[0]["ruleset"], "YouTube.lsr", "youtube-ui.l.google.com must hit YouTube.lsr before Google.lsr!")

        m_yt = simulate_hit.match_target("www.youtube.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_yt[0]["ruleset"], "YouTube.lsr")

        m_gd = simulate_hit.match_target("drive.google.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_gd[0]["ruleset"], "GoogleDrive.lsr", "drive.google.com must hit GoogleDrive.lsr before Google.lsr!")

        m_g = simulate_hit.match_target("google.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_g[0]["ruleset"], "Google.lsr")

        # Gaming platform evaluations
        m_steam = simulate_hit.match_target("steampowered.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_steam[0]["ruleset"], "Gaming.lsr")

        m_epic = simulate_hit.match_target("epicgames.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_epic[0]["ruleset"], "Gaming.lsr")

        # Apple services boundaries
        m_tf = simulate_hit.match_target("testflight.apple.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_tf[0]["ruleset"], "TestFlight.lsr")

        m_media = simulate_hit.match_target("tv.apple.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_media[0]["ruleset"], "Apple-Media.lsr")

        m_apple_dir = simulate_hit.match_target("icloud.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_apple_dir[0]["ruleset"], "Apple-Direct.lsr")

        m_push = simulate_hit.match_target("push.apple.com", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_push[0]["ruleset"], "Apple-Push.lsr")

        # LAN before China-GeoIP priority
        m_lan = simulate_hit.match_target("192.168.1.1", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_lan[0]["ruleset"], "Lan.lsr")

        m_cgnat = simulate_hit.match_target("100.64.1.1", rules_by_file, local_rules=local_rules)
        self.assertEqual(m_cgnat[0]["ruleset"], "Lan.lsr")

        # Mainland China incident IP and IPv6 hit China-GeoIP
        m_incident = simulate_hit.match_target("119.147.195.212", rules_by_file, local_rules=local_rules)
        self.assertTrue(len(m_incident) >= 1, "Douyin incident IP 119.147.195.212 must hit China-GeoIP, not fall through to FINAL!")
        self.assertEqual(m_incident[0]["ruleset"], "China-GeoIP.lsr")

        m_v6 = simulate_hit.match_target("240e:97c:2f:1::1", rules_by_file, local_rules=local_rules)
        self.assertTrue(len(m_v6) >= 1, "China Telecom IPv6 sample must hit China-GeoIP.lsr!")
        self.assertEqual(m_v6[0]["ruleset"], "China-GeoIP.lsr")

        # Stage 4: Unmatched targets fall through to FINAL
        m_unmatched = simulate_hit.match_target("completely-unmatched-unknown-service.xyz", rules_by_file, local_rules=local_rules)
        self.assertEqual(len(m_unmatched), 0, "Unmatched domain must have 0 stage 1-3 hits to trigger FINAL")

        m_foreign_ip = simulate_hit.match_target("1.1.1.1", rules_by_file, local_rules=local_rules)
        self.assertEqual(len(m_foreign_ip), 0, "Foreign IP 1.1.1.1 must not match China-GeoIP and fall through to FINAL")

    def test_33_paypal_curation_regression(self):
        """Verify PayPal curated operational domains are present and scam/phishing domains are excluded."""
        paypal_path = os.path.join(DIST_DIR, "PayPal.lsr")
        with open(paypal_path, "r", encoding="utf-8") as f:
            pp_content = f.read()

        official_domains = [
            "paypal.com", "paypalobjects.com", "paypal.me", "braintreegateway.com",
            "braintreepayments.com", "venmo.com", "xoom.com", "simility.com",
            "paydiant.com", "anfutong.cn", "beibao.cn", "beibao.com.cn"
        ]
        for d in official_domains:
            self.assertIn(d, pp_content, f"Official PayPal domain '{d}' missing from PayPal.lsr!")

        phishing_domains = [
            "pa9pal.com", "account-paypal.info", "accountpaypal.com",
            "login-paypal.com", "filipino-music.net", "i-o-u.info"
        ]
        for p in phishing_domains:
            self.assertNotIn(p, pp_content, f"Phishing/typosquatting domain '{p}' leaked into PayPal.lsr!")

    def test_34_gaming_platform_purged_domains_regression(self):
        """Verify Gaming platform domains (Steam and Epic) are present and non-platform/piracy domains are excluded."""
        gaming_path = os.path.join(DIST_DIR, "Gaming.lsr")
        self.assertTrue(os.path.isfile(gaming_path), "Gaming.lsr missing in dist!")
        with open(gaming_path, "r", encoding="utf-8") as f:
            gaming_content = f.read()

        # Steam platform domains present
        self.assertIn("steampowered.com", gaming_content)
        self.assertIn("steamcommunity.com", gaming_content)
        self.assertIn("steamgames.com", gaming_content)

        # Epic platform domains present
        self.assertIn("epicgames.com", gaming_content)
        self.assertIn("unrealengine.com", gaming_content)

        # Third-party piracy, unbundled stores, and shared customer support SDKs purged
        for p in ["steamunlocked.net", "humblebundle.com", "fanatical.com", "helpshift.com"]:
            self.assertNotIn(p, gaming_content, f"Purged domain '{p}' leaked into Gaming.lsr!")

    def test_35_manifest_offline_integrity_and_mirror_contract(self):
        """Verify manifest.json contains all 19 rulesets with valid SHA256 hashes offline."""
        manifest_path = os.path.join(DIST_DIR, "diagnostics", "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            man = json.load(f)

        rulesets = man.get("rulesets", {})
        self.assertEqual(len(rulesets), 19, f"Expected 19 rulesets in manifest, found {len(rulesets)}")

        for rname, meta in rulesets.items():
            lsr_path = os.path.join(DIST_DIR, rname)
            self.assertTrue(os.path.isfile(lsr_path), f"Ruleset file '{rname}' in manifest missing on disk!")
            with open(lsr_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#") and not l.startswith(";")]
            rule_body = "\n".join(lines)
            computed_hash = hashlib.sha256(rule_body.encode("utf-8")).hexdigest()
            self.assertEqual(meta["sha256"], computed_hash, f"SHA256 mismatch for ruleset '{rname}'!")
            self.assertGreater(meta["total_rules"], 0)

    def test_36_douyin_incident_regression(self):
        """Verify Douyin image, CDN, video, and API domains match China-Direct and incident IP hits China-GeoIP."""
        rules_by_file = simulate_hit.load_dist_rules()

        douyin_incident_domains = [
            "p3-sign.douyinpic.com",
            "p6-sign.douyinpic.com",
            "p9-sign.douyinpic.com",
            "v26-web.douyinvod.com",
            "sf3-cdn-tos.douyinstatic.com",
            "lf3-static.bytednsdoc.com",
            "v5-dy-o-abtest.zjcdn.com",
            "douyincdn.com",
            "douyinpic.com",
            "douyin.com",
            "snssdk.com",
            "bytedance.com",
            "byteimg.com",
            "bytedns.net",
            "zijieapi.com",
            "ibytedtos.com",
            "bilibili.com",
            "bilivideo.com"
        ]

        for domain in douyin_incident_domains:
            matches = simulate_hit.match_domain(domain, rules_by_file)
            self.assertTrue(len(matches) >= 1, f"Douyin domain '{domain}' did not match any rule and fell into FINAL!")
            self.assertEqual(matches[0]["ruleset"], "China-Direct.lsr",
                             f"Douyin domain '{domain}' matched '{matches[0]['ruleset']}' instead of 'China-Direct.lsr'")

        # Incident IP 119.147.195.212 regression: must match China-GeoIP.lsr via 119.144.0.0/14
        ip_matches = simulate_hit.match_target("119.147.195.212", rules_by_file)
        self.assertTrue(len(ip_matches) >= 1, "Douyin incident IP 119.147.195.212 fell into FINAL!")
        self.assertEqual(ip_matches[0]["ruleset"], "China-GeoIP.lsr")

    def test_37_ip_cidr_syntax_and_containment(self):
        """Verify all IP-CIDR and IP-CIDR6 rules in all rulesets have strictly valid syntax, masks, and order."""
        for fname in self.lsr_files:
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f, 1):
                    clean = line.strip()
                    if not clean or clean.startswith("#") or clean.startswith(";"):
                        continue
                    parts = clean.split(",")
                    rtype = parts[0].strip()
                    if rtype in ("IP-CIDR", "IP-CIDR6"):
                        cidr = parts[1].strip()
                        # Strict validation: no host bits allowed, valid subnet notation
                        try:
                            net = ipaddress.ip_network(cidr, strict=True)
                        except ValueError as e:
                            self.fail(f"Invalid {rtype} rule '{clean}' in {fname}:{line_idx}: {e}")

                        if rtype == "IP-CIDR":
                            self.assertEqual(net.version, 4, f"IP-CIDR rule '{clean}' in {fname} is not IPv4!")
                            self.assertTrue(0 <= net.prefixlen <= 32)
                        elif rtype == "IP-CIDR6":
                            self.assertEqual(net.version, 6, f"IP-CIDR6 rule '{clean}' in {fname} is not IPv6!")
                            self.assertTrue(0 <= net.prefixlen <= 128)

        # Verify containment priority: Lan matches before China-GeoIP
        rules_by_file = simulate_hit.load_dist_rules()
        m_lan = simulate_hit.match_target("10.1.2.3", rules_by_file)
        self.assertEqual(m_lan[0]["ruleset"], "Lan.lsr")
        m_cgnat = simulate_hit.match_target("100.64.1.1", rules_by_file)
        self.assertEqual(m_cgnat[0]["ruleset"], "Lan.lsr")

        # Verify Apple Push containment
        m_push = simulate_hit.match_target("17.249.0.5", rules_by_file)
        self.assertEqual(m_push[0]["ruleset"], "Apple-Push.lsr")

        # Verify Telegram containment
        m_tg = simulate_hit.match_target("91.108.4.1", rules_by_file)
        self.assertEqual(m_tg[0]["ruleset"], "Telegram.lsr")

        # Verify Douyin incident IP containment
        m_douyin_ip = simulate_hit.match_target("119.147.195.212", rules_by_file)
        self.assertEqual(m_douyin_ip[0]["ruleset"], "China-GeoIP.lsr")

        # Verify China IPv6 containment
        m_v6 = simulate_hit.match_target("240e:97c:2f:1::1", rules_by_file)
        self.assertEqual(m_v6[0]["ruleset"], "China-GeoIP.lsr")

    def test_38_coverage_and_machine_contract(self):
        """Verify strict machine contract across sources.yml, upstream_lock.json, and dist/*.lsr."""
        sources_path = os.path.join(BASE_DIR, "sources.yml")
        with open(sources_path, "r", encoding="utf-8") as f:
            sources_data = yaml.safe_load(f)

        rulesets = sources_data.get("rulesets", {})
        self.assertEqual(len(rulesets), 19, f"Expected 19 rulesets declared in sources.yml, found {len(rulesets)}")

        with open(build.UPSTREAM_LOCK_FILE, "r", encoding="utf-8") as f:
            lock_data = json.load(f)

        # Mandatory upstream mapping contract: assert each service has its essential upstream configured
        mandatory_upstreams = {
            "AI-Overseas": ["OpenAI", "Claude", "Gemini"],
            "YouTube": ["YouTube"],
            "GoogleDrive": ["GoogleDrive"],
            "Google": ["Google"],
            "OneDrive": ["OneDrive"],
            "Telegram": ["Telegram"],
            "Twitter": ["Twitter"],
            "Discord": ["Discord"],
            "Gaming": ["Steam", "Epic"],
            "GitHub": ["GitHub"],
            "TestFlight": ["TestFlight"],
            "Apple-Media": ["AppleTV", "AppleNews"],
            "Apple-Direct": ["AppleMusic", "iCloud", "SystemOTA"],
            "China-Direct": ["WeChat", "Alibaba", "JingDong", "DouYin", "BiliBili"],
            "China-GeoIP": ["ChinaIPs"]
        }

        for rname, expected_srcs in mandatory_upstreams.items():
            self.assertIn(rname, rulesets, f"Mandatory ruleset '{rname}' missing in sources.yml!")
            configured_srcs = [s["name"] for s in rulesets[rname].get("sources", [])]
            for es in expected_srcs:
                self.assertIn(es, configured_srcs, f"Mandatory upstream '{es}' missing from ruleset '{rname}' in sources.yml!")

        # Semantic domain/IP existence contract in generated .lsr files
        semantic_checks = {
            "AI-Overseas.lsr": ["chatgpt.com", "claude.ai", "gemini.google.com"],
            "YouTube.lsr": ["youtube.com", "googlevideo.com", "youtube-ui.l.google.com"],
            "GoogleDrive.lsr": ["drive.google.com"],
            "Google.lsr": ["google.com", "googleusercontent.com"],
            "Telegram.lsr": ["t.me", "91.108.4.0/22"],
            "Twitter.lsr": ["twitter.com", "x.com"],
            "Discord.lsr": ["discord.com"],
            "PayPal.lsr": ["paypal.com", "braintreegateway.com"],
            "Gaming.lsr": ["steampowered.com", "epicgames.com"],
            "GitHub.lsr": ["github.com"],
            "TestFlight.lsr": ["testflight.apple.com"],
            "Apple-Media.lsr": ["tv.apple.com", "apple.news"],
            "Apple-Push.lsr": ["push.apple.com", "17.249.0.0/16"],
            "Apple-Direct.lsr": ["icloud.com", "music.apple.com", "gsa.apple.com", "idmsa.apple.com", "guzzoni.apple.com", "mesu.apple.com"],
            "AI-China-Direct.lsr": ["deepseek.com", "kimi.ai"],
            "China-Direct.lsr": ["weixin.qq.com", "taobao.com", "jd.com", "douyin.com", "douyinpic.com", "bilibili.com"],
            "Lan.lsr": ["10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12"],
            "China-GeoIP.lsr": ["GEOIP,CN", "119.144.0.0/14"]
        }

        for fname, expected_entries in semantic_checks.items():
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as fh:
                f_text = fh.read()
            for entry in expected_entries:
                self.assertIn(entry, f_text, f"Semantic check failed: '{entry}' missing in {fname}!")

        # Verify excluded domains are strictly absent
        exclusions_check = {
            "AI-Overseas.lsr": ["stripe.com", "auth0.com", "sentry.io"],
            "GoogleDrive.lsr": ["www.googleapis.com"],
            "Twitter.lsr": ["grok.com"],
            "Gaming.lsr": ["steamunlocked.net", "helpshift.com"]
        }
        for fname, forbidden_entries in exclusions_check.items():
            fpath = os.path.join(DIST_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as fh:
                f_text = fh.read()
            for f_entry in forbidden_entries:
                self.assertNotIn(f_entry, f_text, f"Exclusion check failed: '{f_entry}' found in {fname}!")

        # Verify policy neutrality across all 19 rulesets
        forbidden_policy_tokens = [",PROXY", ",DIRECT", ",REJECT", ",US", ",HK", ",JP", ",Final", ",All"]
        for rname in rulesets.keys():
            lsr_file = f"{rname}.lsr"
            lsr_path = os.path.join(DIST_DIR, lsr_file)
            self.assertTrue(os.path.isfile(lsr_path), f"Missing .lsr file for ruleset '{rname}'")

            with open(lsr_path, "r", encoding="utf-8") as f:
                content = f.read()
                for token in forbidden_policy_tokens:
                    self.assertNotIn(token, content, f"Policy token '{token}' leaked into {lsr_file}!")

    def test_39_missing_custom_file_does_not_skip_upstream(self):
        """Verify that a ruleset lacking a local_custom file still ingests its upstream sources."""
        test_sources = {
            "metadata": {"max_shrink_ratio": 0.5},
            "rulesets": {
                "MockSet": {
                    "description": "Mock ruleset without local custom file",
                    "sources": [
                        {
                            "name": "MockUpstream",
                            "url": "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Claude/Claude.list",
                            "min_rules": 1
                        }
                    ]
                    # Note: NO local_custom declared here!
                }
            }
        }
        tmp_sources_file = os.path.join(TEST_TMP_DIR, "sources_no_custom.yml")
        with open(tmp_sources_file, "w", encoding="utf-8") as f:
            yaml.dump(test_sources, f)

        tmp_dist = os.path.join(TEST_TMP_DIR, "dist_no_custom")
        os.makedirs(tmp_dist, exist_ok=True)
        tmp_lock = os.path.join(TEST_TMP_DIR, "lock_no_custom.json")

        # Build with offline cache enabled
        build.build_rulesets(
            sources_file=tmp_sources_file,
            dist_dir=tmp_dist,
            lock_file=tmp_lock,
            allow_new_baseline=True,
            offline=True
        )

        mock_lsr = os.path.join(tmp_dist, "MockSet.lsr")
        self.assertTrue(os.path.isfile(mock_lsr), "MockSet.lsr was not created!")
        rule_cnt = build.count_lsr_rules(mock_lsr)
        self.assertGreater(rule_cnt, 0, "Upstream rules were not ingested when local_custom is absent!")

    def test_40_verify_mirrors_fault_injection(self):
        """Verify scripts/verify_mirrors.py fail-stop and exit code under 5 fault-injection scenarios."""
        import verify_mirrors

        class MockResponse:
            def __init__(self, data, status=200):
                self._data = data if isinstance(data, bytes) else data.encode("utf-8")
                self.status = status

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        # 1. Fault injection: Both mirrors down (raises exception)
        def mock_both_down(req, **kwargs):
            raise urllib.error.URLError("Connection refused")

        res_both_down = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_both_down)
        self.assertFalse(res_both_down, "verify_mirrors must fail when both mirrors are down!")

        # 2. Fault injection: Primary down, backup returns 404
        def mock_single_down(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "raw.githubusercontent.com" in url:
                raise urllib.error.URLError("Host down")
            return MockResponse("", status=404)

        res_single_down = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_single_down)
        self.assertFalse(res_single_down, "verify_mirrors must fail when a mirror is down or 404!")

        # 3. Fault injection: Remote manifest missing rulesets
        bad_manifest = json.dumps({"schema_version": "1.0", "rulesets": {}}).encode("utf-8")
        def mock_bad_manifest(req, **kwargs):
            return MockResponse(bad_manifest, status=200)

        res_bad_man = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_bad_manifest)
        self.assertFalse(res_bad_man, "verify_mirrors must fail when manifest ruleset count is invalid!")

        # 4. Fault injection: Ruleset content corrupted (SHA256 mismatch)
        manifest_path = os.path.join(DIST_DIR, "diagnostics", "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            valid_manifest_bytes = f.read().encode("utf-8")

        def mock_corrupted_file(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(valid_manifest_bytes, status=200)
            return MockResponse("CORRUPTED_RULE_CONTENT\nDOMAIN,corrupt.example.com\n", status=200)

        res_corrupt = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_corrupted_file)
        self.assertFalse(res_corrupt, "verify_mirrors must fail when SHA256 does not match!")

        # 5. Fault injection: Diagnostic script or LPX tampered (bad content / SHA mismatch)
        def mock_tampered_diag(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(valid_manifest_bytes, status=200)
            if "loon-rules-diagnostic.js" in url or "LoonRules-Diagnostic.lpx" in url:
                return MockResponse("TAMPERED_DIAGNOSTIC_CONTENT\nconsole.log('malicious');\n", status=200)
            fname = url.split("/")[-1]
            local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_tampered_diag = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_tampered_diag)
        self.assertFalse(res_tampered_diag, "verify_mirrors must fail when diagnostic JS/LPX is tampered!")

        # 6. Fault injection: Remote manifest ruleset metadata tampered (single ruleset SHA256 altered to zeros)
        tampered_man_dict = json.loads(valid_manifest_bytes.decode("utf-8"))
        if "YouTube.lsr" in tampered_man_dict.get("rulesets", {}):
            tampered_man_dict["rulesets"]["YouTube.lsr"]["sha256"] = "0" * 64
        tampered_man_bytes = json.dumps(tampered_man_dict).encode("utf-8")

        def mock_tampered_manifest_ruleset(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(tampered_man_bytes, status=200)
            fname = url.split("/")[-1]
            if "diagnostics/" in url:
                local_path = os.path.join(DIST_DIR, "diagnostics", fname)
            else:
                local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_tampered_man = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_tampered_manifest_ruleset)
        self.assertFalse(res_tampered_man, "verify_mirrors must fail when remote manifest ruleset metadata is tampered!")

        # 7. Fault injection: Remote manifest package signature tampered
        tampered_pkg_dict = json.loads(valid_manifest_bytes.decode("utf-8"))
        tampered_pkg_dict["package_sha256"] = "f" * 64
        tampered_pkg_bytes = json.dumps(tampered_pkg_dict).encode("utf-8")

        def mock_tampered_pkg(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(tampered_pkg_bytes, status=200)
            fname = url.split("/")[-1]
            if "diagnostics/" in url:
                local_path = os.path.join(DIST_DIR, "diagnostics", fname)
            else:
                local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_tampered_pkg = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_tampered_pkg)
        self.assertFalse(res_tampered_pkg, "verify_mirrors must fail when remote manifest package signature is tampered!")

        # 8. Clean pass: Mock local dist files served accurately
        def mock_clean_pass(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(valid_manifest_bytes, status=200)
            fname = url.split("/")[-1]
            if "diagnostics/" in url:
                local_path = os.path.join(DIST_DIR, "diagnostics", fname)
            else:
                local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_clean = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_clean_pass)
        self.assertTrue(res_clean, "verify_mirrors must return True when all mirrors serve matching files!")

        # 9. Fault injection: Remote manifest missing diagnostic_artifacts
        missing_diag_dict = json.loads(valid_manifest_bytes.decode("utf-8"))
        missing_diag_dict.pop("diagnostic_artifacts", None)
        missing_diag_bytes = json.dumps(missing_diag_dict).encode("utf-8")

        def mock_missing_diag(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(missing_diag_bytes, status=200)
            fname = url.split("/")[-1]
            local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_missing_diag = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_missing_diag)
        self.assertFalse(res_missing_diag, "verify_mirrors must fail when remote manifest lacks diagnostic_artifacts!")

        # 10. Fault injection: Remote manifest missing package_sha256
        missing_pkg_dict = json.loads(valid_manifest_bytes.decode("utf-8"))
        missing_pkg_dict.pop("package_sha256", None)
        missing_pkg_bytes = json.dumps(missing_pkg_dict).encode("utf-8")

        def mock_missing_pkg(req, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "manifest.json" in url:
                return MockResponse(missing_pkg_bytes, status=200)
            fname = url.split("/")[-1]
            local_path = os.path.join(DIST_DIR, fname)
            if os.path.isfile(local_path):
                with open(local_path, "rb") as fh:
                    return MockResponse(fh.read(), status=200)
            return MockResponse("", status=404)

        res_missing_pkg = verify_mirrors.verify_mirrors(exit_on_failure=False, urlopen_fn=mock_missing_pkg)
        self.assertFalse(res_missing_pkg, "verify_mirrors must fail when remote manifest lacks package_sha256!")

        # 11. Fault injection: Local manifest pre-release with missing diagnostic_artifacts
        tmp_man_dir = os.path.join(TEST_TMP_DIR, "diag_test")
        os.makedirs(os.path.join(tmp_man_dir, "diagnostics"), exist_ok=True)
        bad_local_man_path = os.path.join(tmp_man_dir, "diagnostics", "manifest.json")
        with open(bad_local_man_path, "w", encoding="utf-8") as f:
            f.write(missing_diag_bytes.decode("utf-8"))
        res_local_missing_diag = verify_mirrors.verify_local_pre_release(
            dist_dir=DIST_DIR, manifest_path=bad_local_man_path, exit_on_failure=False
        )
        self.assertFalse(res_local_missing_diag, "verify_local_pre_release must fail when manifest lacks diagnostic_artifacts!")

        # 12. Fault injection: Local manifest pre-release with zeroed package_sha256
        zero_pkg_dict = json.loads(valid_manifest_bytes.decode("utf-8"))
        zero_pkg_dict["package_sha256"] = "0" * 64
        with open(bad_local_man_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(zero_pkg_dict))
        res_local_zero_pkg = verify_mirrors.verify_local_pre_release(
            dist_dir=DIST_DIR, manifest_path=bad_local_man_path, exit_on_failure=False
        )
        self.assertFalse(res_local_zero_pkg, "verify_local_pre_release must fail when package_sha256 is zeroed/invalid!")

    def test_41_public_fixture_precedence_and_references(self):
        """Verify public 19-ruleset fixture structure, all 19 ruleset references, and 4-stage first-hit order."""
        fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "sample_order_19.fixture")
        self.assertTrue(os.path.isfile(fixture_path), "sample_order_19.fixture must exist in repository!")

        pipeline = simulate_hit.load_lcf_pipeline(fixture_path)
        self.assertIsNotNone(pipeline, f"Failed to load pipeline from {fixture_path}")
        remote_order = pipeline["remote_order"]

        # 1. Verify 19 rulesets are present
        self.assertEqual(len(remote_order), 19, f"Expected 19 rulesets in sample_order_19.fixture, got {len(remote_order)}")
        self.assertIn("Gaming.lsr", remote_order)
        self.assertIn("China-GeoIP.lsr", remote_order)
        self.assertIn("Lan.lsr", remote_order)

        # 2. Strict precedence assertions
        idx_yt = remote_order.index("YouTube.lsr")
        idx_gd = remote_order.index("GoogleDrive.lsr")
        idx_g = remote_order.index("Google.lsr")
        idx_lan = remote_order.index("Lan.lsr")
        idx_geoip = remote_order.index("China-GeoIP.lsr")
        idx_push = remote_order.index("Apple-Push.lsr")

        self.assertLess(idx_yt, idx_g, f"YouTube.lsr (idx {idx_yt}) must precede Google.lsr (idx {idx_g})")
        self.assertLess(idx_gd, idx_g, f"GoogleDrive.lsr (idx {idx_gd}) must precede Google.lsr (idx {idx_g})")
        self.assertLess(idx_lan, idx_geoip, f"Lan.lsr (idx {idx_lan}) must precede China-GeoIP.lsr (idx {idx_geoip})")
        self.assertLess(idx_push, idx_geoip, f"Apple-Push.lsr (idx {idx_push}) must precede China-GeoIP.lsr (idx {idx_geoip})")

        # 3. 4-Stage First-Hit Simulation
        rules_by_file = simulate_hit.load_dist_rules(remote_order)
        local_rules = pipeline.get("local_rules")

        test_targets = {
            "youtube-ui.l.google.com": "YouTube.lsr",
            "drive.google.com": "GoogleDrive.lsr",
            "google.com": "Google.lsr",
            "119.147.195.212": "China-GeoIP.lsr",
            "240e:97c:2f:1::1": "China-GeoIP.lsr",
            "192.168.1.1": "Lan.lsr",
            "17.249.0.5": "Apple-Push.lsr"
        }

        for target, expected_set in test_targets.items():
            matches = simulate_hit.match_target(target, rules_by_file, local_rules=local_rules)
            self.assertTrue(len(matches) > 0, f"Target '{target}' had no match in sample_order_19.fixture")
            self.assertEqual(matches[0]["ruleset"], expected_set,
                             f"Target '{target}' hit {matches[0]['ruleset']}, expected {expected_set}")

    def test_42_verify_private_lcf_acceptance(self):
        """Regression tests for scripts/verify_private_lcf.py: preemption detection, plugin status, and sanitization."""
        import verify_private_lcf
        import io
        from contextlib import redirect_stdout

        fixture_path = os.path.join(BASE_DIR, "tests", "fixtures", "sample_order_19.fixture")
        self.assertTrue(os.path.isfile(fixture_path))

        # 1. Clean public fixture passes completely
        buf = io.StringIO()
        with redirect_stdout(buf):
            ok = verify_private_lcf.verify_private_lcf(fixture_path)
        self.assertTrue(ok, f"sample_order_19.fixture should pass verify_private_lcf! Output:\n{buf.getvalue()}")

        # 2. Local rule preemption: inject DOMAIN,drive.google.com,DIRECT
        with open(fixture_path, "r", encoding="utf-8") as f:
            content = f.read()
        preempt_content = content.replace("[Rule]\n", "[Rule]\nDOMAIN,drive.google.com,DIRECT\n")
        preempt_file = os.path.join(TEST_TMP_DIR, "preempt.fixture")
        with open(preempt_file, "w", encoding="utf-8") as f:
            f.write(preempt_content)

        buf = io.StringIO()
        with redirect_stdout(buf):
            res_preempt = verify_private_lcf.verify_private_lcf(preempt_file)
        self.assertFalse(res_preempt, "Local rule preemption must cause verify_private_lcf to fail!")
        self.assertIn("[ERR_LOCAL_PREEMPTION]", buf.getvalue())
        self.assertIn("drive.google.com", buf.getvalue())

        # 3. Missing file sanitization: no file path leaked, standardized error code
        nonexistent = os.path.join(TEST_TMP_DIR, "very_secret_user_path_nonexistent.lcf")
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_missing = verify_private_lcf.verify_private_lcf(nonexistent)
        self.assertFalse(res_missing)
        out = buf.getvalue()
        self.assertIn("[ERR_FILE_NOT_FOUND]", out)
        self.assertNotIn("very_secret_user_path", out)

        # 4. Active plugin detection: must be UNVERIFIED and cannot grant full pass
        plugin_content = content + "\n[Plugin]\nhttps://example.com/rule_injector.plugin, tag=injector\n"
        plugin_file = os.path.join(TEST_TMP_DIR, "plugin.fixture")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write(plugin_content)

        buf = io.StringIO()
        with redirect_stdout(buf):
            res_plugin = verify_private_lcf.verify_private_lcf(plugin_file)
        self.assertFalse(res_plugin, "verify_private_lcf must not grant full pass when plugins are active!")
        self.assertIn("Plugin Injected Rules: UNVERIFIED", buf.getvalue())
        self.assertIn("UNVERIFIED_PLUGINS", buf.getvalue())

        # 5. Fault injection: Zero remote rules in [Remote Rule] section
        zero_remote_content = re.sub(r'\[Remote Rule\].*', '[Remote Rule]\n# No remote rules here', content, flags=re.DOTALL)
        zero_remote_file = os.path.join(TEST_TMP_DIR, "zero_remote.fixture")
        with open(zero_remote_file, "w", encoding="utf-8") as f:
            f.write(zero_remote_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_zero = verify_private_lcf.verify_private_lcf(zero_remote_file)
        self.assertFalse(res_zero, "verify_private_lcf must fail when zero remote rulesets are present!")
        out_zero = buf.getvalue()
        self.assertIn("[ERR_ZERO_RULESETS]", out_zero)
        self.assertIn("[ERR_MISSING_RULESET]", out_zero)
        self.assertIn("[ERR_RULESET_COUNT]", out_zero)

        # 6. Fault injection: Disabled remote ruleset
        disabled_content = content.replace("tag=YouTube, enabled=true", "tag=YouTube, enabled=false")
        disabled_file = os.path.join(TEST_TMP_DIR, "disabled_ruleset.fixture")
        with open(disabled_file, "w", encoding="utf-8") as f:
            f.write(disabled_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_disabled = verify_private_lcf.verify_private_lcf(disabled_file)
        self.assertFalse(res_disabled, "verify_private_lcf must fail when a remote ruleset is disabled!")
        self.assertIn("[ERR_DISABLED_RULESET]", buf.getvalue())

        # 7. Fault injection: Duplicate remote ruleset
        dup_content = content.replace("tag=YouTube, enabled=true", "tag=YouTube, enabled=true\nhttps://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr, policy=PROXY, tag=YouTube-Dup, enabled=true")
        dup_file = os.path.join(TEST_TMP_DIR, "dup_ruleset.fixture")
        with open(dup_file, "w", encoding="utf-8") as f:
            f.write(dup_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_dup = verify_private_lcf.verify_private_lcf(dup_file)
        self.assertFalse(res_dup, "verify_private_lcf must fail when duplicate remote rulesets exist!")
        self.assertIn("[ERR_DUPLICATE_RULESET]", buf.getvalue())

        # 8. Fault injection: Unauthorized / fake URL host (e.g. example.invalid)
        fake_url_content = content.replace(
            "https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/",
            "https://example.invalid/fake/"
        )
        fake_url_file = os.path.join(TEST_TMP_DIR, "fake_url.fixture")
        with open(fake_url_file, "w", encoding="utf-8") as f:
            f.write(fake_url_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_fake_url = verify_private_lcf.verify_private_lcf(fake_url_file)
        self.assertFalse(res_fake_url, "verify_private_lcf must fail when remote rulesets point to unauthorized URLs!")
        out_fake = buf.getvalue()
        self.assertIn("[ERR_INVALID_URL]", out_fake)
        self.assertNotIn("example.invalid", out_fake, "Unauthorized URL must NOT be echoed in output")

        # 9. Fault injection: Misplaced FINAL in [Remote Rule] section
        wrong_final_content = content.replace("FINAL, PROXY\n", "") + "\nFINAL, PROXY\n"
        wrong_final_file = os.path.join(TEST_TMP_DIR, "wrong_final.fixture")
        with open(wrong_final_file, "w", encoding="utf-8") as f:
            f.write(wrong_final_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_wrong_final = verify_private_lcf.verify_private_lcf(wrong_final_file)
        self.assertFalse(res_wrong_final, "verify_private_lcf must fail when FINAL is misplaced in [Remote Rule]!")
        out_wrong_final = buf.getvalue()
        self.assertIn("[ERR_FINAL_WRONG_SECTION]", out_wrong_final)
        self.assertIn("[ERR_FINAL_MISSING]", out_wrong_final)

        # 10. Fault injection: Duplicate FINAL in [Rule] section
        dup_final_content = content.replace("FINAL, PROXY", "FINAL, PROXY\nFINAL, DIRECT")
        dup_final_file = os.path.join(TEST_TMP_DIR, "dup_final.fixture")
        with open(dup_final_file, "w", encoding="utf-8") as f:
            f.write(dup_final_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_dup_final = verify_private_lcf.verify_private_lcf(dup_final_file)
        self.assertFalse(res_dup_final, "verify_private_lcf must fail when multiple FINAL rules exist!")
        self.assertIn("[ERR_FINAL_DUPLICATE]", buf.getvalue())

        # 11. Fault injection: Rule positioned after FINAL in [Rule] section
        after_final_content = content.replace("FINAL, PROXY", "FINAL, PROXY\nDOMAIN,after-final.example.com,DIRECT")
        after_final_file = os.path.join(TEST_TMP_DIR, "after_final.fixture")
        with open(after_final_file, "w", encoding="utf-8") as f:
            f.write(after_final_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_after_final = verify_private_lcf.verify_private_lcf(after_final_file)
        self.assertFalse(res_after_final, "verify_private_lcf must fail when a rule appears after FINAL in [Rule]!")
        self.assertIn("[ERR_FINAL_NOT_LAST]", buf.getvalue())

        # 12. Unexpected ruleset filename sanitization: name must not leak into output
        unexpected_content = content.replace(
            "[Remote Rule]\n",
            "[Remote Rule]\nhttps://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/SecretRuleset_User123.lsr, policy=PROXY, tag=Secret, enabled=true\n"
        )
        unexpected_file = os.path.join(TEST_TMP_DIR, "unexpected.fixture")
        with open(unexpected_file, "w", encoding="utf-8") as f:
            f.write(unexpected_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_unexpected = verify_private_lcf.verify_private_lcf(unexpected_file)
        self.assertFalse(res_unexpected, "verify_private_lcf must fail when unexpected rulesets exist!")
        out_unexp = buf.getvalue()
        self.assertIn("[ERR_UNEXPECTED_RULESET]", out_unexp)
        self.assertNotIn("SecretRuleset_User123", out_unexp, "Non-standard ruleset name must NOT be leaked")

        # 13. Verified backup mirror (fastly.jsdelivr.net) passes completely
        backup_content = content.replace(
            "https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/",
            "https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/"
        )
        backup_file = os.path.join(TEST_TMP_DIR, "backup_mirror.fixture")
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(backup_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_backup = verify_private_lcf.verify_private_lcf(backup_file)
        self.assertTrue(res_backup, f"fastly.jsdelivr.net backup fixture should pass verify_private_lcf! Output:\n{buf.getvalue()}")

        # 14. Fault injection: URL with query token (?token=fixture_secret)
        query_token_content = content.replace(
            "YouTube.lsr, policy=PROXIES",
            "YouTube.lsr?token=fixture_secret, policy=PROXIES"
        )
        query_token_file = os.path.join(TEST_TMP_DIR, "query_token.fixture")
        with open(query_token_file, "w", encoding="utf-8") as f:
            f.write(query_token_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_query = verify_private_lcf.verify_private_lcf(query_token_file)
        self.assertFalse(res_query, "verify_private_lcf must fail when ruleset URL contains query parameters!")
        out_query = buf.getvalue()
        self.assertIn("[ERR_INVALID_URL]", out_query)
        self.assertNotIn("fixture_secret", out_query, "Secret query parameter must NOT be leaked in output")
        self.assertNotIn("?token=", out_query, "Query string syntax must NOT be leaked in output")

        # 15. Fault injection: URL with userinfo / credentials in netloc
        userinfo_content = backup_content.replace(
            "https://fastly.jsdelivr.net",
            "https://fixture_secret@fastly.jsdelivr.net"
        )
        userinfo_file = os.path.join(TEST_TMP_DIR, "userinfo.fixture")
        with open(userinfo_file, "w", encoding="utf-8") as f:
            f.write(userinfo_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_userinfo = verify_private_lcf.verify_private_lcf(userinfo_file)
        self.assertFalse(res_userinfo, "verify_private_lcf must fail when ruleset URL contains userinfo/credentials!")
        out_userinfo = buf.getvalue()
        self.assertIn("[ERR_INVALID_URL]", out_userinfo)
        self.assertNotIn("fixture_secret", out_userinfo, "Userinfo credentials must NOT be leaked in output")

        # 16. Fault injection: URL with fragment and unexpected port
        frag_content = content.replace(
            "YouTube.lsr, policy=PROXIES",
            "YouTube.lsr#fixture_fragment, policy=PROXIES"
        )
        frag_file = os.path.join(TEST_TMP_DIR, "fragment.fixture")
        with open(frag_file, "w", encoding="utf-8") as f:
            f.write(frag_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_frag = verify_private_lcf.verify_private_lcf(frag_file)
        self.assertFalse(res_frag, "verify_private_lcf must fail when ruleset URL contains a fragment!")
        out_frag = buf.getvalue()
        self.assertIn("[ERR_INVALID_URL]", out_frag)
        self.assertNotIn("fixture_fragment", out_frag)

        port_content = content.replace(
            "https://raw.githubusercontent.com/",
            "https://raw.githubusercontent.com:8443/"
        )
        port_file = os.path.join(TEST_TMP_DIR, "port.fixture")
        with open(port_file, "w", encoding="utf-8") as f:
            f.write(port_content)
        buf = io.StringIO()
        with redirect_stdout(buf):
            res_port = verify_private_lcf.verify_private_lcf(port_file)
        self.assertFalse(res_port, "verify_private_lcf must fail when ruleset URL has non-standard port!")
        out_port = buf.getvalue()
        self.assertIn("[ERR_INVALID_URL]", out_port)
        self.assertNotIn("8443", out_port)

        # 17. Fault injection: Unverified jsDelivr subdomains
        for unverified_host in ["cdn.jsdelivr.net", "testingcf.jsdelivr.net", "evil.jsdelivr.net"]:
            bad_cdn_content = backup_content.replace(
                "https://fastly.jsdelivr.net",
                f"https://{unverified_host}"
            )
            bad_cdn_file = os.path.join(TEST_TMP_DIR, f"bad_cdn_{unverified_host}.fixture")
            with open(bad_cdn_file, "w", encoding="utf-8") as f:
                f.write(bad_cdn_content)
            buf = io.StringIO()
            with redirect_stdout(buf):
                res_bad_cdn = verify_private_lcf.verify_private_lcf(bad_cdn_file)
            self.assertFalse(res_bad_cdn, f"verify_private_lcf must reject unverified host: {unverified_host}")
            out_bad_cdn = buf.getvalue()
            self.assertIn("[ERR_INVALID_URL]", out_bad_cdn)
            self.assertNotIn(unverified_host, out_bad_cdn, f"Host {unverified_host} must NOT be echoed in failure report")

        # 18. Direct unit validation of validate_ruleset_url contract
        self.assertTrue(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertTrue(verify_private_lcf.validate_ruleset_url("https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/feature/expand-rulesets-v2/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@feature/expand-rulesets-v2/dist/YouTube.lsr", "YouTube.lsr")[0])

        # Negative unit tests: query, userinfo, fragment, non-443 port, unverified hosts, wrong branch, wrong filename
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr?token=secret", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://secret@fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://user:pass@raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr#frag", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com:8443/o-ocn/loon-rules/main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://cdn.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://evil.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/YouTube.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr", "YouTube.lsr")[0])
        self.assertFalse(verify_private_lcf.validate_ruleset_url("https://raw.githubusercontent.com/o-ocn/loon-rules/dev/dist/YouTube.lsr", "YouTube.lsr")[0])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_TMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()

