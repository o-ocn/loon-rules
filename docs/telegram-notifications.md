# GitHub Actions Telegram 异常通知与上游审计监控说明

> 📌 **模块定位**：本项目 GitHub Actions 自动化工作流的轻量级 Telegram 异常报警机制。  
> 核心原则：**正常更新完全静默**、**仅在真正异常或持续缓存降级时告警**、**不新增常驻服务、数据库或额外平台**。

---

## 一、工作机制与核心原则

1. **正常运行完全静默**：
   - 生产流水线（`sync-and-build.yml`）构建、测试与镜像检查成功时不发送通知；
   - 影子审计流水线（`shadow-audit.yml`）每日巡检通过、上游正常新鲜抓取时不发送通知；
   - 规则未变动或单次常规缓存降级时不打扰所有者。
2. **告警触发条件**：
   - **流水线执行异常**：被监听工作流状态为 `failure`、`timed_out` 或 `action_required`（如构建中断、冲突门禁阻断、测试失败、镜像发布失败）；
   - **上游巡检持续降级**：影子审计中存在无缓存失败源（立即需关注），或同一源连续两次及以上缓存降级（`consecutive_cache_count >= 2`），触发审计非零退出并告警。
3. **24 小时抑制去重与自动解除**：
   - 同一工作流的同一失败步骤在 24 小时内只告警一次，防止定时任务重复轰炸；
   - 工作流恢复正常成功（`success`）运行后，自动清除该工作流的所有步骤抑制状态；下一次若再发生故障可立即告警。
4. **安全过滤规则（防误报与防伪造）**：
   - 严格核验运行时事件来源，仅限 `o-ocn/loon-rules` 主仓库 `main` 分支上的 `push`、`schedule`、`workflow_dispatch`；
   - 明确排除并静默忽略：主动取消（`cancelled`）、跳过（`skipped`）、中立（`neutral`）、Pull Request、Fork 仓库及其他分支的运行事件。
5. **安全与隐私保证**：
   - 发送前自动脱敏：清除控制字符、剥离 URL query/userinfo、过滤常见 Token/Key 模式；
   - 严格遮罩本次使用的 `TELEGRAM_BOT_TOKEN` 与 `TELEGRAM_CHAT_ID`；
   - 不开启 HTML/Markdown 等 parse_mode，防止注入攻击；
   - 严禁打印响应正文或 Telegram `description`，遇到错误仅记录类别与数值状态码。

---

## 二、手动触发与维护渠道 (workflow_dispatch)

通知工作流（`notify-exceptions.yml`）提供两种显式手动触发用途：

| 用途模式 (`purpose`) | 必填参数 | 说明与行为边界 |
| :--- | :--- | :--- |
| **`test`** | 无需附加说明 | **通道连通性测试**：验证 Bot Token、Chat ID 与网络链路是否正常。不受 24 小时去重抑制限制。 |
| **`decision`** | **`decision_note`**（必填） | **人工决策提示**：由 AI 协助分析后确需所有者介入决断时触发。**`decision_note` 严禁为空**，必须提供简要决策背景。 |

> ⚠️ **注意**：影子审计中的常规候选规则统计（`REVIEW` / `AUTO_PASS` / `BLOCK`）属于旁路观测指标，**严禁自动转换为告警**。

---

## 三、GitHub Secrets 配置与停用方式

### 1. 所需 Secrets 名称
在 GitHub 仓库设置中的 `Settings -> Secrets and variables -> Actions` 配置：
- `TELEGRAM_BOT_TOKEN`：Telegram Bot 的访问令牌（由 `@BotFather` 生成）；
- `TELEGRAM_CHAT_ID`：接收告警消息的 Telegram 用户或群组/频道 ID。

### 2. 停用方式
若需暂时或永久停用通知，可采用以下任一方式：
- **完全停用**：在仓库 Actions 页面直接点击 `notify-exceptions.yml` 并选择 **Disable workflow**；
- **撤销凭据**：在仓库 Secrets 中删除或修改 `TELEGRAM_BOT_TOKEN`，工作流检测到未配置时将安全跳过并记录提示，不影响主干构建与发布。

---

## 四、局限性与免责声明

1. **非实时强保证**：
   - 本机制完全依赖 GitHub Actions Runner 调度与 `actions/cache`；
   - 若遇到 GitHub 平台排队延迟、Actions 基础服务整体中断或网络隔离，告警可能产生延迟，无法实现 100% 绝对实时的故障自报。
2. **手机端体验与网络环境**：
   - Telegram 客户端能否即时弹出通知取决于手机系统后台唤醒策略、APNs 推送通道及当前网络连接情况；本地测试通过不等于所有网络环境下的即时送达保证。
