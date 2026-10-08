# 项目同步申请单 (AI_HUB_SYNC.md)

> 📌 **统一入口声明**：本项目采用本文件作为向 `AI-Project-Hub` 提交状态同步与索引更新的**标准入口文件**。  
> 存放位置：**存放在项目代码工程根目录**。  
> ⏱ **最近同步单更新日期**：2026-10-08<br/>
> 🏷 **阶段摘要**：Phase 0.5日常观察；App Store正常替代配置已由用户确认，原19集单变量DNS候选待验；3309扩容草案拒绝入库，公开规则不变；此前副CDN传播待复核，详见PROJECT_STATE.md。

---

## 一、项目基础信息
- **项目名称**：`loon-rules`（Loon 原生分流规则系统）
- **项目唯一标识**：`repo:loon-rules`
- **项目物理路径 / 仓库地址**：`E:\Document\Gemini\loon-rules` / [https://github.com/o-ocn/loon-rules](https://github.com/o-ocn/loon-rules)
- **当前所处阶段**：生产稳定（日常观察与常规维护阶段）
- **同步申请类型**：
  - [ ] 新项目接入 (New Ingestion)
  - [x] 状态增量更新 (State Update)
  - [ ] 里程碑/阶段完成 (Milestone Completed)
  - [ ] 转入长期维护 (Long-Term Maintenance)

---

## 二、提议 Hub 变更内容 (Proposed Hub Changes)
- **PROJECT_INDEX.md 拟更新项**：
  - 维护状态：生产稳定（日常观察阶段）
  - 核心特征/说明更新：本次记录常用服务精准补齐、经审查的小上游维护与全清单参考样本回归；Hub项目元数据和事实源路径未变化，本次无需修改地图，确认事实、未验证边界与交接记录保留在本仓库 PROJECT_STATE.md
- **Hub 内项目状态指针 / 档案更新**：
  - 拟同步文件：无；本项目唯一详细事实源为独立仓库根目录 [`PROJECT_STATE.md`](PROJECT_STATE.md)，本次不在Hub新增状态副本。
  - 拟变更摘要：保持地图索引指针与 SSOT 对齐，不将详细技术状态复制进 Hub

---

## 三、对应事实源文件与实测证据
> 📌 **填写原则（写“最近同步摘要”，不写长期固定事实）**：本节只写**本次同步的验证方式与结论**，严禁写入会随时间漂移的固定数字或状态（如测试总数、镜像对称状态、校验规则版本、节点/曲目规模等）。这类内容一律留在项目唯一事实源 `PROJECT_STATE.md` 中，本文件只保留指向它的指针，避免同步单自身过期。

- **项目唯一详细事实源 (SSOT)**：[`PROJECT_STATE.md`](PROJECT_STATE.md)（包含项目目标、当前状态、基线定型、决策账本与未完成项）
- **协作者行为规范与交接规范**：[`AGENTS.md`](AGENTS.md)
- **核心实测证据摘要**：本轮精确Apple主机（guzzoni.smoot.apple.com）增量、DNS白名单和扩大范围故障注入已本地及远端CI（Run #85，ID 37767776142）验证通过，主源GitHub Raw三项资产HTTP200且哈希一致；副源Fastly部分资产存在分支CDN传播延迟（非致命告警，待复核）；手机体验未验。数字、版本和Git/CI证据集中在项目PROJECT_STATE.md；元数据及事实源路径不变，无需Hub索引写入。

---

## 四、安全与合规声明
- [x] 已确认无任何密码、Token、Cookie、API Key、私钥或完整订阅 URL 具体值；
- [x] 已确认无 AI 聊天记录、推理思考过程或操作流水账；
- [x] 变更内容经实际运行验证通过，具备真实性。
