# 分流规则成品与 Loon 本地策略组映射规范

本仓库生成的成品均为符合 Loon 订阅标准的 `.lsr` 文件，存放于 `dist/` 目录。
每份 `.lsr` 独立面向特定策略，避免不同策略规则杂糅。

---

## 1. 规则集与策略组映射总表

| 规则成品文件名 (`.lsr`) | 推荐绑定策略组 | 涵盖核心服务与说明 | 防碰撞与隔离准则 |
| :--- | :--- | :--- | :--- |
| **`AI-Overseas.lsr`** | **`AI`** | ChatGPT, Claude, Gemini, Grok, Muse from Meta, Perplexity 等海外 AI | **绝对不含** `googleapis.com`、`google.com`、`x.com`、`twitter.com`、`meta.com`、`facebook.com`。防大厂社交/普通服务被强行劫持到 AI 节点。 |
| **`AI-China-Direct.lsr`** | **`DIRECT`** | DeepSeek（用户明确要求直连） | 严格直连，避免境外代理绕行与网络封控。 |
| **`GoogleDrive.lsr`** | **`HK`** | Google Drive 云端硬盘专属域名 | 保持现有偏好：Google Drive 走香港节点。已从通用 Google 中完全剔除。 |
| **`OneDrive.lsr`** | **`US`** | 微软 OneDrive、SharePoint 服务 | 保持现有偏好：OneDrive 走美国节点。 |
| **`Google.lsr`** | **`US Test`** | 普通 Google 服务、搜索、基础设施 | 优先走美国节点。已与 Google Drive 及 Gemini 隔离。 |
| **`YouTube.lsr`** | **`US Test`** | YouTube 视频流媒体、图片与 CDN | 绑定美国节点或测速组。 |
| **`Telegram.lsr`** | **`Final`** (或独立) | Telegram 官方 IP 段与核心域名 | 独立低延迟策略。注意：仅接管 App 前台通信流量，不代表系统 APNs 通道。 |
| **`Twitter.lsr`** | **`Final`** | Twitter / X 平台主干及图床 | 已完全剔除 `grok.com` 与 `x.ai`，避免与 Grok 冲突。 |
| **`Discord.lsr`** | **`US`** | Discord 语音与即时通讯 | 绑定低延迟海外节点。 |
| **`Apple-Direct.lsr`** | **`DIRECT`** | iCloud, CloudKit, App Store, Apple ID, Apple Music, HomeKit, OTA | **稳定基线**。严格直连，绝对禁止把整个 `apple.com` 或 `17.0.0.0/8` 当作代理捷径。 |
| **`Apple-Media-US.lsr`** | **`US Test`** | Apple TV+, Apple News, Fitness+, TestFlight | 仅将受美区锁区限制的流媒体与 TestFlight 分流至美区策略。 |
| **`Apple-Push-Experimental.lsr`** | **`Apple Push`** | APNs 专用测试分流（`push.apple.com` 及推送 CIDR） | **实验性规则，默认保持关闭 (`enabled=false`)**。用于验证 APNs 流量命中；与主干 Apple 规则完全解耦。 |
| **`China-Direct.lsr`** | **`DIRECT`** | 微信、淘宝、天猫、京东、闲鱼、抖音、B站、局域网私网段 | 大陆日常高频 App 直连，保障支付、定位及即时通知稳定。 |

---

## 2. 本地 `.lcf` 配置调整示例

### A. 本地 `[Proxy Group]` 补充 `AI` 策略组定义
在本地配置的 `[Proxy Group]` 节中加入 `AI` 策略（将 `[你的VMISS-9929节点名]` 替换为本地节点的真实名称）：

```ini
[Proxy Group]
# 新建 AI 专属策略组，默认优先 VMISS 9929，支持手动切换至 US、HK 等备用节点
AI = select, [你的VMISS-9929节点名], US, HK, JP, DIRECT, img-url = https://raw.githubusercontent.com/Koolson/Qure/master/IconSet/Color/Bot.png
```

### B. 本地 `[Remote Rule]` 规则订阅段示例
将本地原有的第三方杂合规则替换为本仓库专属的独立 `.lsr`：

```ini
[Remote Rule]
# --- AI 规则（严格隔离分类）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr, policy=AI, tag=AI-Overseas, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr, policy=DIRECT, tag=AI-China-Direct, enabled=true

# --- 偏好分流（港美特定策略）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr, policy=HK, tag=GoogleDrive, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr, policy=US, tag=OneDrive, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr, policy=US Test, tag=Google, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr, policy=US Test, tag=YouTube, enabled=true

# --- 独立通讯与社交 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr, policy=Final, tag=Telegram, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr, policy=Final, tag=Twitter, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr, policy=US, tag=Discord, enabled=true

# --- Apple 服务（基线直连与锁区美区）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr, policy=DIRECT, tag=Apple-Direct, enabled=true
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media-US.lsr, policy=US Test, tag=Apple-Media-US, enabled=true

# --- APNs 实验性推送（独立可控，默认关闭）---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push-Experimental.lsr, policy=Apple Push, tag=Apple-Push-Experimental, enabled=false

# --- 大陆直连与内网穿透 ---
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr, policy=DIRECT, tag=China-Direct, enabled=true
```
