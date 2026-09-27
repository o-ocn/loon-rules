# 平滑迁移、多路订阅与分步回滚方案

为了确保现有网络体验不中断，本方案遵循**“先备份基线、离线自立、逐组迁移、单点回滚”**的安全原则。

---

## 1. 离线独立性与首次安装保障

> [!IMPORTANT]
> **绝对不产生网络自锁死循环**：
> 首次导入或恢复 Loon 配置时，必须能直接从保存的本地配置导入节点与策略组，**严禁依赖先下载 GitHub 远程规则才能建立代理连接**。

* **离线自立机制**：
  - 本地节点与自建 VMISS 9929 留在本地 `.lcf` 的 `[Proxy]` / `[Remote Proxy]`。
  - 本地保留基础的 `[Rule]`（包含基本直连与局域网放行）。
  - 即使此时未连接外网或 GitHub 暂不可达，Loon 仍可凭借本地配置建立代理通道，随后再按需拉取 GitHub 上的 `.lsr` 远程分流规则。

---

## 2. 逐组迁移与验收步骤

### 步骤 0：全量备份当前配置
在 Loon App 内点击：【配置】-> 右上角导出/保存为新配置，命名为 `Backup_Baseline_2026.lcf`。

### 步骤 1：创建本地 `AI` 策略组
在本地配置加入：
```ini
[Proxy Group]
AI = select, [你的VMISS-9929节点名], US, HK, JP, DIRECT
```

### 步骤 2：迁移 AI 规则组（第一阶段验收）
1. 在 `[Remote Rule]` 中添加：
   - `AI-Overseas.lsr` -> 绑定 `AI`
   - `AI-China-Direct.lsr` -> 绑定 `DIRECT`
2. 禁用或删除原有的第三方杂合 AI 规则。
3. **验收**：
   - 访问 `deepseek.com`：确认直连畅通，不经过代理。
   - 访问 `chatgpt.com` / `claude.ai` / `gemini.google.com`：确认走 VMISS 9929 正常访问。
   - 访问 `muse.ai`：确认走 AI 策略。
   - 访问 `google.com`：确认仍走原有 `US Test`，未被 Gemini 粗暴带跑。

### 步骤 3：迁移偏好分流与日常通讯（第二阶段验收）
1. 替换 `GoogleDrive.lsr` (`HK`)、`OneDrive.lsr` (`US`)、`Google.lsr` (`US Test`)、`YouTube.lsr` (`US Test`)。
2. 替换 `Telegram.lsr` (`Final`) 与 `Twitter.lsr` (`Final`)。
3. **验收**：
   - Google Drive 文件上传下载测速（走香港）。
   - OneDrive 文档同步（走美国）。
   - Twitter 正常刷推，且 Grok 功能正常。

### 步骤 4：迁移 Apple 服务与大陆直连（第三阶段验收）
1. 依次添加 `Apple-Media-US.lsr` (`US Test`) 与 `Apple-Direct.lsr` (`DIRECT`)（注意：美区媒体规则在 Loon 中必须排在直连规则上方）。
2. 替换 `China-Direct.lsr` (`DIRECT`)。

3. **验收**：
   - HomeKit 摄像头即时推流无黑屏。
   - Apple Watch 天气刷新。
   - 打开【爱乐记】与【猿音】，核验 CloudKit 数据即时同步。
   - 微信、淘宝、京东、闲鱼秒开且支付定位正常。

### 步骤 5：APNs 独立挂载（可选实验）
挂载 `Apple-Push-Experimental.lsr`（默认保持 `enabled=false`），按《Apple 生态与 APNs 实验验证指南》进行单变量对比测试。

---

## 3. 订阅地址清单（官方原始源与 CDN 备选源）

为防止 GitHub Raw 在部分大陆蜂窝网络下偶尔出现解析波动，本仓库提供经测试的静态 CDN 备用镜像。
**提示：CDN 备选源仅在大陆 Wi-Fi 与蜂窝数据实测畅通后才建议启用。**

| 规则成品 | GitHub Raw 官方原始源（首选） | jsDelivr CDN 加速镜像（备用） |
| :--- | :--- | :--- |
| **`AI-Overseas.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-Overseas.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/AI-Overseas.lsr` |
| **`AI-China-Direct.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/AI-China-Direct.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/AI-China-Direct.lsr` |
| **`GoogleDrive.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/GoogleDrive.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/GoogleDrive.lsr` |
| **`OneDrive.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/OneDrive.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/OneDrive.lsr` |
| **`Google.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Google.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Google.lsr` |
| **`YouTube.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/YouTube.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/YouTube.lsr` |
| **`Telegram.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Telegram.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Telegram.lsr` |
| **`Twitter.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Twitter.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Twitter.lsr` |
| **`Discord.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Discord.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Discord.lsr` |
| **`Apple-Direct.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Direct.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Apple-Direct.lsr` |
| **`Apple-Media-US.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Media-US.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Apple-Media-US.lsr` |
| **`Apple-Push-Experimental.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/Apple-Push-Experimental.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/Apple-Push-Experimental.lsr` |
| **`China-Direct.lsr`** | `https://raw.githubusercontent.com/o-ocn/loon-rules/main/dist/China-Direct.lsr` | `https://fastly.jsdelivr.net/gh/o-ocn/loon-rules@main/dist/China-Direct.lsr` |

---

## 4. 回滚与灾备机制

1. **单条远程规则回滚**：
   - 若某单个服务（如 Telegram）异常，直接在 Loon 中将该 `[Remote Rule]` 停用，或将策略临时切换为备用节点。
2. **仓库版本级回滚（恢复上一个可用提交）**：
   - 仓库每次更新都会产生 release 标签（格式如 `release-20260928-xxxxxx`）。
   - 若上游同步引入未知异常，可直接在 GitHub 或本地执行：
     ```bash
     git revert HEAD
     git push origin main
     ```
   - 或将 Loon 订阅链接固定为上一个已知稳定版本的 tag 路径。
3. **一键还原至原配置**：
   - 在 Loon 中点击进入【配置】管理列表，直接一键切换回 `Backup_Baseline_2026.lcf`，即可瞬间恢复初始生产状态。
