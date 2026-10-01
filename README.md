# Loon Rules 分流规则集（策略中立・自动化维护・原生一键诊断）

本项目是一个公开、独立维护的 **Loon 原生分流规则与极速分流插件仓库**。
仓库秉持**“成熟上游覆盖为主、Custom 补丁为辅、策略严格中立、自动化防撞车门禁”**的原则，解决第三方聚合规则中常见的“规则粗暴混杂、AI 与普通服务交叉碰撞、Apple 生态易受干扰、海外 DoH 导致国内 CDN 跨洋漂移”等底层痛点。

> [!IMPORTANT]
> ### 🤖 AI 协作者与新开发者接手必读 (AI & Developer Onboarding Guide)
>
> 本项目已正式纳入 [AI-Project-Hub](https://github.com/o-ocn/AI-Project-Hub)（永久唯一标识：`repo:loon-rules`）全局项目地图纳管。当前工程状态唯一事实源请参阅 **[`PROJECT_STATE.md`](PROJECT_STATE.md)**；完整 AI 行为规范、四大铁律与自动交接流程请严格参阅 **[`AGENTS.md`](AGENTS.md)**。

---

## 核心设计准则与三层架构体系

本项目建立了一套高度工程化的**“规则路由层 + DNS 调度层 + 冲突防护层”**三层协同体系：

1. **第 1 层：规则路由层（Routing Layer・19 个策略中立规则集，共 21,158 条规则）**：
   - **职责**：决定网络请求“去向何方”（走 DIRECT 还是 PROXY）。
   - **成熟上游为主**：以 `blackmatrix7/ios_rule_script` (GPL-2.0) 为主要规则源，保障 Gemini、Telegram、Google Drive、Apple 等成熟服务规则的全面性与健壮度，不要求用户长期手动抓包补域名。
   - **策略绝对中立**：所有 `.lsr` 绝不写入用户策略组名称、地区（HK/US/JP）、节点名称或策略动作。用户在 Loon 中按需自由绑定专属策略组。
   - **8 大服务边界与防碰撞**：包含 Gemini 与普通 Google、YouTube 与 Google、Grok 与 Twitter、Muse from Meta 精准识别、TestFlight/Media 与 Direct 隔离等。
2. **第 2 层：DNS 调度层（Resolution Layer・国内大厂与区域 CDN 极速分流）**：
   - **职责**：决定 DIRECT 直连流量“找哪个就近边缘节点”（解决 IP 调度质量）。
   - **解决直连反向卡顿**：防范全局纯境外 DoH 导致国内 CDN（阿里 1688、抖音支付、App Store 静态图）被调度至美西或香港 Anycast IP，进而引发直连断崖式卡顿。
   - **精细化区域优化**：在 `plugins/Loon-China-DNS.lpx` 中为国内大厂及 Apple 静态资源 CDN（`*.mzstatic.com`）指定国内极速 DNS（`223.5.5.5`），实现毫秒级秒开；同时对 `apple.com`、`icloud.com` 保持严格隔离，绝不泛绑定。
3. **第 3 层：冲突防护层（Conflict & Boundary Guard・自动化 CI 强门禁）**：
   - **职责**：守卫生态边界，严防跨国孪生业务（抖音 vs TikTok、微信 vs WeChat）及 Apple 禁区打穿。
   - **规格化防撞车**：由 `shared_domains.yml` 明确定义共享基础设施与海外独占域名；由 `scripts/check_conflicts.py --strict` 执行双向审查，CI 自动化强拦截任何违规外泄。
4. **中国大陆冷启动与双镜像发布**：
   - 首次导入 `.lcf`，节点未就绪或 GitHub Raw 暂时不可达时，依靠本地 `[Rule]` 中的内网段旁路与必要直连规则维持基础联网。
   - 所有规则与插件均同步提供 Fastly jsDelivr 备用 CDN 镜像，保障高可用。
5. **零变更构建幂等性**：
   - 自动构建没有规则内容变化时，严格禁止修改发布文件、版本号、构建时间或 `manifest.json`，杜绝幽灵提交。
   - 下载失败、异常缩水、语法错误或冲突增加时，自动熔断并保留上一版成品。

---

## 规则订阅清单 (共 19 个独立服务分类)

| 规则成品 (`dist/`) | 涵盖核心服务说明 | 订阅链接 (GitHub Raw) |
| :--- | :--- | :--- |
| **`Apple-Push.lsr`** | APNs 官方最小推送通道（默认建议保持关闭，权威 10 条网段） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push.lsr) |
| **`AI-Overseas.lsr`** | ChatGPT, Claude, Gemini (含 iOS WebChannel), Grok, Muse from Meta | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr) |
| **`YouTube.lsr`** | YouTube 视频流媒体、图片与 CDN（排在 Google 前） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr) |
| **`GoogleDrive.lsr`** | Google Drive 云端硬盘专属服务（独立保护大流量，排在 Google 前） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr) |
| **`Google.lsr`** | 普通 Google 服务、搜索与基础设施（含共享 `www.googleapis.com`） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr) |
| **`OneDrive.lsr`** | Microsoft OneDrive 与 SharePoint 服务 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr) |
| **`Telegram.lsr`** | Telegram 官方 IP 段与核心域名通信 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr) |
| **`Twitter.lsr`** | Twitter / X 平台主干（不含 Grok） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr) |
| **`Discord.lsr`** | Discord 语音与即时通讯 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr) |
| **`PayPal.lsr`** | PayPal 官方支付运营域名（精选官方与备案域名，剔除钓鱼仿冒） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/PayPal.lsr) |
| **`Gaming.lsr`** | Steam 游戏平台与 Epic Games 商店（剔除第三方盗版、非平台分销站及客服SDK） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Gaming.lsr) |
| **`GitHub.lsr`** | GitHub 开发平台、API 与代码托管 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GitHub.lsr) |
| **`TestFlight.lsr`** | Apple TestFlight 内测分发平台 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/TestFlight.lsr) |
| **`Apple-Media.lsr`** | Apple TV+, Apple News, Fitness+ 锁区媒体 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media.lsr) |
| **`AI-China-Direct.lsr`** | DeepSeek、Kimi、通义千问、豆包等国内 10 家大模型 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr) |
| **`Apple-Direct.lsr`** | iCloud, CloudKit, App Store, Apple ID, HomeKit, 音乐, SystemOTA | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr) |
| **`China-Direct.lsr`** | 微信、淘宝、京东、闲鱼、抖音/字节国内生态、B站等高频应用 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr) |
| **`Lan.lsr`** | RFC 1918/6598/6890/2544/4291/4193 局域网与保留网段直连旁路 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Lan.lsr) |
| **`China-GeoIP.lsr`** | 中国大陆 IP 最终兜底保护（含 ChinaIPs IPv4/IPv6，排在 Lan 之后） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-GeoIP.lsr) |

*(备用 CDN 镜像列表详见 [`docs/migration_and_rollback.md`](docs/migration_and_rollback.md))*

---

## Loon 原生一键规则诊断插件

为了减少用户在遇到分流异常时反复手动抓包、逐项排查的负担，仓库内置了专用的 Loon 原生诊断插件。

### 1. 插件安装地址
在 Loon【插件】-> 右上角【+】填入以下 URL：
```text
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/LoonRules-Diagnostic.lpx
```
*(插件遵循 Loon 3.5.1+ Generic Script v2 规范，已正式集成发布于 `main` 分支；导入后即可在客户端直接使用)*

### 2. 极简日常使用流程
```text
打开 Loon
  ↓
点击底部【脚本】或【工具】标签
  ↓
点击“规则诊断(快速)”或“规则诊断(完整)”手动运行
  ↓
等待 3~8 秒，系统弹出通知并生成简短中文报告
  ↓
长按或全选复制简短报告（通常仅 10~15 行），直接发送给 ChatGPT 或 Gemini 审核
```

### 3. 日常诊断报告示例（紧凑精炼，异常即显）
```text
【Loon 规则与核心服务诊断报告】
诊断模式: 快速诊断 (核心规则与服务) | 生成时间: 2026-09-28 16:44:04 UTC
----------------------------------------
[✓] 发布源状态: 主备双源均可达且内容同版本一致 (GitHub + jsDelivr)
- 版本标识: 0b8b8e0be129 (构建时间: 2026-09-30T04:00:00Z, 清单: 19 个规则集)
----------------------------------------
[✓] 规则集校验: 全部 4 个规则集正文、条数与 SHA256 均校验通过 (版本: a1f362bd587f)
----------------------------------------
[✓] 服务连通性: 共探测 10 项服务，当前路由均可达 (其中 7 项仅当前路由可达, DIRECT不可达, 3 项双向均可达)
----------------------------------------
✔ 诊断结论: 已检测核心服务连通性均正常 (7 项仅当前路由可达/DIRECT不可达, 3 项双向均可达)；提示: 若服务可达但特定 App 仍异常，可能存在未收录的遗漏域名。 (耗时: 1.8s)
----------------------------------------
【能力边界提示 (需真机验证)】仅探测已知 HTTPS 端点，无法自动发现全部未知域名。若遇稳定异常，应先核对上游更新与规则；仅在仍无法定位时，方需提供一次本地脱敏请求记录。本插件不能探测 APNs TCP 5223，亦不能替代 Telegram 锁屏蜂窝推送、HomeKit 摄像头、Apple Watch 及 CloudKit 真机测试。
========================================
```
*注：当遇到部分服务不可达时，报告会列出异常项并提供中性建议（例如提示检查 Loon 命中规则或绑定的出口节点），不妄断“代理生效”或“节点故障”。*

### 4. 隐私保证与运行安全
* **100% 本机执行**：不读取或上传 Cookie、Token、Authorization、账号密码或设备标识。
* **零配置修改**：只读探测，绝不修改用户的策略组选择、代理节点、DNS、MitM 证书或运行模式。
* **纯手动触发**：不配置任何定时任务，只在用户手动点击时发起轻量只读请求。
* **时限保护与受控并发**：并发上限为 4，内置硬截止时限（快速 25s / 完整 50s）与安全看门狗，超时亦能安全产出部分简短报告并确保 `$done` 仅调用一次，杜绝被 Loon 异常强退。

---

## 本地辅助离线诊断工具

重要说明：**Loon 官方 Script API 未提供直接读取历史请求记录的接口**，因此仓库不提供也不存在“Loon 内一键导出历史请求日志”插件。日常运维请完全依托上述【Loon 原生诊断插件】复制短报告。
仅当遇到疑难跨分类杂糅排查时，用户可手动在 Loon 中导出 HAR 文件，并在本机运行以下离线分析工具：

### 1. 规则命中模拟器 (`scripts/simulate_hit.py`)
无需真机即可推演 Loon 顶层至底层的规则命中与覆盖逻辑：
```bash
python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com 17.249.1.5
```
* 支持域名及 IPv4/IPv6 CIDR 多阶段静态推演（Local Rule -> Remote Rule -> FINAL）。
* **自动识别并跳过** `enabled=false` 的未启用规则。
* 输出严格脱敏，不打印私人配置与动作。插件规则若未加载明确提示 `[未验证: 插件注入规则未加载]`。

### 2. 日志严格脱敏分析器 (`scripts/sanitize_log.py`)
离线分析 Loon 手动导出的 HAR 或纯文本日志：
```bash
python scripts/sanitize_log.py path_to_log.har
```
* **零敏感泄露**：严格校验时间格式（过滤伪造的时间戳及用户名），规则标签与策略标签使用严格白名单约束，绝不输出 `Authorization: Bearer`、私有设备 ID、节点密钥或 Cookie。
* **自动标出**：失败请求、FINAL 兜底、未收录新域名、大流量传输（>=5MB，如 Primuse 串流）、疑似跨集错误分类。

---

## 目录结构

```text
loon-rules/
├── .github/
│   └── workflows/
│       └── sync-and-build.yml     # 每周自动同步 upstream、严格测试、发版与 CDN 监控流水线
├── diagnostics/                   # 原生诊断插件源码
│   ├── LoonRules-Diagnostic.lpx   # Loon 诊断插件定义清单
│   ├── loon-rules-diagnostic.js   # 诊断核心脚本 (JS)
│   └── services.yml               # 诊断服务测试端点与真机标注配置
├── plugins/                       # DNS 分流插件源码
│   └── Loon-China-DNS.lpx         # 国内大厂与区域 CDN 极速分流插件
├── dist/                          # Loon 最终订阅的 .lsr 与发布产物
│   ├── *.lsr                      # 19 个独立服务分类规则文件 (共 21,158 条策略中立规则)
│   ├── plugins/
│   │   └── Loon-China-DNS.lpx     # 发布版 DNS 极速分流插件
│   └── diagnostics/
│       ├── LoonRules-Diagnostic.lpx
│       ├── loon-rules-diagnostic.js
│       └── manifest.json          # 规则版本、SHA256 校验值、包签名与服务清单
├── docs/                          # 详细运维与对照报告
│   ├── app-audit-matrix.md        # 中国大陆常用 App 与生态分流审计矩阵 (分流/DNS/排除边界)
│   ├── real-device-validation.md  # 真机验证记录与日常巡检底册 (日常使用追踪与异常 SOP)
│   ├── lcf_audit_report.md        # 原始配置脱敏与 Apple 规则清理对照报告
│   ├── policy_mapping.md          # 19 规则集策略映射与 [Remote Rule] 配置总表
│   ├── plugin_compatibility.md    # 外部插件兼容性与互操作指南
│   ├── apple_apns_test_guide.md   # Apple 生态与 APNs 权威推送验证指南
│   └── migration_and_rollback.md  # 逐组平滑迁移步骤与分步回滚方案
├── rules/
│   └── custom/                    # 个人自定义规则（最高优先级，新域名补丁与来源追踪注释）
├── scripts/
│   ├── build.py                   # 规则拉取、清洗、去重与 manifest 签名生成引擎
│   ├── check_conflicts.py         # 跨国孪生业务与 Apple DNS 禁区防撞车检测器 (--strict)
│   ├── test_rules.py              # 自动化单元测试套件 (43 项测试，含多阶段仿真与故障注入)
│   ├── verify_mirrors.py          # 交付物哈希自校验、预发布强门禁与 CDN 健康探针
│   ├── verify_private_lcf.py      # 本地脱敏私人配置结构与隐私验收工具
│   ├── simulate_hit.py            # 4 阶段离线规则命中模拟器
│   ├── sanitize_log.py            # 日志脱敏分析器
│   └── upstream_lock.json         # 各上游有效规则数锁定基线
├── tests/
│   ├── test_diagnostic.js         # 诊断插件 Node.js 本地离线测试套件 (19 项测试)
│   └── fixtures/                  # 公开、脱敏的测试夹具 (含 sample_order_19.fixture)
├── shared_domains.yml             # 跨国孪生业务共享基建、独占域名与 DNS 禁区规范清单
├── sources.yml                    # 声明式只读上游来源配置
├── requirements.txt               # Python 依赖 (pyyaml)
├── PROJECT_STATE.md               # 项目当前工程进度唯一事实源 (Single Source of Truth)
├── AGENTS.md                      # AI 协作者与开发者接手规则
├── RULE_DESIGN.md                 # 规则系统、DNS 解耦与跨国业务隔离核心设计规范
├── README.md
└── LICENSE                        # 完整 GPL-2.0 授权文本
```

---

## 本地构建与全量测试验证

接手本项目后，推荐运行以下命令完成本地环境准备与 100% 离线自测：

```bash
# 1. 安装基础依赖 (仅需 pyyaml)
pip install -r requirements.txt

# 2. 编译规则集并生成诊断 manifest (构建幂等性，无变更时不产生幽灵提交)
python scripts/build.py

# 3. 运行 Python 规则完整性与防撞车测试套件 (全量 43 项测试通过)
python -B -m unittest scripts.test_rules

# 4. 运行跨国孪生业务与 DNS 禁区严格防碰撞校验 (零未授权碰撞)
python scripts/check_conflicts.py --strict

# 5. 运行诊断插件 Node.js 离线全量测试套件 (全量 19 项测试通过)
node --test tests/test_diagnostic.js

# 6. 运行发布前本地完整性强门禁 (校验 19 规则集、诊断产物与全包签名)
python scripts/verify_mirrors.py --pre-release
```

---

## 许可协议与致谢

* 本项目遵循 **GPL-2.0** 协议开源，完整文本见 [`LICENSE`](LICENSE)。
* **上游数据同步声明**：当前实际自动同步 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的开源规则集，严格遵循其 GPL-2.0 开源许可；[luestr/ShuntRules](https://github.com/luestr/ShuntRules) 仅作结构参考，不复制其未授权规则。
