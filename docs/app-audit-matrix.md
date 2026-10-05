# 中国大陆常用 App 与生态分流审计矩阵 (App Audit Matrix)

> 📌 **定位说明**：本文档记录中国大陆主流消费级应用、金融清算及基础云服务的分流策略、DNS 调度优化及海外业务隔离边界。后续任何开发者或 AI 接手本项目，应先核对本矩阵，避免重复全网扫描或盲目引入泛域名。
> ⚠️ **核验边界提示**：本矩阵所列“已完成”指分流规则、DNS 映射及静态门禁测试已收录并编译通过；真实手机端端到端业务交互（如支付实名、特定 App 冷启动及网络环境感知）仍属于日常运行观察项，保持客观审慎，不作绝对体验担保。

---

## 一、常用应用与服务审计矩阵

| 应用 / 生态分类 | 核心生产域名 (`China-Direct`) | 关键图床 / 静态 CDN | 规则状态 | DNS 调度状态 (`223.5.5.5` / `119.29.29.29`) | 明确排除 / 海外隔离边界 | 最后验证时间 | 备注与关键依据 |
| :--- | :--- | :--- | :--- | :---: | :--- | :---: | :--- |
| **微信 (WeChat)** | `weixin.com`<br>`qq.com`<br>`tencent.com` | `qpic.cn`<br>`wx.gtimg.com`<br>`vweixinthumb.tc.qq.com` | ✅ 已完成 | ✅ 已完成 (`119.29.29.29`) | 国际版多媒体 (`novacdn.com`)、WeChat Out 走海外代理 | 2026-10 | 核心长连接与支付稳定，qpic/gtimg 国内极速解析 |
| **支付宝 (Alipay)** | `alipay.com` | `alipayobjects.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 海外本地钱包 (AlipayHK, GCash, TrueMoney) 走海外 | 2026-10 | 补齐 alipayobjects，解决账单、小程序图床加载延迟 |
| **淘宝 / 天猫 / 1688** | `taobao.com`<br>`tmall.com`<br>`1688.com`<br>`idlefish.com` | `alicdn.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 速卖通 (AliExpress)、Lazada、Miravia 走海外代理 | 2026-10 | 1688 批发 API 曾因 DoH 返回香港 CDN 导致绕行，现已完成规则与 DNS 收录 |
| **京东 (JD)** | `jd.com`<br>`jdpay.com` | `360buyimg.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 京东全球售海外端走代理 | 2026-10 | 包含京东支付、商品图床，由 upstream 配合 Custom 维系 |
| **拼多多 (PDD)** | `pinduoduo.com`<br>`yangkeduo.com` | `pddpic.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **Temu (`temu.com`)** 物理隔离，严禁入直连 | 2026-10 | 实测海外 DoH 将 pddpic 跨洋调度至英国伦敦，现已绑定国内 DNS 恢复就近 CDN 解析 |
| **美团 / 大众点评** | `meituan.com`<br>`dianping.com`<br>`sankuai.com` | `meituan.net` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **Keeta (`keeta.com`)**（香港/中东外卖）走海外 | 2026-10 | 补齐母公司核心基建 sankuai 与店铺门头/菜品图床 meituan.net (曾调度至美西) |
| **饿了么 (Ele.me)** | `ele.me` | `elemecdn.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 阿里海外本地生活走代理 | 2026-10 | 特殊黑山顶级域 `.me` 易被外部规则误杀，必须显式直连与极速 DNS |
| **小红书 (RED)** | `xiaohongshu.com` | `xhscdn.com`<br>`xhscdn.net` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 排除第三方风控 `fengkongcloud.com` | 2026-10 | 实测海外 DoH 将 xhscdn 调度至美国洛杉矶 Akamai 导致大图白块，已补充规则与 DNS 映射 |
| **抖音 / 字节国内生态** | `douyin.com`<br>`zijieapi.com`<br>`bytedance.com`<br>`bytetos.com`<br>`doupay.com` | `byteimg.com`<br>`bytemaimg.com`<br>`bytegecko.com`<br>`ibytedtos.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **TikTok (`tiktok.com`, `byteoversea.com`)** 绝不直连 | 2026-10 | 规则与DNS已收录直播源站 (bytegecko) 与图床 (bytemaimg)，相关效果待观察 |
| **快手 (Kuaishou)** | `kuaishou.com`<br>`gifshow.com`<br>`kuaishoupay.com` | `yximgs.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **Kwai (`kwai.com`, `kwaicdn.com`)** 绝不直连 | 2026-10 | 补齐核心 API 网关 gifshow 与支付；实测 yximgs 曾调度至美西 |
| **哔哩哔哩 (Bilibili)** | `bilibili.com` | `bilivideo.com`<br>`hdslb.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | Bilibili 东南亚与海外版权番剧锁区节点走海外代理 | 2026-10 | 视频流与动态图片 CDN 全量国内就近加速 |
| **网易云音乐 (NetEase)** | `music.163.com` | `music.126.net` (`p1~p4`) | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **严禁引入 `netease.com`**（包含海外游戏节点 `global.netease.com`） | 2026-10 | 极窄聚焦方案：不引入 `163.com`/`126.net` 泛域，严格限定音乐 API 与音频流 |
| **QQ / 腾讯全系图床** | `qq.com`<br>`tencent.com` | `gtimg.com` | ✅ 已完成 | ✅ 已完成 (`119.29.29.29`) | 海外游戏 (Level Infinite) 走代理；未发现 gtimg 海外共享 | 2026-10 | 统一腾讯图片专属 CDN (微信表情、QQ空间、腾讯视频播放器内核) |
| **高德地图 (AutoNavi)** | `amap.com`<br>`autonavi.com` | 阿里公用 CDN | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | 无海外业务 | 2026-10 | 补齐 autonavi.com 至 DNS 插件 |
| **百度地图 / 百度网盘** | `baidu.com`<br>`baidupcs.com` | `bdimg.com` | ✅ 已完成 | ✅ 已完成 (`223.5.5.5`) | **排除 `bcebos.com`**（含海外公有云节点）及 **TeraBox** | 2026-10 | 独立收录个人网盘 baidupcs，保护大流量文件传输不爆刷海外代理 |

---

## 二、金融机构与支付清算审计矩阵

| 机构 / 体系 | 核心域名 (`China-Direct`) | DNS 调度优化 (`223.5.5.5`) | 规则状态 | 排除边界 (严禁混入直连) | 审计与验证结论 |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **中国银联 / 云闪付** | `unionpay.com`<br>`unionpaysecure.com`<br>`95516.com` | 显式配置 `223.5.5.5` | ✅ 已完成 | 无 | 实测海外 DoH 曾将 95516 网宿 CDN CNAME 调度至美国丹佛；现已绑定国内解析 |
| **招商银行 / 掌上生活** | `cmbchina.com`<br>`cmbimg.com` | 显式配置 `223.5.5.5` | ✅ 已完成 | **排除 `cmbwinglungbank.com`** (香港永隆银行)<br>**排除 `cignacmb.com`** (合资保险)<br>**排除 `8008205555.com/.cn`** (历史客服) | 规则与DNS已收录，阻断金融流量误走香港 IEPL，相关效果待观察 |
| **六大国有商业银行** | 工行 (`icbc.com.cn`, `icbc.cn`)<br>建行 (`ccb.com`, `ccb.cn`, `ccb.com.cn`)<br>农行 (`abchina.com`, `abchina.com.cn`, `abchina.cn`)<br>中行 (`boc.cn`)<br>交行 (`bankcomm.com`, `bankcomm.com.cn`, `bankcomm.cn`)<br>邮储 (`psbc.com`, `psbc.com.cn`) | 所有非 `.cn` 均显式配置 `223.5.5.5`<br>(所有 `.cn` 由全域 DNS 规则覆盖) | ✅ 已完成 | 境外分行及离岸子行按海外代理走 | 消除上游失效 `USER-AGENT` 规则导致在 HTTPS/SSL Pinning 下 0ms 穿透至 FINAL 的隐患 |
| **全国股份制商业银行** | 平安 (`pingan.com`, `pingan.com.cn`)<br>中信 (`citicbank.com`, `ecitic.com`)<br>光大 (`cebbank.com`)<br>浦发 (`spdb.com.cn`)<br>兴业 (`cib.com.cn`)<br>民生 (`cmbc.com.cn`)<br>广发 (`cgbchina.com.cn`)<br>华夏 (`hxb.com.cn`) | 所有非 `.cn` 均显式配置 `223.5.5.5`<br>(所有 `.cn` 由全域 DNS 规则覆盖) | ✅ 已完成 | 境外离岸投资账户由独立规则管理 | 覆盖动卡空间、阳光惠生活、浦大喜奔、发现精彩等主流信用卡 App |

---

## 三、明确排除与禁区白名单（红线列表）

后续 AI 或协作者**严禁将以下域名加入 `China-Direct.list` 或国内极速 DNS**：

1. **出海独立孪生产品（必须走代理）**：
   - 字节跳动：`tiktok.com`, `byteoversea.com`, `ibyteimg.com`
   - 拼多多：`temu.com`
   - 快手：`kwai.com`, `kwaicdn.com`, `snackvideo.com`
   - 美团：`keeta.com`
   - 百度：`terabox.com`
2. **境外中资金融实体（必须保持境外属性）**：
   - `cmbwinglungbank.com`（香港招商永隆银行，机房位于中国香港）
3. **存在海外多区域节点或跨国业务的公有云/游戏集团泛域**：
   - `netease.com`（网易出海游戏节点 `global.netease.com` 部署在 GCP 日本）
   - `bcebos.com`（百度智能云对象存储，包含新加坡 `sin.bcebos.com` 与香港节点）
4. **Apple 账户安全与全局系统禁区**：
   - `apple.com`, `icloud.com`（严禁泛解析至国内 DNS，仅允许静态资源 `*.mzstatic.com` 走国内 DNS）
