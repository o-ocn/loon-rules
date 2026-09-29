# PROJECT STATE

> 本文件是本项目跨 AI / Agent 协作的当前状态唯一事实源。
>
> 新的 AI 接手项目前请先阅读本文件。
> 完成任何会改变项目状态的实质性工作后，请及时更新本文件。

## 项目目标

1. **自建自托管替代**：将 Loon 客户端原依赖的 15 个外部 KeLee 远端分流规则全面平替为自托管、高质量、策略中立的 19 个独立分流规则集，消除第三方维护滞后、规则混杂与劫持风险。
2. **自动化与完整性保障**：建立自动化构建、语法校验、去重去宽泛、SHA256 完整性清单（manifest.json）及动态双源（GitHub Raw / jsDelivr CDN）分发机制。
3. **单文件与策略中立**：提供单一 `.lcf` 配置文件交付，避免让用户逐条手动添加；所有 `.lsr` 保持策略中立，由用户在客户端按需灵活指派节点策略组。
4. **原生健康诊断**：提供 Loon 原生 `.lpx` 诊断插件，支持本地/网络双源校验与核心服务连通性探测。

---

## 当前状态

* **当前分支**：`feature/expand-rulesets-v2`（对应 GitHub PR #2，尚未合并到 `main`）。
* **最新提交**：`f8f1144`（已推送到 `origin/feature/expand-rulesets-v2`）。
* **功能进展**：
  * 全量 19 个规则集（共 1,742 条规则）已构建完毕并完成策略中立化清洗。
  * 针对 ChatGPT Work 独立审查（基于提交 `0905e32`）提出的 7 项问题，已于提交 `f8f1144` 完成全部修复。
  * 交付文件 `Loon-v2-19Rules.lcf` 与交接报告 `Gemini-PR-2-Delivery-Report.md` 已就绪。
* **运行状态**：测试套件全部通过（Python 35/35，Node.js 17/17），构建系统健康，无故障。
* **等待外部事项**：等待 ChatGPT Work 对提交 `f8f1144` 进行第二轮独立审核，以及用户在 iOS 端进行实机测试。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main）
- 建立初始 14 个自托管规则集及自动化构建流水线（`build.py`）。
- 建立分类边界隔离机制（如 Gemini/Google、YouTube/Google、Grok/Twitter 等）。
- 建立原生一键诊断插件（`LoonRules-Diagnostic.lpx`）与 Node.js 测试套件。

### 2. PR #2 阶段（当前开发中，提交 f8f1144）
- **14 -> 19 规则集扩充**：新增 `PayPal.lsr`、`Gaming.lsr`、`GitHub.lsr`、`Lan.lsr`、`China-GeoIP.lsr`，并在 `Apple-Direct.lsr` 中增补 SystemOTA、Siri 与 Apple ID 认证端点。
- **匹配优先级修正**：
  - 将 `Apple-Push.lsr`（10 条企业规范网段）调整为远端规则优先级 #1；
  - 严格调整细分服务在前、宽泛服务在后：`YouTube.lsr` 与 `GoogleDrive.lsr` 优先于 `Google.lsr`；`Lan.lsr` 优先于 `China-GeoIP.lsr`。
- **高危与非专属域名清洗**：
  - Gaming 清洗 4 条非平台专属域名（`steamunlocked.net`、`humblebundle.com`、`fanatical.com`、`helpshift.com`）；
  - PayPal 人工精选 19 条官方与备案域名，排查排除 230+ 仿冒钓鱼域名。
- **规范与文档修订**：
  - 细化 `Lan.lsr` 的 RFC 规范标注（RFC 1918、6598、6890、2544、4291、4193）；
  - 剔除 APNs“0 延迟、100% 命中 TCP 5223”的不实表述，明确 iOS 推送真机测试边界；
  - 彻底清理仓库与文档中让用户“手动倒序导入 19 次”的旧指引。
- **诊断插件与双源验证**：
  - 诊断脚本全面升级支持 19 规则集，并支持 `$argument` 动态传入 `branch` 参数（PR 阶段读取 `feature/expand-rulesets-v2`）；
  - 实测 jsDelivr 备用 CDN 镜像真实下载并完成 SHA256 校验。
- **单文件交付与结构校验**：
  - 生成单文件候选配置 `Loon-v2-19Rules.lcf`，断言确认 19 条规则完全就位、0 KeLee 远端规则残留，私密节点及订阅块完好保留。

---

## 当前正在处理

* **阶段**：PR #2 等待第二轮复核与实机测试。
* **当前任务**：
  1. 固化跨 AI 协作规范（`AGENTS.md`）与本项目事实源（`PROJECT_STATE.md`）。
  2. 保持工作区与 PR 分支整洁，随时准备响应 ChatGPT Work 第二轮审查反馈。
  3. 若审核通过，执行 PR #2 向 `main` 分支的合并及 URL 切回 `main` 操作。

---

## 关键决策

1. **规则策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在 Loon 客户端自由绑定节点策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **Apple 边界审慎收敛**：`Apple-Push` 仅保留 10 条官方权威 APNs 网段；`AppleDev`（开源项目）与 `AppleHardware`（非核心营销域名）经评估有意不并入核心直连，防止白名单臃肿。
4. **单文件导入替代手工配置**：拒绝向用户提供 19 步手动点击指导，统一采用单个 `.lcf` 文件导入，杜绝因人工操作顺序错乱导致的分流失效。
5. **双源容灾架构**：主源使用 GitHub Raw，备用源使用 Fastly jsDelivr CDN，保障中国大陆网络冷启动可达。
6. **严格隐私保护原则**：严禁在代码、交互输出或公开测试夹具中泄露私有节点、订阅、Token 或账号凭证。

---

## 重要文件与目录

| 路径 | 用途 |
|---|---|
| `PROJECT_STATE.md` | 本项目当前状态的唯一事实源（跨 AI 协作必读必更） |
| `AGENTS.md` | AI / Agent 工作准则与交接规则 |
| `README.md` | 项目对外公开说明与规则订阅说明 |
| `sources.yml` | 规则源声明清单、上游 URL、最小规则数与排除项定义 |
| `dist/` | 构建生成的 19 个策略中立 `.lsr` 文件及诊断产物 |
| `rules/custom/` | 各服务本地补充与例外规则（需有抓包或官方依据） |
| `scripts/build.py` | 规则抓取、解析、去重、清洗与原子发布构建流水线 |
| `scripts/test_rules.py` | 规则系统单元测试套件（含 4 阶段流水线、PayPal 防钓鱼等 35 项测试） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具 |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（支持动态分支与多源校验） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件 |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（17 项测试） |
| `tests/fixtures/sample_order_19.lcf` | 公开、策略中立的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `AGENTS.md`：
  - 新建 AI / Agent 协作规则与 `PROJECT_STATE.md` 强制更新要求。
* `PROJECT_STATE.md`：
  - 初始化项目状态唯一事实源，全面记录目标、现状、已完成项、决策与已知风险。

---

## 验证状态

### 已验证
- [x] **Python 单元测试**：35 项全量通过（`python -B -m unittest scripts.test_rules`）。
- [x] **Node.js 诊断测试**：17 项全量通过（`node --test tests/test_diagnostic.js`）。
- [x] **规则构建幂等性**：`build.py` 运行无报错，19 个规则集策略中立性断言全部成立。
- [x] **jsDelivr 备用 CDN**：网络连通、清单拉取与 SHA256 校验实测一致。
- [x] **候选配置结构**：`Loon-v2-19Rules.lcf` 包含全部 19 条规则且顺序正确，0 KeLee 远端残留，私密块未破坏。

### 尚未验证
- [ ] **iOS Loon 真机实测**：手机端导入 `Loon-v2-19Rules.lcf` 后的流量实际分流与切换体验。
- [ ] **推送长连接真机表现**：Wi-Fi 与蜂窝数据切换下，Telegram / 微信锁屏推送的实际延时与表现。
- [ ] **Apple Watch & HomeKit**：真机环境下智能家居串流与手表数据同步。

---

## 已知问题 / 风险

1. **分支引用临时性**：当前 `Loon-v2-19Rules.lcf` 和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需要无缝切回 `main` 分支地址。
2. **iOS APNs 系统绕行**：若用户未在 Loon 设置中开启“包含 APNS”或连接走非 TUN 栈，TCP 5223 不经过 Loon 代理（属于 iOS 系统机制，需在文档中持续向用户提示）。
3. **Gaming 合并策略**：Steam 与 Epic 当前共存于 `Gaming.lsr`，共用同一出口策略组。若用户后续提出对单一平台使用不同代理的需求，需拆分为独立规则集。

---

## 不要重复踩的坑

1. **严禁向 `.lsr` 写入策略名**：Loon 远程规则必须是纯域名/IP 规则，带有 `,PROXY`、`,DIRECT` 会破坏策略中立性并报错。
2. **严禁颠倒分流顺序**：宽泛域名（如 Google）必须排在细分业务（如 YouTube、Drive）之后；Lan 必须在 GeoIP 之前。
3. **严禁向 C 盘或桌面写入非必要文件**：必须严格遵循用户全局准则，文件统一存放在 `E:\Document\Gemini` 或交付目录。
4. **严禁泄露或打印私密配置**：不得在日志、对话或公开测试夹具中打印用户的私密节点、订阅 Token 和密码。
5. **严禁指导用户手动 19 步逆序配置**：极易产生人为失误，必须交付单一 `.lcf` 文件。
6. **不要做出未经证明的绝对化性能承诺**：如“0 延迟”、“100% 保证 TCP 5223 命中”等。

---

## 下一步

1. **第一优先级（等待复核）**：等待 ChatGPT Work 对 commit `f8f1144` 的第二轮独立审核结论。
2. **第二优先级（真机测试）**：由用户在 iOS 手机端导入 `Loon-v2-19Rules.lcf`，运行插件诊断并按清单测试分流与推送。
3. **第三优先级（合并上线）**：审核与实机测试均通过后，合并 PR #2 到 `main`，同步将 `.lcf` 中的分支 URL 切换为 `main`。

---

## 环境 / 部署说明

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 18+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **交付与复核路径**：`E:\Document\ChatGPT\Loon-Migration`
* **版本控制**：Git（GitHub 远程仓库 `o-ocn/loon-rules`）

---

## 最后更新

- **时间**：2026-09-29 13:52
- **执行者**：Antigravity (Gemini)
- **本轮工作**：确立跨 AI 协作事实源规范，新增 `AGENTS.md`，并在根目录创建与初始化 `PROJECT_STATE.md`。
