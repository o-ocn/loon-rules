# Loon Rules 分流规则集（策略中立・自动化维护・原生一键诊断）

本项目是一个公开、独立维护的 **Loon 分流规则仓库**（`.lsr` 格式）。
仓库秉持**“上游覆盖为主、Custom 补丁为辅、少量必要过滤、策略严格中立”**的原则，解决第三方聚合规则中常见的“规则粗暴混杂、AI 与普通服务交叉碰撞、Apple 生态易受干扰”等问题。

---

## 核心设计准则与三层架构

1. **三层规则结构**：
   - **成熟上游负责服务主体**：以 `blackmatrix7/ios_rule_script` (GPL-2.0) 为主要规则源，保障 Gemini、Telegram、Google Drive、Apple 等成熟服务规则的全面性与健壮度，不要求用户长期抓包补域名。`luestr/ShuntRules` 仅用于分流结构与遗漏核对。
   - **自动断言保护分类边界**：CI/CD 与本地测试套件对 8 大关键分类边界实施 100% 机器可执行断言（包含域名归属、禁止宽泛父域、执行优先级与跨集冲突检测）。
   - **Custom 仅补有证据的例外与遗漏**：自定义规则必须附带来源/抓包证据、加入原因及日期。当成熟上游官方收录后，构建系统自动提示清理重复 Custom。
2. **策略绝对中立（Policy-Neutral）**：
   - 仓库只负责判断“流量属于什么服务”，绝不决定“走什么节点、地区或策略”。
   - 所有生成的 `.lsr` 绝不写入用户策略组名称、地区（HK/US/JP）、机场/VMISS 节点名称，也不写入 DIRECT/PROXY/REJECT 等策略动作。
   - 用户在 Loon 中长按每个远程规则，自由绑定专属策略组、内置策略或指定节点。
3. **8 大服务边界与防碰撞保护**：
   - **Gemini / 普通 Google**：Gemini 专属端点（含 iOS WebChannel、gRPC 流式及官方 API）归入 `AI-Overseas`；允许无害交叉（少量登录与静态资源走 Google）；禁止 `google.com`、`googleapis.com` 宽泛父域进入 AI；`AI-Overseas` 排在 `Google` 之前。
   - **Gemini / Google Drive**：Drive 专属域名归入 `GoogleDrive`，Gemini 端点归入 `AI-Overseas`，互不混杂。
   - **Google Drive / 共享 API**：`www.googleapis.com` 承载 Primuse 音乐串流等多业务共享，严禁归入 Drive 或 AI，统一归于 `Google.lsr`。
   - **YouTube / 普通 Google**：YouTube 视频、CDN IP-CIDRs (`172.110.32.0/21`, `216.73.80.0/20`) 专属于 `YouTube`。`deepmind.com` 归于 AI；YouTube 排在 Google 之前。
   - **Grok / Twitter/X**：`grok.com`、`x.ai` 归入 `AI-Overseas`；Twitter 平台主干归入 `Twitter`；禁止跨集污染。
   - **Muse from Meta 精准核实**：Muse from Meta (App Store ID: 6760173601) 是 Meta 于 2026-09-08 官方发布的个人 AI 代理 (Personal AI Agent)，在 iOS、Android 和 `muse.ai` 上运行。专属域名 `muse.ai` 归入 `AI-Overseas`；`meta.ai` / `api.meta.ai` 属于通用 Meta AI 基础设施，因缺少 Muse 专属端点证据不予收录；严禁引入 Meta 社交套件 (`facebook.com`, `instagram.com`, `meta.com` 等)。
   - **TestFlight / Apple Media / Apple Direct**：TestFlight 独立分发；Apple TV/News 媒体分流；基础直连锁定 iCloud、CloudKit、OTA；排在 Direct 之前生效。
   - **APNs / Apple 基础服务**：`Apple-Push.lsr` 仅收录官方最小 `push.apple.com` 及 5 个 IPv4 + 4 个 IPv6 官方推送 CIDR（严格遵循 Apple 官方文档 102266，IPv6 包含权威 `2620:149:a44::/48`）；保留 `Apple Push` 策略组；严禁混入 `17.0.0.0/8` 或 `apple.com`；排在 Direct 之前生效。
4. **中国大陆冷启动与双镜像发布 (待真机验证)**：
   - 首次导入 `.lcf`，节点未就绪或 GitHub Raw 暂时不可达时，依靠本地 `[Rule]` 中的内网段旁路与必要直连规则维持基础联网。
   - 所有规则与插件均同步提供 Fastly jsDelivr 备用 CDN 镜像。根据 Loon 官方文档，规则订阅 LRU 为近期查询缓存，离线冷启动表现需待真机首次导入验证。
5. **零变更构建幂等性**：
   - 自动构建没有规则内容变化时，严格禁止修改发布文件、版本号、构建时间或 `manifest.json`，杜绝幽灵提交。
   - 下载失败、异常缩水、语法错误或冲突增加时，自动熔断并保留上一版成品。

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
*(在未来 PR 合并并由 ChatGPT Work 于本地装配生成最终唯一 .lcf 时，将配置该远程插件规范；语法遵循 Loon 3.5.1+ Generic Script v2 规范，待 PR 合并后在真机客户端首次导入点击确认)*

### 2. 极简日常使用流程
```text
打开 Loon
  ↓
点击底部【脚本】或【工具】标签
  ↓
点击“规则诊断(快速)”或“规则诊断(完整)”手动运行
  ↓
等待 3~8 秒，系统弹出通知并生成简短中文报告
  ↓
长按或全选复制简短报告（通常仅 10~15 行），直接发送给 ChatGPT 或 Gemini 审核
```

### 3. 日常诊断报告示例（紧凑精炼，异常即显）
```text
【Loon 规则与核心服务诊断报告】
诊断模式: 快速诊断 (核心规则与服务) | 生成时间: 2026-09-28 16:44:04 UTC
----------------------------------------
[✓] 发布源状态: 主备双源均可达且内容同版本一致 (GitHub + jsDelivr)
- 版本标识: 0b8b8e0be129 (构建时间: 2026-09-28T16:37:30.095678+00:00, 清单: 14 个规则集)
----------------------------------------
[✓] 规则集校验: 全部 4 个规则集正文、条数与 SHA256 均校验通过 (版本: a1f362bd587f)
----------------------------------------
[✓] 服务连通性: 共探测 10 项服务，当前分流路由均畅通 (其中 7 项仅当前路由可达, DIRECT不可达, 3 项双向均可达)
----------------------------------------
✔ 诊断结论: 核心服务分流有效运作 (7 项仅当前路由可达/DIRECT不可达, 3 项双向均可达)，连通性平稳 (耗时: 1.8s)
----------------------------------------
【能力边界提示 (需真机验证)】仅探测已知 HTTPS 端点，无法自动发现未知新增域名 (仍需日常抓包或用户反馈补充)；未探测 APNs TCP 5223 及应用内私有长连接。
========================================
```
*注：当遇到部分服务不可达时，报告会列出异常项并提供中性建议（例如提示检查 Loon 命中规则或绑定的出口节点），不妄断“代理生效”或“节点故障”。*

### 4. 隐私保证与运行安全
* **100% 本机执行**：不读取或上传 Cookie、Token、Authorization、账号密码或设备标识。
* **零配置修改**：只读探测，绝不修改用户的策略组选择、代理节点、DNS、MitM 证书或运行模式。
* **纯手动触发**：不配置任何定时任务，只在用户手动点击时发起轻量只读请求。
* **时限保护与受控并发**：并发上限为 4，内置硬截止时限（快速 25s / 完整 50s）与安全看门狗，超时亦能安全产出部分简短报告并确保 `$done` 仅调用一次，杜绝被 Loon 异常强退。

---

## 本地辅助离线诊断工具

重要说明：**Loon 官方 Script API 未提供直接读取历史请求记录的接口**，因此仓库不提供也不存在“Loon 内一键导出历史请求日志”插件。日常运维请完全依托上述【Loon 原生诊断插件】复制短报告。
仅当遇到疑难跨分类杂糅排查时，用户可手动在 Loon 中导出 HAR 文件，并在本机运行以下离线分析工具：

### 1. 规则命中模拟器 (`scripts/simulate_hit.py`)
无需真机即可推演 Loon 顶层至底层的规则命中与覆盖逻辑：
```bash
python scripts/simulate_hit.py webchannel-robinfrontend-pa.googleapis.com 17.249.1.5
```
* 支持域名及 IPv4/IPv6 CIDR 多阶段静态推演（Local Rule -> Remote Rule -> FINAL）。
* **自动识别并跳过** `enabled=false` 的未启用规则。
* 输出严格脱敏，不打印私人配置与动作。插件规则若未加载明确提示 `[未验证: 插件注入规则未加载]`。

### 2. 日志严格脱敏分析器 (`scripts/sanitize_log.py`)
离线分析 Loon 手动导出的 HAR 或纯文本日志：
```bash
python scripts/sanitize_log.py path_to_log.har
```
* **零敏感泄露**：严格校验时间格式（过滤伪造的时间戳及用户名），规则标签与策略标签使用严格白名单约束，绝不输出 `Authorization: Bearer`、私有设备 ID、节点密钥或 Cookie。
* **自动标出**：失败请求、FINAL 兜底、未收录新域名、大流量传输（>=5MB，如 Primuse 串流）、疑似跨集错误分类。

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
