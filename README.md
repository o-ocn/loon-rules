# Loon Rules 分流规则集（策略中立・自动化维护・原生一键诊断）

本项目是一个公开、独立维护的 **Loon 分流规则仓库**（`.lsr` 格式）。
仓库秉持**“上游覆盖为主、Custom 补丁为辅、少量必要过滤、策略严格中立”**的原则，解决第三方聚合规则中常见的“规则粗暴混杂、AI 与普通服务交叉碰撞、Apple 生态易受干扰”等问题。

---

## 核心设计准则

1. **策略绝对中立（Policy-Neutral）**：
   - 仓库只负责判断“流量属于什么服务”，绝不决定“走什么节点、地区或策略”。
   - 所有生成的 `.lsr` 绝不写入用户策略组名称、地区（HK/US/JP）、机场/VMISS 节点名称，也不写入 DIRECT/PROXY/REJECT 等策略动作。
   - 用户在 Loon 中长按每个远程规则，自由绑定专属策略组、内置策略或指定节点。
2. **AI 精准分流与上游优先**：
   - **`AI-Overseas.lsr`**：正式自动同步 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的 Gemini、OpenAI、Claude 开源规则集；Custom 仅补充验证过的全新端点（重点包含 Google Gemini iOS 客户端的 `webchannel-robinfrontend-pa.googleapis.com` 实时流式端点）。
   - **严格防碰撞**：严禁向 AI 写入通配域 `google.com`、`googleapis.com`、`googleusercontent.com`、`twitter.com`、`x.com`、`meta.com`、`facebook.com`、`instagram.com`、`whatsapp.com`。
   - **`AI-China-Direct.lsr`**：独立收录 DeepSeek 等中国大陆 AI 服务，规则内不硬编码 DIRECT，策略由用户在 Loon 自主指定。
   - **Grok 与 Twitter 分离**；**Muse from Meta 精准收录，不扩展为 Meta 全家桶**。
3. **Google Drive 大流量保护与共享 API 隔离**：
   - 用户使用 Primuse 从 Google Drive 播放音乐，已观察到 `www.googleapis.com` 承载数十至上百兆音频流。
   - `www.googleapis.com` 属于共享 Google API，**绝不进入 AI-Overseas，也绝不粗暴塞入 Google Drive**，归入普通 Google 规则；明确的 Google Drive 域名归入 `GoogleDrive.lsr`。
   - `ws.audioscrobbler.com` (Last.fm) 绝不误归为 Google Drive。
4. **Apple 生态稳定性第一与权威 APNs 最小收录**：
   - 严禁将 `apple.com`、`icloud.com`、Apple CDN 或 `17.0.0.0/8` 整段代理。
   - 基础直连服务（`Apple-Direct.lsr`）与媒体流媒体（`Apple-Media.lsr`）分开维护；`TestFlight.lsr` 独立维护。
   - **`Apple-Push.lsr`**：维护唯一的权威最小 APNs 规则，仅含 `*.push.apple.com` 及 Apple 官方验证的 IPv4/IPv6 CIDR，注释说明主要使用 TCP 5223 并可回退至 443。
   - **明确边界**：规则仓库不能保证在 Loon【包含 APNS】关闭时系统连接一定会命中，此为 iOS 内核机制限制。
5. **只读上游与构建安全保障**：
   - 主要同步来源为 `blackmatrix7/ios_rule_script`（遵循 GPL-2.0）；`luestr/ShuntRules` 仅作结构与遗漏对照，不直接复制无明确许可证内容。
   - 建立「最低规则数 + 相对上一版本缩水阈值 + 逐上游锁定基线（`upstream_lock.json`）」三重防护机制。构建失败或异常缩水时保留上一版成品，绝不破坏现有生产。

---

## 规则订阅清单 (共 14 个独立服务分类)

| 规则成品 (`dist/`) | 涵盖核心服务说明 | 订阅链接 (GitHub Raw) |
| :--- | :--- | :--- |
| **`AI-Overseas.lsr`** | ChatGPT, Claude, Gemini (含 iOS WebChannel), Grok, Muse from Meta | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr) |
| **`AI-China-Direct.lsr`** | DeepSeek 等中国大陆 AI 服务 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr) |
| **`GoogleDrive.lsr`** | Google Drive 云端硬盘专属服务（独立保护大流量） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr) |
| **`OneDrive.lsr`** | Microsoft OneDrive 与 SharePoint 服务 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr) |
| **`Google.lsr`** | 普通 Google 服务、搜索与基础设施（含共享 `www.googleapis.com`） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr) |
| **`YouTube.lsr`** | YouTube 视频流媒体、图片与 CDN | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr) |
| **`Telegram.lsr`** | Telegram 官方 IP 段与核心域名通信 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr) |
| **`Twitter.lsr`** | Twitter / X 平台主干（不含 Grok） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr) |
| **`Discord.lsr`** | Discord 语音与即时通讯 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr) |
| **`Apple-Direct.lsr`** | iCloud, CloudKit, App Store, Apple ID, HomeKit, 音乐, 系统更新 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr) |
| **`Apple-Media.lsr`** | Apple TV+, Apple News, Fitness+ 锁区媒体 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media.lsr) |
| **`TestFlight.lsr`** | Apple TestFlight 内测分发平台 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/TestFlight.lsr) |
| **`Apple-Push.lsr`** | APNs 官方最小推送通道（默认建议保持关闭） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push.lsr) |
| **`China-Direct.lsr`** | 微信、淘宝、京东、闲鱼、抖音、B站、局域网私网段 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr) |

*(备用 CDN 镜像列表详见 [`docs/migration_and_rollback.md`](docs/migration_and_rollback.md))*

---

## Loon 原生一键规则诊断插件

为了减少用户在遇到分流异常时反复手动抓包、逐项排查的负担，仓库内置了专用的 Loon 原生诊断插件。

### 1. 插件安装地址
在 Loon【插件】-> 右上角【+】填入以下 URL：
```text
https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/diagnostics/LoonRules-Diagnostic.lpx
```
*(在最终的一体化 `.lcf` 配置中已默认引用，导入 `.lcf` 即可直接使用)*

### 2. 极简使用流程
```text
打开 Loon
  ↓
点击底部【脚本】或【工具】标签
  ↓
点击“规则诊断(快速)”或“规则诊断(完整)”运行
  ↓
等待 3~5 秒，系统弹出通知并完成检测
  ↓
长按或全选复制简短中文报告，直接发送给 ChatGPT 或 Gemini
```

### 3. 诊断报告示例
```text
【Loon 规则与核心服务诊断报告】
诊断模式: 快速诊断 (核心服务) | 生成时间: 2026-09-28 12:00:00 UTC
----------------------------------------
【规则仓库与发布状态】
[✓] 仓库接入: 正常 (GitHub官方源)
- 构建版本: 8a8da46
- 构建时间: 2026-09-28T11:59:50Z
- 规则集清单: 包含 14 个独立 .lsr 文件
----------------------------------------
【已知服务连通性检测】
✔ ChatGPT: 路由正常(198ms) | DIRECT不可达 (代理生效)
✔ Google Gemini: 路由正常(182ms) | DIRECT不可达 (代理生效)
✔ Claude: 路由正常(215ms) | DIRECT不可达 (代理生效)
✔ DeepSeek: 路由正常(42ms) | DIRECT正常
✔ Google Drive: 路由正常(125ms) | DIRECT不可达 (代理生效)
✔ Google 通用: 路由正常(130ms) | DIRECT不可达 (代理生效)
✔ YouTube: 路由正常(152ms) | DIRECT不可达 (代理生效)
✔ Telegram: 路由正常(140ms) | DIRECT不可达 (代理生效)
✔ GitHub: 路由正常(210ms) | DIRECT正常
✔ Apple iCloud: 路由正常(45ms) | DIRECT正常
----------------------------------------
【综合诊断结论】
✔ 判断: 全部 10 项服务及规则源连接正常，分流策略运行平稳 (耗时: 3.2s)
----------------------------------------
【必须诚实标注的能力边界 (需真机验证)】
本诊断插件仅能检测 HTTP/HTTPS 端口与静态路由可达性，以下底层行为必须在 iPhone 真机核验：
1. APNs TCP 5223 守护进程连接 (需在 Loon“包含 APNS”开启时捕获)
2. Telegram 锁屏唤醒与蜂窝后台长连接推送延迟
3. HomeKit 室内摄像头即时视频画面流推流与门铃
4. Apple Watch 独立 Wi-Fi/蜂窝联网与天气表盘刷新
5. 第三方依赖 CloudKit 的 App (爱乐记、猿音) 真实多端双向同步
========================================
```

### 4. 隐私保证与运行安全
* **100% 本机执行**：不读取或上传 Cookie、Token、Authorization、账号密码或设备标识。
* **零配置修改**：不修改用户的策略组选择、代理节点、DNS、MitM 证书或运行模式。
* **纯手动触发**：不配置任何定时任务，只在用户手动点击时发起只读轻量请求。
* **安全回退**：诊断若遭遇网络超时，绝不影响 Loon 的常规网络代理。

---

## 本地低操作量诊断工具

除了 Loon 插件外，仓库本地还提供两套自动化诊断脚本：

### 1. 规则命中模拟器 (`scripts/simulate_hit.py`)
无需真机即可模拟 Loon 顶层至底层的规则命中与覆盖逻辑：
```bash
python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com www.googleapis.com
```
* 输出：命中规则、所属规则集、是否被更早规则覆盖、是否存在跨分类冲突。
* **策略中立**：绝不输出节点或推荐地区。

### 2. 日志脱敏分析器 (`scripts/sanitize_log.py`)
支持分析 Loon 请求日志或 HAR 抓包：
```bash
python scripts/sanitize_log.py path_to_log.har
```
* **彻底脱敏**：本机剔除 Cookie、Token、Authorization、查询参数与 Body。
* **自动标出**：失败请求、FINAL 兜底、未收录新域名、大流量请求（>=5MB，如 Primuse 串流）、疑似错误分类。

---

## 目录结构

```text
loon-rules/
├── .github/
│   └── workflows/
│       └── sync-and-build.yml     # 每周自动同步 upstream、校验与发版流水线
├── diagnostics/                   # 原生诊断插件源码
│   ├── LoonRules-Diagnostic.lpx   # Loon 插件定义清单
│   ├── loon-rules-diagnostic.js   # 诊断核心脚本 (JS)
│   └── services.yml               # 诊断服务测试端点与真机标注配置
├── dist/                          # Loon 最终订阅的 .lsr 与诊断产物
│   ├── *.lsr                      # 14 个独立服务分类规则文件 (策略中立)
│   └── diagnostics/
│       ├── LoonRules-Diagnostic.lpx
│       ├── loon-rules-diagnostic.js
│       └── manifest.json          # 规则版本、SHA256校验值与服务清单
├── docs/                          # 详细运维与对照报告
│   ├── lcf_audit_report.md        # 原始配置脱敏与 Apple 规则清理对照报告
│   ├── policy_mapping.md          # 策略组映射与 [Remote Rule] 配置示例
│   ├── plugin_compatibility.md    # 外部插件兼容性与互操作指南
│   ├── apple_apns_test_guide.md   # Apple 生态与 APNs 权威推送验证指南
│   └── migration_and_rollback.md  # 逐组平滑迁移步骤与分步回滚方案
├── rules/
│   └── custom/                    # 个人自定义规则（最高优先级，新域名补丁）
├── scripts/
│   ├── build.py                   # 拉取、校验、去重、冲突检测与 manifest 生成引擎
│   ├── test_rules.py              # 自动化单元测试（语法、防碰撞、隔离断言）
│   ├── simulate_hit.py            # 规则命中模拟器
│   ├── sanitize_log.py            # 日志脱敏分析器
│   └── upstream_lock.json         # 各上游有效规则数锁定基线
├── tests/
│   └── test_diagnostic.js         # 诊断插件本地夹具测试套件 (Node.js)
├── sources.yml                    # 声明式只读上游来源配置
├── README.md
└── LICENSE                        # 完整 GPL-2.0 授权文本
```

---

## 构建与测试验证

```bash
# 1. 编译规则集并生成诊断 manifest
python scripts/build.py

# 2. 运行规则完整性与防碰撞测试
python scripts/test_rules.py

# 3. 运行诊断插件本地夹具测试 (覆盖 8 种异常与回退场景)
node --test tests/test_diagnostic.js
```

---

## 许可协议与致谢

* 本项目遵循 **GPL-2.0** 协议开源，完整文本见 [`LICENSE`](LICENSE)。
* **上游数据同步声明**：当前实际自动同步 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的开源规则集，严格遵循其 GPL-2.0 开源许可；[luestr/ShuntRules](https://github.com/luestr/ShuntRules) 仅作结构参考，不复制其未授权规则。
