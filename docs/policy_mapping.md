# 分流规则集与 Loon 本地策略组映射规范

本仓库维护符合 Loon 订阅标准的纯规则文件（`.lsr` 格式），发布于 `dist/` 目录。
每份 `.lsr` 保持**策略中立**（不包含任何策略组名称、节点或 DIRECT/PROXY/REJECT 动作），由用户在 Loon 中长按规则自由绑定专属策略组或节点。

---

## 1. 架构三层结构与设计准则

1. **成熟上游负责服务主体**：以 `blackmatrix7/ios_rule_script` (GPL-2.0) 为主要规则源，保障 Gemini、Telegram、Google Drive 等成熟服务规则的全面性，不要求用户长期抓包补域名。`luestr/ShuntRules` 仅用于结构和遗漏核对。
2. **自动断言保护分类边界**：CI/CD 与本地测试套件对 8 大关键分类边界、宽泛父域禁止规则、执行优先级与跨集冲突实施 100% 机器可执行断言。
3. **Custom 仅补有证据的例外与遗漏**：自定义规则必须附带来源/抓包证据、加入原因及日期。当成熟上游官方收录后，构建系统自动提示清理重复 Custom。

---

## 2. 规则集与服务范围总表 (共 14 个独立服务分类)

| 规则成品文件名 (`.lsr`) | 服务范围说明 | 隔离准则与关键边界保护 | 用户策略推荐示例 (可自由调整) |
| :--- | :--- | :--- | :--- |
| **`AI-China-Direct.lsr`** | DeepSeek（大陆 AI 门户及 API） | 严格直连，避免境外节点绕行或服务封控。 | `DIRECT` |
| **`AI-Overseas.lsr`** | ChatGPT, Claude, Gemini, Grok, Muse, Perplexity 等海外 AI | **防碰撞严格约束**：包含官方 Gemini iOS / WebChannel 及 API，绝对排除 `googleapis.com`、`google.com`、`x.com`、`twitter.com`、`facebook.com`、`meta.com` 通用大域；严格区分 `muse.ai` 与 `Muse from Meta`，绝不引入 Meta 社交套件。 | `AI` (自建或专属节点) |
| **`YouTube.lsr`** | YouTube 视频流媒体、图片与 CDN | 独立维护流媒体流量，包含 YouTube CDN IP-CIDR，不被普通 Google 规则带跑。排在 Google 之前。 | `US Test` (或流媒体节点) |
| **`GoogleDrive.lsr`** | Google Drive 云端硬盘专属域名 | 独立保护大流量；绝对不包含共享 API `www.googleapis.com`，排在 Google 之前。 | `HK` (大流量低倍率节点) |
| **`Google.lsr`** | 普通 Google 服务、搜索、基础设施 | 承载通用 `www.googleapis.com` 共享 API。排在 AI、YouTube、Drive 之后。 | `US Test` (通用美区) |
| **`OneDrive.lsr`** | 微软 OneDrive、SharePoint 服务 | 独立维护云存储，不与微软通用服务杂糅。 | `US` |
| **`Telegram.lsr`** | Telegram 官方 IP 段与核心域名 | 独立低延迟策略（接管 App 通信流量，非系统 APNs 通道）。 | `Final` (或独立策略) |
| **`Twitter.lsr`** | Twitter / X 平台主干及图床 | 已完全剔除 `grok.com` 与 `x.ai`，避免与 Grok 冲突。 | `Final` |
| **`Discord.lsr`** | Discord 语音与即时通讯 | 绑定低延迟海外节点。 | `US` |
| **`TestFlight.lsr`** | Apple TestFlight 内测分发平台 | 独立提取为专用 `.lsr`，排在 Apple-Direct 之前，解决直连打不开的问题。 | `US` (或代理节点) |
| **`Apple-Media.lsr`** | Apple TV+, Apple News, Fitness+ | 仅将受美区锁区限制的媒体分流，排在 Apple-Direct 之前。 | `US Test` |
| **`Apple-Push.lsr`** | APNs 官方最小推送（`push.apple.com` 及官方 CIDR） | **官方最小范围**。仅含 APNs 必要 IP 与域名，排在 Apple-Direct 之前；保留 `Apple Push` 策略组。 | `Apple Push` (或 DIRECT) |
| **`Apple-Direct.lsr`** | iCloud, CloudKit, App Store, Apple ID, Apple Music, HomeKit, OTA | **稳定基线**。严格直连，绝对禁止把整个 `apple.com` 或 `17.0.0.0/8` 当作代理捷径。 | `DIRECT` |
| **`China-Direct.lsr`** | 微信、淘宝、天猫、京东、闲鱼、抖音、B站、局域网私网段 | 大陆日常高频 App 直连，保障支付、定位及即时通知稳定。 | `DIRECT` |

---

## 3. Loon 完整执行流水线与匹配顺序 (Full Pipeline Order)

Loon 对流量的分流判定严格遵循以下四层流水线：

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. 本地规则 [Rule] (最高优先级，逐行自顶向下匹配)            │
├─────────────────────────────────────────────────────────────┤
│ 2. 插件规则 [Plugin] 声明的 [Rule] (次高优先级)              │
│    * 本项目诊断插件声明为纯通用工具，注入规则数为 0，零干扰    │
├─────────────────────────────────────────────────────────────┤
│ 3. 远程规则订阅 [Remote Rule] (按列表自顶向下匹配)           │
│    * 精确规则集 (Child) 必须严格排在宽泛父域规则集 (Parent) 之前 │
├─────────────────────────────────────────────────────────────┤
│ 4. 兜底策略 FINAL (最低优先级，未命中任何规则时触发)         │
│    * 命中 FINAL 本身是正常网络行为，绝不代表分流规则失效     │
└─────────────────────────────────────────────────────────────┘
```

### [Remote Rule] 严格依赖排序配置 (已通过测试套件全域验证)

```ini
[Remote Rule]
# 1. 大陆 AI 直连 (避免境外代理绕行)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr, policy = DIRECT, tag = AI-China-Direct, enabled = true

# 2. 海外 AI 核心 (必须排在 Google 与 Twitter 之前)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr, policy = AI, tag = AI-Overseas, enabled = true

# 3. YouTube 流媒体 (必须排在 Google 之前)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr, policy = US Test, tag = YouTube, enabled = true

# 4. Google Drive 云存储 (必须排在 Google 之前)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr, policy = HK, tag = GoogleDrive, enabled = true

# 5. Google 通用服务与基础设施 (承载共享 API www.googleapis.com)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr, policy = US Test, tag = Google, enabled = true

# 6. OneDrive 云存储
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr, policy = US, tag = OneDrive, enabled = true

# 7. Telegram 即时通讯
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr, policy = Final, tag = Telegram, enabled = true

# 8. Twitter / X 社交平台
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr, policy = Final, tag = Twitter, enabled = true

# 9. Discord 语音通讯
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr, policy = US, tag = Discord, enabled = true

# 10. Apple TestFlight (精确内测，必须排在 Apple-Direct 之前)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/TestFlight.lsr, policy = US, tag = TestFlight, enabled = true

# 11. Apple 媒体流媒体 (美区锁区，必须排在 Apple-Direct 之前)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media.lsr, policy = US Test, tag = Apple-Media, enabled = true

# 12. Apple APNs 权威推送 (必须排在 Apple-Direct 之前；保留 Apple Push 策略组)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push.lsr, policy = Apple Push, tag = Apple-Push, enabled = false

# 13. Apple 基础服务基线 (系统级直连基线)
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr, policy = DIRECT, tag = Apple-Direct, enabled = true

# 14. 大陆高频 App 直连与局域网私网段
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr, policy = DIRECT, tag = China-Direct, enabled = true
```

---

## 4. 8 大核心服务分类边界审查与防碰撞准则

| 边界配对 | 核心隔离逻辑 | 宽泛父域禁止规则 | 相对命中顺序 |
| :--- | :--- | :--- | :--- |
| **1. Gemini / 普通 Google** | Gemini 专属端点归入 `AI-Overseas`；允许无害交叉（少量登录 `accounts.google.com` 与静态资源走 Google）。 | 禁止 `google.com`、`googleapis.com` 宽泛父域进入 AI。 | `AI-Overseas` < `Google` |
| **2. Gemini / Google Drive** | Drive 专属域名归入 `GoogleDrive`，Gemini 专属端点归入 `AI-Overseas`。 | 两者互不包含对方专用域名。 | `AI-Overseas` 与 `GoogleDrive` 相互独立 |
| **3. Google Drive / 共享 API** | `www.googleapis.com` 为多服务共享 API（Primuse 串流、Android 等），严禁归入 Drive 或 AI，统一归于 `Google.lsr`。 | 禁止 `www.googleapis.com` 进入 Drive 或 AI；禁止 `googleusercontent.com` 宽泛后缀进入 Drive。 | `GoogleDrive` < `Google` |
| **4. YouTube / 普通 Google** | YouTube 视频与 CDN IP-CIDRs (`172.110.32.0/21`, `216.73.80.0/20`) 专属于 `YouTube`。`deepmind.com` 归于 AI。 | 上游 Google 规则中剔除 YouTube CDN IP 与 `deepmind.com`。 | `YouTube` < `Google` |
| **5. Grok / Twitter/X** | `grok.com`、`x.ai`、`api.x.ai` 归入 `AI-Overseas`；Twitter 平台主干与图床归入 `Twitter`。 | 禁止 `twitter.com`、`x.com` 进入 AI；禁止 `grok.com`、`x.ai` 进入 Twitter。 | `AI-Overseas` < `Twitter` |
| **6. Muse from Meta** | Muse from Meta (App Store ID 6760173601) 是 Meta 于 2026-09-08 官方发布的个人 AI 代理 (Personal AI Agent)，在 iOS、Android 和 `muse.ai` 上运行。专属域名 `muse.ai` 归入 `AI-Overseas`；`meta.ai` / `api.meta.ai` 属于通用 Meta AI 基础设施，因缺少 Muse 专属端点证据不予收录。 | **严禁引入 Meta 全家桶**：禁止 `facebook.com`、`instagram.com`、`meta.com`、`whatsapp.com`、`fbcdn.net` 进入 AI。 | `AI-Overseas` |
| **7. TestFlight / Apple Media / Apple Direct** | `testflight.apple.com` 归于 `TestFlight`；`tv.apple.com`、`apple.news` 归于 `Apple-Media`；基础服务直连归于 `Apple-Direct`。 | 禁止 `apple.com` 宽泛后缀进入 TestFlight 或 Media。 | `TestFlight` < `Apple-Media` < `Apple-Direct` |
| **8. APNs / Apple 基础服务** | `Apple-Push` 仅收录官方最小 `push.apple.com` 及 5 个 IPv4 + 4 个 IPv6 官方推送 CIDR（严格遵循 Apple 官方文档 102266，IPv6 包含权威 `2620:149:a44::/48`）。 | 绝对禁止 `17.0.0.0/8`、`apple.com`、`icloud.com` 宽泛父域进入 Push。 | `Apple-Push` < `Apple-Direct` |

---

## 5. Apple Push 策略组保留与平滑迁移指南

1. **策略组保留**：保留 Loon 中原有的 `Apple Push` 策略组，不新增同类策略组，也不擅自删除。
2. **内联 APNs 规则安全迁移协议**：
   - **步骤 1**：在 `[Remote Rule]` 中配置 `Apple-Push.lsr`，绑定 `Apple Push` 策略组，确认其位置排在 `Apple-Direct.lsr` 之前。
   - **步骤 2**：确认 `Apple Push` 策略组当前有效指向（通常建议选择 DIRECT 直连，或针对特定受限蜂窝网络的专属节点）。
   - **步骤 3**：保持 `enabled = false` 作为备用单变量测试，或开启后验证锁屏推送（微信、Telegram、HomeKit 门铃即时通知）。
   - **步骤 4**：确认远程推送规则与实际推送均正常后，方可移除本地 `[Rule]` 中遗留的重复内联 APNs 规则。

---

## 6. 主备源镜像订阅与冷启动限制说明 (待真机验证)

在首次导入 `.lcf` 或不同网络环境下，分流订阅的可用性与限制说明如下：

1. **主备双源镜像订阅**：
   - **主源 (GitHub Raw)**：
     `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/<规则名>.lsr`
   - **备用源 (Fastly jsDelivr CDN)**：
     `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/<规则名>.lsr`
2. **LRU 缓存与冷启动限制**：
   - 根据 [Loon 官方规则订阅文档](https://nsloon.app/docs/Rule/sub_rule/)，其 LRU 机制主要是**近期匹配结果的查询缓存**，不能简单推断为首次完全离线导入时远程规则依然可用。
   - 用户实际 `.lcf` 的本地 `[Rule]` 主要包含 APNs、个人例外、Apple 基础直连及 `FINAL`，并未内置全量大陆白名单。
   - 因此，“离线首次导入能否平稳启动”必须作为**待真机首次导入验证**项目，依赖本地直连规则及有效的备用镜像源。
3. **构建防缩水与安全兜底**：当上游拉取失败、异常缩水或冲突增加时，构建系统自动熔断，保留上一版发布文件并输出报告。

---

## 7. 零变更构建幂等性

当上游与自定义规则内容均无变动时，构建系统**严格禁止修改发布文件、版本号、时间戳或 `manifest.json`**。
`git status` 将保持干净无差异，彻底杜绝虚假提交（Phantom Commits）。

---

## 8. 日常诊断与排查边界说明

1. **日常运维标准流程**：
   - 打开 Loon -> 运行“规则诊断(快速)” -> 复制简短中文报告（10~15行）-> 粘贴给 ChatGPT 或 Gemini 进行策略评估。
   - 插件语法遵循 Loon 3.5.1+ Generic Script v2 规范 (`generic then script(...) with ...`)，静态规范合规，待 PR 合并后在真机客户端首次导入点击确认。
2. **工具边界声明**：
   - Loon 官方 Script API 未提供直接读取历史请求记录的接口，本项目不承诺也不存在 Loon 原生请求日志导出插件。
   - `scripts/sanitize_log.py` 严格属于离线本地命令行脱敏分析工具，仅在遇到疑难跨分类排查需分析手动导出的 HAR 时使用，严禁向 AI 上传未脱敏原始日志。
