# Apple 生态基线与 APNs 推送实验验证指南

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

## 2. APNs 底层原理与 Loon 捕获机制深度剖析

### A. APNs 的系统级本质
* 在 iOS 与 watchOS 中，APNs 由单一系统守护进程 `apsd` 统一托管。
* 整个系统（**Telegram、微信、邮件、HomeKit 门铃告警、摄像头移动侦测、iCloud 变更推送、Apple Watch 数据唤醒、爱乐记、猿音**）共用同一条长连接 TLS 通道（默认目标为 `courier.push.apple.com`，端口 5223 / 443 / 2197）。
* **绝不能声称 APNs “只影响 Telegram”**。任何针对 APNs 路由的调整，都会瞬间影响整台设备的全部通知与后台数据同步！

### B. Loon “包含 APNS” 开关的关键影响
* **当前状态：关闭 (OFF)**。
* **物理事实**：在 iOS NetworkExtension 架构下，当 Loon 的“包含 APNS”关闭时，iOS 内核直接豁免 `apsd`，其所有连接**绕过 TUN 虚拟网卡，直接通过物理 Wi-Fi 或蜂窝网络发出**。
* **结论**：**若“包含 APNS”处于关闭状态，APNs 流量根本未进入 Loon！此时无论在 `.lsr` 中写何种规则，都绝不可能命中，也绝不可能改变 Telegram 的推送延迟。若 APNs 流量未进 Loon，`.lsr` 无法单独解决该问题。**

---

## 3. APNs 独立实验方案（单变量控制测试）

为了在不破坏 Apple 核心服务的前提下探索 Telegram 的低延迟后台推送，我们设计了独立的 `Apple-Push-Experimental.lsr`，并严格遵守**一次只改变一个变量**的科学测试流程。

### 测试步骤与矩阵

#### 第一阶段：基线确认（“包含 APNS” 保持关闭）
1. 打开 Loon 的“请求日志”（Requests / Recent）。
2. 将 Telegram 彻底退出后台（划掉后台卡片）。
3. 使用另一台设备或桌面端向该 Telegram 发送一条测试消息。
4. **观察点**：
   - Loon 日志中是否出现目标为 `push.apple.com` 或 `17.x.x.x` 的请求？（预期：**不出现**，因为未捕获 APNs）。
   - 手机是否收到系统推送通知？耗时多久？

#### 第二阶段：开启“包含 APNS” 仅绑定 DIRECT（验证捕获能力）
1. 在 Loon 设置中打开【包含 APNS】（保持“包含所有网络”为关闭！）。
2. 在 `[Remote Rule]` 中启用 `Apple-Push-Experimental.lsr`，并将 `Apple Push` 策略组手动固定选为 `DIRECT`。
3. 检查 Loon 请求日志：此时日志中应开始出现 `apsd` 或 `push.apple.com` 的连接记录，并清晰显示命中策略为 `DIRECT`。
4. **验收健康度**：
   - Apple Watch 天气是否正常刷新？
   - HomeKit 摄像头（特别是室内摄像头、门铃实时画面）是否正常秒开？
   - 打开【爱乐记】与【猿音】，检查 iCloud/CloudKit 记录是否秒级同步？

#### 第三阶段：测试代理推送（对比 Wi-Fi 与 蜂窝数据）
1. 将 `Apple Push` 策略组手动切换至自建香港或低延迟专线（如自建 VMISS 9929 或 HK）。
2. **网络 A：大陆家庭 Wi-Fi 环境下**：
   - 锁定屏幕 5 分钟，测试 Telegram 消息推送实时性。
   - 检查是否有通知丢失或延迟激增。
   - 检查 HomeKit 门铃是否有延迟。
3. **网络 B：大陆蜂窝移动数据环境下**：
   - 断开 Wi-Fi，在 5G/4G 蜂窝数据下重复上述测试。
   - 检查基站切换与熄屏唤醒时，APNs 握手是否受阻。

> [!CAUTION]
> **回滚触发红线**：
> 一旦发现 Apple Watch 天气出现破裂/无法获取数据、爱乐记或猿音同步停滞、或 HomeKit 摄像头提示“未响应”，**立即将 `Apple Push` 切回 `DIRECT`，或关闭 Loon 中的【包含 APNS】**，即可秒级恢复原生状态。
