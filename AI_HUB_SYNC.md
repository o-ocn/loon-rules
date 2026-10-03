# 项目同步申请单 (AI_HUB_SYNC.md)

> 📌 **统一入口声明**：本项目采用本文件作为向 `AI-Project-Hub` 提交状态同步与索引更新的**标准入口文件**。  
> 存放位置：**存放在项目代码工程根目录**。

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
  - 核心特征/说明更新：已完成 Phase 1.5 联合审定直连规则与极速 DNS 扩充，详细状态与规则基线见项目单一事实源（元数据未发生结构性变更，无需同步改动 Hub 索引）
- **Hub 内项目状态指针 / 档案更新**：
  - 拟同步文件：`projects/loon-rules/PROJECT_STATE.md`
  - 拟变更摘要：保持地图索引指针与 SSOT 对齐，不将详细技术状态复制进 Hub

---

## 三、对应事实源文件与实测证据
> 📌 **填写原则（写“最近同步摘要”，不写长期固定事实）**：本节只写**本次同步的验证方式与结论**，严禁写入会随时间漂移的固定数字或状态（如测试总数、镜像对称状态、校验规则版本、节点/曲目规模等）。这类内容一律留在项目唯一事实源 `PROJECT_STATE.md` 中，本文件只保留指向它的指针，避免同步单自身过期。

- **项目唯一详细事实源 (SSOT)**：[`PROJECT_STATE.md`](PROJECT_STATE.md)（包含项目目标、当前状态、基线定型、决策账本与未完成项）
- **协作者行为规范与交接规范**：[`AGENTS.md`](AGENTS.md)
- **核心实测证据摘要**：本次 Phase 1.5 增量规则与 DNS 映射经本地 5 道前置质量门禁、跨生态防冲突防泄漏检测、及 GitHub Actions 远程 CI 自动化发布工作流全量核验通过；脱敏验收工具完成候选与回退资产结构核验。详细规则条数、发布基线、测试记录及待办清单唯一由 [`PROJECT_STATE.md`](PROJECT_STATE.md) 维护。

---

## 四、安全与合规声明
- [x] 已确认无任何密码、Token、Cookie、API Key、私钥或完整订阅 URL 具体值；
- [x] 已确认无 AI 聊天记录、推理思考过程或操作流水账；
- [x] 变更内容经实际运行验证通过，具备真实性。
