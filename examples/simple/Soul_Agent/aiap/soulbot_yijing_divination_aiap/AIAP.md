---
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

name: yijing_divination
version: "1.16.0"
pattern: A
flow_format: "mermaid"
summary: "基于易经六十四卦的AI占卜文化学习助手。使用三枚铜钱法起卦，提供卦辞、爻辞解读与人生建议。支持重复占卜防护、sys.io.confirm 确认机制、AI 内容标识。仅供文化学习与娱乐体验。合规覆盖：COPPA 2026、EU AI Act Art.50、GB 45438-2025、NIST CAISI。"
tools:
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
modules:
  - id: yijing_divination.main
    file: main.aisop.json
    nodes: 10
    critical: true
    idempotent: false
    side_effects: [file_write]

governance_hash: "bd7bec301e47a22172e6cbb6dbeb953440b6517dc27fca154af13237c004b6a8"
governance_hash_canonical_version: "1.0"
quality:
  weighted_score: 5.000
  grade: "S"
  last_pipeline: "v1.16.0"
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
  - "查看我的占卜历史"
  - "什么是易经"
discovery_keywords: [易经, 周易, 占卜, 算卦, 六十四卦, hexagram, iching, divination, fortune, 卦象, 爻辞, 卦辞, 变卦, 八卦]
dependencies:
  - file: null
    required: false
    description: "No external dependencies"
identity:
  program_id: "aiap.dev/yijing_divination"
  publisher: ""
  verified_on: "2026-05-12"
  evolution_iteration: 16
---

## 治理声明

易经占卜助手遵循 AIAP V1.0.0 协议，以 Axiom 0 (Human Sovereignty and Wellbeing) 为不可变公理。本程序定位为传统文化学习与娱乐体验工具，不宣扬迷信，不鼓励依赖占卜做决策。Trust Level T3 (Supervised)：file_system 写入操作需监督级信任。

## 功能概述

| 功能 | 说明 |
|------|------|
| 起卦 (divine) | 模拟三枚铜钱法，生成本卦和变卦，含重复占卜防护和降级运行 |
| 解卦 (interpret) | 基于《周易》原文提供卦辞、爻辞、象辞解读 |
| 变卦分析 (analyze_change) | 分析本卦到变卦的转化含义，含互卦分析，三级数据来源验证 |
| 历史记录 (history) | 保存和查看过往占卜记录，清空需 sys.io.confirm 确认 |
| 帮助 (help) | 易经基础知识和使用指南 |

### 模块架构 (Pattern A)

- **main.aisop.json** — 单文件，10 个功能节点

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

### 前置条件

- workspace_dir 目录可写
- AI Agent 支持 file_system 工具

## 免责声明

本内容仅供传统文化学习与娱乐体验，不构成任何医疗、法律、金融或其他专业建议，不属于封建迷信活动。重要决策请咨询相关专业人士。所有输出均为 AI 生成内容（符合 GB 45438-2025 及 EU AI Act Art.50）。

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
