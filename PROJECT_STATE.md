# PROJECT STATE: Loon Rules 原生分流规则系统

> 📌 **唯一详细事实源**：本文档记录当前项目技术运行状态与工程基线；完整交接协作流程与 Agent 行为规范请严格参阅 [`AGENTS.md`](AGENTS.md)。

---

## 一、项目目标

维护一套以 `blackmatrix7/ios_rule_script` 为主要成熟上游、`o-ocn/loon-rules` 为唯一公开发布入口的 Loon 原生分流规则（`.lsr`）及原生诊断插件（`.lpx`）：
1. **服务分类与出口策略彻底解耦**：规则文件只定义服务流量分类，保持 100% 策略中立（严禁写入节点、地区、DIRECT/PROXY 等出口偏好）；用户在 Loon 客户端按需灵活指派节点策略组。
2. **平替外部不受控规则**：全量替代旧版 15 个外部远端分流规则，消除规则混杂、上游滞后、钓鱼域名及劫持风险。
3. **一致性检查与质量保障**：建立“声明契约、来源配置、构建产物、测试套件、自动化更新”全链路一致性，防止上游更新滞后或规则误伤。
4. **单文件交付与安全隐私**：用户最终只导入一份由 ChatGPT Work 在本地安全装配的唯一私人 `.lcf`；严格保护私人凭证、订阅、节点与密钥，杜绝泄露至公开仓库。
5. **AI-Project-Hub 规范纳管**：本项目已正式纳入 [AI-Project-Hub](https://github.com/o-ocn/AI-Project-Hub)（永久唯一标识：`repo:loon-rules`）全局项目地图纳管，具体交接规范与协作协议统一由 [`AGENTS.md`](AGENTS.md) 维护，自动发现与同步入口由 [`AI_HUB_SYNC.md`](AI_HUB_SYNC.md) 提供。

---

## 二、当前状态与基线定型

* **2026-10-09 国内底座静态扩大（China-Baseline.list）已发布，工程及CI通过，手机未验**：恢复起点 `0fd85e6012a39299419c462af069b4bfe9c7df16`。依据所有者减少人工维护的授权，从固定 Commit URL 上游 `blackmatrix7/ios_rule_script`（SHA `036c097eb26c6a52c4f04ebcb6633043cb942669`）`China_Domain.list`（3,689 裸域）实施保守精细过滤。严格排除既有直连覆盖（362）、含 cdn/cloud/dns/global/international/intl 歧义资产（293）、境外商业/学术/跨国机构（255）、红线公有云/多租户/DDNS（108）、精确主机隔离冲突（49，含 gaode.com）、未审查海外主机/VPS/工具（11）、v2fly 正则命中（4，u17i.com, u17t.com, uuu9.com, z28j.com）、海外双向碰撞（6），并暂缓已识别共享平台基础设施（2，tencentyun.com 与 aliyun-iot-share.com 标记 SHARED_PLATFORM_AMBIGUITY 并加入守卫），合计排除 1,090 条；保留 2,599 条 100% 策略中立规则落入静态层 `rules/custom/China-Baseline.list`（正文 SHA256 `8b643f2463199d2e1b7d8fbf53d44ee02f324e94747eec29df5fab747f8d2b72`，由 `shared_domains.yml` 与 `scripts/check_conflicts.py --strict` 强校验保护）。暂缓已识别的共享基础设施和歧义家族；静态 hash 保护未经复审的批次更新；未证明全球域名穷举或全部业务归属。
* **真实编译构建净增长**：China-Direct.lsr 经编译器子域合并去重后从 680 条增至 3,239 条（净增 +2,559 条，40 条被子域剪枝去重）；全库 19 规则集总规则数从 21,323 条增至 23,882 条（净增 +2,559 条）；其余 18 个规则集语义正文 100% 保持不变；DNS Host 120 条保持不变；决策账本 139 条历史字节保持不变；构建内容签名从 `02c5ceb22c3a` 变为 `cc70392cee8a`。
* **离线全量门禁 100% PASS**：Python 规则单元测试 52/52 PASS（test_52 覆盖编译后 7 个新增服务正向首命中、u17i/u17t/uuu9/z28j及probe子域负向隔离、tencentyun/aliyun-iot-share暂缓负例保持FINAL、真实strict对windows.net/hotmail.com/trip.com/tencentyun.com/aliyun-iot-share.com等变异夹具在hash/count完全一致时仍因边界拒绝以及安全夹具通过）；Node 诊断测试 19/19 PASS；评分引擎 4/4 PASS；`check_conflicts --strict` PASS；`verify_mirrors --pre-release` PASS；321 项已知契约样本逐条模拟记录 0 退化，163 边界保持，340 唯一参考主机（273 已知/67 候选），8 项候选（didistatic.com, ceair.com, csair.com 等）首命中升入 China-Direct；`root-verify-implementation.py` PASS。
* **真机未验与边界保留**：321 项契约样本系离线模拟契约（已知契约样本逐条模拟记录），340 为唯一参考主机总量，不能将所有 340 称作既有已验证样本，不伪装真机测试；手机端 App Store 系统 DNS 候选仍未上机、根因未知；手机端 China-Baseline 实际加载与日常网络体验仍待真机确认；Gemini实施阶段未执行Git写入；Codex随后独立完成52规则/19诊断/4评分与strict/pre-release验收，已审核并正常推送。
* **2026-10-09 发布与双AI收尾核验**：Gemini完成实施及正式收尾，Codex独立修正遗留旧待办/同步单重复计数并完成最终验收。工程提交 `919dd4f985d72a31a4a785f79bdc39f44a4bf7f6` 正常推送main；[CI Run #86](https://github.com/o-ocn/loon-rules/actions/runs/37812012657)（job `113430997021`）针对该SHA为completed/success，日志实际52项规则/19项诊断、strict与pre-release通过，构建“No rule changes detected”；主源GitHub Raw全部19集及诊断资产通过CI核对，Codex另核对普通China-Direct与manifest URL均HTTP200且规范化SHA256一致，版本 `cc70392cee8a`。Fastly普通URL这两项独立核对仍旧（manifest `02c5ceb22c3a`），CI软CDN模式容许传播延迟，不宣称主备全部同步。推送后本地HEAD与实际远端一致、工作树clean；随后仅补齐收尾文档。具体本地自包含证据在任务目录20/21/22/23；手机未验与App Store根因未定继续保留。
* **2026-10-08 App Store：正常替代配置已由用户确认，原项目 DNS 单变量候选待真机**：用户报告原项目配置下商店加载失败、全局直连仍慢、全局代理正常；切换 `E:\Download\Baidu\2026_10_03_10_26_49_909_自动配置 (2).lcf` 后商店恢复。该文件含36远程规则，本地 `DOMAIN-SUFFIX,apps.apple.com,DIRECT` 优先命中，默认仅 `dns-server=system`。这不证明整个商店所有请求均直连，也不证明10月3日归档与故障时手机配置完全一致；DNS、插件与绑定存在多变量差异，根因尚未确认。商店改代理仅为已取消的未实施方案。
* **单变量候选与独立验收**：恢复基准 `b0670f87ac37f2fe82b89649d1c7791eae2fdaed`；新候选 `E:\Document\AI-Workspace\loon-rules\2026-10-08-appstore-china-baseline\Loon-19Rules-AppStore-SystemDNS-candidate-2026-10-08.lcf`（SHA256 `939878c460841356d7b1a6fd58d23bb4aa53605f88444951e355990a9a6ea60f`）仅删除原19集归档中的Google DoH单行。Codex字节对照确认原件和正常配置均未动，其他字节及私密字段完全保留；同19远程规则、37插件/36启用。本地验收为 PARTIAL_PASS / UNVERIFIED_PLUGINS；候选未上手机、不是已修复或正式部署。113项公开工程文件与基线比较（归一化换行）不变，公开19集/21,323规则/120 DNS Host/139账本均未改；沿用此前功能CI #85证据。
* **2026-10-08 guzzoni.smoot.apple.com (Siri/搜索) 精确优化：代码/CI/主源已发布核验；副CDN传播待复核，手机未验**：所有者明确授权将 Downloads 三张截图（IMG_1010/1011/1012）中确需优化的项目与 `guzzoni.smoot.apple.com` 一起优化；恢复起点 `57ca124bc2d4276c012093b1a482b3ea110821ab`（起点工作树 clean）。Apple-Direct 新增一条 DOMAIN 精确规则，DNS 插件新增一条 223.5.5.5 精确 Host，白名单从 7 项扩至 8 项；守卫算法不变，严格禁止通配符或 smoot/apple 泛域委托。其余五域名（openaiassets.z19.web.core.windows.net, api.revenuecat.com, o33249.ingest.us.sentry.io, www.nsloon.com, m.hotmail.com）按各自服务用途与既有分流目标，继续保持代理兜底（FINAL）；截图 TCP 有下行，不证明完整业务成功或时间字段含义，不新增 DIRECT/REJECT，Hotmail QUIC 保持不变。独立双 DoH 实时核验证实 AliDNS A 解析返回地址 101.34.195.126，Codex 另次得到同网段 101.34.190.217，均命中现有 China-GeoIP 101.34.0.0/15；Google 返回 54.203.140.83 未命中本库 CN CIDR，支持配套国内 DNS 试行。
* **此前构建基线**：19集 21,323条，Apple-Direct 173、China-Direct 680、China-GeoIP 19,243、China-Personal 109、DNS Host 120；内容签名 `02c5ceb22c3a`。相对起点仅 Apple-Direct 规则正文增加 1 条，其余 18 个规则集正文完全不变。账本 139 条、原 138 条字节前缀完整保留，新增一条 verified=false、180 天复查。

* **此前2026-10-08 两个Apple主机精确优化：已发布，本地/CI/主备验收通过**：所有者明确授权 pancake.apple.com 与 tr.iadsdk.apple.com；恢复起点 `80c8ffb9d9461c01dfede55d3b314f1e3ea615c7`。Apple-Direct新增两个 DOMAIN 精确规则，DNS插件新增两个223.5.5.5精确Host，白名单从cl1-cl5五项扩为七项；守卫代码不变，其他Apple子域、通配和账号/媒体边界未放宽。未改私人LCF、策略绑定、广告拦截或来源配置。原截图TCP已有正常下行；独立双DNS证据支持国内CDN调度试行，不证明业务用途、手机DNS或卡顿原因。
* **此前构建基线（Apple两个主机）**：19集21,322条，Apple-Direct172、China-Direct680、China-GeoIP19,243、China-Personal109、DNS Host119；内容签名 `96fe50cf4464`。个人优化为净增两个规则/两个DNS；正常构建同时同步成熟ChinaIPs上游删除 `103.144.244.0/23` 一项（源条目19,258→19,257，公开原文独立复核），所以全库相对起点净增一条；其余17个规则集正文不变。账本138条、原136条保留，两条新增verified=false、180天复查。
* **此前发布证据（Apple两个主机）**：代码 `85a8327075bd3ce0e82aaf634d2b955bc1992e84` 正常推送成功；[CI Run #84](https://github.com/o-ocn/loon-rules/actions/runs/37733112204)（ID `37733112204`）针对该SHA为completed/success，日志实际规则50项、诊断19项及前置门禁通过，CI构建未产生额外改动。GitHub Raw与Fastly普通订阅地址各六项资产均HTTP200、规范化SHA256与本地一致，manifest签名96fe50cf4464，没有缓存绕过参数；备用China-GeoIP一次SSL传输中断已重试并核验一致。代码发布后工作树clean；手机有效加载与实际效果仍未验证。
* **此前2026-10-07字节与腾讯音乐发布归档**：恢复起点 `ab3f46cf5993574f6cc7ab18a3be380705b20060`。截图中 render.ecombdpage.com、lf6-font-sign.bytehwm.com、img/p/ad.tencentmusic.com 五个国内服务主机，现均首命中 China-Direct；补齐六个服务后缀 bytehwm.com、ecombdpage.com、ecombdimg.com、ecombdstatic.com、ecombdvod.com、tencentmusic.com，并增加六条国内DNS映射。ecombdapi.com 原有覆盖保留；Sentry、RevenueCat、nsloon 未新增国内直连或拦截。规则保持策略中立，实际出口仍由用户既有绑定决定。
* **此前字节/TME基线（历史）**：19规则集、21,321条有效规则；China-Direct 680、Apple-Direct 170、China-Personal 109、DNS Host 117；manifest内容签名 `d3c24481f524`。相对晚间恢复起点仅 China-Direct 规则正文改变，其余18个规则集正文不变，DNS源与dist副本一致。账本136条、原130条完整保留，新六条 verified=false、180天复查。90行服务登记保留，273个已知参考样本与67个候选共340个唯一主机；新增样本包含合成回归主机，不表示完整App依赖或真机成功率。
* **此前字节/TME发布证据**：代码 `8cf4d07bed88a3193310e6f0ec4f4f760b692e26` 正常推送成功；[CI Run #83](https://github.com/o-ocn/loon-rules/actions/runs/37643102870)（ID `37643102870`）针对该SHA为 completed/success，实际日志规则49项、诊断19项及严格冲突/预发布门禁通过，远端构建未产生额外规则改动。GitHub Raw与Fastly普通地址各5项公开资产均HTTP200、规范化换行后的SHA256与本地一致，manifest为 `d3c24481f524`，没有缓存绕过参数；备用四项旧缓存已定向刷新后复核一致。代码发布后本地与origin/main及实际远端一致（0/0），工作树clean；手机加载与体验未验。
* **此前字节/TME已验证与范围决策**：Codex独立全量规则49/49通过；诊断19/19、评分4/4、构建、严格冲突与预发布完整性通过，常用服务参考样本0退化。test_49验证截图首命中、根域及合成同族、海外负例、伪装后缀和扩大范围故障注入，并修补DNS守卫对上层通配符 *.com 的漏检。ByteDance完整目录混有Lark、海外游戏、TikTok UA及公有云，本轮未整包接入；bytehwm及ecombdimg/static/vod在该参考目录，tencentmusic在Tencent_Domain及v2fly/tencent-tme，ecombdpage缺失只指本次抽查来源。独立双DNS返回不同地域CDN，支持配套国内DNS试行；不能据此认定截图时手机DNS或GeoIP未命中的原因。手机有效加载、卡顿和业务改善仍未验证。
* **参考差集复核（只读）**：Gemini交付ByteDance372条、DouYin13条完整快照差集；Codex逐条对照实际基线模拟器，域名根主机探针无结果差异。合计412条参考记录包含重复来源、非域名项、404占位与一条截图补充，不是App漏项数量。补正外部报告411计数与v2fly裸域被误标精确域的口径；TME仅核验18条直接条目，未展开kugou/kuwo/ximalaya。余项保持候选，不能因为未命中就整批直连；本次复核不增加生产规则。
* **此前2026-10-07常用服务专项发布归档**：此前小黑盒仅有两个静态主机规则，现已补齐`xiaoheihe.cn`自有社区/API；`.localfont`双DNS仍NXDOMAIN，仅精确停止代理试行，未证明字体恢复或卡顿唯一原因。由Codex通过Antigravity CLI指挥Gemini完成调查、回归代码和账本，再独立校验与修正范围。原89行服务登记加山姆，90行含别名/类别；`config/common_app_contract.json`登记328个公开参考主机，其中261个当前首命中样本进入现有CI，67个候选未自动准入；不表示App失败数、安装清单或完整依赖覆盖率。`scripts/audit_common_apps.py`可重复生成现状，发现已知样本退化时返回失败。恢复起点`f0eae6bdc1c040d7176d2a6a182d7986c7653e91`；手机加载与真实体验未验。
* **此前27规则/7DNS发布基线（历史证据）**：19规则集、21,315条有效规则；China-Direct 674、Apple-Direct 170、China-Personal 103、DNS Host 111；manifest内容签名`a5b55d35b9a6`。相对恢复起点净增27条规则、7条精确DNS，其他17个规则集正文不变。本地构建、48规则测试、19诊断测试、4评分测试、严格冲突与预发布完整性全部通过。初版发布94d35fa4ebe8459d235140c216c9473edee7b1da的CI81（37566329787）成功；最终代码发布00ce6ba3b3f7b1317a7ae3b38f74e115db5be183已正常推送，CI82（37568672941）completed/success，规则48与诊断19项及前置门禁通过。最终GitHub Raw与Fastly各5项公开资产均HTTP200、与本地一致，无缓存绕过参数；备用China-Direct曾有旧缓存，已按该文件定向刷新后核对通过。最终增量含极兔中国jtexpress.cn、维迈通官方下载app.vimoto.top及模拟器假回退修复；维迈通只是下载页而非对讲API已验。代码发布时本地与origin/main及实际远端SHA一致（0/0），工作树clean；本条为发布证据归档。
* **GitHub Actions 自动化 CI/CD 与发布机制**：
  * **主干生产流水线**：`.github/workflows/sync-and-build.yml`（每周日 00:00 UTC 定时运行与 push 触发，负责生产构建、50+19项门禁与 CDN 镜像校验发布）；
  * **Phase 0.5 旁路影子巡检流水线**：`.github/workflows/shadow-audit.yml`（每日 02:00 UTC / 北京时间 10:00 自动定时运行与 `workflow_dispatch` 手动触发，纯只读拉取多上游并生成影子审计报告，严格抑制空提交，100% 独立于生产规则发布）；
  * 5 门严格前置质量门禁（Ubuntu 环境，Python 3.12 + Node.js 20）：
    1. 构建规则与诊断插件：`python scripts/build.py`
    2. 规则完整性与防撞车单元测试：`python -B -m unittest scripts.test_rules`（当前本地与CI均50/50通过）
    3. 跨境共享基础设施防泄漏与冲突检测：`python scripts/check_conflicts.py --strict`（PASS）
    4. 原生诊断插件夹具测试：`node --test tests/test_diagnostic.js`（19/19 全部通过）
    5. 本地预发布签名自校验（Fail-Stop Release Barrier）：`python scripts/verify_mirrors.py --pre-release`（严格前置熔断屏障：若规则、哈希或签名存在任何异常，流水线在 git commit / push 前立即终止，远程 main 分支与 CDN镜像 100% 保持未被触碰）；
  * 自动化提交与发布后 CDN 探测：
    - 非 PR 运行模式下，若 `dist/`、`sources.yml`、`scripts/upstream_lock.json` 产生构建更新，由 `github-actions[bot]` 自动提交、生成 release tag 并推送到远端；
    - 发布后执行 `python scripts/verify_mirrors.py --branch main --soft-cdn` 对 GitHub Raw 主源及 jsDelivr CDN 备用源进行镜像连通与内容一致性巡检；
  * **已核验的规则发布 CI 运行事实**：本次 Siri/搜索 (`guzzoni.smoot.apple.com`) 精确优化代码 `9b52b0a` 的 [Run #85](https://github.com/o-ocn/loon-rules/actions/runs/37767776142)（ID `37767776142`）completed/success，实际 51 项规则、19 项诊断及前置门禁通过，主源 GitHub Raw 3 项资产一致，副源 CDN 传播待复核。此前 Apple 精确两主机代码 `85a8327` 的 [Run #84](https://github.com/o-ocn/loon-rules/actions/runs/37733112204) completed/success，实际 50/19 及前置门禁通过，普通主备 12 项一致。此前晚间服务族补齐代码 `8cf4d07` 的 [Run #83](https://github.com/o-ocn/loon-rules/actions/runs/37643102870) completed/success，规则 49 项、诊断 19 项与发布前门禁通过；普通主备资产 10/10 一致。以下为此前发布历史：前轮 GitHub Actions Run **#80**（ID `37336844815`，针对 `aa29325d6c53b469f353fed594bba909a141e9b9`）为 completed/success；本轮最终代码发布 [Run #82](https://github.com/o-ocn/loon-rules/actions/runs/37568672941)（ID `37568672941`，针对 `00ce6ba3b3f7b1317a7ae3b38f74e115db5be183`）completed/success；后续独立主备资产核验 10/10 一致，手机生效未验。
* **规则集架构定型**：全库定型为 **19 个独立规则集**（共 **21,323 条有效规则**），已全量构建至 `dist/`；当前本地门禁与主源发布核对通过，副源待自然传播复核；手机生效仍须正常使用确认。
  * `Gaming.lsr` 合并 Steam 与 Epic（65 条规则），消除 404 故障；
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 `ChinaIPs`（19,243 条规则），提供中国 IPv4/IPv6 底层防跌落兜底；
  * 字节跳动直播源站 (`bytegecko.com`)、核心图床 (`bytemaimg.com`) 及调度探针 (`ndcpp.com`) 纳入直连与国内 DNS 分流，彻底根除 120 秒超时卡死；
  * Apple 定位 (`ls.apple.com`, `wps.apple.com`)、天气 (`weatherkit.apple.com`)、设备激活与沙盒认证纳入直连，解决海外代理无谓绕行；
  * Apple MapKit 地图矢量瓦片与 POI 图床 (`apple-mapkit.com`) 纳入 `Apple-Direct` 直连，修复国内电信 CDN 节点 (`119.147.195.212`) 跌入 FINAL 产生折返跑延迟，严格保持 `apple.com` 泛域名不添加并保持 `Apple-Media` 与 `TestFlight` 策略隔离；
  * 招商银行 (`cmbchina.com`, `cmbimg.com`)、中国银联/云闪付 (`unionpay.com`, `unionpaysecure.com`, `95516.com`)、六大国有行及主要股份制银行的已知国内域名已纳入直连，并配套国内DNS；本轮补招行国内官网精确入口。已知主机样本通过不等于银行App完整依赖、支付交易或风控效果已验，海外子行与未决域名保留各自边界；
  * **Phase 0.5 首批人工核验放行**：一键免密认证基建 (`cmpassport.com`)、联通官方 (`10010.com`)、点评图床 (`dpfile.com`)、百度静态资源 (`bdstatic.com`)、央视媒体图床 (`cctvpic.com`) 5 条高置信规则正式入库；
  * **Phase 0.5 第二批真机抓包精准补丁**：Apple 补充组件 OTA 目录 (`gdmf-ados.apple.com`) 纳入直连根除 61s 超时；抖音自建边缘流媒体 CDN (`zzcdnx.com`) 纳入直连根除 1~3s 首帧卡顿；七牛云 PCDN (`qrstuvwxyzab.com`) 暂缓入库并进入隔离池审计；
  * **Phase 0.5 第三批真机抓包精准补丁**：中国大陆百科服务 (`baike.com`) 纳入直连，修复 `m.baike.com` 绕行香港代理访问国内电信节点 (119.147.195.212) 问题；
  * **Phase 1 个人高频生活直连层正式合入 (Personal Layer v3)**：一次性纳管个人 7 大高频场景（出行、物流、电商、生活社区、办公协同、精准政务、医疗问诊与电信营业厅），合入 29 条精选直连规则至 `rules/custom/China-Personal.list`，`China-Direct.lsr` 扩充至 595 条，并同步建立 `docs/China-Personal-Matrix.md` 永久候选资产决策矩阵；
  * **Phase 1.5 联合审定清单合入 (Phase 1.5 T5 Consensus Ingestion)**：依据 ChatGPT 与 DeepSeek 共同审定的 T5 清单，在 `rules/custom/China-Personal.list` 精准扩充 31 条 `DOMAIN-SUFFIX` 规则（携程/去哪儿/飞猪/同程/飞常准出行链、圆通速递、闲鱼/盒马/淘宝短链电商零售、BOSS直聘/夸克、公安部CTID政务认证、协和医院、翼支付/央行数字基建/邮储/平安金融，以及微博与中国移动6条专项来源子集，记录 139.com 多业务共存风险），`China-Direct.lsr` 扩充至 628 条（净增 31 条）；同步在 `plugins/Loon-China-DNS.lpx` 的 `[Host]` 下扩充 20 条非 `.cn` 域名的阿里极速 DNS（223.5.5.5）分流映射，全库总有效规则达到 **21,236 条**；
  * **vegslb.com 定向配套试行 (Targeted Paired Trial)**：依据 ChatGPT 与 DeepSeek 联合审定第十八节共识（`CHATGPT-DEEPSEEK-VEGSLB-CONSENSUS-FINAL`），在 `rules/custom/China-Personal.list` 补充 `DOMAIN-SUFFIX,vegslb.com` 直连规则，并在 `plugins/Loon-China-DNS.lpx` 的 `[Host]` 增补 `*.vegslb.com = server:223.5.5.5` 阿里极速 DNS 配套映射；`China-Direct.lsr` 扩充至 629 条（净增 1 条），全库总有效规则达到 **21,237 条**；决策账本按试行登记（verified 保持 false，效果待验证）。
  * **jspcdn.cn 定向直连补丁**：2026-10-04 所有者明确授权 ChatGPT/Codex 直接执行并推送，针对该域名再次落入 FINAL 且上传517B、下载0B的请求，新增 `DOMAIN-SUFFIX,jspcdn.cn` 至 China-Personal 并编译进 China-Direct；现有 `*.cn` 国内DNS映射已命中，本次不改DNS。China-Personal 62条、China-Direct 630条、全库21,266条。工程检查通过，手机有效加载与体验、国内IP兜底为何未命中仍待验证；未把无下行现象认定为确定握手故障或卡顿唯一原因。
  * **GlobalSign 精确域名出口调整（2026-10-05）**：按所有者要求新增 `DOMAIN,secure.globalsign.com` 至 China-Personal 并编译进 China-Direct；仅调整该主机出口，不扩展 GlobalSign 整域、不改DNS或私人配置。官方资料确认该主机提供证书文件，未找到其代理请求触发本次淘宝验证码的证据；手机加载、证书请求可用性及验证码变化仍待验证，账本保持 `verified=false`。
  * **国内常用服务上游覆盖审计（2026-10-05）**：Alibaba.list全部57条保留，但配套Alibaba_Domain.list未声明接入，其中21/1263项已有域名覆盖。扩展核对22组参考来源后，微信、抖音、京东、B站已接入清单的域名语义均完整；腾讯集团与字节扩展目录未接入，QQ音乐实际引用的y.gtimg.cn、设计要求的iesdouyin.com及部分其他常用服务参考域名在审计时发现缺项（本批后续已补齐，手机效果未验收）。来源范围差异不等于手机必走FINAL、App失败率或已确认卡顿/验证码原因；全清单核查及最终范围见待办15/16及本轮核查记录。
  * **2026-10-05 国内常用服务 21 条直连规则 + 9 条配套 DNS 审定方案正式合入 (Domestic Plan 21/9 Ingestion)**：依据 ChatGPT 与 DeepSeek 共同审定的最终共识清单（08号交接文档），在 `rules/custom/China-Personal.list` 纯本地扩充 21 条直连规则（本批增补淘宝官方资源与阿里兼容域、抖音基础域与QQ音乐图片、BOSS直聘和什么值得买图片、小黑盒静态资源、政务入口与网络身份认证、北京一卡通、天翼云盘与夸克网页资源、微信官方资源、招行/翼支付CDN和中国银行资源及搜索接口；携程、飞猪、飞常准和139主域为既有保留），China-Personal 从 63 条增至 84 条，`China-Direct.lsr` 从 631 条扩充至 652 条（净增 21 条）；严格排除命中既有禁令的 `ndstatic.cdn.bcebos.com` 及百度云主机；同步在 `plugins/Loon-China-DNS.lpx` 的 `[Host]` 扩充 9 条非 `.cn` 域名的阿里极速 DNS（223.5.5.5）映射（总数达 104 条）；全库有效规则达到 **21,288 条**；决策账本按试行登记（verified 保持 false，复查周期 180 天，效果待验证）。

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
| **`AI-Overseas.lsr`** | 38 | ChatGPT, Claude, Gemini (含 iOS WebChannel), Grok, Muse | 100% 策略中立 |
| **`YouTube.lsr`** | 190 | YouTube 视频流媒体、图片与 CDN（排在 Google 前） | 100% 策略中立 |
| **`GoogleDrive.lsr`** | 8 | Google Drive 云端硬盘专属服务（排在 Google 前） | 100% 策略中立 |
| **`Google.lsr`** | 690 | 普通 Google 服务、搜索与基础设施（含共享 googleapis） | 100% 策略中立 |
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
| **`Apple-Direct.lsr`** | 173 | iCloud, CloudKit, App Store, Apple ID, 定位, 天气, OTA 目录 (含 ADOS), MapKit 地图瓦片 (apple-mapkit.com) | 100% 策略中立 |
| **`China-Direct.lsr`** | 3,239 | 国内服务与自有CDN、银行支付、政务出行、China-Personal 109条、已审定China-Baseline静态基线层2,599条（净增+2,559条）；暂缓已识别共享基础设施、出海服务与歧义家族；覆盖非穷举 | 100% 策略中立 |
| **`Lan.lsr`** | 9 | RFC 局域网与保留网段直连旁路（排在 GeoIP 之前） | 100% 策略中立 |
| **`China-GeoIP.lsr`** | 19,243 | 中国大陆 IP-CIDR 兜底防线（引入 ChinaIPs IPv4/IPv6） | 100% 策略中立 |

---

## 四、已尝试但已放弃的方案（严禁后续 AI 重复折腾）

1. **放弃方案 1：纯 GeoIP 兜底分流（GeoIP-only 方案）**
   * *背景与尝试*：曾设想仅依靠 `GEOIP,CN` 作为国内流量的兜底直连防线。
   * *失败/放弃原因*：面对国内具有多国 CDN / 全球 Anycast 架构的大厂业务（如 `1688.com`、`doupay.com`），若客户端启用了海外 DoH（如 `dns.google`），解析返回的境外 IP（如香港 Anycast 节点）将直接绕过 `GEOIP,CN` 跌落进 `FINAL` 代理；必须采取“域名规则（`China-Direct.lsr`）+ 国内极速 DNS（`223.5.5.5`）分流 + 物理 CIDR / GeoIP”双重保险闭环，彻底否决并放弃纯 GeoIP 方案。
2. **放弃方案 2：Apple 全域泛化分流与泛解析（Apple 全域泛化方案）**
   * *背景与尝试*：曾探讨将 `apple.com` 或 `17.0.0.0/8` 全部送入海外代理，或在 DNS 插件中将 `apple.com` / `icloud.com` 泛解析至国内 DNS。
   * *失败/放弃原因*：全量代理 Apple 会严重拖慢国内 App Store 应用下载、导致国内 Apple CDN 缓存失效并消耗大量代理流量；而在 DNS 层将 `apple.com`/`icloud.com` 泛解析至国内 DNS 则触犯账户安全红线并引发跨区认证异常。现已彻底放弃全域泛化，确立精细化分层治理（`Apple-Direct.lsr` 直连基础服务、国内极速DNS就近解析`*.mzstatic.com`及本轮独立核实的cl1-cl5.apple.com精确主机、严禁对 `apple.com`/`icloud.com` 泛解析、独立保留 `Apple-Push` 最小化通道与 `Apple-Media` 流媒体）。
3. **放弃方案 3：TikTok / 微信共享域粗暴分流（共享基础设施粗暴一刀切）**
   * *背景与尝试*：曾考虑将跨国出海孪生业务的底层域名一刀切代理以彻底隔离国内外流量。
   * *失败/放弃原因*：字节跳动出海业务（TikTok）与国内抖音共享底层域名与图床（如 `bytedance.com`, `byteimg.com`, `ibytedtos.com`, `snssdk.com`）；腾讯出海 WeChat 与国内微信共享底层通信基础设施。粗暴一刀切全盘走代理会导致国内抖音刷不出视频、评论卡死或国内微信关键功能受损。现已确立：独占业务域名精准走代理，共享底层基础设施严格保留直连与国内 DNS，严禁粗暴一刀切。

---

## 五、验证状态与自动化门禁基线

### 1. 离线全量测试基线（100% PASS）
- **Python 规则单元测试**：`python -B -m unittest scripts.test_rules` **52/52 全部通过**（新增 test_52 验证 China-Baseline 静态层完整性、哈希锁、真实历史海外/共享云探针隔离、精确主机子域隔离及 4 类故障注入变异测试；test_51 验证 guzzoni.smoot.apple.com；test_50 验证 pancake/tr.iadsdk；test_49 新增字节/TME服务族、境外隔离及通配符故障注入；保留既有门禁；test_46 加入全服务参考样本、精确域与海外边界及真实扩大范围故障注入；test_47 未知FINAL与脱敏；test_48 精确Apple CDN DNS授权）；

- **归档配置只读核验（2026-10-07）**：登记的2026-10-03候选归档（包含子目录检查）含19个启用远程集，China-Direct/Apple-Direct/China-GeoIP启用且绑定DIRECT；10个重点主机在本地+远程顺序下首命中预期分类；结构验收在允许未验插件的条件下通过。归档不是当前手机加载证明；36个启用插件的运行时注入未验；未写私人配置或凭据。
- **公开服务样本复核**：`python -B scripts/audit_common_apps.py --output <任务目录>/common-apps.csv`：90行服务登记、340唯一参考主机（273已知/67候选）、0已知样本退化；候选没有域名命中时不伪报手机FINAL或App故障。
- **评分引擎**：`python -B -m unittest scripts.test_score_engine` **4/4 PASS**。
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

- **2026-10-08/09 国内静态底座准入决策**：为减少逐 App 抓包，采用固定上游快照、Gemini批量筛选与Codex独立审核，将2,599条策略中立域名规则并入既有China-Direct，编译净增2,559条。审查中拒绝未经筛选的3309草案，补除海外分类重叠、共享平台、正则分类冲突和高德等精确主机扩域；原批准层不回滚。shared_domains.yml是静态正文锁定值的唯一配置事实源，边界检查和正确hash的故障变异仍独立生效；未知上游候选不自动进生产，离线检查不代表所有域名归属或手机效果。

- **2026-10-08 取消 App Store 走海外代理方案 (07 计划废止)**：正常文件的apps本地DIRECT与系统DNS提供可工作的反例；两配置多变量不同，缺少直接改商店代理的必要证据；保持 19 规则集策略中立与规则正文不变。

- **2026-10-08 否决未经精细过滤的 3,309 域名大扩容草案**：`root-candidate-mutation-probes.json` 变异仿真证实该草案将导致 `m.hotmail.com`、`openaiassets.z19.web.core.windows.net`、`login.microsoftonline.com` 从代理兜底（FINAL）误突变为国内直连，且 `netease.com` 触发 ScoreEngine 红线；禁止直接扩容落盘。后续采用精细过滤机制扩充国内底座，无需用户逐 App 抓包。


- **2026-10-08 单变量系统 DNS 试行候选决策**：保持 19 集标准体系与全部37插件（36启用）及策略绑定原样，仅在本地候选配置中剔除全局 Google DoH，受控验证系统 DNS 恢复效果；不声称“已确认根因”或“功能已修复”，不要求用户停用正常配置。

- **2026-10-08 Siri / Search 精确主机 (guzzoni.smoot.apple.com) 试行**：官方 Apple 支持文档 https://support.apple.com/en-us/101555 明列 *.smoot.apple.com 为 Siri、Spotlight、Lookup等搜索服务；仅准入精确 DOMAIN 规则与配套 223.5.5.5 精确 DNS，严格禁止通配符或 root/wildcard 委托。其余 5 个截图域名保持现有代理兜底，不为消灭 FINAL 破坏策略边界。

- **2026-10-08 Apple两个完整主机试行**：只准入pancake.apple.com和tr.iadsdk.apple.com的精确规则/精确DNS，保持域树和媒体账号边界；构建同步的单条ChinaIPs删除单独核验，不混称用户补丁。

- **2026-10-07 服务族补齐边界**：采用经独立审查的六个域后缀及六条配套DNS，保留既有上游和 ecombdapi 覆盖，不吞集团目录，不因广告标记改 REJECT，不改变私人配置与策略绑定。DNS上层通配符覆盖Apple禁区也必须拦截。

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
16. **Phase 0.5 首次人工审核规则入库与边界收敛决策**：
    - *批准放行项 (5 条)*：
      - `cmpassport.com`：全国统一移动认证/三大运营商手机号一键免密认证底层接口，覆盖微信/淘宝/京东/美团/银行 App 登录通道，防止直连缺失引发 120s 超时回退短信；
      - `dpfile.com`：大众点评核心商户与探店点评图床 CDN，解决探店瀑布流白块卡顿；
      - `10010.com`：中国联通官方业务与手厅接口，保障账单与流量接口直连；
      - `bdstatic.com`：百度全系产品前端通用静态加速集群，补全百度生态；
      - `cctvpic.com`：央视网与央视频移动端图床 CDN，解决封面与流媒体静态图加载缓慢。
    - *阻断暂缓项 (1 条)*：
      - `cctv.com`：判定为 `REJECTED` 暂缓入库，因泛域名包含复杂涉外宣传与国际合作边缘业务，严格遵循“宁缺毋滥、精准收敛至专用图床/流媒体 CDN”原则。

17. **Phase 0.5 第二批真机抓包与分流优化决策 (Apple OTA & 抖音边缘 CDN)**：
    - *批准放行项*：
      - `gdmf-ados.apple.com`：Apple 官方补充组件与固件 OTA 目录（ADOS），上游 `SystemOTA` 仅收录 `gdmf.apple.com` 因连字符漏判，导致请求跌落 `FINAL` 走海外专线引发 61.38 秒严重挂起；加入 `Apple-Direct.list` 直连修复；
      - `zzcdnx.com`：字节跳动/抖音自建动态边缘 CDN 集群（`dy.zzcdnx.com`），解决短视频与直播边缘分片走香港 IEPL 专线反向拉取引发的 1~3 秒卡顿；
    - *隔离验证项 (暂缓放行)*：
      - `qrstuvwxyzab.com`：疑似七牛云电信 IPv6 编码动态 PCDN 反向映射节点（北京空山信息）。虽单次抓包指向国内电信 IP（119.147.195.212），但考虑到 PCDN 泛域名可能存在多租户混用、动态借道以及海外边缘节点污染风险，按用户指示**暂缓入库**，作为隔离观察对象；
    - *无需优化项*：
      - `m.hotmail.com`：微软 Hotmail/Outlook EAS 移动邮件后台同步，按当前体系自然由 `FINAL` 走海外代理专线，属于符合预期的正常分流，无需干预。

18. **Phase 0.5 第三批真机抓包与分流优化决策 (国内百科服务直连补漏)**：
    - *批准放行项*：
      - `baike.com`：中国大陆移动/桌面百科服务，真机日志确认请求落入国内电信 IP（119.147.195.212）。因底层 `China-GeoIP` 的 IP-CIDR 规则均带有 `no-resolve`，域名请求不会主动触发 DNS 反查而直接跌入 `FINAL`；批准合入 `rules/custom/China-Direct.list`（`DOMAIN-SUFFIX,baike.com`），修复代理折返跑；
    - *正常分流无需干预项*：
      - `m.hotmail.com`：微软 Hotmail/Outlook EAS 移动邮件后台同步，按当前体系自然由 `FINAL` 走海外代理专线，属于符合预期的正常分流，无需干预。

19. **字节跳动静态资源 CDN 收录与 GeoIP 去 `no-resolve` 架构收敛**：
    - *为什么添加 `bytecdn.com`/`bytecdn.cn`*：上游源 `DouYin.list` 仅有 13 条核心规则，母公司底层 CDN 放置在 `ByteDance.list` 未被引用，导致 `lf-leads-fe-scm.bytecdn.com` 前端组件跌落 FINAL，走香港专线折返跑造成抖音评论区图片转圈与卡顿；合入 `China-Direct.list` 并经真机验证秒开；
    - *放弃纯理论洁癖，拥抱实用主义（去 `no-resolve` 决策）*：依据项目最高铁律“稳定使用 > 减少人工 > 易维护 > 极端场景完善”，客户端在 `China-GeoIP` 层放弃 `no-resolve` 强约束。因主流海外服务在顶层早已被域名代理规则完全拦截，底层放开本地 DNS 查验不仅消除了 99% 的未收录国内边缘 CDN 绕道代理卡顿，而且从根本上解放了用户，彻底终结“遇卡顿就抓包打补丁”的高频人工内耗。

20. **常用资源补齐采用21＋9纯本地批次（2026-10-05，审核共识）**：仅4条参考来源候选的接入收益不足以在本批捆绑新来源及编译器维护面，全部通过现有个人层实现；原来源改造方案保留为按需评估的历史方案，不宣称已完成。既有bcebos整树BLOCK保留，精确主机也不能以备注绕过；人工批准与自动置信度、工程检查与手机效果分别记录。最终范围已审定（该“尚未实施”系批准时共识状态；后续已由 Gemini 落地实施并发布，详见下文十、环境与更新记录）。

---

## 七、当前观察期与待办事项

### 1. 常用服务专项发布后的日常观察（不要求逐App抓包）
- **本轮下一步**：先保持用户已确认正常的替代配置；方便时加载既有19集系统DNS候选并在App Store搜索同一软件，做一次对照即可。公开规则发布不等于当前手机已加载；本批扩容、此前Apple精确DNS的真机效果继续如实待验，不要求逐App抓包或停用正常配置。若出现退化，AI按相关增量定位和恢复。
- **核心原则**：当前以日常稳定使用和少人工维护为目标，避免未经证据和审核的盲目扩充；优先依据成熟来源与已审核清单补齐覆盖，出现具体异常时先核对规则、DNS和业务边界，必要时再做针对性验证，不要求逐App抓包；
- **观察对象**：
  1. **图片与多媒体流媒体秒开**：拼多多商品大图 (`pddpic`)、美团外卖菜品 (`meituan.net`/`sankuai`)、小红书笔记瀑布流 (`xhscdn`)、快手短视频流 (`yximgs`/`gifshow`)、App Store 截图与预览 (`mzstatic`)；
  2. **金融交易与风控防拦截**：招行掌上生活信用卡饭票与活动 (`cmbimg`)、云闪付与银联支付 (`95516`/`unionpay`)、支付宝小程序账单 (`alipayobjects`)；
  3. **音视频与云存储传输**：网易云音乐无损起播与专辑图 (`music.163`/`music.126`)、B站高清视频、百度网盘国内直连下载 (`baidupcs`)；
  4. **系统核心协同**：HomeKit 室内摄像头即时推流与 CloudKit 同步、Telegram 蜂窝锁屏即时推送；
  5. **自动化巡检**：每周日 GitHub Actions 自动定时同步上游 rules 与镜像校验的稳定性。
- **结束条件**：
  - 连续日常使用 1~2 周无超时、无误伤、无漂移报错，且自动化 CI 巡航稳定，即可正式解除观察期，冻结日常手动干预。

### 2. 待办事项
- [ ] **App Store 单变量系统 DNS 候选真机试行**：候选文件 `E:\Document\AI-Workspace\loon-rules\2026-10-08-appstore-china-baseline\Loon-19Rules-AppStore-SystemDNS-candidate-2026-10-08.lcf`（仅移除 Google DoH，其余19规则/37插件（36启用）/策略绑定完全一致，`verify_private_lcf.py` PARTIAL_PASS）；待用户方便时加载试行反馈，当前用户继续保留并使用正常配置 `2026_10_03_10_26_49_909_自动配置 (2).lcf`；
- [x] **国内分流底座精细过滤与实施**：固定上游、批量排除、实际编译、分流与故障注入门禁已完成；正式发布证据见当前状态。后续快照变化由AI重新批量审查，不要求所有者逐App抓包。
- [ ] **日常真机追踪记录**：依托 [`docs/real-device-validation.md`](docs/real-device-validation.md) 追踪记录日常使用反馈，严格执行“排查三步法（看规则 -> 看 DNS -> 看业务边界）”，先入矩阵登记再做决策；
- [x] **唯一私人候选与可恢复回退配置装配**：已在 `E:\Document\ChatGPT\Loon-Migration\config-review-2026-10-03\` 装配 `Loon-v2-19Rules-candidate-2026-10-03.lcf` 与 `Loon-v2-19Rules-rollback-1e498f3.lcf`（回退锚点锁定提交 `1e498f3bbcffbbb5e67179d10f4af63bec5b7753`）；两份文件的结构、本地匹配与FINAL检查部分通过（PARTIAL_PASS / UNVERIFIED_PLUGINS，36个启用插件的运行时注入未验证）。两项固定回退资产另经独立取回核对，HTTP 200且SHA256与真实Git对象一致；手机当前加载及实际体验尚未验收；
- [ ] **Phase 0.5 旁路影子巡检稳定观察期 (2~4周)**：依托 `.github/workflows/shadow-audit.yml` 每日自动巡检，持续累积 `audit/shadow_report.md` 观察数据，严禁在此期间进行生产规则接管；
- [x] **测试套件总条数断言解耦优化**：已将 `test_rules.py` 中硬编码的固定数字优化为动态比对 `manifest.json` 规则集条数总和并守卫最低基线（`>= 21158`），彻底消除后续加规则频繁改断言的技术债；
- [ ] **qrstuvwxyzab.com PCDN 隔离池专项核验**：持续收集该域名解析的 IP 归属地与调用 App 特征，验证其是否 100% 局限在中国大陆三大运营商 IPv6/IPv4 段，排查境外 CDN 节点混杂可能性后再行决策；
- [ ] **Phase 1.5 联合审定保留待办（双方一致保留，非分歧项，不阻塞首批交付）**：
  1. `aliexpress.com` 策略迁移与私人层绑定（显式登记“公开直连 vs 文档称代理”矛盾）；
  2. `doh-server = dns.google` 单变量对照验证；
  3. `ctyun.cn` 整域边界核验（天翼云电脑登录、桌面连接、文件传输端点 vs 公有云服务）；
  4. 九号、IoT其余区域接口和Microsoft分流仍待取证；小黑盒自有xiaoheihe.cn已补，Steam独立域保持Gaming；miIO仅api.io.mi.com中国接口准入，Aqara/云鲸新增网站资源不等于设备控制后台验收；
  5. `blank_1688.com`、`jcloudwaftest.com` 真实性确认；
  6. 维迈通已找到官方App/下载支持页，但对讲后台未证；原“325 LIFE”无精确官方条目，疑似352 Life，名称澄清前不发明域名；
  7. 完整回退配置的其余第三方插件（Kelee等）离线冻结与真机加载验收；
  8. iPhone 真机日常使用无感体验验证（国内服务与海外代理正常即可，无需批量抓包）；
  9. 微博与中国移动专项源长期生产接入方案评估（当前首批以本地补充层过渡）；
  10. **根域匹配语义待核验**：核验 Loon `[Host]` 中 `*.域名` 映射是否自动匹配精确根域（如 `*.ctrip.com` 是否自动涵盖 `ctrip.com`），区分顶级域通配与服务域通配，待取得官方依据或真机实测前不机械增补精确根域映射；
  11. **vegslb.com 定向试行真机效果追踪 (1~2天)**：用户更新规则与 DNS 插件后正常使用抖音，反馈“有改善 / 无明显变化 / 变差”；无明显改善不扩大加规则，若退化则单点回退该条增量（不影响 31/20 基线）。
  12. **jspcdn.cn 直连补丁真机验证**：手机更新一次 China-Direct 并重连后正常使用，简短反馈即可，不要求新抓包或统计频次。已归档配置中 China-Direct/China-GeoIP 均启用并绑定DIRECT，公开GeoIP规则覆盖截图IP；手机有效加载及匹配时地址仍未确认，其他服务显示同一IP不能直接据此改直连。
  13. **兜底与抖音覆盖专项待核验（2026-10-05）**：核对手机已加载的 China-GeoIP 内容、启用与 DIRECT 绑定，以及 IP 模式实际生效情况。本轮公共 HTTPS DNS 对截图 JSPCDN 主机仅返回 IPv6，归档新旧配置均写有 `ip-mode = v4-only` / `ipv6-vif = off`；这是待验证线索，不是已确认回归原因。设计文档要求的 `iesdouyin.com` 审计时缺少域名规则（本批后续已补齐，手机效果未验收）；`bytegeckoext.com` / `tlivegslb.com` 属候选缺口，需核验业务边界后决定。现有模拟器不模拟域名解析后的 IP 兜底过程，不能用离线样例通过代替手机验收。

  14. **GlobalSign 精确域名调整与淘宝验证观察（2026-10-05）**：仅更新 China-Direct 后正常使用，不要求反复登录、退出账号或抓包。证书请求走代理不等于淘宝业务请求走代理；若验证码持续出现，应核对淘宝业务实际分流和正常风控因素，不盲目追加证书厂商整域直连。若证书访问退化，只撤本次精确域名。

  15. **淘宝 / 阿里配套域名接入缺口补齐方案（2026-10-05）**：tbcdn.cn、taobaocdn.com、mmstat.com已在本批21＋9共识中批准通过个人层补齐，已按第16项完成实施，手机使用观察待完成；不宣称配套来源已经接入。部分aliyuncs.com下验证码接口虽有公开文档线索，但尚未纳入本批，不能据此补公有云整域或断言本次滑块原因。配套来源为点域名格式，未来确需接入时再评估转换及业务过滤，不捆绑本批编译器改造；不要求所有者逐域名抓包。

  16. **常用国内服务资源补齐方案（2026-10-05，Gemini 已完成 21＋9 实施与本地发布前门禁验证，待手机端使用观察）**：已对63项用户清单/类别/别名及26项扩展候选完成桌面核查，不能等同App完整验收。ChatGPT与DeepSeek审定同意21条规则加入China-Personal、9条DNS加入现有插件；不新增来源、不改编译器/YAML解析器/来源锁/评分器。ndstatic.cdn.bcebos.com命中现有整树HARD_BLOCK，本批排除且不改旧禁令。Gemini 已按共识实施落地，China-Personal 扩充至 84 条，China-Direct 扩充至 652 条，Host 映射扩充至 104 条，账本补充 21 条（verified 标为 false），全部 6 门质量门禁（单测 45/45、严格冲突、诊断 19/19、评分 4/4、预发布校验）全部通过；手机端加载与使用体验留待用户更新后正常观察反馈，无需逐 App 抓包。IP兜底、IoT区域与325 LIFE身份保留独立未决。

  17. **本轮67个参考候选保持可审计未决**：公开DNS仅为当前样本，国外A不能直接证明业务归属、无A不等于永久失效；共享云/SDK、IoT区域、类别/别名及海外业务不自动放行。后续AI先用同一契约重跑，核验原始资料和真实客户端身份；不要求所有者逐App抓包。

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
6. **App Store 故障机制真机未确认与候选待验**：
   - 虽然电脑端观察到 Google DoH 解析 Fastly Anycast，但两份配置存在规则集数量（36 vs 19）、本地规则（apps DIRECT）、DNS 与插件等多重差异；未在真机捕获具体网络重置或抓包，Google DoH 是否为唯一根因尚未证实，单变量候选在真机上的实际效果尚未验证。

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
18. **第一阶段禁止自动放行任何 IP-CIDR/IP-CIDR6 规则入直连**：上游爬取的 IP-CIDR 统一由 Type Filter 拦截，仅允许人工在 `rules/custom/` 中按需维护，防止跨国 Anycast/海外云公网 IP 逃逸；
19. **影子审计每日巡检必须严格消除 Git 空提交**：在上游内容或评分 KPI 未变动时，严禁因时间戳刷新而产生无意义提交。

---

## 十、环境与更新记录

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 20+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **版本控制**：Git（GitHub 远程公开仓库 `o-ocn/loon-rules`，分支 `main`）
* **最后更新**：2026-10-09（Gemini常规实施/收尾；Codex独立审核、完整验收、推送与CI/主源核验；手机效果未验）

  * **2026-10-08 App Store 调查纠正与单变量系统 DNS 候选装配（Gemini实施 / Codex独立复核）**：
    - 完成调查纠正报告（`08-Gemini-corrected-investigation.md` 与 `10-corrected-evidence.json`），纠正将 DNS 差异认定为已证实唯一根因、排除全部运行时插件以及 3309 安全候选的错误；
    - 采纳 `root-candidate-mutation-probes.json`，正式否决 3,309 域名扩容落盘（防范Hotmail、截图中的Azure主机及微软登录改变现有代理分流，`netease.com` 触发红线）；
    - 正式取消 07 商店改代理方案（正常文件apps本地DIRECT、默认系统DNS，但不能归纳全部商店流量或确认单一根因）；
    - 装配全新单变量系统 DNS 候选 `E:\Document\AI-Workspace\loon-rules\2026-10-08-appstore-china-baseline\Loon-19Rules-AppStore-SystemDNS-candidate-2026-10-08.lcf`（SHA256: `939878c4..`），源基准文件 `Loon-v2-19Rules-candidate-2026-10-03.lcf`（SHA256: `293ada72..`）原样未动，仅删除 `doh-server = https://dns.google/dns-query` 单行，经 `verify_private_lcf.py` 脱敏验收（PARTIAL_PASS / UNVERIFIED_PLUGINS）；用户正常配置继续保留使用；
    - 公开规则库（19 规则集、21,323 条规则、120 DNS Host、139 账本）内容未修改，Codex独立验收原件与候选字节差异、113项工程文件一致及配置结构PARTIAL_PASS；本轮不把此前51项CI证据当新测试运行。Gemini完成实施与状态交接，Codex审核后正常提交/推送本次状态文档；未部署规则扩容或候选。

  * **2026-10-08 Apple精确两个主机**：本地50/19/4与严格/预发布门禁通过；新规则、DNS与精确授权各两项，原账本136条保留，另有已核实的ChinaIPs单条自动更新；不声明手机体验已验。

  * **2026-10-07 晚间字节/TME服务族补齐**：六规则/六DNS、新增12个参考主机样本，修补DNS通配符祖先漏检；本地49/19/4与严格/预发布门禁通过。完整增量、边界与未验体验见当前状态；未改 sources.yml、上游锁、构建器、私人配置或上游接入。

  * **2026-10-07 此前常用服务可靠性与全清单回归（发布归档）**：
    - 新增24条手动试行规则（personal 19＋Apple精确5），账本130记录、原106完整保留；新增全部verified=false。4个小上游净增3条字面规则；移除10条重复custom副本，保持原有语义覆盖。贴吧已有关键词覆盖，不冒称本轮修好贴吧全业务。
    - 规则/DNS：TRTC仅mlvbdc；Apple仅cl1-cl5；小米仅中国api.io.mi.com。保持Steam/TikTok/Apple账号媒体、银行海外、公有云及PCDN边界；不采纳Gemini早期整包放行建议。未改私人.lcf策略。
    - 13条公开引用补齐明确区分官网/图片/Web客户端与原生App接口。小米官方HA常量是ha.api.io.mi.com，本轮native中国接口依据是公开miIO区域实现与DNS，不能冒充官方HA的同名证明。
    - 已知样本入CI、模拟器修复无LCF及实际缺FINAL时假FINAL,DIRECT；显式空远程规则列表不再静默恢复默认清单；严格DNS守卫只放5个精确Apple主机，宽泛和委派子域故障注入均拦截。
    - 本地48/19/4、严格冲突、预发布及构建通过；前期Gemini当前账号Pro/Flash均429；通过既有账号切换工具复用备用账号，22号终审补正已真实交付。Codex对照生产文件核验，无阻塞代码问题；20号初稿误把测试负例当生产规则及App身份断言已拒绝，BCE排除的实际三主机以sources.yml为准。最终代码发布00ce6ba及CI82成功，主备各5项公开资产独立核对一致；CDN旧缓存已定向刷新。收尾校正贴吧行误列淘宝tbcdn.cn参考主机，淘宝/1688仍保留其覆盖，261个唯一已知主机集合不变，test_46与全清单审计重跑通过。外部29号报告保存完整证据与收尾Git状态，正式详细事实源仍只有本文件。
  * **字节跳动骨干静态 CDN 补丁与 GeoIP 去 no-resolve 架构收敛**：
    - 精准收录 `bytecdn.com` 与 `bytecdn.cn` 至 `rules/custom/China-Direct.list`，彻底解决字节前端组件（`lf-leads-fe-scm`）绕行香港代理导致的抖音评论区图片转圈与卡顿，真机实测验证秒开；
    - 落地项目最高准则“稳定使用 > 减少人工 > 易维护 > 极端场景完善”，客户端放弃 `no-resolve` 束缚，恢复 GeoIP 主动触发本地 DNS 反查兜底，实现日常使用彻底无感；
    - 全库 19 规则集 21,205 条有效规则通过全套 5 门质量门禁测试。
  * **Phase 0.5 旁路影子巡检正式接入 GitHub Actions**：
    - 新增 `.github/workflows/shadow-audit.yml`，设置每日 02:00 UTC（北京时间 10:00）自动运行，保留 `workflow_dispatch`；
    - 实现智能变动感知：仅在 `audit/shadow_report.*` 或 `state/upstream_state.json` 发生真实数据变化时才提交，杜绝空提交；
    - 绝不修改生产规则，`build.py`、`sources.yml`、`dist/*.lsr` 100% 保持零改动，用户端订阅不受任何影响；
    - 当前进入 2~4 周影子观察期（Shadow Audit Only），不进行生产接管，不引入 VPS，不接入 Telegram。
  * **Phase 0.5 首批人工审核补丁正式合入 (First Human-Approved Patch Ingestion)**：
    - 依据影子审计报告与人工交叉核验，批准入库 5 项高置信规则至 `rules/custom/China-Direct.list`：`cmpassport.com`（统一免密认证SDK）、`dpfile.com`（大众点评商户图床）、`10010.com`（中国联通官网业务）、`bdstatic.com`（百度静态集群）、`cctvpic.com`（央视频媒体图床）；
    - 严格阻断 `cctv.com` 泛域名直连，作为 `REJECTED` 记录入账；
    - 决策追溯链同步更新至 `history/decisions.jsonl`（5 APPROVED + 1 REJECTED），扩展 `scripts/score_engine.py` 支持 APPROVED/REJECTED 语义对齐；
    - 经 `build.py` 编译更新 `dist/China-Direct.lsr`（559 -> 564 条，精准增加 5 条，其余 18 个规则集 100% 零漂移）；
    - 离线 4 门质量门禁全部通过（`test_rules` 43/43 PASS, `test_diagnostic.js` 19/19 PASS, `check_conflicts --strict` PASS, `test_score_engine` 4/4 PASS, `verify_mirrors --pre-release` PASS）。
  * **Phase 0.5 第二批真机抓包精准补丁合入与断言解耦 (Second Human-Approved Patch Ingestion & Assertion Decoupling)**：
    - 依据真机 Loon 抓包日志与人工交叉核验，批准入库 `gdmf-ados.apple.com` 至 `rules/custom/Apple-Direct.list`，精准修复 Apple 附加组件/固件目录（ADOS）跌入 FINAL 导致 61.38s 超时问题；
    - 批准入库 `zzcdnx.com` 至 `rules/custom/China-Direct.list`，避免字节跳动/抖音自建边缘流媒体 CDN（`dy.zzcdnx.com`）绕行香港 IEPL 专线反向拉取导致的 1~3s 首帧卡顿；
    - 暂缓放行 `qrstuvwxyzab.com`（七牛云电信 IPv6 PCDN 动态反向映射），作为 `REJECTED` 隔离池项入账 `history/decisions.jsonl`，防止泛域名动态借道或多租户海外污染风险；
    - 追溯账本规范化：统一人工审核标签为 `"decided_by":"human_approved"`，原因表述收敛为客观、严谨的技术定性；
    - 经 `build.py` 重新编译更新 `dist/Apple-Direct.lsr`（163 -> 164 条）与 `dist/China-Direct.lsr`（564 -> 565 条），有效规则总数提升至 **21,165 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `4e97ba880e24`）；
    - 重构 `scripts/test_rules.py`（`test_31`）总条数硬编码断言，改为动态比对 `manifest.json` 规则集条数之和并守卫安全底线（`>= 21158`），彻底消除后续加规则维护负担；
    - 全套 5 门质量门禁 100% 绿色通过（`test_rules` 43/43 PASS, `test_diagnostic.js` 19/19 PASS, `check_conflicts --strict` PASS, `test_score_engine` 4/4 PASS, `verify_mirrors --pre-release` PASS）；
    - 重新运行 `scripts/audit_pipeline.py`，更新 `audit/shadow_report.json` 与 `shadow_report.md`（生产已覆盖规则提升至 354 条）。
  * **Phase 0.5 第三批真机抓包精准补丁合入 (Third Human-Approved Patch Ingestion - baike.com)**：
    - 依据真机 Loon 抓包日志与人工交叉核验，批准入库 `baike.com` 至 `rules/custom/China-Direct.list`（`DOMAIN-SUFFIX,baike.com`）；
    - 明确核心放行依据：1. `baike.com` 为中国大陆基础服务；2. 真实请求解析至国内电信 IP（119.147.195.212）；3. 因底层 `China-GeoIP` 的 IP-CIDR 规则带有 `no-resolve`，域名请求未命中域名规则时直接滑落至末尾 `FINAL` 走香港代理引发折返跑；4. 规则库先前未收录；
    - 决策追溯链同步更新至 `history/decisions.jsonl`（`human_approved` 追溯放行）；
    - 经 `build.py` 重新编译更新 `dist/China-Direct.lsr`（565 -> 566 条），有效规则总数提升至 **21,166 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `1db0abd85c00`）；
    - 全套 5 门质量门禁 100% 绿色通过（`test_rules` 43/43 PASS, `test_diagnostic.js` 19/19 PASS, `check_conflicts --strict` PASS, `test_score_engine` 4/4 PASS, `verify_mirrors --pre-release` PASS）；
    - 重新运行 `scripts/audit_pipeline.py`，更新 `audit/shadow_report.json` 与 `shadow_report.md`（生产已覆盖规则从 354 提升至 355 条，候选池 REVIEW 项由 411 减为 410）。
  * **Phase 1 个人高频生活直连层正式合入 (Phase 1 Personal Layer v3 Ingestion)**：
    - **背景与痛点**：全库虽加载约 21,780 条规则，但底层 `China-GeoIP` 的 19,216 条 IP 规则带有 `,no-resolve`，域名请求未命中域名规则时在 0ms 内直接击穿至 `FINAL` 走代理；大厂规则覆盖较好但中腰部个人高频服务、政务、物流严重裸奔；
    - **架构决策**：彻底放弃“单个App零星补漏”模式，确立**源码层模块化隔离、客户端单一规则集聚合**体系。在 `rules/custom/China-Personal.list` 中按场景维护，在 `sources.yml` 编译源中并入 `China-Direct`，手机客户端依然只挂载 1 个国内直连集，零增加客户端策略复杂度；
    - **正式入库 29 条精选规则**：
      1. 出行：航旅纵横 (`umetrip.com`)、滴滴出行 (`didichuxing.com`)、哈啰 (`hellobike.com`)；
      2. 物流：顺丰 (`sf-express.com`)、菜鸟 (`cainiao.com`)、通达系 (`zto.com`, `ytoexpress.com`, `yundaex.com`, `sto.cn`)；
      3. 电商/生活：什么值得买 (`smzdm.com`)、京东到家 (`jddj.com`, `daojia.com`)、豆瓣 (`douban.com`, `doubanio.com`)、NGA (`nga.cn`, `ngabbs.com`)、起点读书 (`qidian.com`)；
      4. 办公：WPS (`wps.cn`)、钉钉 (`dingtalk.com`)；
      5. 政务：交管12123 (`122.gov.cn`)、个人所得税 (`chinatax.gov.cn`)、国家医保 (`nhsa.gov.cn`)、国家政务平台 (`gjzwfw.gov.cn`)、移民局12367 (`nia.gov.cn`)、人社部12333 (`12333.gov.cn`)、北京公积金 (`gjj.beijing.gov.cn`)；
      6. 医疗：微医 (`guahao.com`)、好大夫在线 (`haodf.com`)；
      7. 运营商：中国电信 (`189.cn`)；
    - **同步沉淀管理矩阵**：创建 `docs/China-Personal-Matrix.md`，将米家/小米、天翼云、移动云盘、携程、飞猪、高德打车聚合、国内主要航司等纳入 Phase 1.5 观察池，严格将 `trip.com`、`larksuite.com`、`voovmeeting.com` 等出海双生产品排除在直连白名单外；
    - **编译与规则条数**：`China-Direct.lsr` 从 566 条精准扩充至 595 条（净增 29 条），`China-GeoIP.lsr` 自然同步上游微增 7 条至 19,216 条，规则总数达到 **21,202 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `d696a55df4df`）；
    - **全量测试与严格隔离验证**：新增 `test_44` 单元测试，自动化全套 44/44 测试全绿；经 Python 白盒断言严格确认：29 条新规则 100% 存在于 `China-Direct.lsr`，且 `google` / `openai` / `telegram` / `github` 核心海外关键字在 `China-Direct.lsr` 中完全缺席（Zero Collision），出海双生产品排除验证 100% 达成；
    - **账本事实闭环**：29 条规则的准入依据、技术证据及低风险评估事实全量追加录入 `history/decisions.jsonl`。
  * **Apple MapKit 精准直连补丁合入 (Apple MapKit Direct Ingestion)**：
    - **抓包与网络现象**：真机日志捕获 `cdn.apple-mapkit.com` 经国内 DNS 解析至国内电信 CDN 边缘节点 (`119.147.195.212`)，但因 Apple 规则库未收录该独立域名、且 `China-GeoIP` 带 `no-resolve` 无法触发本地 DNS 反查，请求在 0ms 瞬间跌入 `FINAL` 走香港 IEPL 代理，造成大陆节点跨洋折返跑与地图瓦片加载延迟；
    - **架构决策与安全底线**：严禁无脑加入 `DOMAIN-SUFFIX,apple.com`（防止破坏 `Apple-Media.lsr` 锁区流媒体与 `TestFlight.lsr`）；利用 `apple-mapkit.com` 为独立商业域名的天然隔离优势，仅在 `rules/custom/Apple-Direct.list` 中精准增补一条 `DOMAIN-SUFFIX,apple-mapkit.com`；
    - **编译与规则条数**：经 `build.py` 编译，`dist/Apple-Direct.lsr` 由 164 条精准增至 165 条（净增 1 条），全库总有效规则达到 **21,203 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `2772203f8187`）；
    - **门禁验证**：白盒断言确认 `cdn.apple-mapkit.com` 准确命中 `Apple-Direct`，`tv.apple.com` 与 `testflight.apple.com` 100% 保持原有代理策略，`scripts/check_conflicts.py --strict` 零碰撞通过，全套 44/44 单元测试全绿；
    - **决策追溯账本**：同步追加一条 `human_approved` 事实记录至 `history/decisions.jsonl`。
  * **字节跳动骨干静态 CDN 补丁合入与 GeoIP 去 no-resolve 架构收敛 (ByteDance Static CDN & Active-Resolve GeoIP Realignment)**：
    - **抓包与网络现象**：用户真机抓包捕获 `lf-leads-fe-scm.bytecdn.com`（字节跳动商业化与前端静态 JS/CSS 组件包），解析至国内电信机房（`119.147.195.212`），但因上游源 `sources.yml` 仅引入了仅有 13 条规则的 `DouYin.list`，漏掉了包含底层 CDN 的 `ByteDance.list`（含 `bytecdn.com`/`bytecdn.cn`）；叠加底层 `China-GeoIP` 带 `no-resolve` 无法触发本地 DNS 解析，请求直接掉入末尾 `FINAL` 走香港 IEPL 专线，使国内前端组件在香港折返跑造成抖音评论区图片转圈与界面偶发卡顿；
    - **真机实测验证**：用户在手机 Loon 本地规则添加 `DOMAIN-SUFFIX,bytecdn.com,DIRECT` 与 `DOMAIN-SUFFIX,bytecdn.cn,DIRECT` 后，评论区图片卡顿感瞬间彻底消失，获得 100% 客观实证；
    - **最高准则落地与重大战略定调**：
      - 回归项目最高铁律：**“稳定使用 > 减少人工 > 易维护 > 极端场景完善。不要为了理论上的极端安全性，去牺牲日常使用的便利性。”**
      - 深刻复盘：带 `no-resolve` 是在追求理论上“0 DNS 泄漏”的极端洁癖，但代价是规则库必须 100% 完美无缺，否则任何一个未收录的国内边缘 CDN 都会掉入代理造成卡顿，逼迫用户陷入“持续抓包打补丁”的无限内耗；
      - 决策落地：明确在客户端配置中，将 `China-GeoIP` 从 `GEOIP,CN,DIRECT,no-resolve` 切换为 `GEOIP,CN,DIRECT`（去掉 `no-resolve`，恢复主动触发 DNS 反查）。由于主流海外服务在顶层早已被域名代理规则优先截胡，漏网流转到底部的绝大多数国内边缘节点经本地 DNS 查验为 CN IP 后将自动走 DIRECT 直连，真正实现**“日常使用无感，彻底终结频繁修补”**；
    - **编译与规则条数**：`rules/custom/China-Direct.list` 中精准补齐 `bytecdn.com` 与 `bytecdn.cn`；经 `build.py` 编译，`dist/China-Direct.lsr` 由 595 条增至 597 条（净增 2 条），全库总有效规则达到 **21,205 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `c7e7c7f15028`）；
    - **全量门禁与账本闭环**：`check_conflicts.py --strict` PASS（0 跨界冲突），`test_rules` 44/44 PASS，`test_diagnostic.js` 19/19 PASS，`verify_mirrors --pre-release` PASS；决策全量写入 `history/decisions.jsonl`（2 APPROVED）。
  * **Phase 1.5 联合审定清单合入 (Phase 1.5 T5 Consensus Ingestion)**：
    - **背景与共识来源**：严格以 `E:\Document\ChatGPT\Loon-Migration\config-review-2026-10-03\CHATGPT-REVIEW-FOR-DEEPSEEK-2026-10-03.md` 末尾“ChatGPT 最终确认与 Gemini 执行交接”及 DeepSeek T5 清单为准，双方达成一致，零待决分歧；
    - **规则层修改**：在 `rules/custom/China-Personal.list` 中合入 31 条 `DOMAIN-SUFFIX` 规则（25 条本地补充候选 + 6 条微博与中国移动专项来源子集，独立注释来源及核验日期 2026-10-03，披露 `139.com` 整域多业务历史共存风险），保持 100% 策略中立；
    - **DNS 层修改**：在 `plugins/Loon-China-DNS.lpx` 的 `[Host]` 下合入 20 条非 `.cn` 域名的阿里极速 DNS（`*.域名 = server:223.5.5.5`）分流映射，其余 11 条 `.cn` 域名由现有 `*.cn` 通配覆盖不重复添加；
    - **排除边界执行**：严格排除 `pa18.com`、`jk.cn`、`aliexpress.com`、`ctyun.cn`、`ninebot.com`、`mi.com`、`aqara.com`、`narwal.com`、`asus.com`、`microsoft.com`、`xiaoheihe.cn`；`tb.cn` 按淘宝短链归属说明（非贴吧）；
    - **编译与规则条数**：经 `build.py` 编译，`dist/China-Direct.lsr` 由 597 条增至 628 条（净增 31 条），全库总有效规则达到 **21,236 条**，自动刷新 `dist/diagnostics/manifest.json`（版本签名 `36886f3290aa`）；
    - **全量门禁检验**：
      - `python scripts/build.py`：PASS
      - `python scripts/check_conflicts.py --strict`：PASS（0 跨界冲突与泄漏）
      - `python -B -m unittest scripts.test_rules`：44/44 PASS
      - `node --test tests/test_diagnostic.js`：19/19 PASS
      - `python -B -m unittest scripts.test_score_engine`：4/4 PASS
      - `python scripts/verify_mirrors.py --pre-release`：PASS
    - **私人配置与回退锚点交付**：在 `E:\Document\ChatGPT\Loon-Migration\config-review-2026-10-03\` 装配 `Loon-v2-19Rules-candidate-2026-10-03.lcf` 与 `Loon-v2-19Rules-rollback-1e498f3.lcf`（回退锚点锁定提交 `1e498f3bbcffbbb5e67179d10f4af63bec5b7753`）；两份文件的结构、本地匹配与FINAL检查部分通过（PARTIAL_PASS / UNVERIFIED_PLUGINS，36个启用插件的运行时注入未验证）。两项固定回退资产另经独立取回核对，HTTP 200且SHA256与真实Git对象一致；手机当前加载及实际体验尚未验收；
    - **追溯事实闭环**：31 条规则事实与披露录入 `history/decisions.jsonl`（31 APPROVED）。
  * **vegslb.com 定向配套试行执行记录 (Targeted Paired Trial - 2026-10-04)**：
    - **背景与共识来源**：严格依据 `E:\Document\ChatGPT\Loon-Migration\config-review-2026-10-03\CHATGPT-EXECUTION-REVIEW-FOR-DEEPSEEK-2026-10-03.md` 第十八节（`CHATGPT-DEEPSEEK-VEGSLB-CONSENSUS-FINAL`），针对真机访问同一目标多次经代理无下行且用户报告偶发卡顿现象，实施最小范围定向配套试行（直连分流 + 国内 DNS 映射）；明确不推断底层未经验证的握手/报文机制；
    - **规则层修改**：在 `rules/custom/China-Personal.list` 增加 `DOMAIN-SUFFIX,vegslb.com`（注释标注字节/火山相关域名定向试行），保持 100% 策略中立；
    - **DNS 层修改**：在 `plugins/Loon-China-DNS.lpx` 的 `[Host]` 增补 `*.vegslb.com = server:223.5.5.5` 国内极速 DNS 配套映射，不补裸域；
    - **决策账本记录**：在 `history/decisions.jsonl` 登记人工覆盖 shadow simulated_block 试行记录，`verified` 严格保持 `false`（不触发 Hard Pass 免检），明确标注“批准试行，非效果验证完成”；两项时间字段校正为显式时区 `2026-10-04T03:50:00+08:00` 与 `2027-04-02T03:50:00+08:00`（相差 180 天）；其余 82 条历史时间准确性尚未逐条核验，本次保留原值；
    - **编译与规则条数**：`dist/China-Direct.lsr` 由 628 条增至 629 条（净增 1 条），全库有效规则达到 **21,237 条**，自动更新 `dist/diagnostics/manifest.json`；
    - **全量门禁验证**：
      - `python scripts/build.py`：PASS
      - `python scripts/check_conflicts.py --strict`：PASS（0 跨界冲突与泄漏）
      - `python -B -m unittest scripts.test_rules`：44/44 PASS
      - `node --test tests/test_diagnostic.js`：19/19 PASS
      - `python -B -m unittest scripts.test_score_engine`：4/4 PASS
      - `python scripts/verify_mirrors.py --pre-release`：PASS
    - **验证状态与真机边界**：工程发布门禁已通过；手机当前加载及实际使用体验尚未验证（需用户在手机更新规则与 DNS 插件后正常使用 1~2 天反馈是否有改善）；根域 DNS 匹配语义待核验；
    - **回退方式**：若试行无改善或出现退化，仅撤销本轮两项增量（`vegslb.com` 规则及 DNS 映射）并重新构建发布即可，无需回退整套旧配置，保留此前 31/20 成果。


  * **jspcdn.cn 直连补丁执行记录（2026-10-04，ChatGPT/Codex）**：
    - **原因与授权**：用户提供的最新Loon记录再次显示随机子域走FINAL、上传517B/下载0B，所有者明确要求本轮直接新增并推送。按根域收录，避免维护会变化的随机主机名；不声称已证明TLS/GSLB故障机制。
    - **实际改动**：China-Personal新增一条 `DOMAIN-SUFFIX,jspcdn.cn`，编译产物630条；全库从任务起点21,265增至21,266，其余18个规则集内容不变，未修改插件或私人配置。任务起点为 `07977b171a717e7f37243976978ebb8c3e6517a8`，可据此恢复本轮改动。
    - **DNS与业务边界**：保留现有 `*.cn = server:223.5.5.5`；Sentry、RevenueCat、nsloon及全局DoH、QUIC、节点、其他策略本轮不改。
    - **验证**：现有构建PASS；规则44/44、严格冲突检测PASS、诊断19/19、评分4/4、预发布完整性PASS；manifest内容版本 `e994fdff4578`。账本新增人工授权记录并保持 `verified=false`，未把工程通过等同手机验收。
    - **交接与下一步**：详细事实只保存在本仓库；Hub仅更新该项目一条摘要和既有事实源指针。手机只更新China-Direct并重连，正常使用反馈；国内IP兜底与截图目标IP语义继续待核验。若退化，只撤本轮jspcdn规则、记录回退决策并重新构建发布，保留此前31/20和vegslb成果。


  * **国内 IP 兜底与抖音覆盖核查（2026-10-05，ChatGPT/Codex）**：
    - **源码与发布核验**：公开 China-GeoIP 主备源均 HTTP 200、内容一致且与本地一致（SHA256 `f82ff8b59a190bfced6dfa5d56c9a996ba0af2c03194e572b4a96628d6aeb802`），含 `GEOIP,CN`、覆盖截图 IPv4 的 `119.144.0.0/14`；当前公开 China-Direct 已含 jspcdn.cn。排除当前公开规则源缺项或404，不能据此证明手机缓存已加载。
    - **归档配置与验收边界**：10月3日导出的 fixed 配置及候选配置均启用 China-GeoIP 并绑定 DIRECT；重新运行已有脱敏工具仍为 `PARTIAL_PASS / UNVERIFIED_PLUGINS`。模拟器 `match_target` 将域名与 IP 分开处理、不执行域名 DNS 查询，IP 样例命中不能证明域名请求的运行时兜底有效。
    - **解析核查事实**：本轮通过阿里及 Google 的 HTTPS DNS 分别查询截图主机，A 均无地址、AAAA 均返回 `240e:978:b33:102::100`，该 IPv6 也被当前 China-GeoIP 覆盖。归档当前/候选/旧自动配置均包含 `ip-mode = v4-only` / `ipv6-vif = off`；本轮结果不是截图时的 DNS 快照，未证明配置字段在手机的实际效果，也不能据此认定唯一根因或新配置回归。
    - **覆盖核查事实**：审计时生产使用的 blackmatrix7 DouYin.list 现为13条；RULE_DESIGN列为必须覆盖的 iesdouyin.com 审计时无域名命中（本批后续已补齐，手机效果未验收）。Loyalsoldier已缓存参考源另列 bytegeckoext.com / tlivegslb.com，而生产域名层未覆盖；候选缺项不等于必然落FINAL或故障。blackmatrix7 ByteDance大清单包含 larksuite.com / larksuitecdn.com 等国际服务，本轮未整包引入。
    - **处理与下一步**：本轮只记录已确认的调查事实，保留已发布 jspcdn 补丁及既有31/20与vegslb成果；未改规则、DNS、IP模式、插件或私人配置。下一步核对手机实际加载与IP模式，再对明确国内服务做有限覆盖补正；不要求用户反复抓包，不机械删除全部 no-resolve 或按截图相同IP批量改直连。

  * **GlobalSign 与淘宝验证码核查、精确域名调整（2026-10-05，ChatGPT/Codex）**：
    - **原因与授权**：所有者报告正常浏览淘宝时突然弹出滑块验证，查看同期网络记录时只注意到 secure.globalsign.com:80 落 FINAL，并明确要求该主机直连。GlobalSign官方证书资料列出该主机的证书下载链接；荣耀官方支持将VPN、公共网络、多地域登录等列为淘宝验证可能的风控场景，阿里云验证码文档说明会评估IP、设备与行为。上述一般机制不能证明本次验证码由证书流量造成。
    - **范围与恢复**：只新增一条 `DOMAIN,secure.globalsign.com`；China-Personal 62→63，China-Direct 630→631，全库21,266→21,267；其余18个规则集、插件、DNS、QUIC、私人配置不改。任务恢复起点 `b196154d7b08c3644d76ef778b13dadbe4a409fb`，回退只撤本条并重建。
    - **证据依据**：[GlobalSign官方证书下载](https://valid.r1.roots.globalsign.com/)；[荣耀官方淘宝验证说明](https://www.honor.com/cn/support/content/zh-cn15834860/)；[阿里云验证码信息采集](https://help.aliyun.com/zh/captcha/captcha2-0/product-overview/captcha-2-0-collection-letter-description)。当前淘宝 taobao.com、alicdn.com、alipay.com 已有国内分流规则，不能用仓库覆盖代替手机实际加载结论。
    - **验证与下一步**：构建PASS、规则44/44、严格冲突检测PASS、诊断19/19、评分4/4、预发布完整性PASS；精确主机命中与其他GlobalSign主机排除均通过，其余18个规则集内容保持不变，manifest内容版本 `b3eb6329956f`。账本85条解析通过、原84条记录保留，新增记录verified保持false。手机只更新China-Direct并重连后正常用；不把验证码是否消失当作单次因果证明，不要求用户统计或抓包。

  * **国内常用服务上游覆盖审计（2026-10-05，ChatGPT/Codex；合并淘宝与后续扩展核查）**：
    - **快照与接入事实**：项目核查基线 `c33db3312a7f3d2360b485d7bff584d0575e20e4`，与实时远端一致；对应GlobalSign发布CI Run #77（ID `37247045782`）已完成success。上游固定快照 `5a61490ab88ddaff4e9dbd7740b881d75157a49f` 的[Alibaba README](https://github.com/blackmatrix7/ios_rule_script/blob/5a61490ab88ddaff4e9dbd7740b881d75157a49f/rule/Loon/Alibaba/README.md)推荐 Alibaba.list 与 Alibaba_Domain.list 共同使用；sources.yml 仅声明前者，来源锁为57、min_rules为50。
    - **逐条结果与格式边界**：Alibaba.list 实际为3条DOMAIN-SUFFIX、53条IP-CIDR、1条IP-CIDR6，全部57条在当前产物原样保留；未发现该文件编译丢条。配套1263条均为 `.域名`，按后缀语义与全19个规则集对照，21项已有China-Direct覆盖（20项精确同名、userimg.qunar.com由qunar.com包含），其余1242项无域名规则命中；独立对照与既有模拟器结果一致。现有clean_rule_line对原始1263行均报INVALID_SYNTAX，转换为DOMAIN-SUFFIX后可解析，不能仅追加URL完成接入。
    - **业务证据与因果边界**：[淘宝官方小程序域名管控](https://developer.alibaba.com/docs/doc.htm?articleId=120157&docType=1&treeId=634)列出tbcdn.cn、taobaocdn.com、mmstat.com等资源/请求域名；[阿里云验证码客户端FAQ](https://help.aliyun.com/zh/captcha/captcha2-0/user-guide/captcha-2-0-client-access-faq)列出captcha-open、static-captcha、cloudauth-device等客户端接口，当前部分缺域名覆盖，但没有本次淘宝实际调用证据。Loon[官方匹配说明](https://nsloon.app/docs/Rule/)表示域名未命中后仍可进行DNS/IP匹配，离线无域名命中不等于手机必走FINAL；验证码资源加载失败与触发滑块也不能混为因果。GlobalSign精确域名调整仍不作为已确认验证码修复。
    - **扩展核查与独立验证**：扩展核查基线 `6fb453da9a855a2947fdd5b33014ec1d2bc73c2c`，沿用同一上游提交，对22组目录共46个文件核对字节长度、SHA256和Git blob身份；5856条上游域名规则与19个公开产物逐条比较，并经独立精确/后缀/关键词匹配复核全部一致。微信30、抖音13、京东249、B站115条参考域名规则均获China-Direct覆盖；微信6条没有原样保留的精确域名已被qq.com后缀包含，未发现已声明源的域名编译丢条。
    - **新确认的覆盖边界**：腾讯与字节集团目录均未在来源配置声明，微信/抖音README允许独立使用，不能把集团扩展未纳管误称为其必需配套遗漏。[QQ音乐官网](https://y.qq.com/)HTTP 200页面实际引用y.gtimg.cn图片；当前gtimg.com不能覆盖gtimg.cn。iesdouyin.com在字节参考目录及RULE_DESIGN中存在，其官网重定向douyin.com；审计时无域名覆盖（本批后续已补齐，手机效果未验收）。抖音主要图片/静态/视频域douyinpic/douyincdn/douyinstatic/douyinvod已覆盖，字节补充参考域与网易云音乐、小红书等另有差项，详见待办16。集团目录含海外飞书、国际会议、游戏及云客户域，不能整批直连；目录差异不证明手机FINAL或故障因果。
    - **审计资产与处理**：扩展报告与公开证据保存于 `E:\Document\AI-Workspace\loon-rules\2026-10-05-domestic-coverage-audit\01-常用国内服务上游覆盖审计.md`（附逐条CSV、快照与哈希，不将成套材料提交公开仓库）。本轮只更新事实源与同步摘要；此前淘宝核查已纠正表格计数，扩展核查未改规则、DNS、账本、manifest、构建器或私人配置。报告中的tlivegslb.com来源归类只作线索，真实业务边界尚未确认。
    - **下一步与恢复**：按国内资源、图片/音乐接口与验证服务审定有限清单，排除国际业务及公有云整域，单批发布、正常使用反馈，不要求所有者逐App抓包。Hub地图与正式事实源路径未变，无需复制详细状态；本轮文档恢复起点为扩展核查基线，不回退既有功能增量。

  * **常用App全清单核查与具体候选方案（2026-10-05，ChatGPT/Codex；生产未改）**：
    - **目标与证据**：将淘宝/腾讯/字节扩展核查扩到所有者原清单的63项（包含银行类别和boss别名）及26项扩展候选；同一上游提交 `5a61490ab88ddaff4e9dbd7740b881d75157a49f` 的54组参考、110文件Git blob身份、6834条域名对照经独立复核。公开页面60次取回记录（54次保存响应正文、6次失败或异常，含HTTP错误），118项资源引用；页面证据不等于App接口或真机体验验收。
    - **新增确认事实**：北京一卡通AppStore开发者网站/隐私使用bmac.com.cn，国家网络身份认证公安部App条目隐私链接cdnrefresh.ctdidcii.cn，均无现有域名覆盖；多个常用服务官网另有窄资源缺项。12306/银行/滴滴/携程等专用目录含其他或国际业务，不能整包直连；旧矩阵存在过时准入状态及过度体验保证，执行时须按真实规则状态修正。
    - **方案调整与最终验证**：初始22/10加两个有限来源的原型仅为旧方案证据；经两方审核改为21条纯本地规则＋9条DNS，不捆绑来源或编译器改造。ndstatic.cdn.bcebos.com因既有BLOCK/ENTIRE_DOMAIN_TREE及HARD_BLOCK排除，不允许reason备注绕过；其余21条评分处于CONFIDENCE_SCORE，人工共识不是自动放行，实施账本须verified=false。最终候选使用现有剪枝/模拟器预演631→652、无旧规则删除，正例和窄边界/国际反例通过；95＋9条Host无重复。（注：当时未进行正式build、全量发布门禁或手机验收；完整21/9与证据见待办16；后续具体实施与质量门禁见下条“Gemini 执行收尾”记录）。
    - **处理与恢复**：本轮只将最终共识与待实施状态合并进PROJECT_STATE及AI_HUB_SYNC（为共识达成时的状态快照）；92个受保护生产文件SHA256与原核查相同，规则、DNS、来源、账本、manifest、构建器与私人配置未改。Gemini执行本批前重新核对真实基线并设一次恢复起点，发布后仅更新两项资产并正常用；无明显改善不默认撤整批，退化时按相关增量单点恢复，保留31/20及既有补丁。本轮审核收尾的文档恢复起点 `84fa95b16cab38414a96ac817028d0196fad3404`；Hub地图/单一事实源归属不变。

  * **国内常用服务 21 条直连规则 + 9 条配套 DNS 实施发布与收尾（2026-10-05，Gemini 执行收尾）**：
    - **任务依据与范围**：严格依据 `08-ChatGPT-最终共识与Gemini执行交接.md` 清单执行；纯本地增补 21 条规则至 `rules/custom/China-Personal.list`，9 条 DNS 映射至 `plugins/Loon-China-DNS.lpx` 的 `[Host]`；严格排除 `ndstatic.cdn.bcebos.com` 及百度云整域，不整包引入大厂目录。
    - **资产与缓存快照**：China-Personal 63 → 84 (+21)；China-Direct 631 → 652 (+21)；19 规则集总规则数 21,267 → 21,288 (+21)；Host 映射 95 → 104 (+9)；决策账本 85 → 106 (+21，全部 verified: false，复查周期 180 天)；manifest 内容版本 `7635cc51f7d7`；其余 18 个规则集内容保持不变。披露已跟踪缓存刷新：`7871aa32a3ea6248.list` 从 19,230 刷新至 19,258 行，来源锁未改，China-GeoIP 发布集合仍为 19,244 条，无需回退缓存。
    - **提交、CI 与公开资产核验**：发布提交为 `8de8544ecfa3741e4fb12a5a15e0312f238b8c1c`；远端 GitHub Actions 发布 CI Run #78（ID `37328009178`）与收尾 CI Run #79（ID `37334476097`）核验成功（completed / success）；公开主、备产物取回核对通过（SHA256 一致，见 09 号证据）。
    - **测试守护补强与维护指引收尾（F1/F2/F3 与 12 号补正）**：
      - 测试补强（F3）：对 `test_45_domestic_plan_21_9_boundaries` 补充真实匹配模拟（复用 `simulate_hit` 的 `load_dist_rules` 与 `match_target`）与严格负向边界断言（动态覆盖全部 14 项精确主机的 probe 子域隔离、未批准同族主机、禁止的共享云反例，并以内存突变规则验证断言灵敏度）；移除对账本 21 条永久 `verified: false` 的锁定，保留 APPROVED 决策与 boolean 类型断言，确保合法未来验证不被误阻；
      - 文档校正（F2）：消除 `docs/app-audit-matrix.md` 中缺乏真机证据的过度体验断言（改为“规则与DNS已收录，相关效果待观察”）；将 `docs/China-Personal-Matrix.md` 中 9 处常规“抓包”要求降级为维护者低负担标准指引（AI 先核对现有规则与公开资料，确需手机证据才给出单次低负担步骤）；
      - 汇报校正（F1）：澄清 `ctrip.com`、`c-ctrip.com`、`fliggy.com`、`alitrip.com`、`variflight.com`、`feeyo.com`、`139.com` 等 7 项为 Phase 1.5 既有保留规则而非本批新增；校正新增 9 条 DNS 清单（排除已有全域规则覆盖的 `*.cn`，真实映射指向阿里极速 DNS）。
    - **真机边界与恢复**：手机端实际加载与日常使用体验仍未验收（保留待日常使用反馈确认）；若出现退化或异常，按增量条目单点回退并重新构建，保留既有 31/20 及前序补丁成果。

---

## 附：所有者偏好合入记录（2026-10-04）

- **变更性质**：规则与文档级变更（合入《所有者偏好与项目执行规则》母版适用条款），**非功能或服务实测**。
- **母版来源**：`AI-HUB/templates/OWNER_PREFERENCES.md`，导入版本 `2026-10-04 / v1`。
- **本次改动**：`AGENTS.md` 追加“所有者偏好（母版合入内容）”一节；本文档追加本记录。
- **最小修正**：第五节存储口径更新为 E 盘优先并允许必要的系统盘缓存（原“禁止写入 C 盘/桌面”），其余红线不变。
- **未改动**：业务代码、生产配置、真实凭据文件的跟踪状态均未变更。
- **验证方式**：规则一致性人工核对（母版条款与既有规则逐条比对、去重合入）；无代码或服务实测。


---

## 附：收尾校正记录（2026-10-04）

- **变更性质**：规则文本校正（文档级），**非功能或服务实测**。
- **本次改动**：① 来源与版本标记移至文件顶部；② 收窄新增的“宁可不做，也不新增机制”表述——本文“零”节三问门槛**继续适用**于约束“新增机制”，但**不用于否决“为已实际发生的需求增加必要自动化”**。
- **未改动**：业务代码、生产配置、真实凭据文件的跟踪状态均未变更。

