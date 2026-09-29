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

---

## 跨国孪生业务与共享基础设施隔离准则 (Cross-Border Shared Infrastructure Guidelines)

国内互联网企业出海（如字节跳动 TikTok/抖音、腾讯 WeChat/微信、阿里 AliExpress/淘宝）常共享部分底层域名、统一 CDN 或认证网关。在规则维护与 DNS 分流中，必须严格遵循以下原则：

### 1. 业务独占域名与共享基础设施域名严格区分
* **抖音独占域名**：`douyin.com`, `douyincdn.com`, `amemv.com`, `iesdouyin.com`, `doupay.com` 等必须 100% 纳入国内直连与国内极速 DNS（`223.5.5.5`）。
* **TikTok 独占域名**：`tiktok.com`, `tiktokv.com`, `tiktokcdn.com`, `byteoversea.com`, `ibyteimg.com` 等属于海外业务，严禁进入 `China-Direct.lsr` 或 `Loon-China-DNS.lpx`。
* **共享基础设施域名**：`bytedance.com`, `byteimg.com`, `ibytedtos.com`, `snssdk.com`。
  - **当前基准**：当前 19 规则集体系主要保障国内高频 App 秒开与低功耗，故此类共享域名纳入国内直连及国内 DNS 解析。
  - **未来演进红线**：若未来用户需要引入 TikTok 独立规则集，**绝不能将此类共享域名整段迁移至海外代理**（否则会导致国内抖音刷不出视频、评论加载失败或飞书卡死）；必须保持 TikTok 规则集置于顶层（Tier 1）且仅包含 TikTok 独占域名，共享基础设施保留在直连或由精准子域名规则隔离。

### 2. 腾讯生态：微信与 WeChat 分离原则
* **微信国内核心与服务号**：`weixin.qq.com`, `weixin.com`, `qpic.cn` 属于纯国内直连，走国内极速 DNS（`119.29.29.29`）。
* **WeChat 海外业务域名**：`wechat.com` 部分国际端点若涉及海外用户体系，如有分流代理需求应独立设立精准规则，严禁将整个 `qq.com` 或 `tencent.com` 放行给代理。

### 3. GeoIP 不是万能兜底，必须与域名分流+DNS 极速解析联动
* **CDN Geo-DNS 调度漂移陷阱**：
  当客户端使用海外 DoH（如 `dns.google`）解析国内具有全球 Anycast / CDN 架构的域名（如 `air.1688.com` 或 `api.doupay.com`）时，权威 DNS 会感知为境外请求，从而返回境外（如香港 Anycast `155.102.4.44` 或 `139.177.246.206`）IP。
* **GeoIP 无法拦截海外 Anycast IP**：
  `China-GeoIP.lsr` 仅对中国大陆境内 IP（`GEOIP,CN`）生效；一旦国内业务被调度至香港等境外 IP，流量将直接绕过 GeoIP 跌落进 `FINAL` 代理。
* **双重保险铁律**：
  国内关键业务必须同时具备：
  1. **明确的域名规则**（如 `rules/custom/China-Direct.list` 中收录 `1688.com`, `doupay.com`）；
  2. **国内极速 DNS 分流**（在 `plugins/Loon-China-DNS.lpx` 中绑定 `server:223.5.5.5`，确保权威 DNS 始终返回国内边缘节点 IP）。

---

## 自定义规则准入与来源追踪规范 (Custom Rule Admission & Source Tracking Protocol)

项目目前已全面进入工程维护与稳定期。为防止盲目膨胀导致规则泛化与边界模糊，未来任何新增规则必须严格遵循以下准入与注释规范：

### 1. 新规则准入决策四步法
1. **真实日志捕获（First Source）**：以 Loon 客户端的抓包记录或“最近请求”日志为唯一客观事实源，杜绝主观臆测。
2. **三维评估（Three-Dimensional Evaluation）**：
   - 是否为用户日常高频核心业务？
   - 是否采用全球 Anycast / 多国 CDN 架构？
   - 是否存在因海外 DoH 解析导致香港/海外 IP 绕过 GeoIP 跌落 FINAL 的风险？
3. **分流与 DNS 协同决策（Action Decision）**：
   - 纯域名规则：若无 CDN 漂移风险，仅加入对应规则集；
   - 规则 + DNS：若存在 Geo-DNS 跨洋漂移，必须同步追加至 `plugins/Loon-China-DNS.lpx`；
   - 不处理：若为无害内部假域名（如 `blank_xxx`）或低频非核心流量，允许由兜底规则自然处理，杜绝冗余规则堆砌。
4. **单元测试与跨生态防碰撞校验（Verification）**：运行 `python scripts/check_conflicts.py --strict` 及自动化测试套件。

### 2. 自定义规则来源注释格式规范
在 `rules/custom/*.list` 中新增的每一条或每一批自定义规则，必须附带以下格式的元数据注释：
```text
# Target: 目标服务与场景说明
# Source: Loon 真实日志捕获时间（如 2026-09-29）
# Reason: 纳入直连或代理的核心技术原因（如海外 DoH 返回 HK Anycast 节点绕过 GeoIP）
DOMAIN-SUFFIX,example.com
```

---

## 规则层与 DNS 层的两阶段解耦准则 (Two-Stage Resolution & Regional CDN Architecture)

代理分流系统分为两个独立而协同的阶段：
```
域名请求 -> [阶段一: DNS 解析] -> 获得 IP -> [阶段二: 规则匹配] -> 发起连接 (DIRECT / PROXY)
```

### 1. DIRECT 流量亦需考量 DNS 区域调度
* **误区**：“只要规则命中了 DIRECT，速度就一定会快”。
* **现实**：如果 DNS 解析阶段给出了不适合当前网络拓扑的 IP，直连反而会发生跨洋绕远。
  - **真实案例**：App Store 图片与应用静态资源（`apps.mzstatic.com`、`is1-ssl.mzstatic.com`）。
  - 若使用全局境外 DoH（如 `dns.google`）解析，会被调度至苹果美国西海岸机房（`17.253.83.146`）；直连（DIRECT）跨越太平洋连接美国 IP 会遭受跨境公网拥堵与高丢包，导致 711 KB 图片下载耗时长达 118 秒；
  - 若由国内极速 DNS（`223.5.5.5`）分流解析，则就近分配国内电信/联通边缘 CDN 节点（`101.28.130.10`、`121.17.254.3`），毫秒级极速秒开。

### 2. Apple 体系的精细化分层与红线隔离
Apple 生态体系庞大且业务敏感，在分流规则与 DNS 映射中必须严格分层，切忌一刀切：

| 分类 | 典型域名 | 规则层策略 | DNS 层策略 | 设计考量与安全边界 |
|---|---|---|---|---|
| **静态 CDN 资产** | `*.mzstatic.com` | `Apple-Direct.lsr` (DIRECT) | 国内极速 DNS (`223.5.5.5`) | 应用图标、截图预览、静态媒体。数据量大、无敏感认证，就近 CDN 秒开 |
| **商店 API / 元数据** | `apps.apple.com`, `itunes.apple.com` | `Apple-Direct.lsr` (DIRECT) | 默认系统 / DoH 解析 | 承载搜索、跨区账户切换、支付结算，数据量小。不作 DNS 泛绑定以防多区故障 |
| **系统安全与认证** | `appattest.apple.com`, `ocsp.apple.com` | `Apple-Direct.lsr` (DIRECT) | 默认系统 / DoH 解析 | 硬件验签、证书吊销。严禁篡改 DNS |
| **核心系统与 iCloud** | `apple.com`, `icloud.com` | `Apple-Direct.lsr` (DIRECT) | **严禁国内 DNS 泛绑定** | 账户安全红线！`check_conflicts.py` 设立硬门禁拦截 |
| **特种流媒体与测试** | `tv.apple.com`, `testflight.apple.com` | `Apple-Media.lsr`, `TestFlight.lsr` | 对应代理策略 | 区域版权或海外准入，严格走代理出口 |



