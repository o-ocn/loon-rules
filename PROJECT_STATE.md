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
* **本地已提交 HEAD**：`deeabea`（已全面闭环独立复核 5 大阻塞项）。
* **规则集架构定型**：全库正式定型为 **19 个规则集**（共 **21,092 条有效规则**）。
  * 恢复 `Gaming.lsr`（合并 Steam 与 Epic，65 条规则），彻底解决用户私人配置引用 `Gaming.lsr` 返回 404 的问题。
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 上游 `ChinaIPs`（19,209 条规则）；离线模拟确认事故 IP `119.147.195.212` 属于 `119.144.0.0/14`，代表 IPv6 `240e:97c:2f:1::1` 属于 `240e::/20`。
* **分流首命中顺序与真实私人配置验证**：
  * 4 阶段匹配流水线仿真验证通过（Stage 1 Local -> Stage 2 Plugin -> Stage 3 Remote -> Stage 4 FINAL）。
  * 严格保证首命中优先级（First Match Wins）：具体分类先于宽泛分类（YouTube、GoogleDrive 在 Google 之前，`youtube-ui.l.google.com` 稳定命中 YouTube）；内网穿透先于大网兜底（Lan 在 China-GeoIP 之前；Apple Push 在 China-GeoIP 之前）。
  * 新增单元测试 `test_41`，不仅验证公开夹具 `tests/fixtures/sample_order_19.fixture`，亦对用户本地最新私人配置 `E:\Document\ChatGPT\Loon-Migration\Loon-v2-19Rules.lcf` 进行脱敏真实引用、启用状态与首命中顺序自动化检查（全量通过，无泄漏）。
* **构建与发布工具链升级（双重门禁落地）**：
  * 修复离线测试缓存独立性：将 `ChinaIPs` 受控上游缓存 `scripts/.upstream_cache/7871aa32a3ea6248.list` 纳入 Git 跟踪并移除相关 `.gitignore` 规则，同时在 `scripts/test_rules.py` 中增加动态保底，在全新克隆、空缓存环境下实测 **41/41 项测试全部通过**（0 skip，0 fail，4.3s）。
  * 自动化工作流 `.github/workflows/sync-and-build.yml` 正式集成双重门禁：
    1. **发布前本地完整性门禁**：调用 `python scripts/verify_mirrors.py --pre-release`，严格校验 19 个 `.lsr` 的策略中立、规则条数、SHA256 及诊断插件产物，任一失败立即退出，彻底阻断 Git Commit / Tag / Push 流程，100% 保留线上上一稳定版本；
    2. **发布后主备镜像门禁**：在发布完成后等待 10 秒边缘缓存同步，调用 `python scripts/verify_mirrors.py --branch <ref>` 对 GitHub Raw 与 jsDelivr 双源进行 19/19 规则集与诊断产物逐项 SHA256 强校验。
* **诊断插件报告可见性与真机边界彻底闭环**：
  * `diagnostics/loon-rules-diagnostic.js` 全面修复：将 HTTP 401/403/404/502、APNs（HTTPS 443 探针）与 Muse 的谨慎说明直接整合入可复制终端报告 `reportLines` 中（显式输出 `- 端点有响应但应用功能待真机验证 (共 N 项):` 及细分提示），并在总结段落对谨慎项目给出限定性结论。
  * `tests/test_diagnostic.js` 新增 Subtest 18 断言此报告可见性，全量 **18/18 项 Node.js 测试通过**。
* **原开发工作区 `dist/` 现象排查**：
  * 原因已查明：`scripts/build.py` 中 `switch_dist_directory` 在 Windows NTFS 下执行目录重命名交换（`dist` -> `.dist_old` -> `dist_new` -> `dist`）时存在系统调用窗口；在并发进程、文件索引或外部文件监控持有句柄时，可能导致瞬时或单次中断留下空目录。
  * 现工作区已彻底核验并恢复完整，包含全部 19 个 `.lsr`、诊断插件及清单文件（共 22 个文件全部受控跟踪），与干净克隆完全一致。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，用户旅程、全库审计与独立复核 5 大阻塞项全面闭环）
- **Gaming.lsr 404 修复与 Steam/Epic 策略合并**：
  - 响应用户最新私人配置保留 `Gaming.lsr` 的实际情况，将 Steam 与 Epic 统一合并为 `Gaming.lsr`（65 条规则），消除 404 故障，维持 19 个规则集体系与用户出口偏好一致。
- **抖音事故 IP 兜底与中国 IP 自治**：
  - 为 `China-GeoIP` 引入 blackmatrix7 成熟开源 `ChinaIPs`（19,209 条规则），事故 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`，电信 IPv6 `240e:97c:2f:1::1` 命中 `IP-CIDR6,240e::/20,no-resolve`。
- **构建流水线健壮性修复（缩进 Bug）**：
  - 修复 `scripts/build.py` 上游抓取逻辑被错误缩进在 `if custom_file:` 条件块内的隐患（`test_39` 验证）。
- **镜像校验工具严格非零退出门禁与故障注入测试**：
  - 重写 `scripts/verify_mirrors.py`，支持 `exit_on_failure`，新增 5 种故障注入测试（`test_40`）覆盖网络不可达、404、清单不符、SHA256 损坏等场景。
- **离线受控缓存入库与干净克隆 41/41 测试通过**：
  - 将 `scripts/.upstream_cache/7871aa32a3ea6248.list` 正式纳入 Git 跟踪并移除忽略规则，增加测试保底逻辑；干净克隆全新运行 `python -B -m unittest scripts.test_rules` 稳定 41/41 通过（0 skip，0 fail）。
- **CI 流水线双重门禁真正接入**：
  - 更新 `.github/workflows/sync-and-build.yml`，在构建与单元测试后、提交推送前加入 `python scripts/verify_mirrors.py --pre-release` 门禁；在发布后加入双镜像校验，失败时即刻中止并保留上一稳定版本。
- **诊断插件用户可见报告与边界提示闭环**：
  - 修复 `diagnostics/loon-rules-diagnostic.js` 使 `res.verdict` 谨慎提示进入可复制短报告 `reportLines` 和最终结论；更新 `dist/` 对应脚本；新增 Subtest 18，Node.js 诊断测试 18/18 全通。
- **私人配置脱敏结构与首命中自动化验证（test_41）**：
  - 在 `scripts/test_rules.py` 中新增 `test_41`，对用户本地私人配置 `Loon-v2-19Rules.lcf` 验证 19 个规则集引用完整性及 YouTube < Google、GoogleDrive < Google、Lan < China-GeoIP、Apple-Push < China-GeoIP 的首命中顺序，全部验证通过。
- **原工作区 dist/ 现象排查与现场复原**：
  - 定位 Windows NTFS 目录级交换竞争窗口机理，确认当前工作区包含全部 22 个成品且 Git 树干净整洁。

---

## 当前正在处理

* **阶段**：PR #2 的 5 大独立复核阻塞项已全部修复并经全新克隆本地全量验证。
* **下一步工作**：提交并推送修复代码，提交 ChatGPT Work 进行最终验收，并由 ChatGPT Work 在本地安全装配唯一私人 `.lcf` 配置供用户真机导入。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **Steam 与 Epic 正式合并为 Gaming.lsr**：用户确认两者均走代理出口，合并为 `Gaming.lsr`（65 条规则）消除 404 故障，与用户最新私人配置 19 条远程规则保持零冲突契合。
4. **China-GeoIP 引入 ChinaIPs 兜底**：引入 mature GPL-2.0 的 19,209 条中国 IPv4/IPv6 CIDR，彻底解决纯 IP 直连漏入 FINAL 的结构性缺陷。
5. **Apple 基础服务合并、特殊服务独立**：用户希望可直连的 Apple 基础服务集中在 `Apple-Direct.lsr`；`TestFlight`、`Apple-Media`、`Apple-Push` 保持独立，现有 `Apple Push` 策略组保留。
6. **受控缓存入库确保零网络测试独立性**：将大型规则缓存纳入版本控制，彻底根除 CI 或干净克隆运行单元测试依赖外网或特定开发者本机缓存的隐患。
7. **CI 流程发布前拦截与失败零污染**：预发布本地门禁必须在 `git commit/push` 前阻断，任何规则损坏绝不进入主分支发布历史或 CDN 缓存。
8. **诊断报告实事求是，严禁虚假全绿**：针对 HTTP 401/403/404/502、APNs 及 Muse，报告显式声明“端点有响应但应用功能待真机验证”，结论不得直接宣布 App 功能正常。
9. **单文件导入与安全装配**：用户仅导入一份由 ChatGPT Work 在本地装配的唯一私人 `.lcf` 文件；以最新手机导出配置为私人基准，保留用户新增设置、策略组与手动出口选择；严禁在公开仓库、测试夹具或交互中泄露私人配置。

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
| `scripts/build.py` | 规则抓取、解析、去重、清洗与原子发布构建流水线 |
| `scripts/test_rules.py` | 规则系统单元测试套件（全量 41 项测试，含 test_39/40/41） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 4 阶段流水线与 LRU 缓存） |
| `scripts/verify_mirrors.py` | 独立镜像与预发布门禁校验工具（支持 --pre-release 与 fail-stop） |
| `.github/workflows/sync-and-build.yml` | GitHub Actions 自动化流水线（已集成发布前与发布后双重门禁） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（精确标注 HTTP 状态与能力边界，报告可见） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件（19 规则集配置） |
| `diagnostics/services.yml` | 诊断探针服务元数据 |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（18 项测试，含 Subtest 18） |
| `tests/fixtures/sample_order_19.fixture` | 公开、脱敏、策略中立的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `scripts/.upstream_cache/7871aa32a3ea6248.list`：将 ChinaIPs 离线缓存入库并自 `.gitignore` 移除忽略。
* `scripts/test_rules.py`：为离线构建增加受控保底；新增 `test_41` 脱敏校验私人配置与公开夹具的首命中顺序。
* `.github/workflows/sync-and-build.yml`：集成 `verify_mirrors.py --pre-release` 本地门禁及发布后镜像校验。
* `scripts/verify_mirrors.py`：扩展支持 `--pre-release` 模式，同时覆盖 19 个 `.lsr` 与诊断插件文件（.lpx / .js / manifest）。
* `diagnostics/loon-rules-diagnostic.js` & `dist/diagnostics/`：将谨慎提示全面写入最终可复制短报告 `reportLines` 及结论。
* `tests/test_diagnostic.js`：新增 Subtest 18 验证谨慎提示在复制报告中的显式呈现。
* `PROJECT_STATE.md`：更新最新实测数据与状态记录。

---

## 验证状态

### 已验证
- [x] **干净克隆 Python 单元测试（41/41）**：在干净克隆、无外网依赖下全量 41 项测试通过（`python -B -m unittest scripts.test_rules`，4.3s，OK，0 fail，0 skip）。
- [x] **Node.js 诊断测试（18/18）**：全量 18 项通过（`node --test tests/test_diagnostic.js`，1.7s，0 fail）。
- [x] **预发布本地完整性门禁**：`python scripts/verify_mirrors.py --pre-release` 严格校验 19 个规则集及诊断插件产物，退出码 0。
- [x] **CI 发布故障阻断能力**：`test_40` 证实清单缺失、SHA256 损坏或网络异常时，脚本 100% 触发非零退出，CI 工作流立即中止，不触发 Commit/Push/Tag，原线上版本完整保留。
- [x] **线上主备镜像一致性校验**：`python scripts/verify_mirrors.py --branch feature/expand-rulesets-v2` 联网实测 GitHub Raw 与 jsDelivr 双源 19/19 规则集及诊断插件 SHA256 100% 对齐。
- [x] **诊断报告真实可见性**：Subtest 18 实测证实 HTTP 401/403/404/502、APNs 与 Muse 谨慎提示完整呈现在复制短报告中，杜绝虚假全绿。
- [x] **用户私人配置脱敏结构与首命中校验**：`test_41` 证实 `Loon-v2-19Rules.lcf` 包含全部 19 个规则集且顺序正确（YouTube/Drive 在 Google 之前，Lan/ApplePush 在 China-GeoIP 之前），`119.147.195.212` 命中 China-GeoIP。
- [x] **工作区 dist/ 健康度恢复**：原开发目录 `dist/` 22 个成品完整有效，Git 跟踪一致。

### 尚未验证（需 Loon 真机确认）
- [ ] **Loon 手机客户端导入与冷启动**：从 GitHub/jsDelivr 刷新 19 个规则集及诊断插件的实际加载体验与冷启动时间。
- [ ] **iOS APNs TCP 5223 系统绕行**：系统级非 TUN 栈流量在 iOS 设备上的实际推送表现（提示用户按需开启“包含 APNS”）。
- [ ] **Telegram 蜂窝锁屏推送**：蜂窝网络下唤醒与消息即时性实测。
- [ ] **多设备与特种协议**：HomeKit 室内摄像头即时视频推流、Apple Watch 独立蜂窝联网及 CloudKit 双向同步。

---

## 已知问题 / 风险

1. **分支引用临时性**：当前诊断插件和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需统一切回 `main` 分支地址。
2. **iOS APNs 系统绕行**：若用户未在 Loon 设置中开启“包含 APNS”或连接走非 TUN 栈，TCP 5223 不经过 Loon 代理（属于 iOS 系统机制，需在文档中持续向用户提示）。
3. **诊断插件仅能反映探针连通性**：无法探测未知的动态 App CDN，真机若遇分流异常仍需依赖脱敏请求记录核验。
4. **Loon 真机大规则集性能需观测**：`China-GeoIP.lsr` 包含 19,209 条 CIDR 规则，真机加载耗时需在导入单文件后初次观察。

---

## 不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致全新克隆下测试失败。
2. **不要把“上游已有”当作“本仓库已同步”**：必须在 `sources.yml` 明确声明并经构建流水线集成。
3. **不要用单条 `GEOIP,CN` 替代具体的 CIDR 分流**：纯 IP 直连请求需要具体 IP-CIDR 规则兜底，防止落入 FINAL。
4. **单元测试不要依赖动态外网连接或本地机器残留缓存**：必须将离线受控夹具入库或构造完整 mock，确保任何干净克隆 100% 离线通过。
5. **严禁向 `.lsr` 写入策略名**：必须保持 100% 策略中立。
6. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则。
7. **Windows NTFS 目录原子重命名限制**：Windows 下目录交换并非单条原子系统调用，排查时注意进程并发及文件锁暂态，避免将中间暂态误判为永久丢失。

---

## 下一步

1. **提交并推送到 GitHub PR #2**：将本次全量修复提交并推送到 `feature/expand-rulesets-v2`。
2. **交付独立复核**：由 ChatGPT Work 在干净克隆环境下对新提交进行最终验收。
3. **交付唯一私人 `.lcf`**：由 ChatGPT Work 基于用户最新手机导出配置装配完成，交付用户导入。
4. **Loon 真机确认**：由用户导入单文件配置后，在真实手机网络中验证冷启动、规则刷新与日常推送。

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
- **本轮工作**：全面响应《Gemini-PR2-Review-2f3aed6-2026-09-29.md》独立复核阻断项：
  1. 修复离线测试上游缓存，`ChinaIPs` 缓存正式入库，全新克隆下 Python 单元测试 41/41 稳定通过；
  2. 工作流正式接入发布前本地完整性门禁（`verify_mirrors.py --pre-release`）与发布后主备镜像强校验，确保故障时 100% 阻断且旧版不被污染；
  3. 修复诊断插件短报告可见性，将 HTTP 401/403/404/502、APNs 与 Muse 谨慎说明直接呈现在复制报告与结论中，新增 Subtest 18，Node.js 18/18 全通；
  4. 新增 `test_41`，对用户最新私人配置 `Loon-v2-19Rules.lcf` 脱敏完成 19 规则集引用与首命中顺序自动化检查；
  5. 查明原开发工作区 `dist/` 空目录原因，恢复完整现场并同步至 ChatGPT 迁移目录。
