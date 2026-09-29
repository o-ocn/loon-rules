# Loon 分流规则与配置架构设计规范 (RULE_DESIGN.md)

本项目旨在为 Loon 客户端维护一套高度纯净、策略中立、零隐私泄露、完全符合原生语法的分流规则集（`.lsr`）与配置交付规范。

---

## 核心设计铁律：规则与策略绝对分离

> **“规则就是规则，策略就是策略，两者彻底解耦。”**

### 1. 规则集（.lsr）保持 100% 策略中立
* 公开发布的所有 19 个 `.lsr` 分流规则文件**严禁硬编码任何策略动作**（如 `DIRECT`, `PROXY`, `REJECT`, `US`, `HK`, `Final` 等）。
* 规则文件仅负责客观界定网络服务边界（例如：哪些域名/IP 属于海外 AI、哪些属于 Google、哪些属于国内直连、哪些属于 Apple 基础服务）。

### 2. 策略绑定属于用户的绝对主权
* 用户在客户端根据自己的机场节点、网络环境及 VPS 线路，自由决定每个规则集走什么策略组（例如：用户可将 `AI-Overseas` 绑定为自建 VPS 策略组 `All`，将 `Telegram` 绑定为 `Final` 或 `HK`）。
* **AI / Agent 严禁擅自篡改用户的策略组绑定**：
  * 在装配、校验或修复用户的私人配置文件（`.lcf`）时，**绝不允许擅自将用户的策略名称替换为 AI 以为的名称**（例如：严禁未经用户明确授权，私自将用户的 `policy=All` 改为 `policy=US`）。
  * 必须 100% 保留用户原配置中对每个规则集所指派的策略名称。

### 3. AI / Agent 的职责边界
AI 协作接手本项目时，只允许在以下范围内工作：
1. **规则内容维护**：补齐漏网域名/IP、剔除死链与钓鱼域名、保持上游同步与反污染。
2. **顺序与优先级保障**：严格确保 19 个规则集在客户端的排列顺序满足 Loon 首个命中（First Match Wins）语义（如 `YouTube < Google`，`Lan < China-GeoIP`）。
3. **段落与语法合规**：确保原生段落结构合法、`FINAL` 规则唯一且严格置于 `[Rule]` 末尾、清除本地冗余冲突规则。
4. **隐私与安全防线**：杜绝向公开仓库泄露任何 Token、节点、订阅地址或私密文件；严禁生成任何垃圾文件存放在 C 盘或桌面。

---

## 19 规则集标准体系与依赖层级

所有规则必须按照“从特殊到宽泛、从细分到兜底”的顺序排列：

```
[Remote Rule] 正序（自上而下匹配，首次命中即停止）：
01. Apple-Push.lsr       (Apple 推送服务，高优先级)
02. AI-Overseas.lsr      (海外主流 AI，策略由用户指定，如 All / US)
03. YouTube.lsr          (YouTube 细分服务，必须在 Google 之前)
04. GoogleDrive.lsr      (GoogleDrive 大流量存储，必须在 Google 之前)
05. Google.lsr           (Google 宽泛通用服务)
06. OneDrive.lsr         (微软 OneDrive 存储)
07. Telegram.lsr         (Telegram 社交通讯)
08. Twitter.lsr          (Twitter / X 社交平台)
09. Discord.lsr          (Discord 语音与社群)
10. PayPal.lsr           (PayPal 官方支付服务)
11. Gaming.lsr           (Steam 与 Epic 游戏平台)
12. GitHub.lsr           (GitHub 开发平台)
13. TestFlight.lsr       (Apple 官方测试平台)
14. Apple-Media.lsr      (Apple TV+ / Music / 媒体流媒体)
15. AI-China-Direct.lsr  (国内 AI 平台，DIRECT 直连)
16. Apple-Direct.lsr     (Apple 基础服务/OTA/OCSP/NTP，DIRECT 直连)
17. China-Direct.lsr     (国内主流常用 App 与核心 CDN，DIRECT 直连)
18. Lan.lsr              (局域网私网段 RFC1918/RFC6598，必须在 China-GeoIP 之前，DIRECT 直连)
19. China-GeoIP.lsr      (中国大陆 IPv4/IPv6 CIDR 兜底安全网，DIRECT 直连)
```

---

## 脚本与插件运作特性特别说明

1. **`[Script]` 与 `[Plugin]` 的呈现差异**：
   - 凡在配置文件 `[Script]` 段声明的 `generic` 脚本，会直接呈现在 Loon 的“本地脚本”管理页面中，提供直观的运行按钮，零后台耗电与能耗。
   - 凡通过 `[Plugin]` 插件引入的脚本，属于插件内嵌组件，仅在“插件详情”和“脚本任务”大厅中呈现。
2. **`$httpClient` 不经过 TUN 规则分流的底层限制**：
   - Loon 脚本引擎中 `$httpClient` 发起的网络请求，属于 Loon 内部发起的 HTTP 探测，**不会自动走 TUN 层的 `[Remote Rule]` 分流规则**。
   - 若请求未显式指定 `node` 参数，Loon 会直接回落至默认代理（`FINAL`）或本地网络；因此脚本内部探测海外服务的结果，反映的是默认代理通达性，不代表用户在指定策略组（如 `All` 挂载 VPS）下的实际应用通达性。
