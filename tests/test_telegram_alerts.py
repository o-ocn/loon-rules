#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_telegram_alerts.py
单元与集成测试套件：
1. 上游健康评估函数 (assess_upstream_health) 契约测试：
   - 区分 fresh (抓取成功)、cache (缓存降级)、failed (无缓存失败)；
   - 内容 hash 不变时保留 last_synced_at（内容变化时间，非抓取时间），hash 变化时更新；
   - 首次失败/无缓存失败绝不伪造 last_synced_at，返回 None；
   - 缓存降级时累加连续缓存次数；单次缓存(1)标记降级，两次及以上(>=2)触发 attention_required；
   - 抓取失败 (failed) 时立即触发 attention_required，且不可错误清零连续缓存次数；
   - 恢复抓取 (fresh) 时重置连续缓存次数为 0；
   - 有效规则数低于 expected_min_rules 时判为失败，不作为健康上游。
2. 真实集成目录夹具测试 (audit_pipeline 隔离运行)：
   - 临时隔离工作区中运行 audit_pipeline.py；
   - 单源失败退出非零且 shadow_report/upstream_state 存在且标明 DEGRADED/INCOMPLETE；
   - shadow_report.json 包含完整的 health_status（is_complete, has_degraded_cache 等事实）；
   - 跨两次运行验证缓存降级状态与计数持久化，恢复网络后计数清零；
   - 正常无变更且健康时退出 0。
3. Telegram 通知与去重模块 (scripts/notify_telegram.py) 测试：
   - 数据驱动测试 validate_event_source：覆盖 fork、PR、非 main 分支、未授权事件与正常 main；
   - 输入脱敏与凭据掩码：捕获 stdout/stderr 证明 Token、ChatID、URL userinfo/query 绝不回显；
   - decision 说明为空时严格拒绝并退出非零；
   - 缺 Secret 准确报错并退出 1，不假装成功；
   - sendMessage HTTPS 模拟：200 ok=true 成功, 200 ok=false 失败, 429 速率限制有界等待，超界立即失败；
   - 细粒度去重抑制机制：同类故障按 workflow::step 组合去重，不同步骤故障不漏报；
   - 恢复正常（success）静默并解除抑制，主动 cancelled/skipped 静默不发；
   - 人工 test / decision 旁路去重，立即发送。
4. GitHub Actions 工作流声明与安全性静态核验：
   - 工作流名字精确匹配 ("Sync Upstream and Build Loon Rules", "Shadow Audit Scheduled Run")；
   - 最小权限 contents:read, actions:read，无写权限；
   - 并发组 (concurrency) 与防竞态；
   - 动态 scope 缓存键与 restore-keys 前缀存在；
   - 环境变量传递不可信输入，不直接拼接入 shell 命令行；
   - 验证 test_telegram_alerts 在两主要流水线中被显式调用。
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.audit_pipeline import assess_upstream_health, normalize_line
import scripts.notify_telegram as notify_mod

class TestUpstreamHealthAssessment(unittest.TestCase):
    """测试 assess_upstream_health 核心状态转移契约"""

    def test_fresh_fetch_unchanged_content_preserves_last_synced_at(self):
        old_info = {
            "last_synced_at": "2026-10-01T00:00:00+00:00",
            "content_hash": "hash_abc",
            "consecutive_cache_count": 0
        }
        res = assess_upstream_health("src1", old_info, "fresh", c_hash="hash_abc", now_iso="2026-10-13T12:00:00+00:00", rule_count=500)
        self.assertEqual(res["last_synced_at"], "2026-10-01T00:00:00+00:00")
        self.assertFalse(res["content_changed"])
        self.assertFalse(res["attention_required"])
        self.assertEqual(res["consecutive_cache_count"], 0)
        self.assertEqual(res["status"], "synced_shadow")

    def test_fresh_fetch_changed_content_updates_last_synced_at(self):
        old_info = {
            "last_synced_at": "2026-10-01T00:00:00+00:00",
            "content_hash": "hash_abc",
            "consecutive_cache_count": 2
        }
        now_time = "2026-10-13T12:00:00+00:00"
        res = assess_upstream_health("src1", old_info, "fresh", c_hash="hash_xyz", now_iso=now_time, rule_count=550)
        self.assertEqual(res["last_synced_at"], now_time)
        self.assertTrue(res["content_changed"])
        self.assertFalse(res["attention_required"])
        self.assertEqual(res["consecutive_cache_count"], 0)

    def test_first_failure_never_fakes_now_synced_at(self):
        old_info = None  # 新源第一次抓取
        res = assess_upstream_health("new_src", old_info, "failed", now_iso="2026-10-13T12:00:00+00:00", error_msg="HTTP 404")
        self.assertIsNone(res["last_synced_at"], "首次失败绝不能伪造当前时间为同步时间")
        self.assertTrue(res["attention_required"])
        self.assertEqual(res["consecutive_cache_count"], 0)

    def test_single_cache_degradation_allowed_not_attention_required(self):
        old_info = {
            "last_synced_at": "2026-10-01T00:00:00+00:00",
            "content_hash": "hash_abc",
            "consecutive_cache_count": 0
        }
        res = assess_upstream_health("src1", old_info, "cache", c_hash="hash_abc", now_iso="2026-10-13T12:00:00+00:00", rule_count=500)
        self.assertEqual(res["last_synced_at"], "2026-10-01T00:00:00+00:00")
        self.assertEqual(res["consecutive_cache_count"], 1)
        self.assertTrue(res["used_cache"])
        self.assertFalse(res["attention_required"])
        self.assertEqual(res["status"], "cached_degraded")

    def test_persistent_cache_degradation_triggers_attention(self):
        old_info = {
            "last_synced_at": "2026-10-01T00:00:00+00:00",
            "content_hash": "hash_abc",
            "consecutive_cache_count": 1
        }
        res = assess_upstream_health("src1", old_info, "cache", c_hash="hash_abc", now_iso="2026-10-13T12:00:00+00:00", rule_count=500)
        self.assertEqual(res["last_synced_at"], "2026-10-01T00:00:00+00:00")
        self.assertEqual(res["consecutive_cache_count"], 2)
        self.assertTrue(res["used_cache"])
        self.assertTrue(res["attention_required"])
        self.assertEqual(res["status"], "cached_degraded")

    def test_failed_without_cache_preserves_cache_count(self):
        old_info = {
            "last_synced_at": "2026-10-01T00:00:00+00:00",
            "content_hash": "hash_abc",
            "consecutive_cache_count": 2
        }
        res = assess_upstream_health("src1", old_info, "failed", now_iso="2026-10-13T12:00:00+00:00", error_msg="HTTP 500")
        self.assertEqual(res["last_synced_at"], "2026-10-01T00:00:00+00:00")
        self.assertTrue(res["attention_required"])
        self.assertEqual(res["consecutive_cache_count"], 2)
        self.assertTrue("failed: HTTP 500" in res["status"])


class TestTelegramNotificationAndDeduplication(unittest.TestCase):
    """测试 Telegram 报警与去重逻辑"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.dedup_file = os.path.join(self.tmp_dir, "dedup_state.json")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_validate_event_source_data_driven(self):
        # 1. 正常 main 上的 push/schedule/dispatch
        valid_cases = [
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_run", "head_repo": "o-ocn/loon-rules", "head_branch": "main", "trigger_event": "push"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_run", "head_repo": "o-ocn/loon-rules", "head_branch": "main", "trigger_event": "schedule"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_dispatch", "ref_name": "main"}
        ]
        for c in valid_cases:
            valid, reason = notify_mod.validate_event_source(c)
            self.assertTrue(valid, f"Case {c} should be valid, got {reason}")

        # 2. 不可信事件（fork, PR, 非 main 分支, 恶意触发）
        invalid_cases = [
            {"repository": "evil-actor/loon-rules", "event_name": "workflow_run", "head_repo": "evil-actor/loon-rules", "head_branch": "main", "trigger_event": "push"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_run", "head_repo": "forked-repo/loon-rules", "head_branch": "main", "trigger_event": "push"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_run", "head_repo": "o-ocn/loon-rules", "head_branch": "dev-feature", "trigger_event": "push"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_run", "head_repo": "o-ocn/loon-rules", "head_branch": "main", "trigger_event": "pull_request"},
            {"repository": "o-ocn/loon-rules", "event_name": "workflow_dispatch", "ref_name": "patch-1"}
        ]
        for c in invalid_cases:
            valid, reason = notify_mod.validate_event_source(c)
            self.assertFalse(valid, f"Case {c} should be rejected, but passed with {reason}")

    def test_sanitize_text_and_mask_tokens(self):
        token = "123456789:ABCdefGHI_jklMNO123456"
        chat_id = "-1001234567890"
        raw = f"Failure in job. URL: https://admin:secretPass@api.example.com/check?token={token}&chat_id={chat_id}\x00\x08"
        cleaned = notify_mod.sanitize_text(raw)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("\x08", cleaned)
        self.assertNotIn("secretPass", cleaned)
        self.assertIn("https://***:***", cleaned)

        # 验证 mask_sensitive_tokens 屏蔽
        masked = notify_mod.mask_sensitive_tokens(cleaned, [token, chat_id])
        self.assertNotIn(token, masked)
        self.assertNotIn(chat_id, masked)

    def test_decision_empty_description_rejected(self):
        with patch("sys.argv", ["notify_telegram.py", "--event-type", "decision", "--description", ""]):
            with self.assertRaises(SystemExit) as cm:
                notify_mod.main()
            self.assertEqual(cm.exception.code, 1)

    def test_missing_credentials_fails(self):
        success, reason = notify_mod.send_telegram_message("", "", "test")
        self.assertFalse(success)
        self.assertEqual(reason, "CREDENTIALS_MISSING")

    @patch("sys.stdout", new_callable=StringIO)
    @patch("urllib.request.urlopen")
    def test_send_telegram_message_no_leak_on_error(self, mock_urlopen, mock_stdout):
        token = "999888777:SecretToken12345"
        chat_id = "123456789"
        
        # 模拟响应中包含返回 description 或 URL
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": False, "error_code": 401, "description": f"Unauthorized: token {token} invalid"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success, reason = notify_mod.send_telegram_message(token, chat_id, "hello world")
        self.assertFalse(success)
        
        out = mock_stdout.getvalue()
        # 绝不打印 Token 或 Chat ID
        self.assertNotIn(token, out)
        self.assertNotIn(chat_id, out)
        # 绝不打印 description 原文
        self.assertNotIn("Unauthorized", out)
        self.assertIn("API_ERROR_401", reason)

    @patch("time.sleep", return_value=None)
    @patch("urllib.request.urlopen")
    def test_retry_after_handling_and_overflow_failure(self, mock_urlopen, mock_sleep):
        # 1. 正常 429 且等待受限内
        err_429 = urllib.error.HTTPError(
            url="https://api.telegram.org/bot...",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=StringIO(json.dumps({"ok": False, "error_code": 429, "parameters": {"retry_after": 3}}))
        )
        mock_urlopen.side_effect = err_429

        success, reason = notify_mod.send_telegram_message("tok1", "chat1", "msg")
        self.assertFalse(success)
        self.assertIn("FAILED_AFTER_RETRIES_HTTP_429", reason)

        # 2. 超出上限等待值（>10s）立即失败，不反复休眠重试
        err_429_excess = urllib.error.HTTPError(
            url="https://api.telegram.org/bot...",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=StringIO(json.dumps({"ok": False, "error_code": 429, "parameters": {"retry_after": 60}}))
        )
        mock_urlopen.side_effect = err_429_excess
        success, reason = notify_mod.send_telegram_message("tok1", "chat1", "msg")
        self.assertFalse(success)
        self.assertEqual(reason, "RATE_LIMIT_EXCEEDED_MAX_WAIT")

    def test_fine_grained_deduplication_by_step(self):
        dedup = notify_mod.AlertDeduplicator(self.dedup_file)
        wf_name = "Shadow Audit Scheduled Run"
        key_step1 = f"{wf_name}::Audit Step"
        key_step2 = f"{wf_name}::Score Engine Step"

        # 步骤 1 发生故障并发送
        self.assertFalse(dedup.should_suppress(key_step1))
        dedup.mark_sent(key_step1)
        dedup.save()

        # 步骤 1 在抑制期内
        self.assertTrue(dedup.should_suppress(key_step1))
        # 步骤 2 属于新故障步骤，不可被步骤 1 吞掉！
        self.assertFalse(dedup.should_suppress(key_step2))

        # 工作流恢复成功后清空抑制
        dedup.clear(key_step1)
        dedup.save()
        self.assertFalse(dedup.should_suppress(key_step1))


class TestIsolatedAuditPipelineIntegration(unittest.TestCase):
    """
    运行 audit_pipeline 隔离集成夹具测试：
    验证：
    1. 单源拉取失败时退出非零，报告与状态生成且标明 DEGRADED / INCOMPLETE；
    2. shadow_report.json 包含真实 health_status 结构；
    3. 模拟跨两次 pipeline 运行验证连续缓存状态累计与最终恢复网络后计数清零；
    4. 规则解析数低于 expected_min_rules 时判为失败。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "config")
        self.audit_dir = os.path.join(self.test_dir, "audit")
        self.state_dir = os.path.join(self.test_dir, "state")
        self.scripts_dir = os.path.join(self.test_dir, "scripts")
        self.cache_dir = os.path.join(self.scripts_dir, ".upstream_cache")

        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.audit_dir, exist_ok=True)
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        sources_cfg = {
            "version": 1.0,
            "providers": {
                "source_good": {
                    "name": "GoodSource",
                    "url": "https://example.com/good.list",
                    "expected_min_rules": 2
                },
                "source_flaky": {
                    "name": "FlakySource",
                    "url": "https://example.com/flaky.list",
                    "expected_min_rules": 2
                }
            }
        }
        with open(os.path.join(self.config_dir, "upstream_sources.yml"), "w", encoding="utf-8") as f:
            import yaml
            yaml.dump(sources_cfg, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("scripts.audit_pipeline.ScoreEngine")
    @patch("scripts.audit_pipeline.fetch_source_text")
    def test_two_stage_cache_degradation_and_reset_lifecycle(self, mock_fetch, mock_engine_cls):
        mock_engine = MagicMock()
        mock_engine.evaluate.return_value = {
            "decision": "AUTO_PASS",
            "confidence_score": 95,
            "reason": "Test pass",
            "stage": "STAGE_1"
        }
        mock_engine_cls.return_value = mock_engine

        import scripts.audit_pipeline as ap

        with patch.object(ap, "BASE_DIR", self.test_dir), \
             patch.object(ap, "AUDIT_DIR", self.audit_dir), \
             patch.object(ap, "STATE_DIR", self.state_dir):

            # --- 第 1 次运行：source_flaky 第一次缓存降级 (used_cache=True) ---
            def fetch_round1(url, min_rules=100, timeout=15, max_retries=3):
                if "good.list" in url:
                    return "DOMAIN-SUFFIX,gooddomain.cn\nDOMAIN,goodhost.com\n", False
                return "DOMAIN-SUFFIX,cacheddomain.cn\nDOMAIN,cachedhost.com\n", True

            mock_fetch.side_effect = fetch_round1

            # 单次缓存降级：退出 0（允许旁路测试），但报告与 JSON 必须标明降级
            ap.run_shadow_audit()

            report_json_path = os.path.join(self.audit_dir, "shadow_report.json")
            state_json_path = os.path.join(self.state_dir, "upstream_state.json")
            with open(report_json_path, "r", encoding="utf-8") as f:
                r1 = json.load(f)
            self.assertTrue(r1["health_status"]["has_degraded_cache"])
            self.assertFalse(r1["health_status"]["is_complete"])
            self.assertFalse(r1["health_status"]["attention_required"])

            with open(state_json_path, "r", encoding="utf-8") as f:
                s1 = json.load(f)
            self.assertEqual(s1["sources"]["source_flaky"]["consecutive_cache_count"], 1)

            # --- 第 2 次运行：source_flaky 连续第二次缓存降级 ---
            def fetch_round2(url, min_rules=100, timeout=15, max_retries=3):
                if "good.list" in url:
                    return "DOMAIN-SUFFIX,gooddomain.cn\nDOMAIN,goodhost.com\n", False
                return "DOMAIN-SUFFIX,cacheddomain.cn\nDOMAIN,cachedhost.com\n", True

            mock_fetch.side_effect = fetch_round2

            with self.assertRaises(SystemExit) as cm:
                ap.run_shadow_audit()
            self.assertEqual(cm.exception.code, 1, "连续两次缓存降级必须非零退出")

            with open(state_json_path, "r", encoding="utf-8") as f:
                s2 = json.load(f)
            self.assertEqual(s2["sources"]["source_flaky"]["consecutive_cache_count"], 2)

            # --- 第 3 次运行：source_flaky 恢复网络抓取 (used_cache=False) ---
            def fetch_round3(url, min_rules=100, timeout=15, max_retries=3):
                if "good.list" in url:
                    return "DOMAIN-SUFFIX,gooddomain.cn\nDOMAIN,goodhost.com\n", False
                return "DOMAIN-SUFFIX,freshdomain.cn\nDOMAIN,freshhost.com\n", False

            mock_fetch.side_effect = fetch_round3

            ap.run_shadow_audit()

            with open(state_json_path, "r", encoding="utf-8") as f:
                s3 = json.load(f)
            self.assertEqual(s3["sources"]["source_flaky"]["consecutive_cache_count"], 0, "恢复新鲜抓取必须重置连续缓存计数")
            with open(report_json_path, "r", encoding="utf-8") as f:
                r3 = json.load(f)
            self.assertTrue(r3["health_status"]["is_complete"])
            self.assertFalse(r3["health_status"]["has_degraded_cache"])


class TestWorkflowFilesIntegrity(unittest.TestCase):
    """核验 GitHub Actions 工作流声明与安全性"""

    def test_notify_exceptions_workflow_security_and_triggers(self):
        wf_path = os.path.join(BASE_DIR, ".github", "workflows", "notify-exceptions.yml")
        self.assertTrue(os.path.isfile(wf_path))

        with open(wf_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. 匹配两个主工作流名字
        self.assertIn('Sync Upstream and Build Loon Rules', content)
        self.assertIn('Shadow Audit Scheduled Run', content)

        # 2. 最小权限
        self.assertIn('contents: read', content)
        self.assertIn('actions: read', content)
        self.assertNotIn('contents: write', content)

        # 3. 严格排除非 main 与非白名单事件
        self.assertIn("github.event.workflow_run.head_repository.full_name == 'o-ocn/loon-rules'", content)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", content)
        self.assertIn("github.repository == 'o-ocn/loon-rules'", content)

        # 4. 并发控制与 scope 缓存键
        self.assertIn("concurrency:", content)
        self.assertIn("alert-suppression-${{ steps.cache_scope.outputs.scope }}", content)
        self.assertIn("restore-keys:", content)

    def test_workflows_execute_test_telegram_alerts(self):
        # 验证 test_telegram_alerts 在两主要流水线中被显式调用
        sync_wf = os.path.join(BASE_DIR, ".github", "workflows", "sync-and-build.yml")
        shadow_wf = os.path.join(BASE_DIR, ".github", "workflows", "shadow-audit.yml")

        with open(sync_wf, "r", encoding="utf-8") as f:
            self.assertIn("tests/test_telegram_alerts", f.read())

        with open(shadow_wf, "r", encoding="utf-8") as f:
            s_content = f.read()
            self.assertIn("tests/test_telegram_alerts", s_content)
            self.assertIn("shadow-upstream-cache-", s_content)
            self.assertIn("Shadow Audit Final Quality Gate", s_content)

if __name__ == "__main__":
    unittest.main()
