# Apple 生态基线、iCloud/CloudKit 准入与 APNs 推送实验验证指南

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
3. **精准美区分离与导入顺序法则**：
   - 仅将 Apple TV+、Apple News、Fitness+ 以及 TestFlight 精准分流至美区策略组，避免污染日常核心基线。
   - **Loon `[Remote Rule]` 顶层匹配顺序保障**：
     在 Loon 中，远程规则自上而下第一命中即生效。因此，**`Apple-Media-US.lsr` 必须置于 `Apple-Direct.lsr` 之前**。
     这样，精准的美区媒体边缘（如 `play-edge.itunes.apple.com`）会先匹配至 `US Test`，而常规 App Store / iTunes 下载（`itunes.apple.com`）则顺利落入下方的 `Apple-Direct.lsr` 走 `DIRECT`。

---

## 2. 实机 Loon【请求记录】必须核验的域名清单

分流规则不能仅靠代码中的白名单声明，**必须在 iPhone 上打开家庭与系统服务，在 Loon【请求记录】(Requests) 中逐一核对以下域名的真实命中策略**：

### A. 美区限定服务（必须验证命中：`US Test`）
* **Apple TV+ 播放与元数据**：
  - `tv.apple.com`
  - `linear.tv.apple.com`
  - `play-edge.itunes.apple.com`（流媒体核心切片）
  - `np-edge.itunes.apple.com`
  - `uts-api.itunes.apple.com`
  - `hls.itunes.apple.com` 与 `hls-amt.itunes.apple.com`
  - `tv.applemusic.com`（Apple TV 内置音乐视频频道）
* **Apple News 客户端与图床**：
  - `apple.news`
  - `news-client.apple.com`
  - `news-assets.apple.com`
  - `news-edge.apple.com`
  - `news-client-search.apple.com`
  - `gspe1-ssl.ls.apple.com`
* **TestFlight 内测平台**：
  - `testflight.apple.com`
* **Apple Fitness+**：
  - `fitness.apple.com`
  - `amp-api.fitness.apple.com`

### B. 核心系统基线（必须验证命中：`DIRECT`）
* **App Store 应用商店与下载**：
  - `apps.apple.com`
  - `itunes.apple.com`（非流媒体部分）
  - `mzstatic.com`
* **iCloud 与 CloudKit 数据管道**：
  - `apple-cloudkit.com`（爱乐记、猿音等 App 同步时触发）
  - `icloud.com`
  - `icloud.apple.com`
  - `icloud-content.com`
* **Apple Music**：
  - `music.apple.com`
  - `audio-ssl.itunes.apple.com`


为了确保 iCloud、系统相册、备忘录以及第三方重度依赖 CloudKit 的 App（如**爱乐记**、**猿音**）稳定同步，本仓库采取严格的上游准入流程：

1. **权威上游同步**：
   从 `blackmatrix7/ios_rule_script` 的 `iCloud.list` 和 `AppleMusic.list` 进行声明式拉取。
2. **多重安全清洗与过滤**：
   - 上游域名在进入 `dist/Apple-Direct.lsr` 前，自动执行黑名单过滤，严禁混入美区媒体域名（`tv.apple.com`, `apple.news`, `testflight.apple.com`）。
   - 严禁引入任何通配全量域 `apple.com` 或整段 `17.0.0.0/8`。
3. **自动化测试守门**：
   由 `scripts/test_rules.py` 执行断言，任何非法父域通配或跨策略冲突将立即阻断发版。

---

## 3. APNs 机制客观说明与 Loon 捕获实测要求

### A. APNs 的系统级本质
* 在 iOS 与 watchOS 中，APNs 由全局系统守护进程 `apsd` 统一托管。
* 整个系统（**Telegram、微信、邮件、HomeKit 门铃告警、摄像头移动侦测、iCloud 变更推送、Apple Watch 数据唤醒、爱乐记、猿音**）共用同一条长连接 TLS 通道（默认目标为 `courier.push.apple.com`，端口 5223 / 443 / 2197）。
* **绝不能声称 APNs “只影响 Telegram”**。任何针对 APNs 路由的调整，都会同步影响整台设备的全部通知与后台数据同步！

### B. Loon “包含 APNS” 开关与捕获行为的客观说明
* **当前系统开关状态**：“包含所有网络”为 **关闭 (OFF)**；“包含 APNS”为 **关闭 (OFF)**。
* **客观实测要求**：
  在 iOS NetworkExtension 架构下，当“包含 APNS”关闭时，系统通常豁免 `apsd`，其长连接不进入 TUN 虚拟接口。**但这绝不能当作不需要验证的先验绝对真理**。由于 iOS 大版本迭代及蜂窝网卡与 Wi-Fi 路由策略差异，**APNs 流量是否进入 Loon、命中哪条策略，必须以用户在 Loon【请求记录】中的实际抓包数据为准**。
* **默认安全状态**：
  本仓库提供的 `Apple-Push-Experimental.lsr` 在所有导入示例中**默认设为关闭 (`enabled=false`)**。
  只有在用户主动实测、且确认抓包记录中看到了推送连接时，才根据需要启用。若 APNs 流量未进入 Loon，`.lsr` 无法单独解决该问题。

### C. 本地 [Rule] 规则与远程订阅规则的优先级制约（核心原理解析）
* **本地规则的绝对优先级**：
  原配置在本地 `[Rule]` 中显式包含了 6 条指向 `Apple Push` 的 APNs 规则：
  - `DOMAIN-SUFFIX,push.apple.com,Apple Push`
  - `IP-CIDR,17.249.0.0/16,Apple Push,no-resolve`
  - `IP-CIDR,17.252.0.0/16,Apple Push,no-resolve`
  - `IP-CIDR,17.57.144.0/22,Apple Push,no-resolve`
  - `IP-CIDR,17.188.128.0/18,Apple Push,no-resolve`
  - `IP-CIDR,17.188.20.0/23,Apple Push,no-resolve`
* **生效机制说明**：
  在 Loon 的流水线中，本地 `[Rule]` 的优先级高于所有远程订阅 `[Remote Rule]`。当 APNs 流量进入 Loon 时，会优先命中这 6 条本地规则并走 `Apple Push` 策略。
* **重要结论**：
  **单独启用远程实验规则并将远程规则绑定为 `DIRECT`，并不能将 APNs 流量改为直连**，因为本地 `[Rule]` 会在前端先行拦截。因此，现有这 6 条本地 APNs 规则必须保持原样；本轮测试切勿擅自修改本地规则或手机系统开关，APNs、HomeKit、Watch 及 Telegram 推送表现严格留待最后真机实测验证。

---

## 4. APNs 单变量控制测试矩阵

为探索 Telegram 的低延迟后台推送，同时绝对不破坏 Apple 核心服务，请严格遵循**一次只改变一个变量**的测试流程（所有 APNs 变更须在确认本地规则与手机开关后实施）：

| 测试阶段 | Loon 开关组合 | 本地与远程规则状态 | 需实测的网络环境 | 必须核验的观察项 |
| :--- | :--- | :--- | :--- | :--- |
| **阶段 1：基线确认 (当前配置)** | 包含所有网络: 关<br>包含 APNS: **关** | 本地 6 条 APNs 规则保持现状<br>`Apple-Push-Experimental` **禁用** | 大陆 Wi-Fi & 蜂窝数据 | 1. 划掉 Telegram 后台，测试系统推送延迟。<br>2. 观察 Loon 请求记录中是否出现 `push.apple.com` 或 `17.x.x.x`（核验其是否绕过 Loon）。 |
| **阶段 2：捕获测试 (原策略)** | 包含所有网络: 关<br>包含 APNS: **开** | 本地 6 条 APNs 规则走 `Apple Push`<br>远程实验规则保持禁用 | 大陆 Wi-Fi | 1. 查看 Loon 请求记录：是否开始记录 `apsd` / `push.apple.com` 并命中 `Apple Push`。<br>2. 检查 Apple Watch 天气是否正常。<br>3. 检查 HomeKit 室内摄像头画面是否秒开。<br>4. 检查爱乐记、猿音的 CloudKit 同步是否畅通。 |
| **阶段 3：分网综合验证** | 包含所有网络: 关<br>包含 APNS: **开** | 本地 APNs 策略保持 `Apple Push` | **网络 A：大陆 Wi-Fi**<br>**网络 B：大陆蜂窝数据** | 1. 锁屏 5~10 分钟后测试 Telegram 消息唤醒速度。<br>2. 对比蜂窝与 Wi-Fi 切换时推送是否断连。<br>3. 检查全系统其他 App（微信、邮件、门铃）通知是否受牵连。 |

> [!CAUTION]
> **异常回滚红线**：
> 一旦发现 Apple Watch 天气无法获取、爱乐记或猿音同步停滞、或 HomeKit 摄像头提示“未响应”，**立即将 Loon【包含 APNS】关闭**，即可瞬间恢复原生网络表现。
