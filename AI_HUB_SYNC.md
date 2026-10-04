# 项目同步申请单 (AI_HUB_SYNC.md)

> 📌 **统一入口声明**：本项目采用本文件作为向 `AI-Project-Hub` 提交状态同步与索引更新的**标准入口文件**。  
> 存放位置：**存放在项目代码工程根目录**。  
> ⏱ **最近同步单更新日期**：2026-10-04  
> 🏷 **阶段摘要**：Phase 1.5 发布、vegslb.com 配套试行与 jspcdn.cn 定向直连补丁，处于日常观察与常规维护阶段；详细状态见 [`PROJECT_STATE.md`](PROJECT_STATE.md)。

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
  - 核心特征/说明更新：本次按所有者授权记录 jspcdn.cn 定向直连补丁；Hub仅更新既有项目一条摘要和事实源指针，详细原因、验证及待办保留在本仓库 PROJECT_STATE.md
- **Hub 内项目状态指针 / 档案更新**：
  - 拟同步文件：无；本项目唯一详细事实源为独立仓库根目录 [`PROJECT_STATE.md`](PROJECT_STATE.md)，本次不在Hub新增状态副本。
  - 拟变更摘要：保持地图索引指针与 SSOT 对齐，不将详细技术状态复制进 Hub

---

## 三、对应事实源文件与实测证据
> 📌 **填写原则（写“最近同步摘要”，不写长期固定事实）**：本节只写**本次同步的验证方式与结论**，严禁写入会随时间漂移的固定数字或状态（如测试总数、镜像对称状态、校验规则版本、节点/曲目规模等）。这类内容一律留在项目唯一事实源 `PROJECT_STATE.md` 中，本文件只保留指向它的指针，避免同步单自身过期。

- **项目唯一详细事实源 (SSOT)**：[`PROJECT_STATE.md`](PROJECT_STATE.md)（包含项目目标、当前状态、基线定型、决策账本与未完成项）
- **协作者行为规范与交接规范**：[`AGENTS.md`](AGENTS.md)
- **核心实测证据摘要**：本次 jspcdn.cn 单规则补丁已完成构建、规则/冲突/诊断/评分及预发布检查；未新增DNS映射或调整其他策略。手机有效加载、实际体验与国内IP兜底匹配仍待验证。此前私人候选与回退仅为部分通过（`PARTIAL_PASS / UNVERIFIED_PLUGINS`），插件运行时注入未验证。详细过程、历史发布记录、恢复起点和下一步均见 [`PROJECT_STATE.md`](PROJECT_STATE.md)；远端推送及CI结果另以实际收尾核验为准。

---

## 四、安全与合规声明
- [x] 已确认无任何密码、Token、Cookie、API Key、私钥或完整订阅 URL 具体值；
- [x] 已确认无 AI 聊天记录、推理思考过程或操作流水账；
- [x] 变更内容经实际运行验证通过，具备真实性。
