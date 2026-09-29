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
* **本地已提交 HEAD**：`10492a2`（已全面响应并修复 `fcf35a1` 审核提出的 5 大阻断项）。
* **规则集架构定型**：全库正式定型为 **19 个规则集**（共 **21,092 条有效规则**）。
  * 恢复 `Gaming.lsr`（合并 Steam 与 Epic，65 条规则），彻底解决用户私人配置引用 `Gaming.lsr` 返回 404 的问题。
  * `China-GeoIP.lsr` 引入成熟 GPL-2.0 上游 `ChinaIPs`（19,209 条规则）；离线模拟确认事故 IP `119.147.195.212` 属于 `119.144.0.0/14`，代表 IPv6 `240e:97c:2f:1::1` 属于 `240e::/20`。
* **公开测试与私人配置验收工具彻底分离**：
  * 公开 CI 单元测试 `test_41` 仅绑定仓库存放的公开脱敏夹具 `tests/fixtures/sample_order_19.fixture`，移除任何外部绝对私密路径，严禁因文件缺失而静默跳过（夹具缺失直接报错）。
  * 新增独立本地私人验收工具 `scripts/verify_private_lcf.py`：明确接受 `--lcf-path` 传入私人配置；若指定文件不存在直接以退出码 `1` 报错；仅输出脱敏的规则名、次序和布尔判定，严禁回显代理节点、订阅及凭证。
  * **当前手机配置现状客观说明**：用户当前手机最新导出配置仍存在 `YouTube < Google = False` 及 `Lan < China-GeoIP = False`（尚未修好）；最终配置待由 ChatGPT Work 基于最新手机导出在本地装配修正，保留用户全部节点与策略设置。
* **镜像校验与交付物哈希强校验全面升级**：
  * 构建产物 `manifest.json` 正式加入 `diagnostic_artifacts` 节点，记录 `LoonRules-Diagnostic.lpx` 与 `loon-rules-diagnostic.js` 的确切大小与 SHA256 哈希；全包签名 `package_sha256` 统一纳入规则集与诊断产物。
  * 校验工具 `scripts/verify_mirrors.py` 全面强化：
    1. 发布前本地检查不仅核验 19 个规则集，更严格对比诊断插件与本地源码文件的 SHA256 哈希；
    2. 发布后远程检查严格对比远端 `manifest.json` 中每一条规则集的 SHA256 与规则数、诊断产物哈希及全包签名，杜绝远端元数据篡改；
    3. 严格对比下载的远程诊断 `.lpx` 与 `.js` 文件的 SHA256 哈希，杜绝远端被替换或篡改。
  * 单元测试 `test_40` 补充 3 类故障注入（诊断脚本内容篡改、清单元数据篡改、包签名篡改），实测 100% 触发校验失败并退出。
* **流水线发布前拦截与发布后告警语义明确化**：
  * `.github/workflows/sync-and-build.yml` 明确界定双重门禁职责：
    1. **发布前本地门禁（Pre-Release Fail-Stop Barrier）**：在本地 `git commit / git push` 之前执行，任何规则缺陷、哈希不符或策略词违规均立即非零退出并中断流水线，确保主分支历史与线上发布 100% 零修改、零污染；
    2. **发布后远端监控与告警门禁（Post-Release Health Alert Gate）**：在推送完成后探测 CDN 边缘缓存同步状态；若 CDN 传播超时或损坏，流水线立即退出码 1 标红告警通知维护者。按真实 CI/CD 机制，不执行破坏性的 force-push 回滚，亦不承诺发布后失败还能保证线上完全不受影响。
* **原开发工作区 `dist/` 异常根因彻底查明与永久修复**：
  * **真实根因**：Windows NTFS 文件系统权限继承机制与 Python 标准库行为冲突。`scripts/build.py` 原代码使用 `tempfile.mkdtemp` 创建暂存目录，Windows 下该 API 创建的目录具有受保护的私有 DACL（`D:P`，阻断继承），仅授予当前创建进程所有者（`oocn`）访问权。当该暂存目录重命名覆盖为 `dist` 时，`dist` 保留了该私有 ACL。而 ChatGPT Work 运行于独立的沙箱账户 `CodexSandboxOffline`（隶属于 `CodexSandboxUsers`），缺乏读取权限，因此 Windows 系统底层直接拒绝访问，致使其查看到目录为空、Git 提示 22 个文件删除；而 `oocn` 账户查验始终正常。
  * **修复落地**：
    1. 彻底移除 `tempfile.mkdtemp`，采用标准 `os.makedirs` 创建 `.dist_staging` 暂存目录，保留标准继承权限；
    2. 在 `switch_dist_directory` 中增加 Windows 平台自动权限重置逻辑（`icacls dist /reset /T`），确保工作区权限始终完全继承自根目录，向 `CodexSandboxUsers` 与标准用户完全开放读写权限。
* **诊断短报告样例真实化区分**：
  * 纠正先前使用定制夹具混淆模式的描述，明确区分 Loon 真实运行下的两个模式：
    1. **真实快速模式**：验证 4 个核心规则集（`AI-Overseas.lsr`, `Apple-Push.lsr`, `GoogleDrive.lsr`, `China-Direct.lsr`）与 12 项高频服务，不包含 APNs/Muse（约 17 行）；
    2. **真实完整模式**：验证全部 19 个规则集（主备双源对齐）与全部 16 项服务，显式包含 APNs、Muse、TestFlight 与 Grok 的谨慎说明（约 25 行）。

---

## 已完成事项

### 1. PR #1 阶段（已合并至 main，commit 9a703b3）
- 建立初始 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。

### 2. PR #2 阶段（当前开发中，用户旅程、全库审计与独立复核 5 大阻塞项全面闭环）
- **Gaming.lsr 404 修复与 Steam/Epic 策略合并**：消除 404 故障，维持 19 个规则集体系与用户出口偏好一致。
- **抖音事故 IP 兜底与中国 IP 自治**：为 `China-GeoIP` 引入 blackmatrix7 成熟开源 `ChinaIPs`（19,209 条规则），事故 IP `119.147.195.212` 命中 `IP-CIDR,119.144.0.0/14,no-resolve`。
- **构建流水线健壮性修复（缩进 Bug）**：修复 `scripts/build.py` 上游抓取逻辑被错误缩进在 `if custom_file:` 条件块内的隐患。
- **镜像校验工具严格非零退出门禁与故障注入测试**：重写 `scripts/verify_mirrors.py`，支持 `exit_on_failure`，全量覆盖网络故障与内容损坏。
- **离线受控缓存入库与干净克隆 41/41 测试通过**：将 `scripts/.upstream_cache/7871aa32a3ea6248.list` 正式纳入 Git 跟踪并移除忽略规则，干净克隆稳定 41/41 通过。
- **公开 CI 与本地私人配置验收彻底分离**：
  - `test_41` 仅运行仓库内的公开夹具 `tests/fixtures/sample_order_19.fixture`；
  - 交付独立本地工具 `scripts/verify_private_lcf.py`，必须传入私密配置路径，文件缺失或规则倒置直接失败退出（exit 1），且仅打印脱敏判定。
- **诊断产物与清单哈希一致性强校验**：
  - `manifest.json` 正式记录诊断插件大小与 SHA256，包签名统一纳入诊断插件；
  - `verify_mirrors.py` 在发布前和发布后均对诊断产物进行 SHA256 强校验，并对远端 manifest 规则元数据进行逐项对比；新增 3 类篡改故障注入测试。
- **CI 流水线双重门禁与语义规范化**：
  - 明确发布前本地门禁（本地 fail-stop 拦截，线上零修改）与发布后 CDN 告警门禁（失败立即标红退出，不承诺 force-push 回滚）的职责边界。
- **原开发工作区 dist/ 异常根因查明与权限修复**：
  - 确认 Windows NTFS 下 `tempfile.mkdtemp` 产生的私有 DACL 阻断继承致使 `CodexSandboxUsers` 账号无权读取的根因，改用标准 staging 机制并在目录交换后自动重置 ACL 继承，彻底消除多用户沙箱读取异常。
- **诊断短报告样例真实化输出**：分别针对真实快速模式（4 规则/12 服务）与真实完整模式（19 规则/16 服务/含谨慎提示）提供夹具验证报告。

---

## 当前正在处理

* **阶段**：PR #2 的 5 大独立复核阻塞项已全部修复、测试并通过全新克隆复测。
* **下一步工作**：提交并推送修复代码，交由 ChatGPT Work 进行最终验收，并由 ChatGPT Work 基于最新手机导出配置装配修正唯一私人 `.lcf`。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **Steam 与 Epic 正式合并为 Gaming.lsr**：用户确认两者均走代理出口，合并为 `Gaming.lsr`（65 条规则）消除 404 故障，与用户最新私人配置 19 条远程规则保持零冲突契合。
4. **China-GeoIP 引入 ChinaIPs 兜底**：引入 mature GPL-2.0 的 19,209 条中国 IPv4/IPv6 CIDR，彻底解决纯 IP 直连漏入 FINAL 的结构性缺陷。
5. **Apple 基础服务合并、特殊服务独立**：用户希望可直连的 Apple 基础服务集中在 `Apple-Direct.lsr`；`TestFlight`、`Apple-Media`、`Apple-Push` 保持独立，现有 `Apple Push` 策略组保留。
6. **公开 CI 测试绝不依赖或假装测试本地私人文件**：公开测试严格封闭于仓库公开夹具；私人配置验收采用专用本地工具独立执行，缺文件必须显式报错。
7. **交付物哈希强校验闭环**：不仅规则集正文校验 SHA256，诊断 `.lpx`、`.js` 以及远端清单中的每一项规则元数据与包签名均必须 100% 强比对。
8. **CI 门禁客观透明，杜绝虚假承诺**：发布前本地门禁 100% 阻止坏版本推送；发布后远端检查作为监控告警，检测到边缘不同步时退出码 1 报警，不虚假承诺无损自动回滚。
9. **跨账户与沙箱文件系统权限继承准则**：在 Windows 开发环境中严禁使用 `tempfile.mkdtemp` 等产生私有 DACL 的 API 充当成品目录源，必须保证所有成品目录完全继承标准文件系统 ACL。

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
| `scripts/build.py` | 规则抓取、清洗、构建与带 ACL 继承保障的目录切换流水线 |
| `scripts/test_rules.py` | 规则系统公开单元测试套件（全量 41 项测试，含 8 种故障注入与公开夹具） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具（支持 4 阶段流水线与 LRU 缓存） |
| `scripts/verify_mirrors.py` | 独立镜像与预发布门禁校验工具（含规则/诊断/清单全量 SHA256 强校验） |
| `scripts/verify_private_lcf.py` | 独立本地脱敏私人 `.lcf` 验收工具（缺文件必崩，仅输出脱敏布尔结果） |
| `.github/workflows/sync-and-build.yml` | GitHub Actions 自动化流水线（发布前本地强门禁 + 发布后 CDN 监控告警） |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（精确标注 HTTP 状态与能力边界，报告可见） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件（19 规则集配置） |
| `diagnostics/services.yml` | 诊断探针服务元数据（12 快速 / 4 完整项） |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（18 项测试） |
| `tests/fixtures/sample_order_19.fixture` | 公开、脱敏、策略中立的 19 类规则顺序测试夹具 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `scripts/build.py`：移除 `tempfile.mkdtemp`，改用 `.dist_staging`；在 `manifest.json` 中增加 `diagnostic_artifacts` 哈希记录；在目录切换后调用 `icacls` 重置 Windows 权限继承。
* `scripts/verify_mirrors.py`：升级发布前与发布后校验，增加诊断产物 SHA256 强对比及远端 manifest 逐条元数据比对。
* `scripts/test_rules.py`：将 `test_41` 严格限定于公开夹具；在 `test_40` 中新增诊断产物篡改、清单元数据篡改及包签名篡改 3 类故障注入测试。
* `scripts/verify_private_lcf.py`：新增独立私人配置验收工具，提供严格参数检查与脱敏顺序判定。
* `.github/workflows/sync-and-build.yml`：优化双重门禁注释与步骤命名，准确表述发布前拦截与发布后告警职责。
* `dist/diagnostics/manifest.json`：重新构建生成，包含诊断产物确切哈希与新包签名。
* `PROJECT_STATE.md`：更新最新实测数据与状态记录。

---

## 验证状态

### 已验证
- [x] **干净克隆 Python 单元测试（41/41）**：在干净克隆、无外网依赖下全量 41 项测试通过（`python -B -m unittest scripts.test_rules`，4.2s，OK，0 fail，0 skip）。
- [x] **Node.js 诊断测试（18/18）**：全量 18 项通过（`node --test tests/test_diagnostic.js`，1.7s，0 fail）。
- [x] **预发布本地完整性强门禁**：`python scripts/verify_mirrors.py --pre-release` 严格校验 19 个规则集策略中立、条数、SHA256 及诊断插件产物哈希，退出码 0。
- [x] **镜像与交付物篡改注入测试**：`test_40` 覆盖 8 种场景，证实当诊断 JS/LPX 内容篡改、远端清单单项规则 SHA 改为全零、包签名篡改、清单规则缺失或网络故障时，100% 触发校验失败退出。
- [x] **本地私人配置验收工具**：`scripts/verify_private_lcf.py` 经测试，缺文件时 100% 以退出码 1 报错；测试公开夹具与候选配置时输出清晰的脱敏布尔判定（YouTube < Google, Lan < China-GeoIP）。
- [x] **原开发工作区 dist/ 权限与现场确认**：ACL 继承已重置，`CodexSandboxUsers` 权限恢复，工作区 22 个成品文件完整有效。
- [x] **双模式真实短报告生成**：真实快速模式（4 规则/12 服务，17 行）与真实完整模式（19 规则/16 服务/含谨慎说明，25 行）已脱敏验证输出。

### 尚未验证（需 Loon 真机确认）
- [ ] **Loon 手机客户端导入与冷启动**：从 GitHub/jsDelivr 刷新 19 个规则集及诊断插件的实际加载体验与冷启动时间。
- [ ] **iOS APNs TCP 5223 系统绕行**：系统级非 TUN 栈流量在 iOS 设备上的实际推送表现（提示用户按需开启“包含 APNS”）。
- [ ] **Telegram 蜂窝锁屏推送**：蜂窝网络下唤醒与消息即时性实测。
- [ ] **多设备与特种协议**：HomeKit 室内摄像头即时视频推流、Apple Watch 独立蜂窝联网及 CloudKit 双向同步。
- [ ] **唯一私人配置装配**：由 ChatGPT Work 基于最新手机导出配置完成最终规则顺序修正与装配。

---

## 已知问题 / 风险

1. **用户当前手机配置顺序待修**：最新手机导出配置中 YouTube 仍位于 Google 之后，Lan 仍位于 China-GeoIP 之后；待由 ChatGPT Work 在装配唯一交付配置时予以修正。
2. **分支引用临时性**：当前诊断插件和测试引用的是 `feature/expand-rulesets-v2` 分支地址。PR #2 合并至 `main` 后，需统一切回 `main` 分支地址。
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

---

## 下一步

1. **提交并推送到 GitHub PR #2**：将本次全量修复提交并推送到 `feature/expand-rulesets-v2`。
2. **交付独立复核**：由 ChatGPT Work 在干净克隆环境下对新提交进行最终验收。
3. **装配唯一私人 `.lcf`**：由 ChatGPT Work 基于最新手机导出配置装配完成，修正首命中顺序，交付用户导入。
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
- **本轮工作**：全面响应《Gemini-PR2-Review-fcf35a1-2026-09-29.md》独立复核阻断项：
  1. 彻底分离公开测试与私人验收：`test_41` 仅测公开夹具，新增独立 `scripts/verify_private_lcf.py` 工具，明确传入私人配置并强制校验存在性与脱敏首命中顺序；
  2. 强化交付物强哈希校验：`manifest.json` 与 `verify_mirrors.py` 正式接入诊断产物 SHA256 强校验与远端清单逐项元数据/包签名校验，新增 3 类篡改故障注入测试；
  3. 规范化 CI 流水线职责：明确发布前本地强门禁（fail-stop 阻止推送）与发布后 CDN 监控告警（失败标红通知）边界；
  4. 根治 `dist/` 异常：查明 Windows NTFS 下 `tempfile.mkdtemp` 私有 DACL 阻断跨用户继承的机理，恢复标准继承权限；
  5. 真实输出快速模式（4 规则/12 服务）与完整模式（19 规则/16 服务/含谨慎提示）两份规范诊断短报告。
