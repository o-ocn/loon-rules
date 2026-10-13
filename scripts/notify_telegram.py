#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/notify_telegram.py
轻量 Telegram 异常通知与去重调度脚本。
特性：
1. 仅依赖 Python 标准库（urllib, json, os, sys, time, re）。
2. 输入脱敏与安全：
   - 剥离不可信输入的不可见控制字符、清除常见凭据模式与 URL userinfo/query；
   - 发送前对本次使用的 bot_token 与 chat_id 进行精确掩码处理；
   - 纯文本发送，不开启 parse_mode，防止 Markdown/HTML 注入与解析崩溃；
   - decision 事件描述为空时必须严格拒绝并退出。
3. 凭据与安全：使用 TELEGRAM_BOT_TOKEN 与 TELEGRAM_CHAT_ID。
   严格禁止输出 Token、Chat ID、完整请求 URL、响应正文或异常堆栈原文；
   仅返回固定的错误类别枚举与状态码。
4. 容错与重试：
   - sendMessage 采用 HTTPS POST，设置 15 秒超时；
   - 支持 HTTP 200/429 的 retry_after 响应解析（上限等待 10s，负值/非法值防护，超过上限立即失败）；
   - 最多 3 次有界重试，总等待时间受限；
   - 严格校验 HTTP 200 与响应 json["ok"] == True。
5. 智能去重与生命周期管理：
   - 24 小时内同类故障仅发送一次（基于按 scope 隔离的状态 JSON 文件）；
   - 恢复正常（success）时静默并解除该 scope 下的抑制；
   - 主动取消/跳过（cancelled, skipped, neutral）保持静默不发告警；
   - 针对真正异常（failure, timed_out, action_required 等）告警；
   - 发送失败不记录为已送达；
   - 人工触发（test/decision）旁路去重，立即发送。
6. 事件安全过滤契约：
   - 提供 validate_event_source 纯函数供外部调用与测试，严格核验 repository, head_repo, branch, event 等白名单。
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MAX_RETRY_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_SUPPRESSION_HOURS = 24
MAX_WAIT_SECONDS_LIMIT = 10

ALERT_WORTHY_CONCLUSIONS = {"failure", "timed_out", "action_required"}
RECOVERY_CONCLUSIONS = {"success"}
IGNORE_CONCLUSIONS = {"cancelled", "skipped", "neutral"}

WATCHED_WORKFLOWS = {"Sync Upstream and Build Loon Rules", "Shadow Audit Scheduled Run"}

def trusted_runtime_event():
    """Validate the actual Actions event before reading notification input."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return True
    try:
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            event = json.load(f)
        run = event.get("workflow_run", {})
        event_name = os.environ.get("GITHUB_EVENT_NAME", "")
        if event_name == "workflow_run" and run.get("name") not in WATCHED_WORKFLOWS:
            return False
        return validate_event_source({
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "event_name": event_name,
            "head_repo": run.get("head_repository", {}).get("full_name", ""),
            "head_branch": run.get("head_branch", ""),
            "trigger_event": run.get("event", ""),
            "ref_name": os.environ.get("GITHUB_REF_NAME", ""),
        })[0]
    except Exception:
        return False

def validate_event_source(event_payload):
    """
    数据驱动核验事件来源是否受信：
    event_payload 包含:
      - repository: 仓库全名
      - event_name: workflow_run 或 workflow_dispatch
      - head_repo: 运行源仓库全名
      - head_branch: 分支
      - trigger_event: push, schedule, workflow_dispatch, pull_request 等
    返回 (is_valid, reason)
    """
    repo = event_payload.get("repository", "")
    if repo != "o-ocn/loon-rules":
        return False, f"Untrusted repository: {repo}"

    event_name = event_payload.get("event_name", "")
    if event_name not in ("workflow_run", "workflow_dispatch"):
        return False, f"Unsupported event name: {event_name}"

    if event_name == "workflow_run":
        head_repo = event_payload.get("head_repo", "")
        if head_repo != "o-ocn/loon-rules":
            return False, f"Untrusted head repository: {head_repo}"

        head_branch = event_payload.get("head_branch", "")
        if head_branch != "main":
            return False, f"Non-main branch: {head_branch}"

        trigger_event = event_payload.get("trigger_event", "")
        if trigger_event not in ("push", "schedule", "workflow_dispatch"):
            return False, f"Untrusted trigger event: {trigger_event}"

    elif event_name == "workflow_dispatch":
        ref_name = event_payload.get("ref_name", "")
        if ref_name != "main":
            return False, f"Non-main dispatch ref: {ref_name}"

    return True, "VALID_TRUSTED_EVENT"

def sanitize_text(text, max_length=1000):
    """
    清洗不可信输入：
    1. 剥离不可打印控制字符（保留换行 \n 与常规空格）。
    2. 清理常见凭据模式 (Token, Key, Bearer, Passwd) 与 URL userinfo/query 参数。
    3. 限制最大长度。
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    
    # 移除非打印字符（保留 \n, \r, \t 及可打印字符）
    cleaned = re.sub(r"[^\x20-\x7E\r\n\t\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]", "", text)
    # 脱敏 URL 中的 query 参数与 userinfo (例如 https://user:pass@host/path?token=xxx)
    cleaned = re.sub(r"https?://([^/@:]+):([^/@:]+)@", "https://***:***@", cleaned)
    cleaned = re.sub(r"([?&](?:token|key|secret|password|chat_id)=)[^&\s]+", r"\1***", cleaned, flags=re.IGNORECASE)
    # 脱敏明显的常见 token/secret 模式 (例如 bot123456:ABC-DEF...)
    cleaned = re.sub(r"(bot[0-9]{8,12}:[a-zA-Z0-9_-]{20,50})", "bot***:***", cleaned)
    cleaned = re.sub(r"(?<![A-Za-z0-9_])(?:bot)?\d{6,16}:[A-Za-z0-9_-]{20,70}", "***", cleaned)
    cleaned = re.sub(r"(?i)\b(?:token|api[_-]?key|secret|password|passwd)\s*[:=]\s*[^\s,;]+", "credential=***", cleaned)
    cleaned = re.sub(r"(?i)\bBearer\s+\S+", "Bearer ***", cleaned)
    
    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + " [TRUNCATED]"
    return cleaned

def mask_sensitive_tokens(message, tokens_to_mask):
    """在发送前将已知 Token 和 ChatID 进行精确掩码"""
    res = message
    for tok in tokens_to_mask:
        if tok and len(tok) >= 4:
            res = res.replace(tok, "***")
    return res

def parse_retry_after(raw_val):
    """安全解析 retry_after 参数，处理负值、非数字与超界值"""
    try:
        val = int(raw_val)
        if val <= 0:
            return 1
        if val > MAX_WAIT_SECONDS_LIMIT:
            return -1  # 超过允许上限，标记拒绝继续重试
        return val
    except Exception:
        return 2

def send_telegram_message(bot_token, chat_id, message_text):
    """
    调用 Telegram Bot API 发送消息。
    严格防泄漏红线：
    1. 绝对不打印 bot_token、chat_id 或请求完整 URL；
    2. 绝对不打印 API 响应正文、响应 description 或异常文本原文；
    3. 仅返回固定的错误类别枚举与数值码。
    """
    if not bot_token or not chat_id:
        print("[!] 错误: 未配置 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID (未接入/未发送)")
        return False, "CREDENTIALS_MISSING"

    # 发送前对文本进行已知凭据精确掩码
    safe_message = mask_sensitive_tokens(message_text, [bot_token, chat_id])

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": safe_message,
        "disable_web_page_preview": True
    }
    encoded_data = json.dumps(payload).encode("utf-8")

    last_error_code = "UNKNOWN"
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        req = urllib.request.Request(
            api_url,
            data=encoded_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Loon-Rules-Alerter/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                status_code = resp.status
                resp_body = resp.read().decode("utf-8", errors="replace")
                try:
                    resp_json = json.loads(resp_body)
                except Exception:
                    resp_json = {}
                
                if status_code == 200 and resp_json.get("ok") is True:
                    print("[✓] Telegram 消息发送成功 (ok=true)")
                    return True, "SUCCESS"
                else:
                    raw_code = resp_json.get("error_code", status_code)
                    err_code = raw_code if type(raw_code) is int and 100 <= raw_code <= 599 else "UNKNOWN"
                    last_error_code = f"API_ERROR_{err_code}"
                    print(f"[!] 尝试 {attempt}/{MAX_RETRY_ATTEMPTS} 响应异常 (错误码: {err_code})")
                    
                    # 检查 HTTP 200 下的 retry_after
                    retry_after_param = resp_json.get("parameters", {}).get("retry_after")
                    if retry_after_param is not None:
                        wait_sec = parse_retry_after(retry_after_param)
                        if wait_sec < 0:
                            print(f"[!] 速率限制等待时间超上限，终止重试。")
                            return False, "RATE_LIMIT_EXCEEDED_MAX_WAIT"
                        time.sleep(wait_sec)
                    else:
                        time.sleep(attempt * 1.0)
        except urllib.error.HTTPError as e:
            last_error_code = f"HTTP_{e.code}"
            print(f"[!] 尝试 {attempt}/{MAX_RETRY_ATTEMPTS} HTTP 状态码: {e.code}")
            if e.code == 429:
                wait_sec = 2
                try:
                    # 读取 e.fp 或 e.read() 获取参数
                    err_body = e.read()
                    if isinstance(err_body, bytes):
                        err_body = err_body.decode("utf-8", errors="replace")
                    err_json = json.loads(err_body)
                    retry_after_param = err_json.get("parameters", {}).get("retry_after")
                    if retry_after_param is not None:
                        wait_sec = parse_retry_after(retry_after_param)
                except Exception:
                    pass
                if wait_sec < 0:
                    print(f"[!] 429 速率限制等待时间超上限，终止重试。")
                    return False, "RATE_LIMIT_EXCEEDED_MAX_WAIT"
                time.sleep(wait_sec)
            else:
                time.sleep(attempt * 1.0)
        except Exception:
            last_error_code = "NETWORK_TRANSPORT_ERROR"
            print(f"[!] 尝试 {attempt}/{MAX_RETRY_ATTEMPTS} 网络传输异常")
            time.sleep(attempt * 1.0)

    return False, f"FAILED_AFTER_RETRIES_{last_error_code}"

class AlertDeduplicator:
    """基于本地状态 JSON 文件的故障去重器"""
    def __init__(self, state_file_path):
        self.state_file_path = state_file_path
        self.state = self._load()

    def _load(self):
        if self.state_file_path and os.path.isfile(self.state_file_path):
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    value = json.load(f)
                    return value if isinstance(value, dict) else {}
            except Exception:
                return {}
        return {}

    def save(self):
        if not self.state_file_path:
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.state_file_path)), exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
                f.write("\n")
            return True
        except Exception:
            return False

    def should_suppress(self, alert_key, suppression_hours=DEFAULT_SUPPRESSION_HOURS):
        """检查是否在抑制期内"""
        entry = self.state.get(alert_key)
        if not isinstance(entry, dict):
            return False
        last_sent_ts = entry.get("last_sent_epoch", 0)
        if type(last_sent_ts) not in (int, float):
            return False
        current_ts = int(time.time())
        hours_elapsed = (current_ts - last_sent_ts) / 3600.0
        if 0 <= hours_elapsed < suppression_hours:
            return True
        return False

    def mark_sent(self, alert_key):
        """记录成功送达时刻"""
        self.state[alert_key] = {
            "last_sent_epoch": int(time.time()),
            "last_sent_iso": datetime.now(timezone.utc).isoformat()
        }

    def clear(self, alert_key):
        """解除故障抑制（恢复正常）"""
        if alert_key in self.state:
            del self.state[alert_key]

    def clear_workflow(self, workflow_name):
        for key in list(self.state):
            if key.startswith(workflow_name + "::"):
                self.clear(key)

def build_alert_message(event_type, context):
    """
    格式化通知纯文本消息。
    不包含日志原文、上游返回正文或敏感凭据。
    """
    workflow_name = sanitize_text(context.get("workflow_name", "Unknown Workflow"), 100)
    failed_step = sanitize_text(context.get("failed_step", ""), 80)
    run_url = sanitize_text(context.get("run_url", ""), 200)
    conclusion = sanitize_text(context.get("conclusion", "failure"), 50)
    custom_desc = sanitize_text(context.get("description", ""), 300)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if event_type == "test":
        return (
            f"🔔 [Loon Rules 通知测试通道]\n"
            f"• 状态: 连通性测试 (通道验证)\n"
            f"• 说明: {custom_desc or 'Telegram 通道工作正常'}\n"
            f"• 时间: {now_str}\n"
            f"• 来源: {run_url or 'Manual Dispatch'}"
        )
    elif event_type == "decision":
        return (
            f"⚠️ [Loon Rules 待办决策提醒]\n"
            f"• 状态: AI 预审完毕，确需所有者关注或决策\n"
            f"• 事项: {custom_desc}\n"
            f"• 时间: {now_str}\n"
            f"• 来源: {run_url or 'Manual Dispatch'}"
        )
    else:  # workflow_failure
        step_line = f"\n• 失败步骤: {failed_step}" if failed_step else ""
        return (
            f"🚨 [Loon Rules 工作流异常告警]\n"
            f"• 流水线: {workflow_name}\n"
            f"• 结果: {conclusion}{step_line}\n"
            f"• 详情: {custom_desc or '流水线执行未完全通过，请核验门禁与健康状态'}\n"
            f"• 时间: {now_str}\n"
            f"• 链接: {run_url}"
        )

def main():
    if not trusted_runtime_event():
        print("[*] Untrusted event ignored; no notification sent.")
        sys.exit(0)
    import argparse
    parser = argparse.ArgumentParser(description="Loon Telegram Alert CLI")
    parser.add_argument("--event-type", required=True, choices=["workflow_run", "test", "decision"],
                        help="事件类型")
    parser.add_argument("--workflow-name", default="")
    parser.add_argument("--failed-step", default="")
    parser.add_argument("--conclusion", default="failure")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--dedup-state-file", default="")
    parser.add_argument("--suppression-hours", type=float, default=24.0)
    args = parser.parse_args()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    # 1. 严格参数校验：decision 事件说明不能为空
    cleaned_desc = sanitize_text(args.description, 300)
    if args.event_type == "decision" and not cleaned_desc:
        print("❌ 错误: decision 待办决策提醒必须提供明确的简短说明，不可为空。")
        sys.exit(1)

    context = {
        "workflow_name": args.workflow_name,
        "failed_step": sanitize_text(args.failed_step, 80),
        "run_url": args.run_url,
        "conclusion": args.conclusion,
        "description": cleaned_desc
    }

    dedup = AlertDeduplicator(args.dedup_state_file)
    # 按工作流名称 + 失败步骤签名组合生成细粒度 alert_key，防止不同步骤故障被简单整流吞掉
    base_wf = sanitize_text(args.workflow_name or "default_workflow", 60)
    step_tag = sanitize_text(args.failed_step or "generic", 40)
    alert_key = f"{base_wf}::{step_tag}"

    conclusion_lower = args.conclusion.lower().strip()

    if args.event_type == "workflow_run":
        # 恢复事件判断：若成功，解除该工作流下所有步骤去重抑制
        if conclusion_lower in RECOVERY_CONCLUSIONS:
            print(f"[*] 工作流 {base_wf} 执行成功，静默并解除该工作流相关抑制。")
            dedup.clear_workflow(base_wf)
            saved = dedup.save()
            if not saved and args.dedup_state_file:
                print("[!] 警告: 去重账本状态保存失败")
                sys.exit(1)
            sys.exit(0)

        # 忽略事件判断：主动取消或跳过不发告警
        if conclusion_lower in IGNORE_CONCLUSIONS:
            print(f"[*] 工作流状态为 {conclusion_lower}，跳过发送。")
            sys.exit(0)

        # 仅对真正异常告警 (failure, timed_out, action_required 等)
        if conclusion_lower not in ALERT_WORTHY_CONCLUSIONS:
            print(f"[*] 状态 {conclusion_lower} 非关键告警类别，跳过发送。")
            sys.exit(0)

        # 检查是否受 24h 去重抑制
        if dedup.should_suppress(alert_key, suppression_hours=args.suppression_hours):
            print(f"[*] 故障 [{alert_key}] 处于 {args.suppression_hours}h 抑制期内，跳过重复通知。")
            sys.exit(0)

    # 2. 构造安全纯文本消息
    message_text = build_alert_message(args.event_type, context)

    # 3. 发送消息
    success, reason = send_telegram_message(bot_token, chat_id, message_text)
    if not success:
        print(f"❌ 消息发送失败: {reason}")
        # 失败不更新已送达状态，且显式退出失败
        sys.exit(1)

    # 4. 成功后更新已送达去重状态（仅常规故障，test/decision 不写入故障去重）
    if args.event_type == "workflow_run":
        dedup.mark_sent(alert_key)
        saved = dedup.save()
        if not saved and args.dedup_state_file:
            print("[!] 警告: 去重状态更新未成功写入文件")
            sys.exit(1)
        print(f"[✓] 故障状态已更新至去重账本: [{alert_key}]")

    print("[✓] 通知流程执行完毕。")
    sys.exit(0)

if __name__ == "__main__":
    main()
