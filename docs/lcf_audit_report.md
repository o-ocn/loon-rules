# Loon 原始配置文件 (`.lcf`) 脱敏审计与第三方 Apple 规则清理对照报告

> **审计对象**：`2026_09_28_00_10_30_550_自动配置.lcf`  
> **审计时间**：2026-09-28  
> **合规级别**：严格脱敏（零凭据、零真实节点、零私有密钥、零个人主机名泄漏）  
> **对接目标**：为 ChatGPT Work 对话提供权威对照报告，指导 `.lcf` 中第三方杂合 Apple 规则与 Legacy 禁用条目的安全清理，并核对生效顺序。

---

## 1. 敏感信息识别与隔离状态

审计确认原始 `.lcf` 文件包含以下高危敏感数据，**已全部在本地安全隔离，严禁写入任何 Git 追踪文件或公开仓库**：
1. **节点订阅鉴权信息**：包含带 Token / 密钥的远端节点订阅 URL（位于 `[Remote Proxy]` 与 `[Remote Filter]`）。
2. **真实代理节点参数**：包含自建服务器真实的 IPv4/IPv6 地址、端口号、UUID、传输协议口令及混淆 Host。
3. **MITM 根证书私钥与密码**：包含 `[Mitm]` 节中的 CA 证书密文、私钥密文以及解密 Passphrase。
4. **插件私有参数**：部分去广告与脚本插件携带的本地设备标记。

> [!IMPORTANT]
> 本公开规则仓库仅维护纯分流规则（`.lsr`），绝不触碰任何代理节点定义、认证凭据与证书设置。所有真实节点、本地策略组、证书和设备全局设置永久保留在用户的本地 Loon 中。

---

## 2. 基础路由与 TUN 模式审计

| 配置项 | 审计值 | 状态与影响分析 |
| :--- | :--- | :--- |
| `ip-mode` | `v4-only` | 纯 IPv4 模式，规避了 IPv6 DNS 污染与漏网问题。 |
| `disable-stun` | `true` | 已禁用 STUN 穿透，防止 WebRTC/STUN 泄露真实出口 IP。 |
| `dns-server` | `system` | 采用系统 DNS，配合分流规则由 Loon 处理远端 DNS 解析。 |
| `interface-mode` | `auto` | 自动网卡路由模式。 |
| `bypass-tun` | 内网私有网段 | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `100.64.0.0/10` 等全部直连旁路。 |
| **“不作为默认路由”** | **开启 (ON)** | 路由表不接管全流量，仅代理命中路由与规则的流量，保障局域网与基础网络稳定。 |
| **“包含所有网络”** | **关闭 (OFF)** | **必须保持关闭**。开启后会强行接管 Watch 流量与系统底层通道，此前已证实会破坏 Watch 天气与 CloudKit 主动同步。 |
| **“包含 APNS”** | **关闭 (OFF)** | **当前处于关闭状态**。在此状态下，iOS 系统推送守护进程 `apsd` 可能直接绕过 Loon TUN 虚拟网卡走物理网卡直连，**需以真机命中记录确认**。 |

---

## 3. 自有 Apple 规则集与第三方规则覆盖范围深度对照（ChatGPT Work 清理指南）

为了帮助 ChatGPT Work 准确判断哪些仍启用的第三方 Apple 规则可以安全移除，现将本仓库维护的权威自有规则与第三方聚合规则进行全域比对：

### A. 规则集对照矩阵

| 业务场景 | 本仓库权威自有规则 (`dist/`) | 对应第三方常见规则（可清理） | 本仓库优势与安全防护 |
| :--- | :--- | :--- | :--- |
| **内测分发** | **`TestFlight.lsr`** (3 条) | 杂合在 `AppleProxy.lsr` 或 `Apple.lsr` | **独立隔离**。因用户实测 TestFlight 直连可能无法打开，故单独提取为独立 `.lsr`，排在 Apple-Direct 之前，解决锁区及卡加载。 |
| **Apple 媒体锁区** | **`Apple-Media.lsr`** (18 条) | `AppleMedia.lsr` / `AppleProxy.lsr` / `AppleTV.lsr` / `AppleNews.lsr` | **精准收录**。仅收录 Apple TV+、Apple News、Fitness+ 流媒体核心切片与 API，排在 Apple-Direct 之前，不绑架系统其他流量。 |
| **推送通道** | **`Apple-Push.lsr`** (10 条) | 散落的内联 `[Rule]` 或第三方 Push 规则 | **官方最小范围**。仅含 `push.apple.com` 及官方 5 个 IPv4 CIDR + 4 个 IPv6 CIDR，说明 TCP 5223 / 443 回退机制。保留 `Apple Push` 策略组。 |
| **Apple 基础核心** | **`Apple-Direct.lsr`** (80 条) | `Apple.lsr` (Kelee) / `Apple_Direct.list` | **绝不通配代理**。严格锁定 iCloud、CloudKit、Apple ID、App Store、Apple Music 直连，严禁混入 `17.0.0.0/8` 或 `DOMAIN-SUFFIX,apple.com`。 |

### B. ChatGPT Work 针对 `.lcf` 的具体清理建议

1. **安全移除第三方 Apple 订阅**：
   - 可在 `.lcf` 的 `[Remote Rule]` 中安全删除：
     * `https://rule.kelee.one/Loon/Apple.lsr` (或 `AppleProxy.lsr`)
     * `https://rule.kelee.one/Loon/AppleMedia.lsr`
     * 任何第三方的 `AppleTV.lsr` 与 `AppleNews.lsr`
   - **替换为本仓库唯一权威源 (严格自顶向下顺序)**：
     ```ini
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/TestFlight.lsr, policy = US, tag = TestFlight, enabled = true
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media.lsr, policy = US Test, tag = Apple-Media, enabled = true
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push.lsr, policy = Apple Push, tag = Apple-Push, enabled = false
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr, policy = DIRECT, tag = Apple-Direct, enabled = true
     ```
2. **`Apple Push` 策略组保留与内联规则安全清理**：
   - **保留策略组**：保留用户 `.lcf` 中原有的 `Apple Push` 策略组，不新增同类组，也不擅自删除。
   - **清理前确认**：在移除本地 `[Rule]` 中遗留的 APNs 条目（如 `17.0.0.0/8` 或 `push.apple.com`）之前，必须先确认：
     1) 远程 `Apple-Push.lsr` 已配置并排在 `Apple-Direct.lsr` 之前；
     2) `Apple Push` 策略组有效（直连或指定节点可用）；
     3) 锁屏即时通知（微信、Telegram、HomeKit 门铃推送）测试无异常。
3. **清理冗余 Legacy 禁用条目**：
   - 原始 `.lcf` 中存在多条带 `#` 注释或 `enabled=false` 的过时历史订阅（如老旧的第三方合并规则、重复节点规则）。
   - **清理原则**：无需保留 `*-Legacy` 条目。Git 提交历史与 Release Tag 已提供完整的版本回滚支撑，清理后的 `.lcf` 应保持最精简状态。
4. **插件集成**：
   - 在 `.lcf` 中直接引用本仓库一键诊断插件（支持 GitHub Raw 与 Fastly jsDelivr 双镜像）：
     ```ini
     [Plugin]
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/LoonRules-Diagnostic.lpx, tag = LoonRules-Diagnostic
     ```
   - **语法与执行规范**：插件脚本定义已完全遵循 Loon 官方 3.5.1+ Generic Script v2 规范 (`generic then script(...) with ...`)，静态规范合规，待 PR 合并后在真机客户端首次导入点击确认。
   - **日志工具说明**：Loon 官方 Script API 未提供直接读取历史请求记录的接口，本仓库不存在也不提供 Loon 内置请求日志导出插件。日常排查请使用该一键诊断插件复制简短中文报告；`scripts/sanitize_log.py` 严格作为离线本地命令行脱敏工具使用。

---

## 4. Loon 核心规则优先级法则与生效顺序

```text
┌─────────────────────────────────────────────────────────────┐
│ 1. 本地规则 [Rule] (最高优先级)                              │
├─────────────────────────────────────────────────────────────┤
│ 2. 插件规则 [Plugin] 内部声明的 [Rule] (次高优先级)          │
│    * 本仓库诊断插件未声明任何分流规则，零侵入，零副作用       │
├─────────────────────────────────────────────────────────────┤
│ 3. 远程订阅规则 [Remote Rule] (GitHub .lsr, 按顺序逐一匹配)  │
│    * 精确子规则排在宽泛父域规则之前                          │
├─────────────────────────────────────────────────────────────┤
│ 4. 兜底策略 FINAL (最低优先级)                               │
│    * 命中 FINAL 本身是正常网络行为，绝不代表分流失效         │
└─────────────────────────────────────────────────────────────┘
```

> [!WARNING]
> **重要架构事实**：
> 远程订阅 `.lsr` 处于第 3 层，其优先级**天然低于插件内置规则与本地规则**。
> - 若去广告插件内部强制将某个域名置为 `REJECT`，即使我们在 `AI-Overseas.lsr` 中将该域名写入分流，Loon 也会由于插件优先级更高而优先执行 `REJECT`。
> - 任何需要绝对无条件优先的分流例外，必须保留在本地 `.lcf` 的 `[Rule]` 顶层。

---

## 5. 中国大陆冷启动与备用镜像说明 (待真机验证)

首次导入 `.lcf` 时，若代理节点尚未就绪或 GitHub Raw 暂时被阻断，Loon 依靠本地 `[Rule]` 中的内网段旁路与必要直连规则维持基础网络。
同时，所有规则文件均提供 Fastly jsDelivr 备用 CDN 镜像：
`https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/<规则名>.lsr`

**重要技术限制说明**：
- 根据 Loon 官方文档，规则订阅的 LRU 机制主要是针对近期匹配结果的查询缓存，不能推断为首次完全离线导入时远程规则依然可用。
- 首次离线冷启动能否正常加载规则并平稳启动，属于待真机首次导入验证事项；实际环境建议优先保障备用镜像的可达性。
