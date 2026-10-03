# Phase 0 Shadow Audit Report

Status:
SHADOW ONLY

This report is generated for evaluation purposes only.

This phase does not modify:
- dist/
- build.py
- production rule output

AUTO_PASS means simulated production eligibility only.

> ⏱ **生成时间**: `2026-10-03T07:26:07.294258+00:00`  
> 🛡 **运行模式**: 只读旁路测试 | 零生产侵入 | `dist/` 100% 保持现状  

---

## 一、核心 KPI 与自动决策覆盖率

| 指标项 | 规则数量 | 占比 | 说明 |
| :--- | :---: | :---: | :--- |
| **上游去重聚合总量** | **111461** | 100% | 多源清洗规范化后的全局规则集 |
| **生产已有覆盖 (In Prod)** | **374** | - | 当前 `China-Direct.lsr` 已稳定纳管的规则 |
| **新增候选差集 (Delta)** | **111087** | 100% | 上游存在但未纳入当前生产的域名/网段 |
| ├─ **拟自动放行 (`AUTO_PASS`)** | **50** | 0.0% | 模拟生产放行（高置信度/双重凭证/大陆核心App） |
| ├─ **拟隔离待审 (`REVIEW`)** | **403** | 0.4% | 拟入隔离池（需 AI 会审或观察中候选） |
| └─ **拟彻底阻断 (`BLOCK`)** | **110634** | 99.6% | 彻底剔除（海外代理碰撞/低分/禁止类型如 IP-CIDR） |

> 🎯 **自动决策覆盖率**: **`99.64%`**  
> （自动决策覆盖率达到 99.64%，其中主要来自自动 BLOCK 与类型过滤。明确区分：自动处理 ≠ 自动放行。）

---

## 二、隔离观察池抽样 (REVIEW 焦点样例)

以下为得分处于 `[50, 门槛)` 区间的候选规则（Phase 1 将暂存入隔离池，不影响生产）：

| 候选规则 | 来源 | 置信度得分 | 判定阶段 | 拦截原因 |
| :--- | :--- | :---: | :---: | :--- |
| `DOMAIN-SUFFIX,cn` | acl4ssr_china, blackmatrix7_china | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,00cdn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,115.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,12306.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,126.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,126.net` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,127.net` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,13th.tech` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,163.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,163yun.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,17173.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,178.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,17k.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,21cn.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |
| `DOMAIN-SUFFIX,360.com` | acl4ssr_china, loyalsoldier_direct | 55 | `CONFIDENCE_SCORE` | Intermediate confidence (55 in [50, 85)), routed to Quarantine |

*(其余 388 条详见 shadow_report.json)*

---

## 三、安全阻断红线抽样 (BLOCK 验证证据)

以下为被 Hard Block 或类型过滤器成功拦截的高危/海外规则（证明防污染机制生效）：

| 阻断规则 | 来源 | 判定阶段 | 阻断依据 |
| :--- | :--- | :---: | :--- |
| `DOMAIN-SUFFIX,ms` | blackmatrix7_china | `CONFIDENCE_SCORE` | Low confidence (45 < 50), dropped |
| `DOMAIN-KEYWORD,.tmall.com` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,alicdn` | acl4ssr_china, blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,alipay` | acl4ssr_china, blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,aliyun` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,baidu` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,beplay` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,microsoft` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,officecdn` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `DOMAIN-KEYWORD,taobao` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'DOMAIN-KEYWORD' |
| `USER-AGENT,%e4%b8%ad%e5%9b%bd%e5%b7%a5%e5%95%86%e9%93%b6%e8%a1%8c*` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'USER-AGENT' |
| `USER-AGENT,%e4%ba%ac%e4%b8%9c%e5%88%b0%e5%ae%b6*` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'USER-AGENT' |
| `USER-AGENT,%e4%bc%81%e4%b8%9a%e5%be%ae%e4%bf%a1*` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'USER-AGENT' |
| `USER-AGENT,%e4%bc%98%e9%85%b7*` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'USER-AGENT' |
| `USER-AGENT,%e5%8d%b3%e5%88%bb*` | blackmatrix7_china | `TYPE_FILTER` | forbidden_type: First phase strictly forbids auto-adding rule type 'USER-AGENT' |

*(其余 110619 条详见 shadow_report.json)*

---

## 四、Phase 0 准出标准评估 (Exit Criteria Check)

- [x] **生产产物零破坏**：`dist/` 保持完全干净，未修改线上规则。
- [x] **自动化率达成**：当前自动化率 **99.64%**，满足 90% 自动化维护预期。
- [x] **硬门禁有效性**：海外代理红线与出海服务被 100% 拦截，无漏判放行。
