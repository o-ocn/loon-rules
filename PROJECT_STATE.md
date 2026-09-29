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

* **当前分支**：`feature/expand-rulesets-v2`（对应 GitHub PR #2，尚未合并至 `main`）。
* **最新提交**：待提交（包含节点 ①：覆盖契约、Douyin 事故回归、Steam/Epic 分立、IPv4/IPv6 检查与干净克隆夹具入库）。
* **阶段状态**：已完成**节点 ①（覆盖契约与事故回归）**全部工作，等待 ChatGPT Work 独立复核。
* **工作区检查**：
  * 已确认此前 `dist/` 显示的未提交删除为单元测试中目录原子切换（`test_29_atomic_directory_switch_and_rollback`）执行过程中的毫秒级暂态，实际文件完整受控。
  * 全库规则集正式扩充并分立为 **20 个规则集**（共 **1,884 条有效规则**）。
  * 根目录 `tests/fixtures/sample_order_20.fixture` 已替代被忽略的 `.lcf` 夹具，彻底解决全新克隆下测试失败问题。
* **测试套件状态**：
  * Python 单元测试：**38/38 全量通过**（无失败，无跳过，测试耗时 ~1.3s）。
  * Node.js 诊断逻辑：**17/17 全量通过**（已同步适配 20 规则集）。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，节点 ① 已闭环）
- **dist 状态与暂态核实**：确认为原子目录切换测试中的瞬时状态，实际 `dist/` 完整且零损坏。
- **全 ruleset 覆盖矩阵与 Steam/Epic 分立（20 规则集体系）**：
  - 响应审查意见，将 `Gaming.lsr` 重新拆分为独立的 `Steam.lsr`（51 条）与 `Epic.lsr`（14 条），恢复用户在客户端对两款平台独立选择出口策略的能力。
  - 保留已验证的第三方域名清洗（排除 `steamunlocked.net`、`humblebundle.com`、`fanatical.com` 与 `helpshift.com`）。
- **Douyin 真实事故定位与修复**：
  - **根因确认**：此前 `China-Direct` 在 `sources.yml` 声明了 Douyin/Bilibili，但上游仅配置了 WeChat、Alibaba、JingDong，Custom 仅补了 `douyin.com` 和 `snssdk.com`，导致 Douyin 核心图片与 CDN 域名（`douyinpic.com`、`douyincdn.com`、`douyinstatic.com` 等）未命中任何规则而落入 `FINAL`。
  - **修复落地**：在 `sources.yml` 为 `China-Direct` 正式引入官方成熟上游 `DouYin`（13 条）与 `BiliBili`（127 条），并在 `rules/custom/China-Direct.list` 中补齐字节国内基础设施域名（`bytedance.com`、`byteimg.com`、`zijieapi.com`、`ibytedtos.com`）。
  - **回归测试**：新增 `test_36_douyin_incident_regression`，对事故样本中的 `p3-sign.douyinpic.com` 等 18 个关键域名进行仿真命中断言，100% 确认命中 `China-Direct.lsr`。
- **声明契约与覆盖机器契约**：
  - 新增 `test_38_coverage_and_machine_contract`，通过程序严格断言 `sources.yml`（20 类）、`upstream_lock.json`、`dist/*.lsr` 与 `manifest.json` 之间的全要素契约，且 100% 保证规则策略中立性（零策略动作泄露）。
- **IPv4 / IPv6 语法与包含关系严格检查**：
  - 新增 `test_37_ip_cidr_syntax_and_containment`，通过 Python `ipaddress` 对全量规则中的每一个 IP-CIDR 与 IP-CIDR6 执行严格验证（禁止主机位不为 0、禁止前缀超限、严格区分 IPv4 与 IPv6），并断言 Lan 在 GeoIP 之前的优先级及 Apple Push、Telegram IP 包含。
- **测试夹具入库（解决全新克隆失败）**：
  - 将脱敏测试夹具命名为 `tests/fixtures/sample_order_20.fixture`（不受 `.gitignore` 中的 `*.lcf` 影响），保持对私人 `.lcf` 的严格忽略防泄密保护。
- **离线测试与真实镜像检查解耦**：
  - 单元测试 `test_35` 改造为纯离线结构与规则体 SHA256 契约测试（无网络依赖，杜绝 CI 中静默 skip）。
  - 新增独立脚本 `scripts/verify_mirrors.py`，专门用于发版前对 GitHub Raw 与 jsDelivr 备用 CDN 的 20 份规则及清单进行零跳过的真实联网比对。
- **GitHub Actions CI 升级**：
  - 更新 `.github/workflows/sync-and-build.yml`，增加 `pull_request` 触发分支检查，并在非 PR 事件中才执行 tag/push。

---

## 当前正在处理

* **阶段**：**交接节点 ① 完成**，提交代码并交付 ChatGPT Work 进行独立复核。
* **待复核要点**：
  1. 确认全新克隆下 Python 单测（38 项）与 Node 测试（17 项）100% 可复现通过，零失败、零跳过。
  2. 复核 Steam/Epic 分立及 20 规则集机器契约。
  3. 复核 Douyin 图片/CDN 域名事故回归与 IP 检查。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **保留独立选择能力**：遵循用户既有使用习惯，Steam 与 Epic 保持独立远程规则分类，不强制捆绑。
4. **单文件导入与安全装配**：用户仅导入一份由 ChatGPT Work 在本地装配的唯一私人 `.lcf` 文件；严禁在公开仓库、测试夹具或交互中泄露私人配置。
5. **门禁解耦**：单元测试追求 100% 离线可复现，真实网络与 CDN 校验由发布脚本严格执行，避免网络波动干扰自动化 CI。

---

## 重要文件与目录

| 路径 | 用途 |
|---|---|
| `PROJECT_STATE.md` | 本项目当前状态的唯一事实源（跨 AI 协作必读必更） |
| `AGENTS.md` | AI / Agent 工作准则与交接规则 |
| `README.md` | 项目对外公开说明与规则订阅说明（已更新至 20 规则集） |
| `sources.yml` | 规则源声明清单、上游 URL、最小规则数与排除项定义 |
| `dist/` | 构建生成的 20 个策略中立 `.lsr` 文件及诊断产物 |
| `rules/custom/` | 各服务本地补充与例外规则（需有抓包或官方依据） |
| `scripts/build.py` | 规则抓取、解析、去重、清洗与原子发布构建流水线 |
| `scripts/test_rules.py` | 规则系统单元测试套件（全量 38 项测试） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 20 类分流） |
| `scripts/verify_mirrors.py` | 独立镜像真实联网校验工具（零跳过，严格退出码） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（支持动态分支与多源校验） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件 |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（17 项测试） |
| `tests/fixtures/sample_order_20.fixture` | 公开、脱敏、策略中立的 20 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `sources.yml`：拆分 `Gaming` 为 `Steam` 和 `Epic`；为 `China-Direct` 增加 `DouYin` 和 `BiliBili` 官方上游。
* `rules/custom/China-Direct.list`：补入字节跳动国内基础服务域名，清理上游已收录的冗余项。
* `scripts/test_rules.py`：升级至 20 规则集体系，新增测试 36（Douyin事故回归）、37（IPv4/IPv6语法与包含检查）、38（机器覆盖契约），修复 32（采用 .fixture 夹具）与 35（离线契约）。
* `tests/fixtures/sample_order_20.fixture`：新建并入库 20 类脱敏测试夹具。
* `scripts/verify_mirrors.py`：新建独立严格镜像校验工具。
* `.github/workflows/sync-and-build.yml`：加入 `pull_request` CI 触发。
* `README.md` 与诊断插件：更新为 20 规则集说明。

---

## 验证状态

### 已验证
- [x] **Python 单元测试**：全量 38 项通过（`python -B -m unittest scripts.test_rules`，38 tests in 1.265s，OK，0 fail，0 skip）。
- [x] **Node.js 诊断测试**：全量 17 项通过（`node --test tests/test_diagnostic.js`，17 tests in 1.6s，0 fail）。
- [x] **全 ruleset 覆盖契约**：20 个 ruleset 声明与来源、上游锁、产物全量通过机器检查。
- [x] **Douyin 事故回归**：18 个关键图片/CDN 域名全部命中 `China-Direct.lsr`，零漏入 FINAL。
- [x] **IPv4/IPv6 检查**：全量 CIDR 规则语法及前缀合法，无主机位溢出，Lan 与 Push 优先级正常。
- [x] **夹具入库**：`sample_order_20.fixture` 已通过 git 跟踪，不再受 `*.lcf` 忽略影响。

### 尚未验证（节点 ② & ③ 待办）
- [ ] **全新临时克隆复测**：在未初始化的临时目录全新 clone 并跑通门禁。
- [ ] **发版后镜像校验**：待提交推送到 GitHub 后，执行 `verify_mirrors.py` 检验 CDN 镜像一致性。
- [ ] **Loon 真机环境表现**：手机端导入后的分流体验、冷启动可达性及 APNs 推送长连接实测。

---

## 已知问题 / 风险

1. **分支引用临时性**：当前诊断插件和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需统一切回 `main` 分支地址。
2. **iOS APNs 系统绕行**：若用户未在 Loon 设置中开启“包含 APNS”或连接走非 TUN 栈，TCP 5223 不经过 Loon 代理（属于 iOS 系统机制，需在文档中持续向用户提示）。

---

## 不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致全新克隆下测试失败。
2. **不要把“上游已有”当作“本仓库已同步”**：`China-Direct` 此前因未声明 DouYin 上游导致图片域名漏入 FINAL。
3. **不要用 `GEOIP,CN` 替代具体的域名分流**：国内 App 在非解析或代理模式下漏判会导致流量落入 FINAL。
4. **单元测试不要依赖动态外网连接**：外网波动导致 `skipTest` 会让 CI 门禁形同虚设；网络校验应使用独立专项脚本。
5. **严禁向 `.lsr` 写入策略名**：必须保持 100% 策略中立。
6. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则。

---

## 下一步

1. **交付节点 ① 复核**：通知 ChatGPT Work 在独立克隆中复跑门禁并核验覆盖矩阵与 Douyin 回归。
2. **推进节点 ②（全新克隆与自动更新链）**：从全新克隆验证构建幂等性，验证无规则变化时不产生幽灵构建，校验 GitHub Actions 配置。
3. **推进节点 ③（正式发布就绪）**：完成正式发布切换方案，配合 ChatGPT Work 装配最终私人 `.lcf` 并准备真机测试。

---

## 环境 / 部署说明

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 18+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **交付与复核路径**：`E:\Document\ChatGPT\Loon-Migration`
* **版本控制**：Git（GitHub 远程仓库 `o-ocn/loon-rules`，PR #2）

---

## 最后更新

- **时间**：2026-09-29 14:06
- **执行者**：Antigravity (Gemini)
- **本轮工作**：完成节点 ①（全 ruleset 覆盖矩阵建立、Steam/Epic 分立为 20 类、Douyin 事故修复与回归测试、IPv4/IPv6 检查、测试夹具脱敏入库、机器契约自动化断言）。
