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
* **当前 HEAD**：已推送到 `origin/feature/expand-rulesets-v2`。
* **规则集架构定型**：全库正式定型为 **19 个规则集**（共 **21,092 条有效规则**）。
  * 恢复 `Gaming.lsr`（合并 Steam 与 Epic，65 条规则），彻底解决用户私人配置引用 `Gaming.lsr` 返回 404 的问题。
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 上游 `ChinaIPs`（19,209 条规则）；离线模拟确认事故 IP `119.147.195.212` 属于 `119.144.0.0/14`，代表 IPv6 `240e:97c:2f:1::1` 属于 `240e::/20`。
* **私人配置验收器原有三类假通过已封堵，URL 隐私缺口已全链路闭合**：
  1. **零远程引用防伪与全覆盖强校验**：移除了 `scripts/simulate_hit.py` 在零引用时对默认 19 条规则的静默回退，严格如实返回解析所得的远程规则列表；任何缺失、禁用（`enabled=false`）、重复或零远程规则引用均触发 `[ERR_ZERO_RULESETS]`、`[ERR_MISSING_RULESET]` 或 `[ERR_DUPLICATE_RULESET]` 并在验收器中报错退出。
  2. **发布 URL 隐私边界收紧与白名单严格授权**：全面重构 `validate_ruleset_url`：
     - 协议严格限定 HTTPS；
     - 拒绝任何用户名、密码或用户凭证（`parsed.username`, `parsed.password`, `@`）；
     - 拒绝任何查询参数（query，如 `?token=...`）；
     - 拒绝任何 URL 片段标识符（fragment，如 `#...`）；
     - 拒绝非预期端口（仅允许默认 443 或无端口，拒绝 `:8443` 等）；
     - 发布主机严格限定于经实际验收的主机（`raw.githubusercontent.com` 与 `fastly.jsdelivr.net`），拒绝未经验证的泛 jsDelivr 子域名；
     - 严格匹配仓库路径、允许分支（`main` 或 `feature/expand-rulesets-v2`）与期待文件名；
     - 校验失败时绝不回显输入 URL 或任何测试字符串，实现 100% 脱敏保护。
  3. **Loon 原生语法段落与单条末尾 FINAL 强校验**：规范修正公开测试夹具 `sample_order_19.fixture`，将误放在 `[Remote Rule]` 下的 FINAL 规则移回 `[Rule]` 末尾；验收器严格校验 `FINAL` 必须存在且仅有一条启用的规则位于 `[Rule]` 段末尾，严禁错段置于 `[Remote Rule]`、`[Plugin]` 或在其后追加其他规则，分别报告 `[ERR_FINAL_WRONG_SECTION]`、`[ERR_FINAL_DUPLICATE]`、`[ERR_FINAL_NOT_LAST]` 或 `[ERR_FINAL_MISSING]`。
  4. **未知/私人规则文件名脱敏保护**：建立 `safe_ruleset_name` 脱敏转换机制，仅对官方公开 19 个规则集回显名称；若用户配置中存在未知或第三方自建规则集，一律遮罩为 `[NON_STANDARD_RULESET]` 并单独统计报告 `[ERR_UNEXPECTED_RULESET]` 总数，杜绝因规则文件名包含用户名、私有订阅或 Token 导致信息外泄。
  5. **公开回归测试全面扩充（test_42）**：`scripts/test_rules.py` 的 `test_42` 扩充涵盖零引用、禁用规则、重复规则、未授权伪造 URL、错段 FINAL、重复 FINAL、FINAL 后置规则、未知规则名脱敏、Fastly jsDelivr 备用源验证、URL 查询参数拒绝且零回显、URL 认证信息拒绝且零回显、片段拒绝、非标准端口拒绝、未验证 jsDelivr 子域名拒绝以及 `validate_ruleset_url` 契约单测等 18 类场景，实测 100% 触发预期断言。
* **交付物清单强制字段与包签名自重算强校验**：
  * `scripts/verify_mirrors.py` 将 `rulesets`, `diagnostic_artifacts`, `package_sha256`, `content_revision` 设为严格必填项；
  * 无论是本地预发布还是远端镜像校验，均依据清单中声明的规则集元数据与诊断产物元数据，重新计算 SHA256 包签名进行二次核对，杜绝任何全零哈希或篡改元数据绕过；
  * `test_40` 故障注入场景扩充至 12 类，包括缺诊断元数据、缺包签名、本地全零包签名等，实测 100% 触发校验失败。
* **真实分支备用源同步与有限重试门禁**：
  * `verify_mirrors.py` 增加重试机制（默认 3 次重试，间隔 6 秒），妥善处理 CDN 边缘缓存传播延迟，并在超时后输出清晰的 `[TIMEOUT/FAIL]` 状态诊断；
  * 真实分支 `feature/expand-rulesets-v2` 在 GitHub Raw 与 jsDelivr CDN 均已 100% 达到版本 `5d76a6200a78`，所有 19 个规则集及诊断产物校验全部通过。
* **构建流水线权限重置收紧**：
  * 彻底移除 `switch_dist_directory` 中对整个 `dist/` 递归执行且静默忽略失败的 `icacls /reset /T`；
  * 收紧为仅在创建 `.dist_staging` 容器目录时执行 `icacls staging_dir /reset`，且严格检查返回码，若非零立即抛出显式 `RuntimeError`，杜绝静默吞掉异常或递归影响 Git 跟踪文件。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，验收器假通过阻断项与 URL 隐私缺口已全面修复并通过回归测试）
- **Gaming.lsr 404 修复与 Steam/Epic 策略合并**：消除 404 故障，维持 19 个规则集体系与用户出口偏好一致。
- **抖音事故 IP 兜底与中国 IP 自治**：为 `China-GeoIP` 引入 blackmatrix7 成熟开源 `ChinaIPs`（19,209 条规则），事故 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`。
- **构建流水线健壮性修复（缩进 Bug）**：修复 `scripts/build.py` 上游抓取逻辑被错误缩进在 `if custom_file:` 条件块内的隐患。
- **离线受控缓存入库与干净克隆 42/42 测试通过**：将 `scripts/.upstream_cache/7871aa32a3ea6248.list` 正式纳入 Git 跟踪并移除忽略规则，干净克隆稳定 42/42 通过。
- **公开 CI 与本地私人配置验收彻底分离**：
  - `test_41` 仅运行仓库内的公开夹具 `tests/fixtures/sample_order_19.fixture`；
  - 交付独立本地工具 `scripts/verify_private_lcf.py`，完整检查 Local `[Rule]`、Plugin `[Rule]`、`[Remote Rule]`、`FINAL` 四阶段；
  - 封堵零远程引用回退、伪造发布 URL、错段/重复/缺失 FINAL 等假通过漏洞；
  - 封闭 URL 隐私缺口：严格拒绝 query、userinfo、fragment、非预期端口与未验证 jsDelivr 子域名；
  - 错误输出不回显任何未知文件路径、私有 URL 或私密规则名；检测到活跃第三方插件时明确标注 `Plugin Injected Rules: UNVERIFIED`，禁止给出“完全通过”。
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

* **阶段**：Gemini 已完成 URL 隐私缺口修复，并在 `test_42` 中扩充 6 项故障注入测试；42/42 Python 测试、18/18 Node.js 测试、预发布门禁与分支双源镜像校验全部稳定通过。
* **下一步工作**：ChatGPT Work 独立复核最新提交，随后基于最新手机导出配置在本地安全沙箱装配唯一合规私人 `.lcf` 文件（修正 YouTube/Lan 顺序并保持用户所有私人设置）；PR 合并至 `main` 并校验正式主备源后，再由用户进行 Loon 真机实测。

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
10. **私人配置验收器严禁在零引用时静默回退默认规则**：必须真实反映文件内容，缺规则、禁用规则或重复引用必须显式报错拦截。
11. **远程规则 URL 必须强校验主机与路径白名单**：仅允许官方仓库与合法发布分支，且报错时严禁回显私有 URL 或私密规则名。
12. **Loon 原生配置中 FINAL 必须严格且仅有一条位于 [Rule] 段末尾**：严禁将 FINAL 置于 [Remote Rule] 或其他段落，也严禁在 FINAL 后继续声明规则。
13. **发布 URL 必须严格拒绝 query、userinfo、fragment 和非预期端口**：防止用户或插件误将包含 token 或账号信息的私有订阅地址带入远程规则，且 jsDelivr 备用源必须精确到已验收的主机（`fastly.jsdelivr.net`），禁止使用通配子域名。

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
| `scripts/test_rules.py` | 规则系统公开单元测试套件（全量 42 项测试，含 12 种清单故障注入与 18 类 verify_private_lcf 行为回归） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 4 阶段流水线、严格段落/FINAL 解析与 LRU 缓存） |
| `scripts/verify_mirrors.py` | 独立镜像与预发布校验工具（含必填元数据校验、包签名重算与 CDN 有限重试） |
| `scripts/verify_private_lcf.py` | 独立本地脱敏私人 `.lcf` 验收工具（URL 白名单、privacy 拦截、段落结构、FINAL 定位、多阶段仿真、本地抢占拦截、插件未验证标记、路径与规则名零泄露） |
| `.github/workflows/sync-and-build.yml` | GitHub Actions 自动化流水线（发布前本地强门禁 + 发布后 CDN 监控告警） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（精确标注 HTTP 状态与能力边界，报告可见） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件（19 规则集配置） |
| `diagnostics/services.yml` | 诊断探针服务元数据（12 快速 / 4 完整项） |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（18 项测试） |
| `tests/fixtures/sample_order_19.fixture` | 公开、脱敏、策略中立、符合 Loon 原生段落结构的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `scripts/verify_private_lcf.py`：增强 `validate_ruleset_url` 隐私边界，全面拒绝账号、密码、查询参数、片段及非预期端口，主机白名单收紧为仅限 `raw.githubusercontent.com` 与 `fastly.jsdelivr.net`，错误报告绝不回显 URL 或测试字符串。
* `scripts/test_rules.py`：在 `test_42` 中扩充 6 项针对 URL 隐私与备用源的回归测试（Fastly jsDelivr 备用源通过、query token 拦截且不回显、userinfo 认证拦截且不回显、fragment/port 拦截且不回显、未验证 jsDelivr 子域名拦截且不回显、validate_ruleset_url 契约单测）；全量 42 项 Python 规则测试稳定通过。
* `PROJECT_STATE.md`：保留 ChatGPT Work 独立复核记录，同步合并 URL 隐私缺口修复事实与测试断言。

---

## 验证状态

### 已验证
- [x] **干净克隆 Python 单元测试（42/42）**：全量 42 项测试通过（`python -B -m unittest scripts.test_rules`，Ran 42 tests in ~176s, OK, 0 fail, 0 skip）。
- [x] **Node.js 诊断测试（18/18）**：全量 18 项通过（`node --test tests/test_diagnostic.js`，1.6s，0 fail）。
- [x] **预发布本地完整性强门禁**：`python scripts/verify_mirrors.py --pre-release` 严格校验 19 个规则集策略中立、条数、SHA256、必填诊断元数据及全包签名重算自校验，退出码 0。
- [x] **URL 隐私边界与主备源验证**：正常主源 (GitHub Raw) 与备用源 (fastly.jsdelivr.net) 通过；query (`?token=...`)、userinfo (`user:pass@` / `fixture_secret@`)、fragment (`#...`)、异常端口 (`:8443`) 及未验证 jsDelivr 子域名 (`cdn` / `testingcf` / `evil.jsdelivr.net`) 100% 触发拒绝，且报错信息中绝无敏感字符串回显。
- [x] **验收器原有假通过漏洞 8 类故障注入实测**：零引用、禁用规则、重复引用、伪造 URL、错段 FINAL、重复 FINAL、FINAL 后追加规则、未知规则名遮罩全部触发拦截，退出码 1，无任何私密数据泄漏。
- [x] **镜像与交付物 12 类故障注入实测**：覆盖网络故障、404、规则集数量不符、正文篡改、诊断脚本篡改、元数据单项篡改、远端签名篡改、缺诊断元数据、缺包签名、本地缺元数据、本地全零包签名等，100% 触发校验失败并以退出码 1 退出。
- [x] **本地抢占、插件未验证与缺文件行为**：完整多阶段仿真引擎精准捕获本地规则抢占，对活跃第三方插件明确标记 `UNVERIFIED`，文件不存在时显式报错且无路径泄漏。
- [x] **真实分支主备源一致性验证**：`feature/expand-rulesets-v2` 分支在 GitHub Raw 与 jsDelivr CDN 均已同步至版本 `5d76a6200a78`，19/19 规则及诊断产物实测完全通过。
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

1. **私人配置验收器 URL 隐私缺口已封闭**：已通过 `test_42` 18 项故障注入及单测严格覆盖，所有携带 token、认证信息、片段、异常端口或未经验证子域名的 URL 均被 100% 拦截且零信息泄漏。原有零引用、错误主机、错段 FINAL 假通过亦全部保持修复。
2. **当前手机配置顺序待修**：YouTube 在 Google 之后、Lan 在 China-GeoIP 之后；由 ChatGPT Work 在装配最终单文件时修正。
3. **插件边界**：当前配置有 36 个启用插件，静态工具只标记其规则注入为未验证，不能声称插件已通过，也不应默认要求用户为全部插件抓包。
4. **分支引用临时性**：插件和规则仍引用 `feature/expand-rulesets-v2`；PR 合并后需切到 `main` 并再次验证主备源。
5. **真机边界**：诊断探针无法代替 APNs TCP 5223、Telegram 蜂窝锁屏推送、HomeKit、Apple Watch、CloudKit 或 19,209 条 CIDR 在 Loon 真机的加载测试。

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
10. **私人配置验收器严禁在零引用时静默回退默认规则**：必须真实反映文件内容，缺规则、禁用规则或重复引用必须显式报错拦截。
11. **远程规则 URL 必须强校验主机与路径白名单**：仅允许官方仓库与合法发布分支，且报错时严禁回显私有 URL 或私密规则名。
12. **Loon 原生配置中 FINAL 必须严格且仅有一条位于 [Rule] 段末尾**：严禁将 FINAL 置于 [Remote Rule] 或其他段落，也严禁在 FINAL 后继续声明规则。
13. **发布 URL 必须严格拒绝 query、userinfo、fragment 和非预期端口**：防止用户或插件误将包含 token 或账号信息的私有订阅地址带入远程规则，且 jsDelivr 备用源必须精确到已验收的主机（`fastly.jsdelivr.net`），禁止使用通配子域名。

---

## 下一步

1. ChatGPT Work 独立复核最新提交，随后基于最新手机导出装配唯一私人 `.lcf`（调整 YouTube/Lan 顺序并保留用户私人设置）；PR #2 合并至 `main`。
2. 校验 `main` 主备发布源并由用户在手机 Loon 客户端导入进行真机实测。

---

## 环境 / 部署说明

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 18+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **交付与复核路径**：`E:\Document\ChatGPT\Loon-Migration`
* **版本控制**：Git（GitHub 远程仓库 `o-ocn/loon-rules`，PR #2）

---

## 最后更新

- 时间：2026-09-29
- 执行者：ChatGPT Work（独立审核；仓库实现由 Gemini / Antigravity 负责）
- 本轮工作：ChatGPT Work 独立复核提交 `41ffb8a`：原有三类假通过已修复；干净克隆 42/42 Python、18/18 Node.js、预发布和分支双源 19/19 校验通过；发现 URL query/userinfo 可绕过验收，已列为修复阻断项。

- 时间：2026-09-29
- 执行者：Gemini / Antigravity
- 本轮工作：完成 `validate_ruleset_url()` 隐私收紧与主机白名单限定（拒绝 userinfo、query、fragment、非预期端口，收紧 jsDelivr 为已验证的 fastly.jsdelivr.net，错误输出零回显）；在 `test_42` 中新增 6 组主备源与隐私故障注入测试；42/42 Python 测试、18/18 Node.js 测试及预发布门禁全部通过。
