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
* **最新提交**：`d7e4212`（在提交 `f8f1144` 基础上增加了 `AGENTS.md` 与交接事实源规范）。
* **独立复审结论**：ChatGPT Work 使用全新独立克隆 `review-pr2-f8f1144` 完成了对 `f8f1144` 的独立复跑验收：
  * Node 诊断测试 **17/17 通过**。
  * Python 规则测试在干净克隆下共 35 项，**1 失败、1 跳过**：失败原因为测试夹具 `tests/fixtures/sample_order_19.lcf` 被根目录 `.gitignore` 全局 `*.lcf` 规则自动忽略，导致未入库提交；跳过为备用镜像网络连通性受环境影响时触发 `skipTest`。
  * 候选私密 `.lcf` 结构完整，保留既有节点、订阅、策略组与 MitM 结构，19 个唯一自有规则排序无误。
  * **工作区检查**：当前原工作区 `dist/` 完整且已被 git 跟踪，工作区处于正常干净状态。
* **验收结果**：PR #2 仍处于复审迭代阶段，尚未合并。待根据审查意见完成夹具入库、Steam/Epic 拆分、镜像门禁与冷启动说明后，再次进行独立验收。

---

## 已完成事项

- **PR #1 基础底座建设**（已合并至 `main`，commit `9a703b3`）：
  - 建立 14 个自托管规则集、自动构建流水线 `build.py`、8 大服务边界隔离断言及原生诊断插件。
- **PR #2 规则扩展与排序优化**（commit `f8f1144`）：
  - 完成从 14 到 19 规则集扩充：新增 `PayPal.lsr`、`Gaming.lsr`、`GitHub.lsr`、`Lan.lsr`、`China-GeoIP.lsr`，增补 SystemOTA、Siri、AppleID。
  - 将 `Apple-Push.lsr`（10 条企业规范网段）调整为远端规则优先级 #1。
  - 修正分流匹配顺序：细分规则在前，宽泛规则在后（`YouTube` 与 `GoogleDrive` 排在 `Google` 前；`Lan` 排在 `China-GeoIP` 前）。
  - Gaming 规则清洗：通过 `filter_excluded` 剔除 `steamunlocked.net`、`humblebundle.com`、`fanatical.com`、`helpshift.com` 等 4 个非平台专属与盗版域名。
  - 诊断脚本增加 `$argument` 多分支动态支持（`branch=feature/expand-rulesets-v2`）。
  - 剔除 APNs“0 延迟、100% 命中 TCP 5223”等绝对化承诺，明确真机测试验收边界。
  - 彻底清理仓库与文档中让用户手动逆序导入 19 次的历史操作指引。
- **跨 AI 交接机制建立**（commit `d7e4212`）：
  - 新增 `AGENTS.md` 规范跨 Agent 协作流程与更新准则。
  - 初始化根目录 `PROJECT_STATE.md` 作为全项目唯一事实源。

---

## 当前正在处理

1. **测试夹具入库修复**：将 `tests/fixtures/sample_order_19.lcf` 更名为不受 `.gitignore` 影响的扩展名（如 `.fixture` 或 `.txt`），更新 `scripts/test_rules.py` 路径并提交，确保全新克隆下测试 100% 可复现。
2. **Steam 与 Epic 分立恢复**：将 `Gaming.lsr` 重新拆分为独立的 `Steam.lsr` 与 `Epic.lsr`（全库规则集由 19 变为 20 个），保留已验证的第三方域名清洗，恢复用户在 Loon 客户端对两者独立选出口的能力。
3. **镜像门禁与离线单测解耦**：将常规单测与网络集成测试分离，避免因外网网络波动导致单测跳过；完善主备镜像 SHA256 校验逻辑。
4. **发布流程与大陆冷启动说明**：明确 PR 临时分支与 `main` 正式发布时的脚本 URL 转换流程；客观阐明 Loon 首次冷启动边界。

---

## 关键决策

1. **策略绝对中立**：所有 `.lsr` 规则文件绝不硬编码策略动作（如 DIRECT/PROXY/REJECT/US 等），由用户在客户端按需自由绑定策略组。
2. **细分服务必须排在宽泛服务之前**：遵循 Loon 首个命中（First Match Wins）语义，细分规则（如 YouTube、Drive）必须在对应宽泛服务（Google）之前，防止流量被泛域名规则误劫持。
3. **成熟上游为主，Custom 最小补丁**：以成熟许可上游（`blackmatrix7`）为主体，Custom 仅补有公开依据的遗漏；禁止无序堆砌未经证实的宽泛大列表。
4. **保留独立选择能力**：遵循用户既有使用习惯，Steam 与 Epic 保持独立远程规则分类，不强制捆绑。
5. **单文件导入与安全装配**：用户仅导入一份由 ChatGPT Work 在本地装配的唯一私人 `.lcf` 文件；严禁在公开仓库、测试夹具或交互中泄露私人配置。
6. **事实源唯一性**：跨 AI 协作严格以 `PROJECT_STATE.md` 和实际文件为准，禁止脱离事实凭记忆猜测。

---

## 重要文件与目录

| 路径 | 用途 |
|---|---|
| `PROJECT_STATE.md` | 本项目当前状态的唯一事实源（跨 AI 协作必读必更） |
| `AGENTS.md` | AI / Agent 工作准则与交接规则 |
| `README.md` | 项目对外公开说明与规则订阅说明 |
| `sources.yml` | 规则源声明清单、上游 URL、最小规则数与排除项定义 |
| `dist/` | 构建生成的策略中立 `.lsr` 文件及诊断产物 |
| `rules/custom/` | 各服务本地补充与例外规则（需有抓包或官方依据） |
| `scripts/build.py` | 规则抓取、解析、去重、清洗与原子发布构建流水线 |
| `scripts/test_rules.py` | 规则系统单元测试套件（含 4 阶段流水线、PayPal 防钓鱼等测试） |
| `scripts/simulate_hit.py` | 本地流量命中仿真测试工具 |
| `diagnostics/loon-rules-diagnostic.js` | Loon 原生诊断脚本（支持动态分支与多源校验） |
| `diagnostics/LoonRules-Diagnostic.lpx` | Loon 诊断插件声明文件 |
| `tests/test_diagnostic.js` | 诊断插件 Node.js 离线全量测试（17 项测试） |
| `tests/fixtures/` | 公开、脱敏、策略中立的测试夹具目录 |
| `E:\Document\ChatGPT\Loon-Migration\` | 外部独立审查、交付配置与报告专属目录 |

---

## 最近一次修改

* `AGENTS.md`：
  - 新建 AI / Agent 协作规则与 `PROJECT_STATE.md` 强制更新要求。
* `PROJECT_STATE.md`：
  - 初始化项目状态唯一事实源，同步 ChatGPT Work 独立复审结论，理清阻断项与后续修复计划。

---

## 验证状态

### 已验证
- [x] **Node.js 诊断测试**：全新独立克隆复测 17 项全量通过（`17 passed, 0 failed`）。
- [x] **规则构建与格式规范**：`git diff --check` 无格式错误，19 个规则集策略中立性断言通过。
- [x] **本地私密候选结构**：`Loon-v2-19Rules.lcf` 包含全部唯一自有规则，既有节点、订阅、策略组与 MitM 结构完整保留。
- [x] **工作区健康度**：`dist/` 目录完整，无未提交的删除，无脏数据残留。

### 尚未验证
- [ ] **全新克隆 Python 单测**：待修复忽略夹具入库后，在无本地缓存的干净检出下验证 `35/35 passed`。
- [ ] **Steam/Epic 分立构建**：拆分为 20 个规则集后的构建、清单及单测复跑。
- [ ] **Loon 真机环境表现**：手机端导入后的分流体验、冷启动可达性及 APNs 推送长连接实测。

---

## 已知问题 / 风险

1. **测试夹具被忽略未入库**：`tests/fixtures/sample_order_19.lcf` 因扩展名匹配 `*.lcf` 被忽略，干净克隆报错，需更名入库。
2. **Steam/Epic 独立性缺失**：目前合并为 `Gaming.lsr`，导致用户无法在客户端为两款平台独立指派不同策略组，需重构分立。
3. **诊断插件 URL 分支硬编码**：`dist/diagnostics/LoonRules-Diagnostic.lpx` 写死 PR 分支，合并至 `main` 前需有切换机制。
4. **冷启动说明需要收敛**：备用 CDN 镜像由诊断脚本使用，并不等于 Loon 首次导入 `.lcf` 时具备自动回退能力，需客观说明。

---

## 不要重复踩的坑

1. **严禁将测试夹具命名为 `*.lcf`**：全局 `.gitignore` 会将其静默忽略，导致本地测试通过但干净克隆失败；绝不能为了夹具放开全局 `*.lcf` 忽略，以防私人配置泄露。
2. **严禁向 `.lsr` 写入策略名**：Loon 远程规则必须保持策略中立，严禁带 `,DIRECT` 或 `,PROXY`。
3. **严禁颠倒分流顺序**：细分业务必须排在对应宽泛服务之前，Lan 必须排在 GeoIP 之前。
4. **严禁向 C 盘或桌面写入非必要文件**：严格遵循用户全局准则，文件统一存放在 `E:\Document\Gemini` 或指定交付目录。
5. **严禁泄露或打印私密配置**：不得在日志、对话或公开测试夹具中打印用户的私密节点、订阅 Token 和密码。
6. **不要做无法证明的绝对化承诺**：如“100% 解决冷启动”、“0 延迟 APNs 命中”等。

---

## 下一步

1. **第一优先级（修复夹具与分立 Gaming）**：
   - 将测试夹具更名为 `sample_order_19.fixture`（或 `.txt`）并提交入库；
   - 将 `Gaming` 拆分为 `Steam` 与 `Epic` 两个独立规则集，更新 `sources.yml`、`build.py`、`test_rules.py` 与清单。
2. **第二优先级（全新克隆验证）**：
   - 在本地干净克隆或临时目录执行完整门禁复测，确保 Python 35+ 项和 Node 17 项全绿无 skip/fail。
3. **第三优先级（更新交接报告与提交）**：
   - 推送提交至 `feature/expand-rulesets-v2`，更新 `PROJECT_STATE.md` 与交接报告，通知 ChatGPT Work 独立复审。

---

## 环境 / 部署说明

* **开发操作系统**：Windows 11
* **运行环境**：PowerShell, Python 3.12+, Node.js 18+
* **主工作区路径**：`E:\Document\Gemini\loon-rules`
* **交付与复核路径**：`E:\Document\ChatGPT\Loon-Migration`
* **版本控制**：Git（GitHub 远程仓库 `o-ocn/loon-rules`，PR #2）

---

## 最后更新

- **时间**：2026-09-29 13:58
- **执行者**：Antigravity (Gemini)
- **本轮工作**：确立跨 AI 协作事实源规范，新增 `AGENTS.md`，同步 ChatGPT Work 独立复审意见，全面规范化更新 `PROJECT_STATE.md`。
