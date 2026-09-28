# Apple 生态基线、iCloud/CloudKit 准入与 APNs 权威推送验证指南

## 1. Apple 服务基线原则（稳定性第一）

用户的核心要求是：**HomeKit、室内摄像头、门铃、Apple Watch、iCloud、第三方 CloudKit 同步绝不能因分流规则重构而劣化**。

### 核心设计基准
1. **零通配、零粗暴代理**：绝对禁止以 `DOMAIN-SUFFIX,apple.com`、`17.0.0.0/8` 或 Apple CDN 整段代理作为捷径。
2. **锁死直连项**：
   - iCloud 云盘与数据同步 (`DOMAIN-SUFFIX,icloud.com`)
   - CloudKit 数据库管道 (`DOMAIN-SUFFIX,apple-cloudkit.com`)
   - App Store 与 Apple ID 认证 (`apps.apple.com`, `appleid.apple.com`)
   - Apple Music 串流 (`music.apple.com`)
   - HomeKit 局域网协同与本地串流 (`192.168.0.0/16` 直连)
3. **精准媒体分离与导入顺序法则**：
   - 仅将 Apple TV+、Apple News、Fitness+ 以及 TestFlight 精准分流，避免污染日常核心基线。
   - **Loon `[Remote Rule]` 顶层匹配顺序保障**：
     在 Loon 中，远程规则自上而下第一命中即生效。因此，**`Apple-Media.lsr` 与 `TestFlight.lsr` 必须置于 `Apple-Direct.lsr` 之前**。
     这样，精准的美区媒体边缘（如 `play-edge.itunes.apple.com`）与 TestFlight 先行匹配，而常规 App Store / iTunes 下载（`itunes.apple.com`）则顺利落入下方的 `Apple-Direct.lsr`。

---

## 2. APNs 官方最小规则定义 (`Apple-Push.lsr`)

为了避免多个推送来源产生漂移，本仓库维护唯一的权威推送规则文件：`Apple-Push.lsr`。

### A. 端口与协议机制
* **主要端口**：**TCP 5223**（iOS/watchOS/macOS 上 Wi-Fi 和蜂窝移动网络下与 APNs 保持的长连接默认端口）。
* **回退端口**：**TCP 443**（仅当企业或局域网防火墙阻断 5223 端口时，系统 `apsd` 会尝试回退到 443 端口）。
* **开发者推送端口**：**TCP 2197**（向 APNs 服务器发送推送消息时使用）。
* **安全红线**：APNs 流量绝对严禁开启 MitM 解密，否则会导致整机证书校验失败并彻底断开通知通道。

### B. 官方最小收录范围
严格依据 Apple 官方企业网络部署规范（[Apple 官方技术支持](https://support.apple.com/zh-cn/102266)）：
* **域名**：`DOMAIN-SUFFIX,push.apple.com`
* **官方验证 IPv4 网段**：
  - `17.249.0.0/16`
  - `17.252.0.0/16`
  - `17.57.144.0/22`
  - `17.188.128.0/18`
  - `17.188.20.0/23`
* **官方验证 IPv6 网段**：
  - `2620:149:a44::/48`
  - `2403:300:a42::/48`
  - `2403:300:a51::/48`
  - `2a01:b740:a42::/48`
* **明确排除**：不收录整个 `17.0.0.0/8`、不收录整个 `apple.com` 或 `icloud.com`，杜绝扩大化。

---

## 3. APNs 机制客观说明与 Loon “包含 APNS” 开关限制

> [!WARNING]
> **规则仓库核心能力边界与限制说明**：
> 规则仓库只能决定“进入 Loon 的数据流如何匹配规则”，**无法改变 iOS 系统内核将哪些流量交由 TUN 虚拟网卡**。

1. **“包含 APNS” 关闭 (OFF) 时**：
   - iOS 系统守护进程 `apsd` 直接走物理蜂窝或 Wi-Fi 网卡直连，**其数据包根本不进入 Loon TUN 虚拟网卡**。
   - 此时，无论在 Loon 中配置何种远程推送规则，系统连接都绝不会命中远程分流规则。
2. **“包含 APNS” 开启 (ON) 时**：
   - Loon 才会通过 NetworkExtension 接管 `apsd` 的 TCP 5223/443 连接。
   - 此时，`Apple-Push.lsr` 方可实际拦截并按用户指定的策略进行路由。
3. **默认安全建议**：
   - 本仓库在所有文档与示例中建议 `Apple-Push.lsr` **默认保持关闭 (`enabled=false`)**。
   - 仅当用户明确开启 Loon【包含 APNS】进行单变量对照实验时，方可按需启用。

---

## 4. APNs 单变量控制测试矩阵

为探索 Telegram 的低延迟后台推送，同时绝对不破坏 Apple 核心服务，请严格遵循**一次只改变一个变量**的测试流程：

| 测试阶段 | Loon 开关组合 | 本地与远程规则状态 | 需实测的网络环境 | 必须核验的观察项 |
| :--- | :--- | :--- | :--- | :--- |
| **阶段 1：基线确认 (当前配置)** | 包含所有网络: 关<br>包含 APNS: **关** | 远程 `Apple-Push.lsr` **禁用** | 大陆 Wi-Fi & 蜂窝数据 | 1. 划掉 Telegram 后台，测试系统推送延迟。<br>2. 观察 Loon 请求记录中是否出现 `push.apple.com`（核验其是否绕过 Loon）。 |
| **阶段 2：捕获测试 (开启开关)** | 包含所有网络: 关<br>包含 APNS: **开** | 远程 `Apple-Push.lsr` 启用并绑定指定策略 | 大陆 Wi-Fi | 1. 查看 Loon 请求记录：是否开始记录 `apsd` / `push.apple.com` 并命中规则。<br>2. 检查 Apple Watch 天气是否正常。<br>3. 检查 HomeKit 室内摄像头画面是否秒开。<br>4. 检查爱乐记、猿音的 CloudKit 同步是否畅通。 |
| **阶段 3：分网综合验证** | 包含所有网络: 关<br>包含 APNS: **开** | `Apple-Push.lsr` 保持开启 | **网络 A：大陆 Wi-Fi**<br>**网络 B：大陆蜂窝数据** | 1. 锁屏 5~10 分钟后测试 Telegram 消息唤醒速度。<br>2. 对比蜂窝与 Wi-Fi 切换时推送是否断连。<br>3. 检查全系统其他 App（微信、邮件、门铃）通知是否受牵连。 |

> [!CAUTION]
> **异常回滚红线**：
> 一旦发现 Apple Watch 天气无法获取、爱乐记或猿音同步停滞、或 HomeKit 摄像头提示“未响应”，**立即将 Loon【包含 APNS】关闭**，即可瞬间恢复原生网络表现。
