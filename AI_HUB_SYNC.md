# AI-Project-Hub 项目发现与同步入口 (AI_HUB_SYNC.md)

> 📌 **项目唯一标识**：`repo:loon-rules`  
> 🔗 **Hub 管理中心**：[AI-Project-Hub](https://github.com/o-ocn/AI-Project-Hub)  
> 🏠 **本项目独立仓库**：[o-ocn/loon-rules](https://github.com/o-ocn/loon-rules)  
> 📖 **独立详细单一事实源 (SSOT)**：[`PROJECT_STATE.md`](PROJECT_STATE.md)  
> 🤝 **AI 协作者行为规范**：[`AGENTS.md`](AGENTS.md)  
> ⏱ **最新同步时间**：`2026-10-02`  
> 🏷 **当前项目阶段**：`Phase 0.5 - Shadow Audit & Daily Observation`（旁路影子审计巡检与真机日常静默观察期）

---

## 一、项目目标

本项目旨在构建并维护一套高可靠、高质量、策略中立、自动化质量守护的 **iOS Loon 原生分流规则库（`.lsr`）** 及 **原生一键诊断插件（`.lpx`）**。

### 1. 核心解决的问题
- **根除国内大厂与高频 App 代理绕路**：微信、淘宝、京东、抖音/字节生态、B站、拼多多、美团、百度，以及全国六大行和股份制商业银行等金融支付服务，因上游规则滞后、USER-AGENT 失效或域名漏判而错误跌入 `FINAL` 走海外专线，引发跨洋折返跑、高延迟、白块卡顿或银行风控拦截；
- **保障海外核心服务不被错误直连**：严密守卫 Apple/iCloud、Google、OpenAI、Telegram、Twitter/X、Discord、GitHub 等海外基础设施与锁区媒体边界，避免海外独占域名被国内直连规则污染；
- **平替不受控的外部黑盒规则**：彻底替代旧版 15+ 外部远端订阅源，消除上游滞后、钓鱼域名混杂及劫持风险；
- **分流规则与出口策略彻底解耦**：规则文件保持 100% 策略中立，不写入任何策略组或出口偏好；出口指派完全归属用户在 Loon 客户端的主权。

### 2. 最终目标
实现一套兼具**精准直连体验**、**海外安全分流**、**自动化影子风险审计**与**真机自诊断闭环**的免人工深度维护体系。

---

## 二、当前状态

- **当前阶段**：`Phase 0.5 - Shadow Audit & Daily Observation`
- **已完成工作**：
  1. **规则架构定型**：定型为 **19 个独立规则集**（共 **21,166 条有效规则**），全量编译于 `dist/`，主备双源（GitHub Raw / jsDelivr CDN）校验通过；
  2. **三层架构闭环**：
     - **规则路由层**：19 个策略中立规则集，细分服务排在宽泛服务之前；
     - **DNS 调度层**：`plugins/Loon-China-DNS.lpx` 分流阿里极速 DNS（223.5.5.5），确保国内 CDN 就近秒开；
     - **防撞车防护层**：`shared_domains.yml` 与 `scripts/check_conflicts.py --strict` 自动化守卫边界，杜绝海外域名泄露；
  3. **原生诊断插件**：`dist/diagnostics/LoonRules-Diagnostic.lpx` 与 JS 引擎就绪，支持 Loon 3.5.1+ Generic Script v2 双模式极速自检；
  4. **Phase 0 旁路影子审计流水线**：
     - 只读拉取多上游，经 `score_engine.py` 进行 `AUTO_PASS / REVIEW / BLOCK` 三态裁决；
     - 接入 `.github/workflows/shadow-audit.yml` 每日自动巡检，零生产侵入，智能消除 Git 空提交；
  5. **常态化应用审计矩阵**：建立 [`docs/app-audit-matrix.md`](docs/app-audit-matrix.md) 纳管 18 类高频应用边界与红线；
  6. **三批真机日志补丁精准合入**：
     - 第一批：一键免密认证 (`cmpassport.com`)、点评图床 (`dpfile.com`)、中国联通 (`10010.com`)、百度静态 (`bdstatic.com`)、央视频图床 (`cctvpic.com`)；
     - 第二批：Apple 固件/附加组件 OTA 目录 (`gdmf-ados.apple.com`)、抖音边缘 CDN (`zzcdnx.com`)；
     - 第三批：中国大陆百科服务 (`baike.com`)；
     - 决策追溯账本 [`history/decisions.jsonl`](history/decisions.jsonl) 完整闭环；
  7. **测试套件解耦**：`scripts/test_rules.py` 条数断言改为动态比对 `manifest.json` 规则集条数之和并守卫安全底线，消除后续技术债。
- **正在进行**：
  - 1~2 周日常使用真机静默稳定观察期；
  - 2~4 周 Phase 0.5 旁路影子巡检定时观察期。
- **当前暂停 / 阻塞项**：
  - **生产规则自动接管处于绝对冻结状态**：Phase 0/0.5 期间严禁自动将上游候选放行至生产规则库；
  - **隔离池待审项**：`qrstuvwxyzab.com`（疑似七牛云电信 IPv6 PCDN 动态反向映射）暂缓合入，保留在隔离池观察；
  - **最终私人配置装配**：等待用户在本地通过 ChatGPT Work 基于最新手机导出配置装配为唯一正式 `.lcf` 文件。

---

## 三、历史记录与关键决策

| 决策编号 | 决策内容 | 简要原因 |
| :---: | :--- | :--- |
| **01~03** | 规则与策略彻底解耦；自研原子化暂存构建流水线；发布镜像主备源校验 | 确保规则 100% 策略中立；构建过程防崩溃防截断；防范 CDN 单点故障与缓存投毒 |
| **04~06** | 引入成熟 GPL-2.0 `ChinaIPs`（19,209 条）；Gaming 与 PayPal 独立为专有规则集 | 解决纯 IP 直连因单条 GEOIP 失效跌落 FINAL 的痛点；消除 Steam 404 与海外支付钓鱼规则污染 |
| **07~09** | 阿里极速 DNS（223.5.5.5）分流国内 CDN；国内主流商业银行全量纳管；严禁海外服务泛解析 | 解决境外 DoH 引发的跨洋反向卡顿；根除银行与支付风控拦截；守卫 Apple/Google 境外调度红线 |
| **10~12** | 原生诊断插件定型 Generic Script v2；建立常态化应用审计矩阵；用户全局存储规范 | 消除外部依赖，15 行紧凑中文短报告；消除盲目扩充风险；严禁向 C 盘或桌面写非必要文件 |
| **13~15** | Phase 0 旁路影子审计方案确立；决策追溯账本规范化；接入 GitHub Actions 定时巡检 | 生产与审计双轨物理隔离；每次放行均有客观证据链；每日巡检严格消除 Git 空提交 |
| **16** | Phase 0.5 首批人工审核补丁（5 APPROVED + 1 REJECTED） | `cmpassport`/`dpfile` 等高置信基建入库，严格拒收 `cctv.com` 涉外泛域名 |
| **17** | Phase 0.5 第二批真机抓包补丁（2 APPROVED + 1 REJECTED）与单测断言解耦 | 精准修复 `gdmf-ados` 61s 超时与 `zzcdnx` 卡顿；暂缓七牛云 PCDN；单测解耦动态适配条数 |
| **18** | Phase 0.5 第三批真机抓包补丁（1 APPROVED） | 修复 `baike.com` 因 `China-GeoIP` 带 `no-resolve` 未命中域名规则而跌入 FINAL 代理折返跑 |

---

## 四、当前问题、已知风险与待确认事项

### 1. 未解决问题与待确认事项
- [ ] **qrstuvwxyzab.com 隔离池核验**：持续核验其解析 IP 是否严格局限在大陆电信 IPv6/IPv4 段，排查多租户借道与海外边缘节点污染风险后再做决策；
- [ ] **私人正式配置本地装配**：待用户使用本地环境完成新导出 `.lcf` 的规则顺序对准。

### 2. 已知风险与真机环境边界
- **离线测试边界**：离线单测无法替代真机真实环境中的 APNs TCP 5223 绕行、HomeKit 硬件推流与 Apple Watch 独立蜂窝测试；
- **第三方插件未验证状态 (UNVERIFIED)**：诊断插件对第三方插件规则注入标记为 `UNVERIFIED`，不给出虚假全通；
- **蜂窝网络 IPv6 绕过**：运营商双栈网络下底层连接可能直连逃逸；
- **长连接保活心跳**：部分节点对空闲 TCP 设置超时断开可能导致推送延迟。

---

## 五、下一步计划（AI 接手执行指南）

任何后续接手本项目的 AI Agent，必须严格按以下顺序执行：

### 1. 接手必读与状态核对
1. 首先阅读根目录 [`PROJECT_STATE.md`](PROJECT_STATE.md)（唯一详细事实源）；
2. 阅读 [`AGENTS.md`](AGENTS.md) 了解行为规范与禁忌；
3. 检查当前 `git status`，确认工作区 clean。

### 2. 推荐执行步骤
- **第一优先级（保持观察期纪律）**：
  * 当前处于静默观察期，**严禁主动发起大规模上游规则扫描，严禁修改 `build.py` 生产逻辑**；
  * 保持节奏：**“真机出现一个 $\rightarrow$ 验证 $\rightarrow$ 精准合入 $\rightarrow$ 观察”**，杜绝一次性盲目合入几十条规则。
- **第二优先级（日常真机日志分析流程）**：
  * 若用户提供新的真机 FINAL 截图或脱敏日志，按标准 4 步法输出：
    1. **问题描述**（明确现象与请求域名）；
    2. **排查证据链**（当前规则状态、目标 IP 归属、上游收录、DNS/CDN 分流情况）；
    3. **修改建议**（精准匹配 `DOMAIN` 或 `DOMAIN-SUFFIX`）；
    4. **风险分析**（收益评估、客观描述潜在风险，避免绝对化夸大词汇）。
  * 经用户明确确认后，方可写入 `rules/custom/` 与 `history/decisions.jsonl`。
- **第三优先级（合入后闭环验证与自动交接）**：
  * 运行 `python scripts/build.py` 编译产物；
  * 执行全部 5 门质量门禁：
    1. `python -B -m unittest scripts.test_rules`
    2. `python scripts/check_conflicts.py --strict`
    3. `node --test tests/test_diagnostic.js`
    4. `python -B -m unittest scripts.test_score_engine`
    5. `python scripts/verify_mirrors.py --pre-release`
  * 运行 `python scripts/audit_pipeline.py` 同步更新影子审计报告；
  * 更新 `PROJECT_STATE.md` 与本文件 `AI_HUB_SYNC.md`；
  * 执行 `git commit` 并 `git push` 推送至 `main` 分支。

---

## 六、AI-Project-Hub 标准 Intake / 发现元数据 (Standard Intake Manifest)

```yaml
schema_version: "1.0"
project:
  hub_id: "repo:loon-rules"
  name: "loon-rules"
  display_name: "Loon 原生分流规则系统"
  repo_url: "https://github.com/o-ocn/loon-rules"
  hub_url: "https://github.com/o-ocn/AI-Project-Hub"
  category: "network_rules"
  lifecycle_status: "active_observation"
  stage: "Phase 0.5 - Shadow Audit & Daily Observation"
  single_source_of_truth: "PROJECT_STATE.md"
  handoff_specification: "AGENTS.md"
  discovery_entrypoint: "AI_HUB_SYNC.md"
  primary_author: "o-ocn"
  license: "GPL-2.0 / Strategy-Neutral"

architecture:
  ruleset_count: 19
  total_valid_rules: 21166
  components:
    - name: "Routing Rulesets"
      path: "dist/*.lsr"
      count: 19
      policy_neutral: true
    - name: "DNS Dispatch Plugin"
      path: "plugins/Loon-China-DNS.lpx"
      upstream_dns: "223.5.5.5"
    - name: "Diagnostic Plugin"
      path: "dist/diagnostics/LoonRules-Diagnostic.lpx"
      specification: "Loon Generic Script v2"
    - name: "Shadow Audit Pipeline"
      path: "scripts/audit_pipeline.py"
      scheduled_workflow: ".github/workflows/shadow-audit.yml"
      mode: "read_only_shadow"
    - name: "Production CI/CD"
      path: ".github/workflows/sync-and-build.yml"
      quality_gates: 5

quality_gates:
  - "python -B -m unittest scripts.test_rules (43 tests)"
  - "python scripts/check_conflicts.py --strict"
  - "node --test tests/test_diagnostic.js (19 tests)"
  - "python -B -m unittest scripts.test_score_engine (4 tests)"
  - "python scripts/verify_mirrors.py --pre-release"

audit_status:
  shadow_report: "audit/shadow_report.md"
  decisions_ledger: "history/decisions.jsonl"
  app_audit_matrix: "docs/app-audit-matrix.md"
  real_device_log_patch_count: 3
```
