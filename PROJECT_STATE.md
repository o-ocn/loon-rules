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
* **最新提交**：`66da96f`（已成功推送到远程分支 `origin/feature/expand-rulesets-v2`）。
* **规则集架构定型**：全库正式定型为 **19 个规则集**（共 **21,092 条有效规则**）。
  * 恢复 `Gaming.lsr`（合并 Steam 与 Epic，65 条规则），彻底解决用户私人配置引用 `Gaming.lsr` 返回 404 的问题。
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 上游 `ChinaIPs`（19,209 条 IPv4/IPv6 规则），彻底闭环抖音事故 IP（`119.147.195.212` 属于 `119.144.0.0/14`）及中国电信 IPv6（`240e:97c:2f:1::1` 属于 `240e::/20`）漏入 FINAL 的安全漏洞。
* **分流首命中顺序与夹具**：
  * 4 阶段匹配流水线仿真验证通过（Stage 1 Local -> Stage 2 Plugin -> Stage 3 Remote -> Stage 4 FINAL）。
  * 严格保证首命中优先级（First Match Wins）：具体分类先于宽泛分类（YouTube、GoogleDrive 在 Google 之前，`youtube-ui.l.google.com` 稳定命中 YouTube）；内网穿透先于大网兜底（Lan 在 China-GeoIP 之前；Apple Push 在 China-GeoIP 之前）。
  * 建立脱敏策略中立 19 类真实顺序夹具 `tests/fixtures/sample_order_19.fixture`。
* **构建与发布工具链升级**：
  * 修复 `scripts/build.py` 在 `local_custom` 缺失时缩进跳过上游抓取的隐患，新增 `test_39`。
  * 重构 `scripts/verify_mirrors.py`，实现严格的 fail-stop 门禁语义（任何异常均 `sys.exit(1)`），新增 5 种故障注入单元测试（`test_40`）并全量通过。
* **诊断插件精准度与边界界定**：
  * `diagnostics/loon-rules-diagnostic.js` 与 `diagnostics/services.yml` 明确界定能力边界，杜绝将 401/403/404/502 响应误判为正常功能，将 APNs 明确标注为 443 探针响应，提示 TCP 5223 与 App 分流需真机实测。
* **测试套件状态**：
  * Python 单元测试：**40/40 全量通过**（无失败，无跳过，测试耗时 ~3.1s）。
  * Node.js 诊断逻辑：**17/17 全量通过**（无失败，测试耗时 ~1.6s）。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，用户旅程与全库审计修复完成）
- **Gaming.lsr 404 修复与 Steam/Epic 策略合并**：
  - 响应用户最新私人配置保留 `Gaming.lsr` 的实际情况，将 Steam 与 Epic 统一合并为 `Gaming.lsr`（65 条规则），消除 404 故障，维持 19 个规则集体系与用户出口偏好一致。
  - 清理无用拆分，删除过期的 `dist/Epic.lsr`、`dist/Steam.lsr`、`rules/custom/Epic.list`、`rules/custom/Steam.list`。
- **抖音事故 IP 兜底与中国 IP 自治**：
  - 根因：仅依靠 `GEOIP,CN` 在离线模拟或非解析模式下无法拦截纯 IP 直连请求，用户手机实测 `119.147.195.212` 漏入 FINAL。
  - 修复：在 `sources.yml` 为 `China-GeoIP` 引入 blackmatrix7 成熟开源 `ChinaIPs`（19,223 条原生规则，清洗后 19,209 条），通过 `filter_excluded` 剔除与 `China-Direct` 冲突的 15 个 CIDR，保留单个 `GEOIP,CN` 作为终极兜底。
  - 验证：仿真测试确认事故 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`；中国电信 IPv6 `240e:97c:2f:1::1` 命中 `IP-CIDR6,240e::/20,no-resolve`。
- **4 阶段匹配流水线与 YouTube/Google 优先级验证**：
  - 在 `scripts/simulate_hit.py` 与 `scripts/test_rules.py` 中引入完整 4 阶段匹配（Local -> Plugin -> Remote -> Final）。
  - 脱敏夹具 `sample_order_19.fixture` 将 YouTube/GoogleDrive 置于 Google 之前，`youtube-ui.l.google.com` 100% 优先命中 `YouTube.lsr`；Lan 置于 China-GeoIP 之前，`192.168.1.1` 命中 `Lan.lsr`。
- **构建流水线健壮性修复（缩进 Bug）**：
  - 修复 `scripts/build.py` 第 642 行上游抓取逻辑被错误缩进在 `if custom_file:` 条件块内的隐患，确保即使未提供 local_custom 文件也能正常抓取上游规则。
  - 新增单元测试 `test_39_missing_custom_file_does_not_skip_upstream` 验证此逻辑。
- **镜像校验工具严格非零退出门禁与故障注入测试**：
  - 重写 `scripts/verify_mirrors.py`，支持 `exit_on_failure` 与自定义 `urlopen_fn`。当 GitHub Raw 或 jsDelivr 出现连接失败、404、清单规则数不符、SHA256 哈希不符时，100% 触发 `sys.exit(1)`。
  - 新增单元测试 `test_40_verify_mirrors_fault_injection`，覆盖全部 5 种故障注入与正常通行场景，全面阻断不一致版本发布。
- **诊断插件报告精确性与真机能力边界界定**：
  - 更新 `diagnostics/loon-rules-diagnostic.js` 与 `diagnostics/services.yml`，对 HTTP 状态码 401/403/404/502 明确标记为 `[HTTP xxx响应,应用功能未验证]`，APNs 标注为 `[443探测响应,TCP5223与推送待实测]`，Muse 标注为 `[网站探针,不代表App功能]`。
  - 显式声明插件仅探测远端发布源可用性及已知 HTTPS 探针响应，手机内部的真实 App 规则命中、首条规则匹配及 APNs TCP 5223 必须依赖真机验证。

---

## 当前正在处理

* **阶段**：节点 ①（覆盖契约与事故回归）与节点 ②（全新克隆测试及自动更新链）已完成修复，等待提交并由 ChatGPT Work 独立复核。
* **下一步工作**：将本次变更提交并推送到 GitHub 远程仓库，校验远程构建状态及发布源。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **Steam 与 Epic 正式合并为 Gaming.lsr**：用户 2026-09-29 确认两者均走代理出口，合并为 `Gaming.lsr`（65 条规则）消除 404 故障，与用户最新私人配置 19 条远程规则保持零冲突契合。
4. **China-GeoIP 引入 ChinaIPs 兜底**：引入 mature GPL-2.0 的 19,209 条中国 IPv4/IPv6 CIDR，彻底解决纯 IP 直连漏入 FINAL 的结构性缺陷。
5. **Apple 基础服务合并、特殊服务独立**：用户希望可直连的 Apple 基础服务集中在 `Apple-Direct.lsr`；`TestFlight`、`Apple-Media`、`Apple-Push` 保持独立，现有 `Apple Push` 策略组保留。
6. **单文件导入与安全装配**：用户仅导入一份由 ChatGPT Work 在本地装配的唯一私人 `.lcf` 文件；以最新手机导出配置为私人基准，保留用户新增设置、策略组与手动出口选择；严禁在公开仓库、测试夹具或交互中泄露私人配置。
7. **镜像门禁严格 fail-stop**：`scripts/verify_mirrors.py` 在发布校验中遇到任何异常一律以非零状态码退出，杜绝带病发版。

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
| `scripts/build.py` | 规则抓取、解析、去重、清洗与原子发布构建流水线（缩进已修复） |
| `scripts/test_rules.py` | 规则系统单元测试套件（全量 40 项测试，新增 39 与 40） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 4 阶段流水线与 LRU 缓存） |
| `scripts/verify_mirrors.py` | 独立镜像联网校验工具（重构完成，具备严格非零退出门禁与故障注入支持） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（精确标注 HTTP 状态与能力边界） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件（19 规则集配置） |
| `diagnostics/services.yml` | 诊断探针服务元数据 |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（17 项测试） |
| `tests/fixtures/sample_order_19.fixture` | 公开、脱敏、策略中立的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `sources.yml`：将 Steam 与 Epic 重新合并为 `Gaming`；为 `China-GeoIP` 正式接入 `ChinaIPs` 上游源。
* `rules/custom/Gaming.list`：恢复 Gaming 本地规则清单；删除已废弃的 `Steam.list` 和 `Epic.list`。
* `scripts/build.py`：修复上游规则抓取缩进错误；维护 ruleset 原子更新机制。
* `scripts/simulate_hit.py`：更新默认远程规则顺序为 19 类，引入 `functools.lru_cache` 提升大规模 CIDR 匹配性能。
* `scripts/verify_mirrors.py`：重写为严格 fail-stop 工具，捕获所有异常并退出码 1，支持注入 mock urlopen 函数。
* `scripts/test_rules.py`：更新全库规则断言为 19 规则集、21,092 条规则；新增 `test_39`（上游无 custom 抓取）与 `test_40`（镜像校验 5 类故障注入）。
* `tests/fixtures/sample_order_19.fixture`：新建 19 类策略中立脱敏顺序夹具。
* `diagnostics/`：更新 `LoonRules-Diagnostic.lpx`、`services.yml` 与 `loon-rules-diagnostic.js`，精准界定探测状态及真机验证边界。
* `dist/`：全量重新构建，生成最新的 19 个 `.lsr`（含 65 条的 `Gaming.lsr` 与 19,209 条的 `China-GeoIP.lsr`）及诊断产物。
* `.gitignore`：增加 `.upstream_cache/`、`scripts/.upstream_cache/` 与 `.test_tmp/`。

---

## 验证状态

### 已验证
- [x] **Python 单元测试**：全量 40 项通过（`python -B -m unittest scripts.test_rules`，40 tests in 3.1s，OK，0 fail，0 skip）。
- [x] **Node.js 诊断测试**：全量 17 项通过（`node --test tests/test_diagnostic.js`，17 tests in 1.6s，0 fail）。
- [x] **Gaming.lsr 404 消除**：`dist/Gaming.lsr` 正常生成（65 条规则），包含 Steam（51 条）与 Epic（14 条），第三方侵权/促销域名已清洗。
- [x] **Douyin 事故 IP 与 IPv6 回归**：事故样本 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`（China-GeoIP.lsr）；电信 IPv6 `240e:97c:2f:1::1` 命中 `IP-CIDR6,240e::/20,no-resolve`。
- [x] **首命中优先级（First Match Wins）**：`youtube-ui.l.google.com` 命中 `YouTube.lsr`（优先于 Google.lsr）；`drive.google.com` 命中 `GoogleDrive.lsr`；`192.168.1.1` 命中 `Lan.lsr`（优先于 China-GeoIP.lsr）；`17.249.0.5` 命中 `Apple-Push.lsr`。
- [x] **构建流水线上游独立性**：`test_39` 证实缺失 `local_custom` 文件时，上游依然正常抓取并构建产物。
- [x] **镜像校验故障注入测试**：`test_40` 证实双源故障、主源不可达、清单缺失、哈希不符均触发门禁失败，本地完全匹配时返回通过。
- [x] **诊断插件能力边界声明**：401/403/404/502 状态码标注为应用未验证，APNs 标注为 443 探针响应。

### 尚未验证（需 Loon 真机确认）
- [ ] **Loon 手机客户端导入与冷启动**：从 GitHub/jsDelivr 刷新 19 个规则集及诊断插件的实际加载体验。
- [ ] **iOS APNs TCP 5223 绕行**：系统级非 TUN 栈流量在 iOS 设备上的实际推送表现。
- [ ] **Telegram 蜂窝锁屏推送**：蜂窝网络下唤醒与消息即时性实测。
- [ ] **私人唯一 .lcf 装配**：由 ChatGPT Work 在本地基于用户手机最新导出配置完成组装与交付。

---

## 已知问题 / 风险

1. **抖音事故 IP 兜底已闭环**：`China-GeoIP.lsr` 已集成 `ChinaIPs`（19,209 条规则），原事故 IP `119.147.195.212` 命中测试通过。
2. **镜像校验门禁已闭环**：`verify_mirrors.py` 已实现非零退出与故障注入测试覆盖。
3. **Gaming.lsr 404 已闭环**：合并后的 `Gaming.lsr` 已就绪，与用户私人配置保持一致。
4. **分支引用临时性**：当前诊断插件和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需统一切回 `main` 分支地址。
5. **iOS APNs 系统绕行**：若用户未在 Loon 设置中开启“包含 APNS”或连接走非 TUN 栈，TCP 5223 不经过 Loon 代理（属于 iOS 系统机制，需在文档中持续向用户提示）。
6. **诊断插件仅能反映探针连通性**：无法探测未知的动态 App CDN，真机若遇分流异常仍需依赖脱敏请求记录核验。

---

## 不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致全新克隆下测试失败。
2. **不要把“上游已有”当作“本仓库已同步”**：必须在 `sources.yml` 明确声明并经构建流水线集成。
3. **不要用单条 `GEOIP,CN` 替代具体的 CIDR 分流**：纯 IP 直连请求需要具体 IP-CIDR 规则兜底，防止落入 FINAL。
4. **单元测试不要依赖动态外网连接**：外网波动导致 `skipTest` 会让 CI 门禁形同虚设；网络校验应使用独立专项脚本及 mock 故障注入。
5. **严禁向 `.lsr` 写入策略名**：必须保持 100% 策略中立。
6. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则。

---

## 下一步

1. **提交并推送到 GitHub PR #2**：将本次全量修复提交并推送到 `feature/expand-rulesets-v2`。
2. **交付独立复核**：由 ChatGPT Work 在干净克隆环境下执行节点 ① 与节点 ② 的最终验收。
3. **由 ChatGPT Work 装配最终私人 `.lcf`**：将 19 条规则顺序与用户最新手机导出配置合并，交付用户导入。
4. **Loon 真机确认**：由用户导入单文件配置后，在真实手机网络中验证日常分流与推送体验。

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
- **本轮工作**：全面响应《Gemini-Prompt-User-Journey-2026-09-29.md》审计意见：
  1. 恢复 `Gaming.lsr`（合并 Steam/Epic，65 条规则），彻底消除 404 隐患；
  2. 为 `China-GeoIP.lsr` 引入成熟 `ChinaIPs`（19,209 条规则），彻底闭环 Douyin 事故 IP `119.147.195.212` 漏入 FINAL 漏洞；
  3. 修复 `scripts/build.py` 在缺失 custom 文件时跳过上游的缩进缺陷；
  4. 重构 `scripts/verify_mirrors.py`，实现严格 fail-stop 门禁（`sys.exit(1)`），新增 5 种故障注入单元测试；
  5. 修正诊断插件与探针判定标准，精准区分探针连通与 App 功能，明确真机能力边界；
  6. 验证 4 阶段首命中顺序（YouTube/GoogleDrive 先于 Google，Lan 先于 China-GeoIP）；
  7. 全量测试：Python 40/40 通过，Node.js 17/17 通过。
