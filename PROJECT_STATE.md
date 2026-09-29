# PROJECT STATE

> 本文件是本项目跨 AI / Agent 协作的当前状态唯一事实源（Single Source of Truth）。
>
> 任何 AI / Agent 接手项目前请先阅读本文件。
> 完成任何会改变项目状态的实质性工作后，请严格按规范更新本文件。

---

## 项目目标

维护一套以 `blackmatrix7/ios_rule_script` 为主要成熟上游、`o-ocn/loon-rules` 为唯一公开发布入口的 Loon 原生分流规则（`.lsr`）及原生诊断插件（`.lpx`）：
1. **服务分类与出口策略彻底分离**：规则文件只定义服务流量分类，保持策略中立（严禁写入节点、地区、DIRECT/PROXY 等出口偏好）；用户在 Loon 客户端按需灵活指派节点策略组。
2. **平替外部不受控规则**：全量替代旧版 15 个 KeLee 远端分流规则，消除规则混杂、上游滞后、钓鱼域名及劫持风险。
3. **一致性检查与质量保障**：建立“声明契约、来源配置、构建产物、测试套件、自动化更新”全链路一致性，防止上游更新滞后或规则误伤。
4. **单文件交付与安全隐私**：用户最终只导入一份由 ChatGPT Work 在本地安全装配的唯一私人 `.lcf`；严格保护私人凭证、订阅、节点与密钥，杜绝泄露至公开仓库。

---

## 当前状态

* **当前分支**：`feature/expand-rulesets-v2`（对应 GitHub PR #2，待合并至 `main`）。
* **本地已提交 HEAD**：`4b44f3b`。已全面解决 ChatGPT Work 在 `8f428d6` 独立复测中发现的所有阻断项（首命中多阶段模型、本地抢占检出、未验证插件状态、manifest 必填自校验重算、分支备用源有限重试与超时报警、构建器权限重置收紧）。
* **规则集架构定型**：全库正式定型为 **19 个规则集**（共 **21,092 条有效规则**）。
  * 恢复 `Gaming.lsr`（合并 Steam 与 Epic，65 条规则），彻底解决用户私人配置引用 `Gaming.lsr` 返回 404 的问题。
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 上游 `ChinaIPs`（19,209 条规则）；离线模拟确认事故 IP `119.147.195.212` 属于 `119.144.0.0/14`，代表 IPv6 `240e:97c:2f:1::1` 属于 `240e::/20`。
* **私人配置多阶段验收与本地规则抢占彻底治理**：
  * `scripts/verify_private_lcf.py` 接入完整多阶段仿真引擎（Local `[Rule]` -> Plugin `[Rule]` -> `[Remote Rule]` -> `FINAL`），预置 12 项典型服务基准探针；
  * 实测能够精准捕获本地更高优先级规则抢占（例如在 `[Rule]` 加入 `DOMAIN,drive.google.com,DIRECT`，工具立即报出 `[ERR_LOCAL_PREEMPTION]` 并以退出码 1 失败退出）；
  * 强制核验 `FINAL` 兜底规则的存在性与位置合规性；
  * 检测到配置中包含第三方活跃插件时，明确标注 `Plugin Injected Rules: UNVERIFIED`，禁止给出“完全通过”，避免虚假安全感；
  * **完全脱敏**：所有失败分支采用标准化错误码（如 `[ERR_FILE_NOT_FOUND]`, `[ERR_LOCAL_PREEMPTION]`），绝不回显文件路径或原始异常堆栈。
* **交付物清单强制字段与包签名自重算强校验**：
  * `scripts/verify_mirrors.py` 将 `rulesets`, `diagnostic_artifacts`, `package_sha256`, `content_revision` 设为严格必填项；
  * 无论是本地预发布还是远端镜像校验，均依据清单中声明的规则集元数据与诊断产物元数据，重新计算 SHA256 包签名进行二次核对，杜绝任何全零哈希或篡改元数据绕过；
  * `test_40` 故障注入场景扩充至 12 类，包括缺诊断元数据、缺包签名、本地全零包签名等，实测 100% 触发校验失败。
* **真实分支备用源同步与有限重试门禁**：
  * `verify_mirrors.py` 增加重试机制（默认 3 次重试，间隔 6 秒），妥善处理 CDN 边缘缓存传播延迟，并在超时后输出清晰的 `[TIMEOUT/FAIL]` 状态诊断；
  * 经 Fastly HTTP PURGE 刷新，当前 `feature/expand-rulesets-v2` 分支在 GitHub Raw 与 jsDelivr CDN 均已 100% 达到版本 `5d76a6200a78`，所有 19 个规则集及诊断产物校验全部通过。
* **构建流水线权限重置收紧**：
  * 彻底移除 `switch_dist_directory` 中对整个 `dist/` 递归执行且静默忽略失败的 `icacls /reset /T`；
  * 收紧为仅在创建 `.dist_staging` 容器目录时执行 `icacls staging_dir /reset`，且严格检查返回码，若非零立即抛出显式 `RuntimeError`，杜绝静默吞掉异常或递归影响 Git 跟踪文件。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，复核发现问题已全部解决）
- **Gaming.lsr 404 修复与 Steam/Epic 策略合并**：消除 404 故障，维持 19 个规则集体系与用户出口偏好一致。
- **抖音事故 IP 兜底与中国 IP 自治**：为 `China-GeoIP` 引入 blackmatrix7 成熟开源 `ChinaIPs`（19,209 条规则），事故 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`。
- **构建流水线健壮性修复（缩进 Bug）**：修复 `scripts/build.py` 上游抓取逻辑被错误缩进在 `if custom_file:` 条件块内的隐患。
- **离线受控缓存入库与干净克隆 42/42 测试通过**：将 `scripts/.upstream_cache/7871aa32a3ea6248.list` 正式纳入 Git 跟踪并移除忽略规则，干净克隆稳定 42/42 通过。
- **公开 CI 与本地私人配置验收彻底分离**：
  - `test_41` 仅运行仓库内的公开夹具 `tests/fixtures/sample_order_19.fixture`；
  - 交付独立本地工具 `scripts/verify_private_lcf.py`，支持多阶段仿真、本地抢占检测、FINAL 验证与未验证插件标记，错误输出路径完全脱敏；`test_42` 专门保障其回归行为。
- **诊断产物与清单哈希一致性强校验闭环**：
  - `manifest.json` 将 `diagnostic_artifacts` 与 `package_sha256` 设为必填，并包含精确大小与 SHA256；
  - `verify_mirrors.py` 与 `verify_local_pre_release` 均重算全包签名进行自校验，杜绝缺字段与全零伪通过；`test_40` 补充 12 类故障注入。
- **CI 流水线双重门禁与分支镜像有限重试**：
  - 明确发布前本地门禁（本地 fail-stop 拦截，线上零修改）与发布后 CDN 告警门禁（失败立即标红退出，不承诺 force-push 回滚）的职责边界；
  - 镜像校验增加有限重试与明确超时诊断，真实分支备用源已同步通过。
- **构建器权限重置操作全面收紧**：
  - 移除宽泛且静默忽略失败的 `icacls dist /reset /T`，仅保留针对 staging 容器目录且严格报错的 `icacls /reset`。
- **诊断短报告样例真实化输出**：分别针对真实快速模式（4 规则/12 服务）与真实完整模式（19 规则/16 服务/含谨慎提示）提供夹具验证报告。

---

## 当前正在处理

* **阶段**：PR #2 所有代码修复与测试已闭环（HEAD: `4b44f3b`），待推送到 GitHub PR #2。
* **下一步工作**：提交并推送代码；由 ChatGPT Work 基于最新手机导出配置装配修正唯一私人 `.lcf`，再进行 Loon 真机实测。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **Steam 与 Epic 正式合并为 Gaming.lsr**：用户确认两者均走代理出口，合并为 `Gaming.lsr`（65 条规则）消除 404 故障，与用户最新私人配置 19 条远程规则保持零冲突契合。
4. **China-GeoIP 引入 ChinaIPs 兜底**：引入 mature GPL-2.0 的 19,209 条中国 IPv4/IPv6 CIDR，彻底解决纯 IP 直连漏入 FINAL 的结构性缺陷。
5. **Apple 基础服务合并、特殊服务独立**：用户希望可直连的 Apple 基础服务集中在 `Apple-Direct.lsr`；`TestFlight`、`Apple-Media`、`Apple-Push` 保持独立，现有 `Apple Push` 策略组保留。
6. **公开 CI 测试绝不依赖或假装测试本地私人文件**：公开测试严格封闭于仓库公开夹具；私人配置验收采用专用本地工具独立执行，缺文件必须显式报错，错误输出禁止回显路径。
7. **交付物哈希全闭环强校验**：不仅规则集正文校验 SHA256，诊断 `.lpx`、`.js` 以及清单中的每一项元数据均必须存在，且由工具依据实体内容动态重算 `package_sha256` 进行自校验。
8. **CI 门禁客观透明，杜绝虚假承诺**：发布前本地门禁 100% 阻止坏版本推送；发布后远端检查作为监控告警，引入有限重试应对 CDN 边缘传播，检测到不同步时退出码 1 报警，不虚假承诺无损自动回滚。
9. **跨账户与沙箱文件系统权限继承准则**：在 Windows 开发环境中严禁使用 `tempfile.mkdtemp` 等产生私有 DACL 的 API 充当成品目录源，必须保证所有成品目录完全继承标准文件系统 ACL；权限重置仅作用于暂存容器并严格校验返回值。

---

## 重要文件与目录

| 路径 | 用途 |
|---|---|
| `PROJECT_STATE.md` | 本项目当前状态的唯一事实源（跨 AI 协作必读必更） |
| `AGENTS.md` | AI / Agent 工作准则与交接规则 |
| `README.md` | 项目对外公开说明与规则订阅说明（19 规则集体系） |
| `sources.yml` | 规则源声明清单、上游 URL、最小规则数与排除项定义 |
| `dist/` | 构建生成的 19 个策略中立 `.lsr` 文件及诊断产物（共 21,092 条规则） |
| `rules/custom/` | 各服务本地补充与例外规则（需有抓包或官方依据） |
| `scripts/build.py` | 规则抓取、清洗、构建与带收紧 ACL 继承保障的目录切换流水线 |
| `scripts/test_rules.py` | 规则系统公开单元测试套件（全量 42 项测试，含 12 种故障注入与 verify_private_lcf 回归） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 4 阶段流水线与 LRU 缓存） |
| `scripts/verify_mirrors.py` | 独立镜像与预发布校验工具（含必填元数据校验、包签名重算与 CDN 有限重试） |
| `scripts/verify_private_lcf.py` | 独立本地脱敏私人 `.lcf` 验收工具（多阶段仿真、本地抢占拦截、插件未验证标记、路径零泄露） |
| `.github/workflows/sync-and-build.yml` | GitHub Actions 自动化流水线（发布前本地强门禁 + 发布后 CDN 监控告警） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（精确标注 HTTP 状态与能力边界，报告可见） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件（19 规则集配置） |
| `diagnostics/services.yml` | 诊断探针服务元数据（12 快速 / 4 完整项） |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（18 项测试） |
| `tests/fixtures/sample_order_19.fixture` | 公开、脱敏、策略中立的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `scripts/verify_private_lcf.py` & `scripts/simulate_hit.py`：升级多阶段仿真模型，支持检测本地 `[Rule]` 抢占（如 `DOMAIN,drive.google.com,DIRECT`）；检查 `FINAL` 兜底规则；检测活跃第三方插件并标注 `UNVERIFIED`，禁止给予“完全通过”；错误输出路径与异常完全脱敏。
* `scripts/verify_mirrors.py`：将 `diagnostic_artifacts` 与 `package_sha256` 设为必填；本地与远端检查均动态重新计算全包签名对比验证；为远端 CDN 检查增加有限重试与明确超时输出。
* `scripts/test_rules.py`：新增 `test_42` 专项测试 `verify_private_lcf.py` 的本地抢占、插件未验证与路径脱敏行为；在 `test_40` 中补齐缺诊断元数据、缺包签名、本地全零签名 4 项故障注入测试（测试总数升至 42 项）。
* `scripts/build.py`：收紧 ACL 权限处理，移除对整个 `dist/` 递归执行且静默忽略失败的 `icacls /reset /T`，仅在暂存目录上重置并严格检查返回码。
* `PROJECT_STATE.md`：同步最新修复数据与提交状态。

---

## 验证状态

### 已验证
- [x] **干净克隆 Python 单元测试（42/42）**：全量 42 项测试通过（`python -B -m unittest scripts.test_rules`，OK，0 fail，0 skip）。
- [x] **Node.js 诊断测试（18/18）**：全量 18 项通过（`node --test tests/test_diagnostic.js`，1.7s，0 fail）。
- [x] **预发布本地完整性强门禁**：`python scripts/verify_mirrors.py --pre-release` 严格校验 19 个规则集策略中立、条数、SHA256、必填诊断元数据及全包签名重算自校验，退出码 0。
- [x] **镜像与交付物 12 类故障注入实测**：覆盖网络故障、404、规则集数量不符、正文篡改、诊断脚本篡改、元数据单项篡改、远端签名篡改、缺诊断元数据、缺包签名、本地缺元数据、本地全零包签名等，100% 触发校验失败并以退出码 1 退出。
- [x] **本地私人配置验收与本地规则抢占拦截**：测试验证公开夹具加入 `DOMAIN,drive.google.com,DIRECT` 能够精准触发 `[ERR_LOCAL_PREEMPTION]` 并失败退出；加入第三方插件触发 `Plugin Injected Rules: UNVERIFIED` 并禁止通过；缺文件仅输出通用错误代码且不泄露路径。
- [x] **真实分支主备源一致性验证**：`feature/expand-rulesets-v2` 分支经 Fastly PURGE 刷新，GitHub Raw 与 jsDelivr CDN 均已同步至版本 `5d76a6200a78`，19/19 规则及诊断产物实测完全通过。
- [x] **原开发工作区 dist/ 权限与现场确认**：ACL 继承正常，工作区 22 个成品文件完整有效。
- [x] **双模式真实短报告生成**：真实快速模式（4 规则/12 服务，17 行）与真实完整模式（19 规则/16 服务/含谨慎说明，25 行）已脱敏验证输出。

### 尚未验证（需 Loon 真机确认）
- [ ] **Loon 手机客户端导入与冷启动**：从 GitHub/jsDelivr 刷新 19 个规则集及诊断插件的实际加载体验与冷启动时间。
- [ ] **iOS APNs TCP 5223 系统绕行**：系统级非 TUN 栈流量在 iOS 设备上的实际推送表现（提示用户按需开启“包含 APNS”）。
- [ ] **Telegram 蜂窝锁屏推送**：蜂窝网络下唤醒与消息即时性实测。
- [ ] **多设备与特种协议**：HomeKit 室内摄像头即时视频推流、Apple Watch 独立蜂窝联网及 CloudKit 双向同步。
- [ ] **唯一私人配置装配**：由 ChatGPT Work 基于最新手机导出配置完成最终规则顺序修正与装配。

---

## 已知问题 / 风险

1. **当前手机配置顺序待修**：最新手机导出配置中 YouTube 仍位于 Google 之后，Lan 仍位于 China-GeoIP 之后；待由 ChatGPT Work 在装配唯一交付配置时予以修正。
2. **分支引用临时性**：当前诊断插件和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需统一切回 `main` 分支地址并再次验证主备源。
3. **iOS APNs 系统绕行**：若用户未在 Loon 设置中开启“包含 APNS”或连接走非 TUN 栈，TCP 5223 不经过 Loon 代理（属于 iOS 系统机制，需在文档中持续向用户提示）。
4. **诊断插件仅能反映探针连通性**：无法探测未知的动态 App CDN，真机若遇分流异常仍需依赖脱敏请求记录核验。
5. **Loon 真机大规则集性能需观测**：`China-GeoIP.lsr` 包含 19,209 条 CIDR 规则，真机加载耗时需在导入单文件后初次观察。

---

## 不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致全新克隆下测试失败。
2. **不要把“上游已有”当作“本仓库已同步”**：必须在 `sources.yml` 明确声明并经构建流水线集成。
3. **不要用单条 `GEOIP,CN` 替代具体的 CIDR 分流**：纯 IP 直连请求需要具体 IP-CIDR 规则兜底，防止落入 FINAL。
4. **单元测试不要依赖动态外网连接或本地机器残留缓存**：必须将离线受控夹具入库或构造完整 mock，确保任何干净克隆 100% 离线通过。
5. **严禁向 `.lsr` 写入策略名**：必须保持 100% 策略中立。
6. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则。
7. **Windows NTFS 下严禁使用 tempfile.mkdtemp 充当发布产物暂存目录**：`mkdtemp` 默认设置私有 DACL 阻断继承，会导致跨用户（如 Codex/ChatGPT 沙箱账户）读取被拒绝报空目录或删除假象；必须使用标准目录创建并确保 ACL 继承。
8. **公开 CI 测试严禁引用本地私密路径**：私密路径缺失会导致测试静默跳过而形成虚假安全感；公开测试只测公开夹具，私密测试使用专用工具显式传参并强制校验存在性。
9. **私人配置验收不能仅比对远程规则顺序**：必须运行完整多阶段仿真拦截本地高优先级抢占，且对第三方插件规则标记未验证，禁止给出虚假全通结论。

---

## 下一步

1. 提交并推送到 GitHub PR #2。
2. 交付 ChatGPT Work 复核最新提交与镜像状态。
3. 由 ChatGPT Work 基于最新手机导出配置装配修正唯一私人 `.lcf`，交付用户导入。
4. 用户在真实网络环境中进行 Loon 真机确认。

---

## 环境 / 部署说明

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 18+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **交付与复核路径**：`E:\Document\ChatGPT\Loon-Migration`
* **版本控制**：Git（GitHub 远程仓库 `o-ocn/loon-rules`，PR #2）

---

## 最后更新

- **时间**：2026-09-29
- **执行者**：Antigravity (Gemini)
- **本轮工作**：全面响应并闭环复核阻断项：
  1. 升级 `verify_private_lcf.py` 为多阶段仿真引擎，增加本地规则抢占检测、FINAL 校验与未验证插件标记，错误输出路径完全脱敏；
  2. 强化清单元数据与全包签名动态重算自校验，在 `verify_mirrors.py` 与 `test_rules.py` 中补充 4 项故障注入，彻底消除假通过隐患；
  3. 为 `verify_mirrors.py` 增加 CDN 传播有限重试与明确超时输出，经 Fastly PURGE 刷新，分支主备双源均已同步至版本 `5d76a6200a78`；
  4. 收紧构建器 ACL 权限处理，移除宽泛递归静默重置，仅针对 staging 容器并在失败时显式报错；
  5. 离线全量单元测试扩充至 42/42 通过，Node 诊断测试 18/18 通过。
