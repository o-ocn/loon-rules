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
3. **精准美区分离**：仅将 Apple TV+、Apple News、Fitness+ 以及 TestFlight 精准分流至美区策略组，避免污染日常核心基线。

---

## 2. iCloud / CloudKit 上游准入与验证机制

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

---

## 4. APNs 单变量控制测试矩阵

为探索 Telegram 的低延迟后台推送，同时绝对不破坏 Apple 核心服务，请严格遵循**一次只改变一个变量**的测试流程：

| 测试阶段 | Loon 开关组合 | 规则与策略设置 | 需实测的网络环境 | 必须核验的观察项 |
| :--- | :--- | :--- | :--- | :--- |
| **阶段 1：基线确认** | 包含所有网络: 关<br>包含 APNS: **关** | `Apple-Push-Experimental` **禁用** | 大陆 Wi-Fi & 蜂窝数据 | 1. 划掉 Telegram 后台，测试系统推送延迟。<br>2. 观察 Loon 请求记录中是否出现 `push.apple.com` 或 `17.x.x.x`（验证其是否绕过 Loon）。 |
| **阶段 2：捕获测试 (直连)** | 包含所有网络: 关<br>包含 APNS: **开** | 启用 `Apple-Push-Experimental`<br>策略手动固定为 **`DIRECT`** | 大陆 Wi-Fi | 1. 查看 Loon 请求记录：是否开始记录 `apsd` / `push.apple.com` 并命中 `DIRECT`。<br>2. 检查 Apple Watch 天气是否正常。<br>3. 检查 HomeKit 室内摄像头画面是否秒开。<br>4. 检查爱乐记、猿音的 CloudKit 同步是否畅通。 |
| **阶段 3：代理测试 (分网验证)** | 包含所有网络: 关<br>包含 APNS: **开** | 策略切换至 **`Apple Push`** (代理节点) | **网络 A：大陆 Wi-Fi**<br>**网络 B：大陆蜂窝数据** | 1. 锁屏 5 分钟后测试 Telegram 消息唤醒速度。<br>2. 对比蜂窝与 Wi-Fi 切换时推送是否断连。<br>3. 检查全系统其他 App（微信、邮件、门铃）通知是否受牵连。 |

> [!CAUTION]
> **异常回滚红线**：
> 一旦发现 Apple Watch 天气无法获取、爱乐记或猿音同步停滞、或 HomeKit 摄像头提示“未响应”，**立即将 `Apple-Push-Experimental.lsr` 停用或将 Loon【包含 APNS】关闭**，即可瞬间恢复原生网络表现。
