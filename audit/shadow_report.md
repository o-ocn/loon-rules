# Phase 0 Shadow Audit Report

Status:
SHADOW ONLY

This report is generated for evaluation purposes only.

This phase does not modify:
- dist/
- build.py
- production rule output

AUTO_PASS means simulated production eligibility only.

> ⏱ **生成时间**: `2026-11-21T13:02:24.620945+00:00`  
> 🛡 **运行模式**: 只读旁路测试 | 零生产侵入 | `dist/` 100% 保持现状  

---

## 一、核心 KPI 与自动决策覆盖率

| 指标项 | 规则数量 | 占比 | 说明 |
| :--- | :---: | :---: | :--- |
| **上游去重聚合总量** | **110358** | 100% | 多源清洗规范化后的全局规则集 |
| **生产已有覆盖 (In Prod)** | **2860** | - | 当前 `China-Direct.lsr` 已稳定纳管的规则 |
| **新增候选差集 (Delta)** | **107498** | 100% | 上游存在但未纳入当前生产的域名/网段 |
| ├─ **拟自动放行 (`AUTO_PASS`)** | **52** | 0.0% | 模拟生产放行（高置信度/双重凭证/大陆核心App） |
| ├─ **拟隔离待审 (`REVIEW`)** | **120** | 0.1% | 拟入隔离池（需 AI 会审或观察中候选） |
| └─ **拟彻底阻断 (`BLOCK`)** | **107326** | 99.8% | 彻底剔除（海外代理碰撞/低分/禁止类型如 IP-CIDR） |

> 🎯 **自动决策覆盖率**: **`99.89%`**  
> （自动决策覆盖率达到 99.89%，其中主要来自自动 BLOCK 与类型过滤。明确区分：自动处理 ≠ 自动放行。）

---

## 二、隔离观察池抽样 (REVIEW 焦点样例)

以下为得分处于 `[50, 门槛)` 区间的候选规则（Phase 1 将暂存入隔离池，不影响生产）：

| 候选规则 | 来源 | 置信度得分 | 判定阶段 | 拦截原因 |
| :--- | :--- | :---: | :---: | :--- |
| `DOMAIN-SUFFIX,00cdn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,13th.tech` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,163yun.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,17k.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,423down.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,51jobcdn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,8686c.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,88cdn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,alibabachengdun.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,alibabacloud.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,alicloudccp.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,aliyuncdn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,aliyuncs.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,allawnfs.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,allawno.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |

*(其余 105 条详见 Actions Artifact `shadow-audit-reports` 中的完整报告 `shadow_report_full.json`)*

---

## 三、安全阻断红线抽样 (BLOCK 验证证据)

以下为被 Hard Block 或类型过滤器成功拦截的高危/海外规则（证明防污染机制生效）：

| 阻断规则 | 来源 | 判定阶段 | 阻断依据 |
| :--- | :--- | :---: | :--- |
| `DOMAIN,dl.steam.clngaa.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,dl.steam.ksyna.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,st.dl.bscstorage.net` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,st.dl.eccdnx.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,st.dl.pinyuncloud.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,steampipe.steamcontent.tnkjmec.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,steampowered.com.8686c.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,steamstatic.com.8686c.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,wmsjsteam.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,xz.pphimalayanrt.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN,ye.dun.163yun.com` | acl4ssr_china | `CONFIDENCE_SCORE` | Low confidence (35 < 50), dropped |
| `DOMAIN-KEYWORD,.tmall.com` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,360buy` | acl4ssr_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,alicdn` | acl4ssr_china, blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,alimama` | acl4ssr_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |

*(其余 107311 条详见 Actions Artifact `shadow-audit-reports` 中的完整报告 `shadow_report_full.json`)*

---

## 四、Phase 0 准出标准评估 (Exit Criteria Check)

- [x] **生产产物零破坏**：`dist/` 保持完全干净，未修改线上规则。
- [x] **自动化率达成**：当前自动化率 **99.89%**，满足 90% 自动化维护预期。
- [x] **已执行配置中的红线与类型过滤**：结果仅为旁路分类，不等同于全网覆盖或真机验收。
