---
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

name: yijing_divination
version: "1.20.0"
pattern: A
flow_format: "mermaid"
summary: "基于易经六十四卦的AI占卜文化学习助手。三枚铜钱法由 Python secrets 工具真随机起卦（密码学安全 CSPRNG，tool_dirs/cast_hexagram.py），提供卦辞、爻辞解读与人生建议。支持起卦、解卦、变卦分析、本卦/变卦/互卦/综卦/错卦五卦联网详解、历史记录、重复占卜防护。综卦（整卦上下颠倒）与错卦（每爻阴阳全反）由确定性算法计算，并可经 web_search/web_fetch 联网检索权威释义详解给用户；联网内容均带 [AI生成内容] 标识。仅供文化学习与娱乐体验。合规覆盖：COPPA 2026、EU AI Act Art.50、GB 45438-2025、NIST CAISI。"
tools:
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
  - name: python_tool_run
    required: false
    annotations:
      read_only: true
      destructive: false
      idempotent: false
      open_world: false
    note: "CastHexagram 经执行器 shell 调用 tool_dirs/cast_hexagram.py（纯 stdlib，Python secrets 密码学安全 CSPRNG 三枚铜钱法起卦数字生成器，只向 stdout 输出数字、零文件写、零网络）；工具缺失时降级回 LLM 模拟随机。"
  - name: web_search
    required: false
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
    note: "ExplainHexagram 节点用于联网检索本卦/变卦/互卦/综卦/错卦的权威释义；只读检索、查询净化、来源可信度分级；返回内容视为不可信外部数据并带 [AI生成内容] 标识，不作占卜权威结论。"
  - name: web_fetch
    required: false
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
    note: "ExplainHexagram 节点用于抓取高可信度来源页面正文；只读、仅 http(s)、拒内网地址、URL 须来自本轮 web_search 命中；抓取内容带 [AI生成内容]/AI 摘要标识并保持传统文化学习定位。"
modules:
  - id: yijing_divination.main
    file: main.aisop.json
    nodes: 11
    critical: true
    idempotent: false
    side_effects: [file_write]

governance_hash: "af1b0f3de4943983a155be73fc4f978838d9c218e14a67b8786f29803521d571"
governance_hash_canonical_version: "1.0"
quality:
  weighted_score: 4.933
  grade: "S"
  last_pipeline: "v1.20.0"
tags: [yijing, iching, divination, hexagram, culture, entertainment, fortune]
author: ""
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

trust_level:
  level: 3
  justification: "file_system write operations (SaveRecord, ViewHistory clear) require Supervised trust level. Read/write scope limited to workspace_dir/yijing_history/."
  constraints:
    - "file_system write scope limited to workspace_dir/yijing_history/"
    - "No network access required"
    - "Destructive operations (history clear) gated by sys.io.confirm"
permissions:
  file_system:
    scope: "./"
    operations: ["read", "write"]
runtime:
  timeout_seconds: 120
  max_retries: 2
  token_budget: 20000
  idempotent: false
  side_effects: [file_write]

status: active
applicability_condition:
  triggers:
    - "用户想占卜或算卦"
    - "用户提到易经、六十四卦、周易、卦象"
    - "用户想了解卦象含义或爻辞"
    - "用户输入卦名或卦象符号"
  preconditions:
    - "workspace_dir writable"
  exclusions:
    - "涉及医疗、法律、金融等专业领域的严肃决策"
    - "涉及自杀、自残、犯罪等敏感内容"
    - "要求提供具体投资建议或健康诊断"
  confidence_threshold: 0.8
intent_examples:
  - "帮我算一卦"
  - "我想问问工作发展方向"
  - "乾为天是什么意思"
  - "帮我分析这个变卦"
  - "详细讲讲本卦、变卦、互卦、综卦、错卦"
  - "查一下这一卦的综卦和错卦是什么"
  - "查看我的占卜历史"
  - "什么是易经"
discovery_keywords: [易经, 周易, 占卜, 算卦, 六十四卦, hexagram, iching, divination, fortune, 卦象, 爻辞, 卦辞, 本卦, 变卦, 互卦, 综卦, 错卦, 八卦]
dependencies:
  - file: null
    required: false
    description: "No external dependencies"
identity:
  program_id: "aiap.dev.yijing_divination"
  publisher: ""
  verified_on: "2026-06-13"
  evolution_iteration: 20
---

## 治理声明

易经占卜助手遵循 AIAP V1.0.0 协议，以 Axiom 0 (Human Sovereignty and Wellbeing) 为不可变公理。本程序定位为传统文化学习与娱乐体验工具，不宣扬迷信，不鼓励依赖占卜做决策。Trust Level T3 (Supervised)：file_system 写入操作需监督级信任。

## 功能概述

| 功能 | 说明 |
|------|------|
| 起卦 (divine) | 三枚铜钱法由 Python secrets 工具（密码学安全 CSPRNG，tool_dirs/cast_hexagram.py）真随机起卦，生成本卦和变卦，含重复占卜防护；工具缺失时降级回 LLM 模拟随机 |
| 解卦 (interpret) | 基于《周易》原文提供卦辞、爻辞、象辞解读 |
| 变卦分析 (analyze_change) | 分析本卦到变卦的转化含义，含互卦分析，三级数据来源验证 |
| 五卦联网详解 (explain) | **v1.18.0 新增**：以本卦为基准，确定性计算变卦（变爻取反）、互卦（2-3-4 爻下互、3-4-5 爻上互）、综卦（整卦上下颠倒 180°）、错卦（每爻阴阳全反），并经 web_search/web_fetch 联网检索五卦权威释义详细解释给用户；联网内容带 [AI生成内容] 标识、来源可信度分级、超时降级回《周易》本地原典 |
| 历史记录 (history) | 保存和查看过往占卜记录，清空需 sys.io.confirm 确认 |
| 帮助 (help) | 易经基础知识和使用指南 |

### 模块架构 (Pattern A)

- **main.aisop.json** — 单文件，11 个功能节点（v1.18.0 新增 ExplainHexagram 五卦联网详解节点）
- **tool_dirs/cast_hexagram.py** — Python 起卦数字生成器（纯 stdlib：secrets/json/argparse/sys；READ-only，只向 stdout 输出数字）

### 五卦关系说明（v1.18.0）

| 卦名 | 计算方式 | 备注 |
|------|----------|------|
| 本卦 | 起卦/用户输入得到的原卦 | 解读的基准 |
| 变卦 | 将变爻（老阴 6 / 老阳 9）阴阳取反 | 反映事态发展方向 |
| 互卦 | 取本卦 2-3-4 爻为下卦、3-4-5 爻为上卦 | 揭示事中潜藏因素 |
| 综卦 | 整卦上下颠倒 180°（新第 i 爻=原第 7-i 爻） | 乾/坤/坎/离/大过/小过/颐/中孚 8 个对称卦的综卦等于本卦（边界特例已正确处理） |
| 错卦 | 每爻阴阳全反 | 六十四卦皆有，恒不等于本卦 |

### v1.20.0 变更日志

- **B3: 会话/情景式多作用域记忆层（session/episodic memory layer）**: 在 Pattern A 单文件（11 节点不变）内为占卜流程增加情景式记忆能力，提升跨会话占卜的连续性与一致性。本轮经 EvolveStep 主权门由用户亲自选定 B3（拒绝 B1 C2PA 来源溯源、B2 GB45438 隐式元数据标签、B4 Art.50 终稿文本审计）。ModifyStep 落实 5 项加固、跳过 1 项（详见下）：
  - **Q1 情景写入「不可信」校验**: SaveRecord.step3 对 topic_keyword/advice_gist 按不可信外部数据净化（剥离 prompt 注入/shell/URL）后再持久化，残留注入则拒绝写入并记 WARNING（RF-2/RF-5）
  - **Q2 记忆分层（tier separation）**: SaveRecord.step3 + ViewHistory.step3 明确「用户可删除记忆」与「保留的 .audit_log 审计层」分离；清空操作保留审计元数据（RF-2 避免单层塌缩）
  - **Q3 有界遗忘（bounded forgetting）内联依据**: SaveRecord.step3 就 100 条上限/365 天保留期内联有界遗忘依据（RF-1/RF-7），不另设节点
  - **Q4 陈旧情景守卫（stale-context guard）**: CastHexagram.step2 情景连续性增加新鲜度守卫（365 天/出现次数>=2），优先当前占卜、主题不匹配不复现（RF-3）
  - **Q5 保留依据与来源溯源（retention rationale + provenance）**: memory_path_guard 补充 D6/D10 协调所需的保留依据与来源细节（最弱 Detail 维 4.93）
  - **Q6（跳过）nihil GH3 合并**: Research2 标记为 SUGGEST_ONLY、超出严格 B3 范围、非阻塞；按最小改动纪律将 nihil 合并交还 NihilDensityStep 责任域
- **C1: 版本同步 1.19.0→1.20.0**（main.aisop.json/AIAP.md/AIAP_cn.md/agent_card.json/quality_baseline.json）
- **C2: name 字段更新 v1.20.0**
- **C3: evolution_history / version_history append-only 追加 v1.20.0 条目**（不改既有条目）
- **C4: governance_hash 重算 + QUAD-SYNC**（canonical v1.0 = af1b0f3d…；AIAP.md/AIAP_cn.md/agent_card.json/quality_baseline.json 四处同步）
- **C5: bootstrap_advisory 刷新 + 进化方向生成**
- **质量**: ThreeDimTest（Standard 层 C×0.35+I×0.35+D×0.30）终态加权 4.933、Grade S（Generate2 复测 C=4.929/I=4.923/D=4.85→ReviewFinalize 协调 D6/D10 后 D=4.95）；SIMULATE 18/18 GREEN、VALIDATE 通过、0 RED、0 DEGRADED；相对 v1.19.0 基线（4.95）为 −0.017 微负 delta（B3 为成熟程序上的纯增量记忆能力增强、无回归，主权门已由用户显式批准落盘）

### v1.19.0 变更日志

- **B1: 恢复 I12/I13（开放世界工具注解成熟化）**: 为既有 web_search/web_fetch 补充正式 open_world_tool_justification 块（retry-backoff、来源可信度分级 学术>百科>一般、OWASP LLM01 不可信数据处理、loading_mode 依据），由 M1 hint_rationale_mapping 加固
- **B2: 恢复 Cognitive 维度**: ExplainHexagram 五卦（本/变/互/综/错）worked-example 示例夹具 + 明确不可信来源合成策略（命名 PRIMARY DEFENSES 0a 输入隔离 + 0b 内容分离，对齐 arXiv 2506.08837 / IEEE S&P 2026）
- **B3: EU AI Act Art.50 行为准则终稿对齐**（2026-06-10 发布；跨 main/AIAP.md/AIAP_cn.md/agent_card 核对 Art.50 引用描述「终稿」而非「草案」+ 官方 AI 内容标签图标）
- **C1: program_id 斜杠→点分** 'aiap.dev/yijing_divination'→'aiap.dev.yijing_divination'（消除自 v1.16.0 起持续的 YELLOW = 用户「修复 yellow」意图）
- **C2: 版本同步 1.18.0→1.19.0**（5 文件）；**C3: name 字段嵌入版本同步**；**C4: evolution_history v1.19.0 append-only**
- **注**: 本条目由 v1.20.0 ReviewFinalize 自 quality_baseline.evolution_history.v1.19.0 追溯补全（前一周期 AIAP.md 变更日志未同步该条，本轮一并修复）

### v1.18.0 变更日志

- **A1: 新增 web_search + web_fetch 两个联网工具**: open_world 只读工具，供 ExplainHexagram 节点联网检索本卦/变卦/互卦/综卦/错卦五卦的权威释义；web_search 查询经净化（剥离 shell 元字符与注入模式）、来源按可信度分级（学术/经典文献 > 百科 > 一般网页），web_fetch 仅放行 http(s)、拒绝内网地址、URL 须来自本轮检索命中；返回内容均视为不可信外部数据并带 [AI生成内容] 标识
- **B1: 新增综卦（Zong Gua）确定性计算**: 整卦上下颠倒 180°（新第 i 爻 = 原第 7-i 爻、阴阳不变），正确处理乾/坤/坎/离/大过/小过/颐/中孚 8 个对称卦综卦等于本卦的边界特例（全 64 卦中自反卦恰为 8 个，与规范一致）
- **B2: 新增错卦（Cuo Gua）确定性计算**: 每爻阴阳全反，六十四卦皆有且恒不等于本卦（穷举验证）
- **B3: 新增 ExplainHexagram 五卦联网详解节点**: 以本卦为基准计算变卦/互卦/综卦/错卦后，联网检索五卦释义并详细解释给用户；联网内容带 [AI生成内容]/AI 摘要标识、保持「传统文化学习」而非「占卜权威」定位（对齐 GB 45438-2025 §4.1 / EU AI Act Art.50）；超时/失败时优雅降级回《周易》本地原典并记 WARNING
- **C1: 版本同步 1.17.0→1.18.0**（main.aisop.json/AIAP.md/AIAP_cn.md/agent_card.json/quality_baseline.json）
- **C2: name 字段更新 v1.18.0**
- **C3: 联网工具注解**（web_search/web_fetch：read_only=true、destructive=false、idempotent=true、open_world=true）
- **C4: AI 内容合规标识对齐**（GB 45438-2025 显式+隐式双标识、EU AI Act Art.50 机读 ai_content_metadata、网络来源归属层级 + 「AI 检索摘要可能存在偏差/非占卜权威」免责）
- **C5: 查询净化 + 来源可信度分级 + 抓取守卫**（http(s)-only、拒内网、prompt 注入中和 OWASP LLM01）
- **C6: ExplainHexagram 节点注入 [ASSERT] 入口门 + 完整 Error 链**（retry/circuit-breaker/fallback/inform）
- **C7: governance_hash 重算 + 文档同步**（AIAP.md/AIAP_cn.md/agent_card.json/quality_baseline.json）

### v1.17.0 变更日志

- **A1: 新增 tool_dirs/cast_hexagram.py 起卦数字生成器**: 纯 stdlib（secrets/json/argparse/sys），用 Python secrets（密码学安全 CSPRNG）模拟传统三枚铜钱法 6 次（每次掷 3 枚硬币，每枚 secrets.choice([2,3])，三枚求和得一爻值 6/7/8/9），天然满足概率分布 P(6)=1/8、P(7)=3/8、P(8)=3/8、P(9)=1/8；READ-only（只向 stdout 输出 JSON {lines, yin_yang, changing_lines, coins_detail, method, rng}、零文件写、零网络）；可选 --seed 仅供 SimulateStep 可复现测试
- **B1: CastHexagram.step3 wire + 随机性声明翻转**: step3 改为 MUST run `<python> -X utf8 {DIR_OF_PROGRAM}/tool_dirs/cast_hexagram.py`（绝对路径），解析其 stdout JSON 构本卦，绝不再由 LLM 自行「掷」；工具缺失/exit≠0 时降级回 LLM 模拟并记 WARNING（保持可用、标注降级）。step3 NOTE 与 constraints 的「LLM 模拟随机性声明 / RANDOMNESS DISCLAIMER」翻转为「起卦数字由 Python secrets（密码学安全 CSPRNG）真随机生成，符合三枚铜钱法概率分布；仅工具缺失时降级为 LLM 模拟随机」
- **C1: 版本同步 1.16.0→1.17.0**
- **C2: name 字段更新 v1.17.0**
- **C3: tools 列表 / 能力声明补 Python 工具运行**（CastHexagram 经执行器 shell 调 cast_hexagram.py）
- **C4: 文档同步**: summary/description/agent_card「三枚铜钱法模拟」更新为「三枚铜钱法由 Python secrets 工具真随机起卦（密码学安全）」
- **C5: governance_hash 重算 + QUAD-SYNC**（AIAP.md/AIAP_cn.md/agent_card.json/quality_baseline.json）
- **C6: snapshot_build v1.17.0/ + snapshot_audit exit 0**

### v1.16.0 变更日志

- **B1: TAKE IT DOWN Act FTC 执法指导更新**: description 和 GiveAdvice.constraints 更新 — FTC Chairman Ferguson 于 May 19 执法日前向 15+ 大型科技公司（Amazon, Alphabet, Apple, Meta, Microsoft 等）发出合规咨询函；民事罚款更新为 $53,088/违规（per FTC enforcement guidance）；agent_card.json COPPA_2026 compliance 同步
- **C1: 版本同步 1.15.0→1.16.0**
- **C2: name 字段更新 v1.16.0**
- **C3: Art.50 CoP 时间线精化**: 'May-June 2026' → 'early June 2026'
- **C4: governance_hash 重算**
- **C5: quality_baseline.json 进化历史更新**

### v1.15.0 变更日志

- **A1: COPPA 2026 官方日期校准**: 将错误的 “FTC final rule published June 23 2025” 修正为 FTC 2025-01-16 官方 final rule announcement + 2026-04-22 compliance deadline，避免治理说明引用错误发布日期。
- **A2: EU AI Act Art.50 Code of Practice 状态校准**: 对齐欧盟官方 2026-05-08 页面：draft guidelines published May 8 2026，final code expected May-June 2026，CoP 若获 Commission 批准则作为 voluntary compliance demonstration tool。
- **B1: SaveRecord 水印合规措辞收敛**: 将 “presumption of conformity” 改为更保守的 “voluntary tool for demonstrating compliance”，降低过度承诺风险。
- **C1: 版本同步 1.14.0→1.15.0**
- **C2: main.aisop.json / AIAP.md / AIAP_cn.md / agent_card.json / quality_baseline.json 治理同步**
- **C3: governance_hash 重算**

### v1.14.0 变更日志

- **B1: EU AI Act Omnibus 5月7日临时协议更新**: description 和 GiveAdvice.constraints 全面更新 — 5月7日临时协议达成（非"trilogue失败"），Annex III 独立高风险延期 Dec 2 2027，Annex I 嵌入 Aug 2 2028，新增 Art.5 CSAM/nudifier 禁令 Dec 2 2026，Art.50(2) 水印 Aug 2 2026（过渡期至 Dec 2 2026），Code of Practice 最终版预计 June 2026（合规即推定符合）
- **B2: UNESCO 文化遗产 AI 伦理对齐**: ShowHelp.step1 和 system_prompt 新增 — UNESCO 2021 AI 伦理建议书七项原则、易经非物质文化遗产认可、ICH 文化真实性尊重声明
- **B3: GB 45438-2025 清朗执法防御性定位**: shared_constraints 新增 cultural_learning_positioning — CAC 2026 清朗整治行动针对 AI 误用，占卜 AI 需明确文化学习定位而非迷信服务；宗教事务办公室 AI 算命禁令适用域界定
- **B4: COPPA 2026 AI 伴侣交互安全增强**: Start.constraints 新增 — 青少年(13-17)AI 聊天机器人使用统计、温馨提示机制、California SB 243 (Jan 2026) 自伤检测对齐
- **B5: Art.50 实践守则多层水印对齐**: SaveRecord.constraints 新增 — 显式+隐式双层水印方法论声明、CoP 合规推定符合、Art.50(2) 时间线更新
- **C1: 版本同步 1.13.0→1.14.0**
- **C2: name 字段更新 v1.14.0**
- **C3: AIAP.md / AIAP_cn.md 治理同步**
- **C4: agent_card.json 版本和合规同步**
- **C5: quality_baseline.json 进化历史更新**
- **C6: governance_hash 重算**

### v1.13.0 变更日志

- **A1: TAKE IT DOWN Act 执行强化**: description 和 GiveAdvice.constraints 更新 — 首例刑事定罪 (2026-04 Ohio, AI-generated NCII)、平台48小时NCII移除要求、法律已进入刑事执法阶段；agent_card.json COPPA_2026 compliance 同步
- **B1: NIST COSAiS 时间线精化**: description 和 GiveAdvice.constraints 更新 — agent-specific overlays 无确切发布日期，正式指南可能2027年；NCCoE 概念论文最终发布时间线不确定；agent_card.json NIST_AI_Agent_2026 compliance 同步
- **C1: 版本同步 1.12.0→1.13.0**
- **C2: name 字段更新 v1.13.0**
- **C3: AIAP.md / agent_card.json 治理同步**
- **C4: quality_baseline.json 更新**
- **C5: bootstrap_advisory NIST/TAKE IT DOWN Act 状态更新**
- **C6: governance_hash 重算**

### v1.11.0 变更日志

- **A1: EU AI Act Omnibus 第三次 trilogue 时间线与上下文更新**: description 和 GiveAdvice.constraints 更新 — 补充 Omnibus "potentially clear path toward simplified agreement" 上下文、Parliament/Council 5-6月背书预期、OJ 7月发布预期；NIST COSAiS agent-specific overlay "expected mid-to-late 2026" 时间线精化；COPPA 2026 FTC age verification policy statement (Feb 25 2026) 新增
- **B1: Bootstrap 验证状态追踪增强**: quality_baseline.json bootstrap_advisory 6 项特性验证状态持续追踪
- **C1: 版本同步 1.10.0→1.11.0**
- **C2: name 字段更新 v1.11.0**
- **C3: AIAP.md / AIAP_cn.md 治理同步**
- **C4: agent_card.json 版本同步**
- **C5: quality_baseline.json 更新**
- **C6: governance_hash 重算**

### v1.10.0 变更日志

- **A1: EU AI Act Omnibus Annex I 合格评定分歧原因补充**: 在 description 和 GiveAdvice.constraints 中补充第二次 trilogue 失败的具体原因：Annex I 合格评定架构（AI Act 与现有 EU 行业安全立法的合规评估关系未解决，经约 12 小时谈判未达成协议）。第三次 trilogue 2026-05-13 安排确认
- **B1: Bootstrap 特性验证状态更新**: quality_baseline.json 中 6 项 bootstrap_advisory 特性添加当前验证进展注释（COPPA NOW EFFECTIVE 确认、Art.50 deadline 约束力确认、COSAiS 开发进度、生产部署待验证项标记）
- **C1: 版本同步 1.9.0→1.10.0**
- **C2: name 字段更新 v1.10.0**
- **C3: AIAP.md / AIAP_cn.md 治理同步**
- **C4: agent_card.json 版本同步**
- **C5: quality_baseline.json 更新**
- **C6: governance_hash 重算**

### v1.9.0 变更日志

- **A1: EU AI Act Digital Omnibus 第三次 trilogue 更新**: 2026-05-13 第三次三方协商已安排。4/28 trilogue 失败后的进展 — 核心分歧点为 AI 嵌入产品与现有 EU 行业安全立法的交叉问题。若时间表不变，Parliament/Council 5-6 月背书，OJ 7 月发布。Art.50 2026-08-02 deadline 在 Omnibus 正式通过前保持约束力。更新 GiveAdvice.constraints 和 description 中的 Omnibus 时间线
- **B1: 卦象 ASCII 可视化增强**: CastHexagram.step5 新增文本图形六爻展示 — 阳爻 ━━━━━━━、阴爻 ━━╸ ╺━━（中间断开）、变爻标注 ○/×。本卦与变卦并排对照
- **C1: 版本同步 1.8.0→1.9.0**
- **C2: name 字段更新 v1.9.0**
- **C3: description Omnibus trilogue 3 更新**
- **C4: AIAP.md / AIAP_cn.md 治理同步**
- **C5: agent_card.json 版本同步**
- **C6: quality_baseline.json 更新**
- **C7: governance_hash 重算**

### v1.8.0 变更日志

- **A1: EU AI Act Digital Omnibus trilogue 失败更新**: 2026-04-28 三方协商失败 — 政治协议未达成，Council 和 Parliament 在中小企业豁免和高风险 AI 时间线延长问题上未能协调。Art.50 原定 2026-08-02 截止日现取决于 Omnibus 后续进展。更新 GiveAdvice.constraints 和 description 中所有 Digital Omnibus 时间线引用
- **B1: summary/description P28 合规清理**: 移除 summary 和 description 字段中的 changelog 条目，压缩为功能描述。changelog 仅保留在 AIAP.md 和 quality_baseline.json 中
- **C1: 版本同步 1.7.0→1.8.0**
- **C2: name 字段更新 v1.8.0**
- **C3: description changelog 移除 + trilogue failure 更新**
- **C4: AIAP.md / AIAP_cn.md 治理同步**
- **C5: agent_card.json 版本同步**
- **C6: quality_baseline.json 更新**
- **C7: governance_hash 重算**

### v1.7.0 变更日志

- **A1: COPPA 2026 合规语言更新**: §312.10 书面数据留存政策（written data retention policy）、增强父母通知（enhanced parental notice with third-party categories）、定向广告和第三方披露 opt-in 同意、生物识别标识符扩展（指纹 eyeprints 声纹 面部模板）纳入个人信息定义、政府颁发标识符、书面信息安全计划含年度风险评估、罚款超 $50,000/violation
- **A2: EU AI Act Digital Omnibus 时间线更新**: trilogue 2026-03-26 启动（Parliament 569-45 投票）、trilogue 2026-04-28 失败 — 政治协议未达成（Council/Parliament 在中小企业豁免和高风险 AI 时间线延长问题上未能协调）、Art.50 透明度义务原定截止 2026-08-02 现取决于 Omnibus 后续进展、standalone high-risk 2027-12-02、embedded AI 2028-08-02、水印 2026-11-02、罚款最高 35M EUR 或全球年营收 7%
- **A3: NIST 2026 AI Agent Standards 参考更新**: CAISI 三支柱框架正式运营、COSAiS SP 800-53 控制覆盖层（single-agent + multi-agent）、NCCoE 概念论文（OAuth/OIDC/SCIM 身份授权）评论期 2026-04-02 截止
- **B1: SaveRecord 数据留存策略加固**: DATA_RETENTION_POLICY 结构化声明对齐 COPPA §312.10（purpose_limitation + data_minimization + retention_period_365d + disposal_method_lazy_purge + audit_trail）
- **C1: 版本同步 1.6.0→1.7.0**
- **C2: name 字段更新 v1.7.0**
- **C3: summary/description 更新**
- **C4: AIAP_cn.md 治理同步**
- **C5: agent_card.json 版本同步**
- **C6: quality_baseline.json 更新**
- **C7: governance_hash 重算**

### v1.6.0 变更日志

- **A1: 监管时间戳全面刷新**: COPPA 2026 NOW EFFECTIVE（2026年4月22日生效，FTC 最终规则 2025年6月23日发布）、EU AI Act Digital Omnibus trilogue（2026年3月26日启动，政治协议预计4月28日，执行截止日2026年8月2日不变，拟议推迟 standalone 2027年12月 embedded 2028年8月 水印2026年11月）、NIST AI Agent Standards 2026（RFI 3月9日截止、NCCoE 4月2日截止、行业听证会4月2026）
- **A2: 全部 10 函数 output 数据合约完备**: Start（menu_displayed, user_input_validated）、NLU（intent, confidence, route）、ShowHelp（help_text, guidance_prompt）、ErrorHandler（error_message, recovery_suggestion）四函数补全 → 10/10 全覆盖
- **A3: COPPA 2026 合规语言加固**: NOW EFFECTIVE 标记、AI chatbot 交互明确条款、生物识别数据（指纹、面部扫描、声纹）纳入保护信息、无限期数据留存禁令、单独可验证家长同意要求、每次违规每天最高 $51,744 罚款
- **B1: AIAP_cn.md 中文本地化治理文档**: 新建中文版治理文档，包含治理声明、功能概述、模块架构、信任级别、安全合规、免责声明
- **C1: 版本同步 1.5.0→1.6.0**
- **C2: name 字段更新 v1.6.0**
- **C6: summary/description 更新**

### v1.5.0 变更日志

- **A1: 显式 output 数据合约**: CastHexagram、InterpretHexagram、AnalyzeChange、GiveAdvice、SaveRecord、ViewHistory 六个函数添加结构化 output 字段，明确输出数据类型和字段名
- **A2: AnalyzeChange ASSERT Required 修复**: hexagram_data 从 Required 降级为 Optional，实现三级数据来源可选依赖（会话上下文 > 用户输入 > 历史记录），三源均空时引导用户起卦
- **A3: shared_constraints 公共约束提取**: 提取 path_guard、atomic_write、error_pattern、ai_labeling、session_scope 五个共用约束到 shared_constraints 字段，减少跨节点重复声明
- **B1: COPPA 2026 未成年人检测细化**: Start.constraints 添加年龄关键词检测列表（中英文）、拒绝服务模板、COPPA_MINOR_DETECTED 事件日志、合规截止日期 2026-04-22
- **B2: sys.io.confirm headless 模式超时**: ViewHistory.step3 添加 AT7 安全标准的 confirm_timeout（30秒默认）、超时视为 reject、CONFIRM_TIMEOUT_HEADLESS 日志、NEVER auto-approve 声明
- **B3: I14 审计完整性声明**: ViewHistory.step3 添加 confirm 事件审计追溯（timestamp/prompt_text/user_response/session_id）持久化声明
- **C1: 版本同步 1.4.0→1.5.0**
- **C2: params 格式升级**: 参数定义从内联字符串升级为结构化 JSON Schema 对象
- **C3: summary 去重**: 移除与描述字段重叠的冗余内容
- **C4: fractal_exempt 修复**: 添加 functional_node_count 字段，明确功能节点统计
- **C5: ShowHelp→ErrorHandler Mermaid 边补全**: 补充缺失的错误出口边
- **C6: InterpretHexagram ASSERT 来源区分**: 区分 CastHexagram（起卦模式）和 NLU（解卦模式）两种入口来源
- **C7: SaveRecord 跨节点依赖声明**: 明确 hexagram_data 来源为 CastHexagram/InterpretHexagram via pipeline context
- **C8: 监管时间戳刷新**: COPPA 2026 compliance_date 2026-04-22、GB 45438-2025 enforced 标记
- **C9: NIST AI Agent Standards 参考更新**: NCCoE concept paper 2026 引用

### v1.4.0 变更日志

- **A1: agent_card D8 完整性加固**: 添加 security_scheme（none + safety_card 引用）、compliance（GB 45438-2025/EU AI Act Art.50/COPPA 2026/NIST AI Agent 2026）、limitations 独立字段
- **A2: quality_baseline D10 同步强化**: governance_hash 校验标记、cache_schema_version 对齐、evolution_history v1.4.0 条目
- **A3: EU AI Act Art.50 Code of Practice 2026 草案对齐**: 第二稿发布标注、2026年6月定稿预期、machine-readable 标记强化
- **A4: COPPA 2026 未成年人保护声明**: Start.constraints 添加未成年人检测和拒绝服务条款（2026年4月22日合规截止）
- **B1: NLU D5 消歧信号增强**: +2 新混淆对（历史/解卦#4, 变卦/起卦#5）、+6 边界示例及置信度
- **C1: 版本同步 1.3.0→1.4.0**
- **C5: GB 45438-2025 合规时间戳刷新**: 明确标注 2025年9月1日已生效
- **C6: NIST AI Agent Standards Initiative 2026 参考**: agent identity framework 透明度原则
- **C9: ViewHistory sys.io.confirm executor guard 完善**: 明确 §6.2 executor_hard_rule + NEVER auto-approve
- **SaveRecord pre-write check**: 目录存在性验证
- **SaveRecord lazy purge error recovery**: 清理失败不阻塞新记录创建

### v1.3.0 变更日志

- **json_schema 结构化输出定义**: 添加 divination_result schema，包含 hexagram_name、interpretation_summary、ai_generated (const: true) 等字段
- **I8 Prompt Injection 系统性威胁缓解**: 三层防御（C2 模式检测 + C3 HTML/XSS 消毒 + 输入边界隔离），OWASP LLM Top 10 AT6 对齐
- **ErrorHandler Mermaid 边完备**: +2 条边（Start→ErrorHandler, NLU→ErrorHandler），实现所有功能节点均可路由至 ErrorHandler
- **I11 program_id 身份声明**: 添加 program_id "aiap.dev/yijing_divination"，支持跨 AIAP 程序身份识别
- **I13 AI 内容标识结构化声明**: GB 45438-2025 显式标识（[AI生成内容]）+ 隐式标识（机器可读 metadata）+ EU AI Act Art.50 机器可读格式
- **token_estimate 添加**: 每路径约 4K tokens，完整起卦流程约 8K tokens
- **EU AI Act Art.50 合规时间线更新**: 明确标注 2026 年 8 月 2 日全面生效
- **SaveRecord 数据保留策略**: 365 天 + lazy purge（超期记录在下次写入时自动清理并告知用户）

### v1.2.0 变更日志

- **Trust Level 修正**: T1→T3 (Supervised)，file_system 写入操作需要监督级信任
- **system_prompt 协议 2.3 对齐**: 移除产品描述冗余，添加 Mirror 指令和 Axiom 0 对齐声明
- **ErrorHandler Mermaid 边完备**: +4 条边（AnalyzeChange, GiveAdvice, SaveRecord, ViewHistory → ErrorHandler）
- **监管合规强化**: 中国 AI 标识办法 GB 45438-2025 隐式元数据 + EU AI Act Art.50 机器可读标记
- **AnalyzeChange 数据来源验证**: 三级优先级（会话上下文 > 用户输入 > 历史记录），无数据时引导用户
- **SaveRecord 失败补偿**: 保存失败时向用户展示 JSON 摘要，附带 ai_generated 元数据
- **会话上下文超时**: 30 分钟无交互自动清除卦象上下文
- **ErrorHandler 错误限流**: 会话级连续错误计数，3 次阈值后路由到 endNode
- **Start HTML/XSS 防护**: 剥离 HTML 标签和 JavaScript 事件处理器
- **CastHexagram 重复防护降级**: 历史读取失败时跳过重复检查直接起卦

### v1.1.0 变更日志

- **协议对齐**: protocol AISOP→AIAP, 添加 axiom_0/flow_format/output_mode/execution_mode
- **tools 升级**: 裸字符串→注解对象格式
- **ASSERT 加固**: 所有节点补充 Required 声明
- **Error 规范化**: 四关键字模式 (retry/circuit-breaker/fallback/inform)
- **重复占卜防护**: CastHexagram 新增 24h 查重逻辑
- **确认机制**: ViewHistory 清空操作使用 sys.io.confirm
- **AI 标识**: 所有输出强制包含 [AI生成内容] 标识
- **endNode 标准化**: 结束→End
- **随机性声明**: 明确 LLM 模拟随机与密码学安全随机的区别
- **params I7**: 类型注解和 agentic_prompt 描述

## 使用方式

### 入口文件

`main.aisop.json` — AI Agent 加载此文件启动易经占卜助手。

### 工具需求

| 工具 | 必需 | 用途 |
|------|------|------|
| file_system | 是 | 读写占卜历史记录 |
| python_tool_run | 否 | CastHexagram 经执行器 shell 调 tool_dirs/cast_hexagram.py（Python secrets 真随机起卦）；缺失时降级回 LLM 模拟随机 |
| web_search | 否 | ExplainHexagram 联网检索五卦权威释义；缺失/超时时降级回《周易》本地原典 |
| web_fetch | 否 | ExplainHexagram 抓取高可信度来源页面正文；缺失/超时时降级回《周易》本地原典 |

### 前置条件

- workspace_dir 目录可写
- AI Agent 支持 file_system 工具
- （可选）AI Agent 支持 Python 工具运行：cast_hexagram.py 真随机起卦；缺失时自动降级回 LLM 模拟随机
- （可选）AI Agent 支持 web_search / web_fetch 联网工具：ExplainHexagram 五卦联网详解；缺失时自动降级回《周易》本地原典解释

## 免责声明

本内容仅供传统文化学习与娱乐体验，不构成任何医疗、法律、金融或其他专业建议，不属于封建迷信活动。重要决策请咨询相关专业人士。所有输出均为 AI 生成内容（符合 GB 45438-2025 及 EU AI Act Art.50）。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
