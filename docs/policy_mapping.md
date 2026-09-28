# 分流规则集与 Loon 本地策略组映射规范

本仓库生成的成品均为符合 Loon 订阅标准的纯规则文件（`.lsr` 格式），存放于 `dist/` 目录。
每份 `.lsr` 保持**策略中立**（不含任何策略组名称、节点或 DIRECT/PROXY/REJECT 动作），由用户在 Loon 中长按规则自由绑定专属策略组或节点。

---

## 1. 规则集与服务范围总表 (共 14 个独立服务分类)

| 规则成品文件名 (`.lsr`) | 服务范围说明 | 隔离与防碰撞准则 | 用户策略推荐示例 (可自由调整) |
| :--- | :--- | :--- | :--- |
| **`AI-Overseas.lsr`** | ChatGPT, Claude, Gemini, Grok, Muse from Meta, Perplexity 等海外 AI | **绝对不含** `googleapis.com`、`google.com`、`x.com`、`twitter.com`、`meta.com`、`facebook.com`、通用验证码及共享 LiveKit 节点。 | `AI` (或自建节点 / 节点自选) |
| **`AI-China-Direct.lsr`** | DeepSeek（大陆 AI 服务） | 严格直连，避免境外代理绕行与不必要封控。 | `DIRECT` |
| **`GoogleDrive.lsr`** | Google Drive 云端硬盘专属域名 | 独立保护大流量；绝对不含 `www.googleapis.com`。 | `HK` (或低倍率大流量节点) |
| **`OneDrive.lsr`** | 微软 OneDrive、SharePoint 服务 | 独立维护，不与微软通用服务杂糅。 | `US` |
| **`Google.lsr`** | 普通 Google 服务、搜索、基础设施 | 已与 Google Drive 及 Gemini 隔离；承载通用 `www.googleapis.com`。 | `US Test` (或通用美区) |
| **`YouTube.lsr`** | YouTube 视频流媒体、图片与 CDN | 独立维护流媒体流量，不被普通 Google 规则带跑。 | `US Test` (或流媒体节点) |
| **`Telegram.lsr`** | Telegram 官方 IP 段与核心域名 | 独立低延迟策略（接管 App 通信流量，非系统 APNs 通道）。 | `Final` (或独立低延迟策略) |
| **`Twitter.lsr`** | Twitter / X 平台主干及图床 | 已完全剔除 `grok.com` 与 `x.ai`，避免与 Grok 冲突。 | `Final` |
| **`Discord.lsr`** | Discord 语音与即时通讯 | 绑定低延迟海外节点。 | `US` |
| **`Apple-Media.lsr`** | Apple TV+, Apple News, Fitness+ | 仅将受美区锁区限制的媒体分流，不影响系统基础服务。 | `US Test` |
| **`TestFlight.lsr`** | Apple TestFlight 内测分发平台 | 独立维护，解决部分网络下无法加载 Beta 应用的问题。 | `US` (或代理节点) |
| **`Apple-Direct.lsr`** | iCloud, CloudKit, App Store, Apple ID, Apple Music, HomeKit, OTA | **稳定基线**。严格直连，绝对禁止把整个 `apple.com` 或 `17.0.0.0/8` 当作代理捷径。 | `DIRECT` |
| **`Apple-Push.lsr`** | APNs 官方最小推送（`push.apple.com` 及官方 CIDR） | **官方最小范围**。默认保持关闭 (`enabled=false`)，单变量测试 APNs。 | `Apple Push` (或 DIRECT) |
| **`China-Direct.lsr`** | 微信、淘宝、天猫、京东、闲鱼、抖音、B站、局域网私网段 | 大陆日常高频 App 直连，保障支付、定位及即时通知稳定。 | `DIRECT` |

---

## 2. 本地 `.lcf` 配置调整示例

### A. 本地 `[Remote Rule]` 规则订阅段示例
将本地原有的第三方杂合规则替换为本仓库专属的独立 `.lsr`：

```ini
[Remote Rule]
# --- AI 服务分类 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr, policy = AI, tag = AI-Overseas, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr, policy = DIRECT, tag = AI-China-Direct, enabled = true

# --- 偏好分流与独立大流量 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr, policy = HK, tag = GoogleDrive, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr, policy = US, tag = OneDrive, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr, policy = US Test, tag = YouTube, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr, policy = US Test, tag = Google, enabled = true

# --- 独立通讯与社交 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr, policy = Final, tag = Telegram, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr, policy = Final, tag = Twitter, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr, policy = US, tag = Discord, enabled = true

# --- Apple 服务（顺序注意：媒体与 TestFlight 置于直连之前优先命中）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media.lsr, policy = US Test, tag = Apple-Media, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/TestFlight.lsr, policy = US, tag = TestFlight, enabled = true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr, policy = DIRECT, tag = Apple-Direct, enabled = true

# --- APNs 权威推送规则（单变量验证，默认建议保持关闭）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push.lsr, policy = Apple Push, tag = Apple-Push, enabled = false

# --- 大陆日常直连与局域网 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr, policy = DIRECT, tag = China-Direct, enabled = true
```

### B. 本地 `[Plugin]` 一键诊断插件配置
在 `.lcf` 的 `[Plugin]` 节中加入本仓库专属的一键诊断插件：

```ini
[Plugin]
# Loon 一键规则与核心服务诊断插件 (策略中立、零隐私上传、手动触发)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/LoonRules-Diagnostic.lpx, tag = LoonRules-Diagnostic
```
