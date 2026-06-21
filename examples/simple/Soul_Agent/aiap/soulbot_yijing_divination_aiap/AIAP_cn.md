---
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL
governance_hash: "af1b0f3de4943983a155be73fc4f978838d9c218e14a67b8786f29803521d571"

name: yijing_divination
version: "1.20.0"
pattern: A
flow_format: "mermaid"
summary: "基于易经六十四卦的AI占卜文化学习助手。三枚铜钱法由 Python secrets 工具真随机起卦（密码学安全 CSPRNG，tool_dirs/cast_hexagram.py），提供卦辞、爻辞解读与人生建议。支持起卦、解卦、变卦分析、本卦/变卦/互卦/综卦/错卦五卦联网详解、历史记录、重复占卜防护。综卦（整卦上下颠倒）与错卦（每爻阴阳全反）由确定性算法计算，并可经 web_search/web_fetch 联网检索权威释义详解给用户；联网内容均带 [AI生成内容] 标识。仅供文化学习与娱乐体验。合规覆盖：COPPA 2026、EU AI Act Art.50、GB 45438-2025、NIST CAISI。"
---

## 治理声明

易经占卜助手遵循 AIAP V1.0.0 协议，以 Axiom 0（人类主权与福祉）为不可变公理。本程序定位为传统文化学习与娱乐体验工具，不宣扬迷信，不鼓励依赖占卜做决策。信任等级 T3（监督级）：file_system 写入操作需监督级信任。

## 功能概述

| 功能 | 说明 |
|------|------|
| 起卦 (divine) | 三枚铜钱法由 Python secrets 工具（密码学安全 CSPRNG，tool_dirs/cast_hexagram.py）真随机起卦，生成本卦和变卦，含重复占卜防护；工具缺失时降级回 LLM 模拟随机 |
| 解卦 (interpret) | 基于《周易》原文提供卦辞、爻辞、象辞解读 |
| 变卦分析 (analyze_change) | 分析本卦到变卦的转化含义，含互卦分析，三级数据来源验证 |
| 五卦联网详解 (explain) | **v1.18.0 新增**：以本卦为基准确定性计算变卦/互卦/综卦/错卦，并经 web_search/web_fetch 联网检索五卦权威释义详解给用户；联网内容带 [AI生成内容] 标识、来源可信度分级、超时降级回《周易》本地原典 |
| 历史记录 (history) | 保存和查看过往占卜记录，清空需 sys.io.confirm 确认 |
| 帮助 (help) | 易经基础知识和使用指南 |

### 模块架构（Pattern A）

- **main.aisop.json** — 单文件，11 个功能节点（v1.18.0 新增 ExplainHexagram 五卦联网详解节点）
- **tool_dirs/cast_hexagram.py** — Python 起卦数字生成器（纯 stdlib：secrets/json/argparse/sys；READ-only，只向 stdout 输出数字）

### v1.20.0 更新

- **B3 会话/情景式记忆层**：为占卜流程增加情景式记忆能力（节点数仍为 11），提升跨会话占卜的连续性与一致性。情景写入按不可信外部数据净化；审计层与用户可删除记忆层分离；100 条/365 天有界遗忘；CastHexagram 增加陈旧情景守卫（优先当前占卜、主题不匹配不复现）。
- 质量：终态加权 4.933、Grade S（Standard 层 C×0.35+I×0.35+D×0.30）；SIMULATE 18/18 GREEN、VALIDATE 14/14、0 RED、0 DEGRADED。governance_hash 重算 QUAD-SYNC（canonical v1.0）。

### 五卦关系（v1.18.0）

| 卦名 | 计算方式 | 备注 |
|------|----------|------|
| 本卦 | 起卦/用户输入得到的原卦 | 解读基准 |
| 变卦 | 变爻（老阴 6/老阳 9）阴阳取反 | 事态发展方向 |
| 互卦 | 2-3-4 爻为下卦、3-4-5 爻为上卦 | 事中潜藏因素 |
| 综卦 | 整卦上下颠倒 180° | 乾/坤/坎/离/大过/小过/颐/中孚 8 个对称卦综卦等于本卦 |
| 错卦 | 每爻阴阳全反 | 六十四卦皆有，恒不等于本卦 |

### 工具需求

| 工具 | 必需 | 用途 |
|------|------|------|
| file_system | 是 | 读写占卜历史记录 |
| python_tool_run | 否 | CastHexagram 经执行器 shell 调 tool_dirs/cast_hexagram.py（Python secrets 真随机起卦）；缺失时降级回 LLM 模拟随机 |
| web_search | 否 | ExplainHexagram 联网检索五卦权威释义；缺失/超时降级回《周易》本地原典 |
| web_fetch | 否 | ExplainHexagram 抓取高可信度来源页面正文；只读、仅 http(s)、拒内网、URL 须来自本轮检索；缺失/超时降级回本地原典 |

### 信任等级

- **等级**: T3（监督级）
- **理由**: file_system 写入操作（SaveRecord 保存记录、ViewHistory 清空历史）需要监督级信任
- **约束**:
  - file_system 写入范围限定于 workspace_dir/yijing_history/
  - 无需网络访问
  - 破坏性操作（清空历史）由 sys.io.confirm 守护

### 安全与合规

- **GB 45438-2025**: AI 内容标识办法（2025年9月1日已生效）—— 显式标识（[AI生成内容]）+ 隐式标识（机器可读元数据）
- **EU AI Act Art.50**: 机器可读 AI 生成内容标记（2026年8月2日截止）; Digital Omnibus 临时协议 2026-05-07 达成 — Council 和 Parliament 谈判代表于5月7日凌晨达成政治协议; Annex III 独立高风险延期至 2027-12-02, Annex I 嵌入产品 2028-08-02; 新增 Art.5 CSAM/nudifier 禁令 2026-12-02 生效; Art.50(2) 水印 2026-08-02（过渡期至 2026-12-02）; 正式背书预计 2026年8月前; OJ 2026年夏季发布; Art.50 实践守则官方页面 2026-05-08 更新：draft guidelines 于 2026-05-08 发布，final code 预计 2026年6月初；若获 Commission 批准，CoP 是用于证明符合 Art.50(2)/(4) 的自愿工具; 罚款最高 35M EUR/7%
- **COPPA 2026**: 儿童在线隐私保护法修正案（2026年4月22日已生效）—— 不面向13岁以下未成年人，不收集未成年人个人数据; §312.10 书面数据留存政策; 增强父母通知; FTC年龄验证政策声明 2026-02-25; 生物识别扩展（指纹 eyeprints 声纹 面部模板）; 罚款 >$50k/violation
- **NIST AI Agent 2026**: CAISI 三支柱框架正式运营; CAISI AI Agent Standards Initiative 官方页面 2026-04-20 更新：三大支柱为行业主导标准、社区主导协议、agent identity/security 研究；COSAiS agent-specific overlay 尚无确定发布日期; NCCoE 概念论文（OAuth/OIDC/SCIM）公众评论审核中，最终出版预计Q3 2026

### 输入安全防护

- 类型检查（仅接受字符串）
- 大小限制（截断超过1000字符）
- Shell 元字符过滤
- Prompt 注入检测与中和（LLM 注入模式识别）
- HTML/XSS 防护（标签和事件处理器剥离）
- 路径遍历防护（拒绝 '..' 和 workspace_dir 外路径）
- 编码规范化（NFC）

## 免责声明

本内容仅供传统文化学习与娱乐体验，不构成任何医疗、法律、金融或其他专业建议，不属于封建迷信活动。重要决策请咨询相关专业人士。所有输出均为 AI 生成内容（符合中国 GB 45438-2025 AI 标识办法及 EU AI Act Art.50）。

---

遵循 Axiom 0: 人类主权与福祉。版本: AIAP V1.0.0。www.aiap.dev
