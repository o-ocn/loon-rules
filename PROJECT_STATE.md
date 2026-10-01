# PROJECT STATE: Loon Rules 原生分流规则系统

> 📌 **唯一详细事实源**：本文档记录当前项目技术运行状态与工程基线；完整交接协作流程与 Agent 行为规范请严格参阅 [`AGENTS.md`](AGENTS.md)。

---

## 一、项目目标

维护一套以 `blackmatrix7/ios_rule_script` 为主要成熟上游、`o-ocn/loon-rules` 为唯一公开发布入口的 Loon 原生分流规则（`.lsr`）及原生诊断插件（`.lpx`）：
1. **服务分类与出口策略彻底解耦**：规则文件只定义服务流量分类，保持 100% 策略中立（严禁写入节点、地区、DIRECT/PROXY 等出口偏好）；用户在 Loon 客户端按需灵活指派节点策略组。
2. **平替外部不受控规则**：全量替代旧版 15 个外部远端分流规则，消除规则混杂、上游滞后、钓鱼域名及劫持风险。
3. **一致性检查与质量保障**：建立“声明契约、来源配置、构建产物、测试套件、自动化更新”全链路一致性，防止上游更新滞后或规则误伤。
4. **单文件交付与安全隐私**：用户最终只导入一份由 ChatGPT Work 在本地安全装配的唯一私人 `.lcf`；严格保护私人凭证、订阅、节点与密钥，杜绝泄露至公开仓库。
5. **AI-Project-Hub 规范纳管**：本项目已正式纳入 [AI-Project-Hub](https://github.com/o-ocn/AI-Project-Hub)（永久唯一标识：`repo:loon-rules`）全局项目地图纳管，具体交接规范与协作协议统一由 [`AGENTS.md`](AGENTS.md) 维护。

---

## 二、当前状态与基线定型

* **当前分支与提交基线**：`main`（当前 HEAD 提交为 `d91da37`，与远程 `origin/main` 零差异同步保持最新；前序治理提交基线为 `d91da37` / `69555ca` / `c711ffe` / `eb66580` / `b1434f5` / `82382a0`）。
* **GitHub Actions 自动化 CI/CD 与发布机制**：
  * 流水线定义：`.github/workflows/sync-and-build.yml`；
  * 触发机制：`push` to `main`、`pull_request` to `main`、每周日 00:00 UTC（北京时间 08:00）Cron 定时自动同步上游构建、以及 `workflow_dispatch` 手动触发；
  * 5 门严格前置质量门禁（Ubuntu 环境，Python 3.12 + Node.js 20）：
    1. 构建规则与诊断插件：`python scripts/build.py`
    2. 规则完整性与防撞车单元测试：`python -B -m unittest scripts.test_rules`（43/43 单元测试全部通过）
    3. 跨境共享基础设施防泄漏与冲突检测：`python scripts/check_conflicts.py --strict`（PASS）
    4. 原生诊断插件夹具测试：`node --test tests/test_diagnostic.js`（19/19 全部通过）
    5. 本地预发布签名自校验（Fail-Stop Release Barrier）：`python scripts/verify_mirrors.py --pre-release`（严格前置熔断屏障：若规则、哈希或签名存在任何异常，流水线在 git commit / push 前立即终止，远程 main 分支与 CDN 镜像 100% 保持未被触碰）；
  * 自动化提交与发布后 CDN 探测：
    - 非 PR 运行模式下，若 `dist/`、`sources.yml`、`scripts/upstream_lock.json` 产生构建更新，由 `github-actions[bot]` 自动提交、生成 release tag 并推送到远端；
    - 发布后执行 `python scripts/verify_mirrors.py --branch main --soft-cdn` 对 GitHub Raw 主源及 jsDelivr CDN 备用源进行镜像连通与内容一致性巡检；
  * **最新远程 CI 运行事实**：GitHub Actions Run **#49**（ID `36753242952`，针对 commit `d91da37`，push 事件）执行完毕，最终状态 **completed / success**（URL: `https://github.com/o-ocn/loon-rules/actions/runs/36753242952`）。
* **规则集架构定型**：全库定型为 **19 个独立规则集**（共 **21,158 条有效规则**），已全量构建至 `dist/`，主备源（GitHub Raw / jsDelivr CDN）校验通过。
  * `Gaming.lsr` 合并 Steam 与 Epic（65 条规则），消除 404 故障；
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 `ChinaIPs`（19,209 条规则），提供中国 IPv4/IPv6 底层防跌落兜底；
  * 字节跳动直播源站 (`bytegecko.com`)、核心图床 (`bytemaimg.com`) 及调度探针 (`ndcpp.com`) 纳入直连与国内 DNS 分流，彻底根除 120 秒超时卡死；
  * Apple 定位 (`ls.apple.com`, `wps.apple.com`)、天气 (`weatherkit.apple.com`)、设备激活与沙盒认证纳入直连，解决海外代理无谓绕行；
  * 招商银行 (`cmbchina.com`, `cmbimg.com`)、中国银联/云闪付 (`unionpay.com`, `unionpaysecure.com`, `95516.com`)、六大国有行（工建农中交邮）及全国股份制商业银行（平安、中信、光大、浦发、兴业、民生、广发、华夏等）全量金融域名纳入直连与国内极速 DNS（223.5.5.5）分流调度，彻底阻断国内银行与支付流量因上游 USER-AGENT 规则失效而跌落 FINAL 绕行海外专线引发的风控拦截。
* **三层架构体系闭环**：
  1. **规则路由层**：19 个策略中立规则集，首命中优先原则，细分服务排在宽泛服务之前；
  2. **DNS 调度层**：`plugins/Loon-China-DNS.lpx` 分流阿里极速 DNS（223.5.5.5），保障国内大厂及 Apple 静态资源 (`*.mzstatic.com`) 就近调度，解决境外 DoH 引发的跨洋反向卡顿；
  3. **冲突防护层**：`shared_domains.yml` 与 `scripts/check_conflicts.py --strict` 自动化守卫生态边界，严禁海外独占域名泄露至国内规则，严禁将 `apple.com` / `icloud.com` 泛解析至国内 DNS。
* **原生一键诊断插件**：`LoonRules-Diagnostic.lpx` 已就绪，遵循 Loon 3.5.1+ Generic Script v2 规范，支持海外 AI 策略动态嗅探，支持快速与完整双模式，纯本机只读执行，输出 15 行内紧凑中文短报告。
* **大陆应用分流与 DNS 审计矩阵 (`docs/app-audit-matrix.md`)**：正式建立常态化审计矩阵，完整收录 18 类高频应用、金融清算与云存储基建的规则状态、DNS 调度状态、最后验证时间与明确排除边界（红线列表），避免后续 AI 盲目全网扫描或误引入泛域名。

---

## 三、规则订阅清单 (19 规则集)

| 规则集名称 | 规则条数 | 涵盖核心服务说明 | 策略中立保证 |
| :--- | :---: | :--- | :---: |
| **`Apple-Push.lsr`** | 10 | APNs 官方最小推送通道（默认建议关闭） | 100% 策略中立 |
| **`AI-Overseas.lsr`** | 71 | ChatGPT, Claude, Gemini (含 iOS WebChannel), Grok, Muse | 100% 策略中立 |
| **`YouTube.lsr`** | 56 | YouTube 视频流媒体、图片与 CDN（排在 Google 前） | 100% 策略中立 |
| **`GoogleDrive.lsr`** | 6 | Google Drive 云端硬盘专属服务（排在 Google 前） | 100% 策略中立 |
| **`Google.lsr`** | 568 | 普通 Google 服务、搜索与基础设施（含共享 googleapis） | 100% 策略中立 |
| **`OneDrive.lsr`** | 17 | Microsoft OneDrive 与 SharePoint 服务 | 100% 策略中立 |
| **`Telegram.lsr`** | 48 | Telegram 官方 IP 段与核心通信域名 | 100% 策略中立 |
| **`Twitter.lsr`** | 32 | Twitter / X 平台主干（不含 Grok） | 100% 策略中立 |
| **`Discord.lsr`** | 30 | Discord 语音与即时通讯 | 100% 策略中立 |
| **`PayPal.lsr`** | 19 | PayPal 官方支付运营域名（精选官方，剔除仿冒） | 100% 策略中立 |
| **`Gaming.lsr`** | 65 | Steam 游戏平台与 Epic Games 商店 | 100% 策略中立 |
| **`GitHub.lsr`** | 31 | GitHub 开发平台、API 与代码托管 | 100% 策略中立 |
| **`TestFlight.lsr`** | 3 | Apple TestFlight 内测分发平台 | 100% 策略中立 |
| **`Apple-Media.lsr`** | 18 | Apple TV+, Apple News, Fitness+ 锁区媒体 | 100% 策略中立 |
| **`AI-China-Direct.lsr`** | 19 | DeepSeek、Kimi、通义千问、豆包等国内大模型 | 100% 策略中立 |
| **`Apple-Direct.lsr`** | 163 | iCloud, CloudKit, App Store, Apple ID, 定位, 天气, OTA | 100% 策略中立 |
| **`China-Direct.lsr`** | 559 | 微信、淘宝、京东、抖音/字节生态、B站、1688、拼多多、饿了么、美团、快手、小红书、云音乐、银行金融等高频应用 | 100% 策略中立 |
| **`Lan.lsr`** | 9 | RFC 局域网与保留网段直连旁路（排在 GeoIP 之前） | 100% 策略中立 |
| **`China-GeoIP.lsr`** | 19,209 | 中国大陆 IP-CIDR 兜底防线（引入 ChinaIPs IPv4/IPv6） | 100% 策略中立 |

---

## 四、已尝试但已放弃的方案（严禁后续 AI 重复折腾）

1. **放弃方案 1：纯 GeoIP 兜底分流（GeoIP-only 方案）**
   * *背景与尝试*：曾设想仅依靠 `GEOIP,CN` 作为国内流量的兜底直连防线。
   * *失败/放弃原因*：面对国内具有多国 CDN / 全球 Anycast 架构的大厂业务（如 `1688.com`、`doupay.com`），若客户端启用了海外 DoH（如 `dns.google`），解析返回的境外 IP（如香港 Anycast 节点）将直接绕过 `GEOIP,CN` 跌落进 `FINAL` 代理；必须采取“域名规则（`China-Direct.lsr`）+ 国内极速 DNS（`223.5.5.5`）分流 + 物理 CIDR / GeoIP”双重保险闭环，彻底否决并放弃纯 GeoIP 方案。
2. **放弃方案 2：Apple 全域泛化分流与泛解析（Apple 全域泛化方案）**
   * *背景与尝试*：曾探讨将 `apple.com` 或 `17.0.0.0/8` 全部送入海外代理，或在 DNS 插件中将 `apple.com` / `icloud.com` 泛解析至国内 DNS。
   * *失败/放弃原因*：全量代理 Apple 会严重拖慢国内 App Store 应用下载、导致国内 Apple CDN 缓存失效并消耗大量代理流量；而在 DNS 层将 `apple.com`/`icloud.com` 泛解析至国内 DNS 则触犯账户安全红线并引发跨区认证异常。现已彻底放弃全域泛化，确立精细化分层治理（`Apple-Direct.lsr` 直连基础服务、国内极速 DNS 仅就近解析静态 CDN `*.mzstatic.com`、严禁对 `apple.com`/`icloud.com` 泛解析、独立保留 `Apple-Push` 最小化通道与 `Apple-Media` 流媒体）。
3. **放弃方案 3：TikTok / 微信共享域粗暴分流（共享基础设施粗暴一刀切）**
   * *背景与尝试*：曾考虑将跨国出海孪生业务的底层域名一刀切代理以彻底隔离国内外流量。
   * *失败/放弃原因*：字节跳动出海业务（TikTok）与国内抖音共享底层域名与图床（如 `bytedance.com`, `byteimg.com`, `ibytedtos.com`, `snssdk.com`）；腾讯出海 WeChat 与国内微信共享底层通信基础设施。粗暴一刀切全盘走代理会导致国内抖音刷不出视频、评论卡死或国内微信关键功能受损。现已确立：独占业务域名精准走代理，共享底层基础设施严格保留直连与国内 DNS，严禁粗暴一刀切。

---

## 五、验证状态与自动化门禁基线

### 1. 离线全量测试基线（100% PASS）
- **Python 规则单元测试**：`python -B -m unittest scripts.test_rules` **43/43 全部通过**（包含 URL 隐私白名单、主备源自校验、FINAL 段落严格拦截、12 类清单故障注入及 3 类跨生态防碰撞注入）；
- **Node.js 诊断插件测试**：`node --test tests/test_diagnostic.js` **19/19 全部通过**（快速/完整模式、看门狗超时保全、4 态路由判定、策略嗅探）；
- **防撞车与 DNS 禁区检测**：`python scripts/check_conflicts.py --strict` **PASS**（0 未授权跨界碰撞）；
- **预发布镜像签名自校验**：`python scripts/verify_mirrors.py --pre-release` **PASS**（19 规则集正文、诊断元数据与包 SHA256 签名完全吻合）。

### 2. 本地私人配置验收工具基线
- 交付独立本地工具 `scripts/verify_private_lcf.py`，脱敏验收私人 `.lcf`；
- 封闭 URL 隐私漏洞（严格拒绝 query、userinfo、fragment、非标准端口，仅允许 GitHub Raw 与 Fastly jsDelivr）；
- 严格校验 `FINAL` 必须且仅有一条置于 `[Rule]` 末尾；
- 规则名与路径严格脱敏，不回显未知私密规则名（遮罩为 `[NON_STANDARD_RULESET]`）。

---

## 六、关键架构决策

1. **策略绝对中立**：所有 `.lsr` 规则绝不硬编码策略动作（如 DIRECT/PROXY/US 等），由用户在 Loon 客户端自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在宽泛规则（Google）之前，防止泛域名误劫持。
3. **Steam 与 Epic 合并为 `Gaming.lsr`**：消除 404 故障，与用户最新私人配置 19 条远程规则保持零冲突契合。
4. **`China-GeoIP` 引入 `ChinaIPs` 兜底**：引入成熟 GPL-2.0 的 19,209 条 CIDR，解决纯 IP 直连漏入 FINAL 的结构性缺陷。
5. **Apple 基础服务直连、特殊服务独立**：可直连的基础服务集中在 `Apple-Direct.lsr`；`TestFlight`、`Apple-Media`、`Apple-Push` 保持独立。
6. **公开 CI 与本地私密配置彻底隔离**：公开测试严格封闭于仓库公开夹具；私密配置验收由专用本地脱敏脚本运行，公开测试中绝不假装测试私密文件。
7. **交付物哈希全闭环自校验**：规则正文、诊断插件以及清单元数据均有严格 SHA256 校验，工具依据实体内容动态重算 `package_sha256`。
8. **拒绝全局纯海外 DoH 导致的国内 CDN 调度瘫痪**：防范全局纯境外 DoH 导致国内大厂 App 解析出跨洋 IP；采用客户端 `[Host]` 国内 DNS（223.5.5.5）分流解决秒开，外网服务走境外 DoH 杜绝泄漏。
9. **DNS 插件加载优先序准则**：`Loon-China-DNS.lpx` 必须排在 `Prevent_DNS_Leaks.lpx` 之前，确保国内白名单优先就近解析。
10. **用户策略主权原则**：分流规则（`.lsr`）必须 100% 策略中立；私人配置文件（`.lcf`）中用户的策略组指派归属用户主权，AI 严禁擅自改写策略绑定。
11. **跨国孪生业务与共享基础设施隔离**：抖音与 TikTok、微信与 WeChat 的共享底层域名保留在直连，独占域名严格走代理。
12. **三步排查 SOP**：遇分流或速度异常时，严格执行：**第 1 步看规则（DIRECT / PROXY） -> 第 2 步看 DNS（解析所得 IP 是国内还是跨洋） -> 第 3 步看 CDN（就近国内节点还是 Anycast 漂移）**。坚决杜绝无依据盲目加规则。
13. **AI-Project-Hub 纳管与单一事实源定位**：确立本项目为独立 GitHub 仓库（类型 A），本项目自身的 `PROJECT_STATE.md` 为唯一详细事实源，`AI-Project-Hub` 仅做索引寻址；完整交接协作规范与行为约束统一由 [`AGENTS.md`](AGENTS.md) 维护。
14. **商业银行与金融机构分流决策与边界划分**：
    - *为什么添加*：揭示了开源上游依赖已过时的 `USER-AGENT` 规则导致银行请求在现代 iOS（强制 HTTPS + SSL Pinning）下无法读取明文 User-Agent，且后续 `China-GeoIP` 带 `no-resolve` 触发 0ms 穿透至 `FINAL` 走海外专线的重大结构性隐患。因此在 `China-Direct.list` 与 `Loon-China-DNS.lpx` 中显式收录工农中建交邮六大行、股份制银行、招行及银联云闪付的核心域名并绑定国内解析。
    - *为什么排除*：严格排除历史客服跳转域名（如 `8008205555.com/.cn`，非 App 运行时依赖）、关联保险公司（`cignacmb.com`，非核心银行存贷业务）；特别是**严禁收录境外离岸银行**（如香港持牌机构 `cmbwinglungbank.com` 招商永隆银行，其机房位于香港，强行直连会破坏离岸金融与境外分流边界）。
15. **常用国民级应用高危图床/网关收录与海外业务隔离决策**：
    - *为什么添加*：实测证实拼多多（`pddpic.com` 调度至伦敦）、美团（`meituan.net` 调度至丹佛）、小红书（`xhscdn.com` 调度至洛杉矶 Akamai）、快手（`yximgs.com` 调度至美西）在海外 DoH 下会被调度至跨洋 Anycast 节点；由于返回非大陆 IP 无法命中 GeoIP，直接掉入 `FINAL` 走海外代理专线造成商品图与短视频严重卡顿。因此必须“规则直连 + 国内极速 DNS（223.5.5.5）分流”双重绑定实现就近秒开。
    - *精准收缩与排除原则*：
      - **网易系精准收缩**：坚决排除 `netease.com`（实测出海游戏 `global.netease.com` 部署在 GCP 日本机房，直连会污染海外游戏加速），收缩至云音乐专属域名 `music.163.com` 与 `music.126.net`；
      - **百度网盘与企业云隔离**：仅收录百度个人网盘 `baidupcs.com`（保护大流量不爆刷代理流量，海外 TeraBox 独立），坚决排除百度智能云 `bcebos.com`（实测包含新加坡 `sin.bcebos.com`、香港等海外公有云节点）；
      - **快手与海外 Kwai 隔离**：仅收录国内快手主干（`kuaishou.com`, `yximgs.com`, `gifshow.com`, `kuaishoupay.com`），绝不收录海外独立品牌 Kwai（`kwai.com`, `kwaicdn.com`）；
      - **美团与海外 Keeta 隔离**：仅收录国内三快基建（`sankuai.com`, `meituan.net`），不波及出海品牌 Keeta（`keeta.com`）；
      - **腾讯公共图床准入**：收录 `gtimg.com` 解决微信表情、QQ音乐、视频封面遗漏，经核实海外微信使用 `novacdn.com`，海外游戏使用 `levelinfinite.com`，当前验证未发现需要排除的海外业务共享场景。

---

## 七、当前观察期与待办事项

### 1. 1~2 周静默稳定观察期（正式启动・规则库进入冻结观察期）
- **核心原则**：已全面停止理论扫描与规则盲目扩充，转入依托真机日常网络体验的静默验证阶段；
- **观察对象**：
  1. **图片与多媒体流媒体秒开**：拼多多商品大图 (`pddpic`)、美团外卖菜品 (`meituan.net`/`sankuai`)、小红书笔记瀑布流 (`xhscdn`)、快手短视频流 (`yximgs`/`gifshow`)、App Store 截图与预览 (`mzstatic`)；
  2. **金融交易与风控防拦截**：招行掌上生活信用卡饭票与活动 (`cmbimg`)、云闪付与银联支付 (`95516`/`unionpay`)、支付宝小程序账单 (`alipayobjects`)；
  3. **音视频与云存储传输**：网易云音乐无损起播与专辑图 (`music.163`/`music.126`)、B站高清视频、百度网盘国内直连下载 (`baidupcs`)；
  4. **系统核心协同**：HomeKit 室内摄像头即时推流与 CloudKit 同步、Telegram 蜂窝锁屏即时推送；
  5. **自动化巡检**：每周日 GitHub Actions 自动定时同步上游 rules 与镜像校验的稳定性。
- **结束条件**：
  - 连续日常使用 1~2 周无超时、无误伤、无漂移报错，且自动化 CI 巡航稳定，即可正式解除观察期，冻结日常手动干预。

### 2. 待办事项
- [ ] **日常真机追踪记录**：依托 [`docs/real-device-validation.md`](docs/real-device-validation.md) 追踪记录日常使用反馈，严格执行“排查三步法（看规则 -> 看 DNS -> 看业务边界）”，先入矩阵登记再做决策；
- [ ] **唯一私人配置装配**：由 ChatGPT Work 基于最新手机导出配置在本地完成最终规则顺序对齐并装配为唯一正式 `.lcf` 文件供用户导入；
- [ ] **Phase 0 旁路影子数据观察与低频告警集成**：持续评估 `audit/shadow_report.md` 中的 417 条 REVIEW 候选规则，校准上游多源加权模型，为进入 Phase 1（重构 build.py 与接入正式 quarantine）奠定实测数据基线。

---

## 八、已知风险、真机边界与未验证项 (UNVERIFIED)

1. **真机环境边界（必须真机验证，不可凭单测断言）**：
   - 诊断探针与离线单测无法完全代替真实真机上的 APNs TCP 5223 绕行、HomeKit 硬件推流或 Apple Watch 独立蜂窝测试。
2. **插件未验证标记 (UNVERIFIED)**：
   - 当前用户环境存在多个第三方插件，验收工具只标记其规则注入状态为 `UNVERIFIED`，不给出虚假全通，亦不强制要求全部抓包。
3. **系统全局推送共用通道风险（全或无）**：
   - 代理 APNs 意味着整台 iPhone 的所有应用推送（含微信）握手连接均会走所选代理节点；若节点不稳定或断流可能引发通知延迟。
4. **蜂窝网络 IPv6 绕过风险**：
   - 在中国大陆运营商 5G/4G 双栈网络下，若未妥善分流 IPv6，系统底层长连接可能逃逸至物理网卡直连国内。
5. **节点长连接保活心跳（Keep-Alive）**：
   - 部分机场对空闲 TCP 设置超时断开，可能导致 APNs 5223 长连接频繁重建引起通知延迟。

---

## 九、不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致全新克隆下测试失败。
2. **不要把“上游已有”当作“本仓库已同步”**：必须在 `sources.yml` 明确声明并经构建流水线集成。
3. **不要用单条 `GEOIP,CN` 替代具体的 CIDR 分流**：纯 IP 直连请求需要具体 IP-CIDR 规则兜底，防止落入 FINAL。
4. **单元测试不要依赖动态外网连接或本地机器残留缓存**：必须将离线受控夹具入库或构造完整 mock，确保任何干净克隆 100% 离线通过。
5. **严禁向 `.lsr` 写入策略名**：必须保持 100% 策略中立。
6. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则。
7. **Windows NTFS 下严禁使用 tempfile.mkdtemp 充当发布产物暂存目录**：`mkdtemp` 默认设置私有 DACL 阻断继承；必须使用标准目录创建并确保 ACL 继承。
8. **公开 CI 测试严禁引用本地私密路径**：公开测试只测公开夹具，私密测试使用专用工具显式传参并强制校验存在性。
9. **私人配置验收不能仅比对远程规则顺序**：必须运行完整多阶段仿真拦截本地高优先级抢占，且对第三方插件规则标记未验证，禁止给出虚假全通结论。
10. **私人配置验收器严禁在零引用时静默回退默认规则**：必须真实反映文件内容，缺规则、禁用规则或重复引用必须显式报错拦截。
11. **远程规则 URL 必须强校验主机与路径白名单**：仅允许官方仓库与合法发布分支，且报错时严禁回显私有 URL 或私密规则名。
12. **Loon 原生配置中 FINAL 必须严格且仅有一条位于 [Rule] 段末尾**：严禁将 FINAL 置于 [Remote Rule] 或其他段落，也严禁在 FINAL 后继续声明规则。
13. **发布 URL 必须严格拒绝 query、userinfo、fragment 和非预期端口**：防止用户或插件误将包含 token 或账号信息的私有订阅地址带入远程规则，且 jsDelivr 备用源必须精确到已验收的主机（`fastly.jsdelivr.net`），禁止使用通配子域名。
14. **切忌盲目追求 BrowserLeaks 纯净而全局只开境外 DoH 并禁用系统 DNS**：该极端配置会导致所有国内主流 App 的 CDN 域名向境外 DNS 查询，直连发生跨洋拉取引发断崖式卡顿；必须在客户端采用 `[Host]` 国内 DNS（223.5.5.5）分流实现就近秒开。
15. **不要把香港或境外中资商业银行（如招商永隆银行 `cmbwinglungbank.com`）混入国内直连**：其核心机房与业务在香港本地，强行国内直连会导致离岸金融与代理策略混乱。
16. **严禁将公有云通用对象存储（如百度云 `bcebos.com`）或跨国游戏集团泛域名（如网易 `netease.com`）粗暴放入国内直连**：它们往往包含新加坡、日本 GCP 等跨国出海节点，必须精准限定在消费级 App 的专属子域（如 `baidupcs.com`、`music.163.com`）。
17. **Hard Pass 严禁凭大厂企业名称单方免检放行**：必须满足 `verified: true` 且在 `history/decisions.jsonl` 中存在显式审计放行凭证，未经验证的全新大厂泛域名必须走评分或隔离待审；
18. **第一阶段禁止自动放行任何 IP-CIDR/IP-CIDR6 规则入直连**：上游爬取的 IP-CIDR 统一由 Type Filter 拦截，仅允许人工在 `rules/custom/` 中按需维护，防止跨国 Anycast/海外云公网 IP 逃逸。

---

## 十、环境与更新记录

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 20+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **版本控制**：Git（GitHub 远程公开仓库 `o-ocn/loon-rules`，分支 `main`）
* **最后更新**：2026-10-01
  * **Phase 0 旁路影子审计体系正式建立**：
    - 新增全局风控配置 `config/risk_policy.yml` 与独立静态上游数据库 `config/upstream_sources.yml`；
    - 新增永久审计决策历史账本 `history/decisions.jsonl`（包含 `scope`, `recheck_interval_days`, `validation_source`）；
    - 新增动态同步状态账本 `state/upstream_state.json` 与固定回归测试夹具 `tests/fixtures/audit_cases.json`；
    - 开发置信度与三态分流引擎 `scripts/score_engine.py` 及回归单测 `scripts/test_score_engine.py`（4/4 单测全部 PASS，成功守卫 Hard Pass、Hard Block 及类型过滤边界）；
    - 开发并执行 Phase 0 旁路影子流水线 `scripts/audit_pipeline.py`，产出 `audit/shadow_report.json` 与 `audit/shadow_report.md`；
  * **旁路运行客观事实验证**：
    - 聚合上游（blackmatrix7 + Loyalsoldier + ACL4SSR）去重规则总量：111,461 条；
    - 生产已有覆盖覆盖数：348 条；
    - 新增候选差集：111,113 条（拟放行 34 条，拟隔离待审 417 条，拟彻底阻断 110,662 条）；
    - **自动化运维率 (Automation Rate)** 达到 **99.62%**；
    - 生产 `dist/` 产物与 `build.py` **100% 保持零改动**，全量 43 项 Python 规则测试、19 项 Node.js 诊断测试与冲突检测全部绿灯通过。
