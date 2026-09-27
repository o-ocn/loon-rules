# Loon Rules 分流规则集（个人专属订阅源）

本项目是一个公开、独立维护的 **Loon 分流规则仓库**（`.lsr` 格式）。
作为个人唯一的规则维护入口，本项目旨在解决第三方聚合规则中常见的“规则粗暴混杂、AI 与普通服务交叉碰撞、Apple 生态易受干扰”等问题，提供结构清晰、策略解耦、可自动化验证的分流规则。

---

## 核心设计准则

1. **AI 严格二分与防碰撞隔离**：
   - **`AI-Overseas.lsr`**：收录 ChatGPT、Claude、Gemini、Grok 与 **Muse from Meta**。
     - *精准防碰撞*：严禁写入 `googleapis.com`、`google.com`（避免影响普通 Google 服务）；严禁写入 `x.com`、`twitter.com`（避免破坏 Twitter 独立策略）；严禁写入 `meta.com`、`facebook.com`、`instagram.com`、`whatsapp.com`（杜绝全家桶污染）。
     - *策略绑定*：绑定本地 `AI` 策略组（默认优先自建 VMISS 9929，支持手动切换）。
   - **`AI-China-Direct.lsr`**：收录中国大陆 AI 服务（**DeepSeek 用户明确要求直连**），绑定 `DIRECT`。
2. **Apple 生态稳定性第一**：
   - iCloud、CloudKit、Apple ID、App Store、HomeKit 及 Apple Music 坚持原生直连基线。
   - 严禁将 `apple.com`、`icloud.com`、`17.0.0.0/8` 或 Apple CDN 整段代理。
   - APNs 采用独立的实验性规则（`Apple-Push-Experimental.lsr`），与主干解耦，默认保持关闭 (`enabled=false`)。
3. **策略精准解耦**：
   - 坚持 Google Drive 走香港（`HK`）、OneDrive 走美国（`US`）、普通 Google 优先美国（`US Test`）、Telegram 走独立低延迟策略（`Final`）。
4. **只读上游与构建安全**：
   - 以 `blackmatrix7/ios_rule_script` 为只读代码上游（GPL-2.0），以 `luestr/ShuntRules` 为结构分类参考。
   - 本地规则具有最高优先权，构建流水线自动执行 Loon 语法校验、精确去重、跨策略冲突与父域覆盖检查。任一必需上游异常立即终止构建并保留既有成品。

---

## 目录结构

```text
loon-rules/
├── .github/
│   └── workflows/
│       └── sync-and-build.yml     # 每周自动化同步上游、校验与发布流水线
├── rules/
│   └── custom/                    # 个人自定义规则（最高优先级）
│       ├── AI-Overseas.list
│       ├── AI-China-Direct.list
│       ├── Apple-Direct.list
│       ├── Apple-Media-US.list
│       ├── Apple-Push-Experimental.list
│       ├── China-Direct.list
│       ├── Discord.list
│       ├── Google.list
│       ├── GoogleDrive.list
│       ├── OneDrive.list
│       ├── Telegram.list
│       ├── Twitter.list
│       └── YouTube.list
├── sources.yml                    # 声明式只读上游来源与防冲突排除表
├── scripts/
│   ├── build.py                   # 拉取、校验、去重、冲突检测与 .lsr 生成引擎
│   └── test_rules.py              # 自动化单元测试（语法、防碰撞、隔离断言）
├── dist/                          # Loon 最终订阅的 .lsr 成品
├── docs/                          # 详细交接与运维文档
│   ├── lcf_audit_report.md        # 原始 .lcf 配置文件脱敏审计报告
│   ├── policy_mapping.md          # 策略组映射与 [Remote Rule] 配置示例
│   ├── apple_apns_test_guide.md   # Apple 生态与 APNs 单变量测试指南
│   └── migration_and_rollback.md  # 逐组平滑迁移步骤与分步回滚方案
├── requirements.txt               # 构建依赖声明
├── README.md
└── LICENSE                        # 完整 GPL-2.0 授权文本
```

---

## 规则订阅清单

| 规则成品 (`dist/`) | 绑定策略 | 包含核心服务 | 订阅链接 (GitHub Raw) |
| :--- | :--- | :--- | :--- |
| **`AI-Overseas.lsr`** | `AI` | ChatGPT, Claude, Gemini, Grok, Muse from Meta | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr) |
| **`AI-China-Direct.lsr`** | `DIRECT` | DeepSeek（大陆 AI 直连） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr) |
| **`GoogleDrive.lsr`** | `HK` | Google Drive 独立香港分流 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr) |
| **`OneDrive.lsr`** | `US` | Microsoft OneDrive 独立美国分流 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr) |
| **`Google.lsr`** | `US Test` | 普通 Google 服务优先美区 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr) |
| **`YouTube.lsr`** | `US Test` | YouTube 流媒体 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr) |
| **`Telegram.lsr`** | `Final` | Telegram 独立低延迟通讯 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr) |
| **`Twitter.lsr`** | `Final` | Twitter / X 平台主干（不含 Grok） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr) |
| **`Discord.lsr`** | `US` | Discord 语音与通讯 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr) |
| **`Apple-Direct.lsr`** | `DIRECT` | iCloud, CloudKit, App Store, HomeKit, 音乐 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr) |
| **`Apple-Media-US.lsr`** | `US Test` | Apple TV+, Apple News, Fitness+, TestFlight | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media-US.lsr) |
| **`Apple-Push-Experimental.lsr`** | `Apple Push` | APNs 独立实验推送规则（默认关闭） | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push-Experimental.lsr) |
| **`China-Direct.lsr`** | `DIRECT` | 微信、淘宝、京东、闲鱼、局域网 | [Raw 链接](https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr) |

*(备用 CDN 镜像格式详见 [`docs/migration_and_rollback.md`](docs/migration_and_rollback.md))*

---

## 详细运维指南

* 策略组配置与 Loon 导入配置：详见 [`docs/policy_mapping.md`](docs/policy_mapping.md)
* 原始配置脱敏与插件优先级法则：详见 [`docs/lcf_audit_report.md`](docs/lcf_audit_report.md)
* APNs 推送原理与单变量测试矩阵：详见 [`docs/apple_apns_test_guide.md`](docs/apple_apns_test_guide.md)
* 逐组平滑迁移与回滚步骤：详见 [`docs/migration_and_rollback.md`](docs/migration_and_rollback.md)

---

## 许可协议与致谢

* 本项目规则解析与构建脚本遵循 **GPL-2.0** 协议开源，完整文本见 [`LICENSE`](LICENSE)。
* 数据上游遵循 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) 的开源许可与规范。
