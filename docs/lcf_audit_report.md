# Loon 原始配置文件 (`.lcf`) 脱敏审计与第三方 Apple 规则清理对照报告

> **审计对象**：`2026_09_28_00_10_30_550_自动配置.lcf`  
> **审计时间**：2026-09-28  
> **合规级别**：严格脱敏（零凭据、零真实节点、零私有密钥、零个人主机名泄漏）  
> **对接目标**：为 ChatGPT Work 提供权威对照报告，指导 `.lcf` 中第三方杂合 Apple 规则与 Legacy 禁用条目的安全清理。

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
| **“包含 APNS”** | **关闭 (OFF)** | **当前处于关闭状态**。在此状态下，iOS 系统推送守护进程 `apsd` 直接走物理网卡直连，**根本不进入 Loon TUN 虚拟网卡**。 |

---

## 3. 自有 Apple 规则集与第三方规则覆盖范围深度对照（ChatGPT Work 清理指南）

为了帮助 ChatGPT Work 准确判断哪些仍启用的第三方 Apple 规则可以安全移除，现将本仓库维护的权威自有规则与第三方聚合规则进行全域比对：

### A. 规则集对照矩阵

| 业务场景 | 本仓库权威自有规则 (`dist/`) | 对应第三方常见规则（可清理） | 本仓库优势与安全防护 |
| :--- | :--- | :--- | :--- |
| **Apple 基础核心** | **`Apple-Direct.lsr`** (80 条) | `Apple.lsr` (Kelee) / `Apple_Direct.list` | **绝不通配代理**。严格锁定 iCloud、CloudKit、Apple ID、App Store、Apple Music 直连，严禁混入 `17.0.0.0/8` 或 `DOMAIN-SUFFIX,apple.com`。 |
| **Apple 媒体锁区** | **`Apple-Media.lsr`** (18 条) | `AppleMedia.lsr` / `AppleProxy.lsr` / `AppleTV.lsr` / `AppleNews.lsr` | **精准收录**。仅收录 Apple TV+、Apple News、Fitness+ 流媒体核心切片与 API，不绑架系统其他流量。 |
| **内测分发** | **`TestFlight.lsr`** (3 条) | 杂合在 `AppleProxy.lsr` 或 `Apple.lsr` | **独立隔离**。因用户实测 TestFlight 直连可能无法打开，故单独提取为独立 `.lsr`，不与 Direct 冲突。 |
| **推送通道** | **`Apple-Push.lsr`** (10 条) | 散落的内联 `[Rule]` 或第三方 Push 规则 | **官方最小范围**。仅含 `push.apple.com` 及官方 5 个 IPv4 CIDR + 4 个 IPv6 CIDR，注释说明 TCP 5223 / 443 回退。 |

### B. ChatGPT Work 针对 `.lcf` 的具体清理建议

1. **安全移除第三方 Apple 订阅**：
   - 可在 `.lcf` 的 `[Remote Rule]` 中安全删除：
     * `https://rule.kelee.one/Loon/Apple.lsr` (或 `AppleProxy.lsr`)
     * `https://rule.kelee.one/Loon/AppleMedia.lsr`
     * 任何第三方的 `AppleTV.lsr` 与 `AppleNews.lsr`
   - **替换为本仓库唯一权威源**：
     * `Apple-Media.lsr`
     * `TestFlight.lsr`
     * `Apple-Direct.lsr`
     * `Apple-Push.lsr` (默认建议 enabled=false，需测试时手动开启)
2. **清理冗余 Legacy 禁用条目**：
   - 原始 `.lcf` 中存在多条带 `#` 注释或 `enabled=false` 的过时历史订阅（如老旧的第三方合并规则、重复节点规则）。
   - **清理原则**：无需保留 `*-Legacy` 条目。Git 提交历史与 Release Tag 已提供完整的版本回滚支撑，清理后的 `.lcf` 应保持最精简状态。
3. **插件集成**：
   - 在 `.lcf` 中直接引用本仓库一键诊断插件：
     ```ini
     [Plugin]
     https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/LoonRules-Diagnostic.lpx, tag = LoonRules-Diagnostic
     ```

---

## 4. 插件审计与分流规则执行优先级定律

原始配置加载了 37 个插件（包括 `iRingo.WeatherKit`, `iRingo.Siri`, `Block_HTTPDNS`, `BlockAdvertisers`, `Prevent_DNS_Leaks` 及主流 App 去广告插件）。

### Loon 核心规则优先级法则

```text
┌─────────────────────────────────────────────────────────┐
│ 1. 本地规则 [Rule] (最高优先级)                         │
├─────────────────────────────────────────────────────────┤
│ 2. 插件规则 [Plugin] 内部声明的 [Rule] (次高优先级)    │
├─────────────────────────────────────────────────────────┤
│ 3. 远程订阅规则 [Remote Rule] (GitHub .lsr, 较低优先级) │
├─────────────────────────────────────────────────────────┤
│ 4. 兜底策略 FINAL (最低优先级)                          │
└─────────────────────────────────────────────────────────┘
```

> [!WARNING]
> **重要架构事实**：
> 远程订阅 `.lsr` 处于第 3 层，其优先级**天然低于插件内置规则与本地规则**。
> - 若 `BlockAdvertisers` 插件内部强制将某个域名置为 `REJECT`，即使我们在 `AI-Overseas.lsr` 中将该域名写入分流，Loon 也会由于插件优先级更高而优先执行 `REJECT`。
> - 任何需要绝对无条件优先的分流例外，必须保留在本地 `.lcf` 的 `[Rule]` 顶层。
